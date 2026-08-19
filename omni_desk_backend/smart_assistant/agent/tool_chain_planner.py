"""工具链计划生成器。

当用户查询涉及多个意图时（如"查询张三的值班安排和待审批流程"），
LLM 生成工具执行计划，指定工具顺序和依赖关系。
"""

import json

from llm_service.router import get_router
from .prompt_builder import TOOL_CHAIN_PROMPT

from observability import get_logger

logger = get_logger(__name__, "smart_assistant")


def generate_tool_chain_plan(query: str, schemas: list, history: list = None) -> list | None:
    """判断是否需要多工具，并生成执行计划。

    Args:
        query: 用户查询
        schemas: 所有工具的 schema 列表
        history: 可选的对话历史

    Returns:
        执行计划列表（需要多工具时），或 None（单工具场景）
    """
    # 先尝试单意图分类
    from .intent_classifier import classify_intent

    primary_intent = classify_intent(query, schemas, history)

    # 检查查询中是否包含多个意图的关键词(子串重叠已消解)
    relevant_tools = _resolve_intent_overlap(query, schemas)

    # 如果只有一个工具匹配，不需要链式执行
    if len(relevant_tools) <= 1:
        return None

    # 多工具场景，生成执行计划
    try:
        plan = _ask_llm_for_plan(query, schemas, history)
        return plan
    except Exception as e:
        logger.warning("工具链计划生成失败: %s", e)
        return None


# 意图关键词映射(模块级常量,供 _matches_intent 只读使用)
intent_keywords = {
    "schedule_query": ["排班", "值班", "谁值班", "值班表"],
    "event_query": ["事件", "日程", "节假日", "假期", "放假"],
    "personnel_query": ["人员", "谁", "部门", "职位", "电话", "联系人"],
    "knowledge_qa": ["知识", "文档", "文档库", "怎么", "如何", "是什么"],
    "document_search": ["文档", "公文", "模板", "搜索文档"],
    "memo_query": ["备忘录", "便签", "提醒"],
    "memo_create": ["建一条", "创建备忘", "新增备忘", "记一条", "提醒我", "记一下"],
    "memo_update": ["改备忘", "修改备忘", "更新备忘", "改提醒"],
    # 用动词作关键词(用户说"删除买菜备忘"时动词"删除"后跟标题"买菜",
    # 组合词"删除备忘"不成立);且不与 memo_query/memo_update 关键词产生子串重叠
    "memo_delete": ["删除", "删掉", "移除", "清除"],
    "project_status": ["项目", "进度", "里程碑", "负责人"],
    "news_search": ["新闻", "通知", "公告"],
    # 换班三分支(P0-1,llm-swap-shift Phase 2)。注:换班是单工具场景,
    # 此处关键词仅参与多工具粗筛,最终路由以 classify_intent 的 LLM 分类为准;
    # 误命中多工具时 TOOL_CHAIN_PROMPT 会让 LLM 返回空数组回退单工具路径。
    "swap_request_create": ["换班", "替班", "调班", "换一下", "替一下"],
    "swap_request_decide": ["同意换班", "拒绝换班", "撤销换班", "取消换班", "接受换班", "不同意换班"],
    "swap_request_query": ["我发起的换班", "换班进度", "换班状态", "收到的换班", "收到的换班申请", "谁要跟我换班"],
}


def _matches_intent(query: str, schema: dict) -> list:
    """返回查询命中的 keyword 列表(空 = 不匹配)。

    返回 list 而非 bool,供 generate_tool_chain_plan 做子串重叠消解
    (短 keyword 命中被更长且包含它的命中覆盖)。
    """
    intent_name = schema.get("name", "").lower()
    keywords = intent_keywords.get(intent_name, [])
    return [kw for kw in keywords if kw in query]


def _resolve_intent_overlap(query: str, schemas: list) -> list:
    """消解 keyword 子串重叠后,返回匹配的意图名列表。

    规则:若命中 kw_a 是另一命中 kw_b 的严格子串(kw_a in kw_b 且不同),
    则 kw_a 的命中被覆盖丢弃。例:「提醒我明天开会」——
    memo_query 命中 "提醒"(2),memo_create 命中 "提醒我"(3);
    "提醒" in "提醒我" → memo_query 命中被覆盖,只剩 memo_create(单意图)。
    """
    hits = []  # [(intent, kw)]
    for schema in schemas:
        for kw in _matches_intent(query, schema):
            hits.append((schema["name"], kw))

    resolved: list = []
    seen: set = set()
    for name, kw in hits:
        covered = any(kw in other_kw and kw != other_kw for _, other_kw in hits)
        if covered or name in seen:
            continue
        seen.add(name)
        resolved.append(name)
    return resolved


def _ask_llm_for_plan(query: str, schemas: list, history: list = None) -> list | None:
    """让 LLM 生成工具执行计划。"""
    schema_text = json.dumps(schemas, ensure_ascii=False, indent=2)

    prompt = TOOL_CHAIN_PROMPT.format(
        tool_schemas=schema_text,
        user_query=query,
    )

    client = get_router()
    response, _ = client.generate(prompt=prompt)

    # 解析 JSON 响应
    try:
        # 尝试从响应中提取 JSON
        json_start = response.find("[")
        json_end = response.rfind("]") + 1
        if json_start >= 0 and json_end > json_start:
            plan = json.loads(response[json_start:json_end])
            # 验证计划格式
            if isinstance(plan, list) and all("tool" in step for step in plan):
                return plan
        return None
    except (json.JSONDecodeError, ValueError):
        logger.warning("工具链计划 JSON 解析失败: %s", response[:200])
        return None
