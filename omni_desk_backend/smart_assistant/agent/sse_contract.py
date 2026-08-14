"""SSE 输出契约与错误分类(从 orchestrator.py 提取,行为不变)。

提供与前端共享的机器可读契约:SSE 事件序列化、错误 kind 判定、中文 hint。
独立成模块供 orchestrator 与 views/chat.py 复用。
"""

import json

from observability import get_logger

from .conversation_context import is_failed_answer
from ..models import LlmAppConfig

logger = get_logger(__name__, "smart_assistant")


# ---------------------------------------------------------------------------
# 后端输出契约（与前端共享，机器可读；借鉴 claw-code 的 doctor 契约思路）
# ---------------------------------------------------------------------------

# SSE 事件契约版本号：所有 meta/chunk/done/session 事件均携带
FORMAT_VERSION = 1

# 错误分类 → 可操作的中文指引（前端按 kind 决定提示样式与跳转入口）
ERROR_KIND_HINTS = {
    "no_llm_endpoint": "请前往管理后台 → AI 应用配置 LLM 端点",
    "llm_unavailable": "LLM 服务暂时不可用，请稍后重试或检查端点连通性",
    "ragflow_unavailable": "知识库服务暂时不可用",
    "internal_error": "服务异常，请稍后重试",
}


def _has_active_llm_config() -> bool:
    """是否存在激活的智能助手 LLM 应用配置（且其端点同样激活）。"""
    return LlmAppConfig.objects.filter(
        app_name="smart_assistant",
        is_active=True,
        endpoint__is_active=True,
    ).exists()


def _mentions_ragflow(answer, tool_result) -> bool:
    """判断错误信息是否涉及 Ragflow（大小写不敏感）。"""
    haystacks = [str(answer or "")]
    if isinstance(tool_result, dict):
        for key in ("message", "error", "detail"):
            value = tool_result.get(key)
            if isinstance(value, str):
                haystacks.append(value)
    elif isinstance(tool_result, str):
        haystacks.append(tool_result)
    return any("ragflow" in text.lower() for text in haystacks)


def classify_error_kind(result: dict):
    """判定编排结果的机器可读错误分类（kind）。

    输出契约判定规则（优先级自上而下）：
    - 非失败响应（error 为假且回答无失败前缀）→ 返回 ``None``
    - knowledge_qa 工具失败且错误涉及 Ragflow → ``"ragflow_unavailable"``
    - 无激活的 LLM 应用配置/端点 → ``"no_llm_endpoint"``
    - 有配置但 LLM 回答生成失败 → ``"llm_unavailable"``
    - 其他失败（如显式 error 标记但回答无失败前缀）→ ``"internal_error"``

    保持纯函数 + 单次 DB 查询的形式，便于单测（需 django_db）。
    """
    if not (bool(result.get("error")) or is_failed_answer(result.get("answer"))):
        return None
    tool_used = result.get("tool_used") or ""
    if tool_used == "knowledge_qa" and _mentions_ragflow(result.get("answer"), result.get("tool_result")):
        return "ragflow_unavailable"
    if not _has_active_llm_config():
        return "no_llm_endpoint"
    if is_failed_answer(result.get("answer")):
        return "llm_unavailable"
    return "internal_error"


def sse_event(payload: dict) -> str:
    """序列化单条 SSE 事件：统一附带契约版本号 ``format_version``。"""
    return f"data: {json.dumps({'format_version': FORMAT_VERSION, **payload}, ensure_ascii=False)}\n\n"


def annotate_error_kind(payload: dict, answer: str, tool_used=None, tool_result=None) -> dict:
    """为失败事件载荷追加 ``kind`` + ``hint``（输出契约）。

    供 orchestrator 的 done 事件与视图层的 session/同步响应复用，
    保证同一失败场景在各出口拿到一致的错误分类。
    """
    kind = classify_error_kind(
        {
            "answer": answer,
            "error": True,
            "tool_used": tool_used,
            "tool_result": tool_result,
        }
    )
    payload["kind"] = kind
    payload["hint"] = ERROR_KIND_HINTS.get(kind, ERROR_KIND_HINTS["internal_error"])
    return payload
