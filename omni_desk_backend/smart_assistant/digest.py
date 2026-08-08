"""每日晨报生成逻辑(主动循环 Proactivity MVP)。

借鉴 claw-code personal-assistant-roadmap 的 proactivity MVP 三段式:
定时巡检 → 生成简报 → 推送通知。本模块只负责"生成简报"这一段。

复用策略:
- 不另起炉灶,直接复用聊天路径已有的聚合链路 ——
  ``AgentOrchestrator.process()`` 命中 ``generate_tool_chain_plan`` 后走
  ``ToolChainExecutor`` + ``ResultSynthesizer``,产出 intent="aggregated_day" 的
  ``tool_result``::{summary, items, total_count, moduleCounts, chain_results}。
- 本模块把该结构渲染为 Markdown 简报(日期标题 + summary + 各模块条数 + 重点条目列表),
  再由 ``smart_assistant.tasks.send_single_digest`` 子任务(经 ``send_daily_digests``
  按用户派发)写入 Notification 完成推送。

失败语义:
- 生成失败(编排器抛异常 / 返回失败回答 / 返回结构非法)一律返回 None 并记日志,
  不向调用方抛异常 —— 由 tasks 层决定跳过该用户并继续推送其余用户。
"""

from __future__ import annotations

import logging
from datetime import date

from django.utils import timezone

from .agent.orchestrator import AgentOrchestrator
from .scope import resolve_scope
from .tools.tool_context import ToolContext

logger = logging.getLogger(__name__)

# 触发聚合链路的晨检查询语(命中多工具计划 → intent="aggregated_day")
DIGEST_QUERY = "今天我有哪些安排？请汇总今日的排班、会议室、备忘录和待办事项。"

# 简报重点条目最多展示条数,超出截断,避免通知正文过长
MAX_HIGHLIGHT_ITEMS = 10

# 单条摘要最大字符数
MAX_ITEM_DESC_LENGTH = 80

# ResultSynthesizer 对缺失时间字段的兜底 sort_key,视为"无时间信息"不展示
_NO_SORT_KEY = "9999"

# 星期中文名(weekday(): 周一=0)
_WEEKDAY_CN = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")

# 条目摘要候选字段(按优先级依次尝试,覆盖各工具常见输出键名)
_DESC_KEYS = ("title", "name", "subject", "room_name", "content", "summary", "memo", "description")


def generate_daily_digest(user, query: str = DIGEST_QUERY, today: date | None = None) -> str | None:
    """为指定用户生成每日晨报 Markdown。

    参数:
        user: 目标用户(users.CustomUser),用于派生 scope-aware 的 ToolContext,
            保证晨报只聚合该用户权限范围内的数据。
        query: 聚合查询语,默认固定晨检查询;开放参数便于后续定制。
        today: 简报日期,默认 Asia/Shanghai 时区当天;测试可注入固定日期。

    返回:
        Markdown 简报文本;任何失败场景返回 None(记日志,不抛异常)。
    """
    today = today or timezone.localdate()
    username = getattr(user, "username", user)
    tool_context = ToolContext(user=user, scope=resolve_scope(user))

    try:
        result = AgentOrchestrator().process(
            query,
            conversation_history=None,  # 晨报是独立巡检,不携带任何会话历史
            tool_context=tool_context,
            # I-1 修复(Final review fix wave):晨报必须走 JSON 路径。
            # 原生 tool_calls 路径产出的是「单轮自然语言回答」,而晨报依赖
            # 多工具链(排班/会议室/备忘录/待办)聚合出的 intent="aggregated_day"
            # 结构化卡片;且 staff + 端点支持时默认会静默切到原生路径,丢掉
            # aggregated_day 并继承 C-1 的跨用户泄漏风险。显式禁用原生路径,
            # 强制走 _process_json_path → _process_chain 的聚合链路。
            use_native_tool_calls=False,
        )
    except Exception:
        logger.exception("每日晨报生成失败: user=%s date=%s", username, today.isoformat())
        return None

    if not isinstance(result, dict):
        logger.warning("晨报聚合链路返回非法结果: user=%s result_type=%s", username, type(result).__name__)
        return None
    if result.get("error"):
        # orchestrator 已通过 is_failed_answer() 判定 LLM 回答失败
        logger.warning("晨报聚合链路返回失败回答: user=%s intent=%s", username, result.get("intent"))
        return None

    return _render_markdown(result, today)


def _render_markdown(result: dict, today: date) -> str:
    """把 orchestrator 结果渲染为 Markdown(日期标题 + summary + 各模块条数 + 重点条目)。"""
    lines = [f"# 智能助手每日晨报（{today.isoformat()} {_WEEKDAY_CN[today.weekday()]}）", ""]

    tool_result = result.get("tool_result") or {}
    if result.get("intent") == "aggregated_day" and isinstance(tool_result, dict):
        lines.extend(_render_aggregated(tool_result))
    else:
        # 降级路径:未命中多工具链(单工具/通用对话),直接采用 LLM answer 作为简报正文
        answer = (result.get("answer") or "").strip()
        lines.append(answer or "今日暂无安排。")
        lines.append("")

    lines.append(f"_生成时间：{timezone.localtime(timezone.now()).strftime('%Y-%m-%d %H:%M')}（Asia/Shanghai）_")
    return "\n".join(lines)


def _render_aggregated(tool_result: dict) -> list[str]:
    """渲染聚合链路(ResultSynthesizer 输出)部分。"""
    lines: list[str] = []

    summary = (tool_result.get("summary") or "未找到相关信息").strip()
    lines.append(f"> {summary}")
    lines.append("")

    module_counts = tool_result.get("moduleCounts") or {}
    if module_counts:
        lines.append("## 各模块统计")
        lines.append("")
        for module, count in module_counts.items():
            lines.append(f"- {module}：{count} 条")
        lines.append("")

    items = tool_result.get("items") or []
    if items:
        shown = items[:MAX_HIGHLIGHT_ITEMS]
        remaining = len(items) - len(shown)
        suffix = "" if remaining <= 0 else f"，另有 {remaining} 条未展示"
        lines.append(f"## 重点条目（前 {len(shown)} 条{suffix}）")
        lines.append("")
        for item in shown:
            lines.append(_render_item(item))
        lines.append("")

    return lines


def _render_item(item: dict) -> str:
    """渲染单条条目为列表项：- 【模块】时间 摘要。"""
    if not isinstance(item, dict):
        return f"- {str(item)[:MAX_ITEM_DESC_LENGTH]}"
    module = item.get("module") or "未知模块"
    sort_key = item.get("sort_key")
    time_part = "" if not sort_key or str(sort_key) == _NO_SORT_KEY else f"{sort_key} "
    return f"- 【{module}】{time_part}{_item_description(item.get('data'))}"


def _item_description(data) -> str:
    """从条目 data 中抽取一行摘要。

    依次尝试常见字段(标题/名称/内容等);全部缺失时兜底取第一个非空字符串值,
    仍无则返回"(无摘要)"。任何情况下都截断到 MAX_ITEM_DESC_LENGTH。
    """
    if not isinstance(data, dict):
        return str(data)[:MAX_ITEM_DESC_LENGTH]
    for key in _DESC_KEYS:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()[:MAX_ITEM_DESC_LENGTH]
    for value in data.values():
        if isinstance(value, str) and value.strip():
            return value.strip()[:MAX_ITEM_DESC_LENGTH]
    return "(无摘要)"
