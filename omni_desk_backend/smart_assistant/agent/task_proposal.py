"""complex_task 意图 → 任务计划卡（S2）。

意图分类器早已会返回 ``complex_task``（多步骤 / 多角色 / 长文本产出），但此前没有
任何分支处理，最终落到通用对话。现在流式路径遇到它时不调用 LLM，直接返回一张
"任务计划卡"：前端展示任务目标，由用户决定创建多 Agent 协作任务（走
``/tasks/`` 创建 + 执行，卡片内订阅 SSE 进度），或改为直接回答。

``settings.SMART_ASSISTANT_COMPLEX_TASK_PROPOSAL = False`` 可回退到旧行为。
"""

from __future__ import annotations

from django.conf import settings

from .sse_contract import sse_event

COMPLEX_TASK_INTENT = "complex_task"

#: 任务目标最大长度（与 AgentTask 创建接口的 query 保持同一量级）
OBJECTIVE_MAX_CHARS = 500

PROPOSAL_ANSWER = (
    "这个问题需要多个步骤协作完成（例如检索资料、分析、撰写）。"
    "我可以为你创建一个协作任务，由多个 Agent 分步执行，并在这里实时显示进度；"
    "如果只需要简要回答，也可以选择直接回答。"
)


def task_proposal_enabled() -> bool:
    return bool(getattr(settings, "SMART_ASSISTANT_COMPLEX_TASK_PROPOSAL", True))


def should_propose_task(intent: str | None, tool_context=None) -> bool:
    """意图为 complex_task、开关打开、且本次请求没有要求"直接回答"时返回 True。"""
    if intent != COMPLEX_TASK_INTENT or not task_proposal_enabled():
        return False
    return bool(getattr(tool_context, "task_proposal_allowed", True))


def build_task_proposal(user_query: str) -> dict:
    objective = " ".join(str(user_query or "").split())[:OBJECTIVE_MAX_CHARS]
    return {"objective": objective, "mode": "agent_task"}


def stream_task_proposal(user_query: str):
    """依次产出 meta（含 task_proposal）→ chunk → done 三个 SSE 事件。"""
    yield sse_event(
        {
            "type": "meta",
            "intent": COMPLEX_TASK_INTENT,
            "tool_used": None,
            "tool_result": None,
            "sources": None,
            "task_proposal": build_task_proposal(user_query),
        }
    )
    yield sse_event({"type": "chunk", "content": PROPOSAL_ANSWER})
    yield sse_event({"type": "done", "finish_reason": "stop", "error": False})
