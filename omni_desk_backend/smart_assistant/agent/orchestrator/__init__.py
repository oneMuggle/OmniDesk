"""Agent 编排器包(R5-D5 拆分)。

原 orchestrator.py(660 行单文件)拆为:
- entry.py:AgentOrchestrator 公开入口(process / process_stream + 原生路径)
- run_path.py:use_native 路径决策 + endpoint 能力检查(RunPathResolver)
- persistence.py:legacy JSON 路径方法集(LegacyProcessMixin)

行为零变化:本 __init__ re-export 原模块的全部公开名,外部
``from smart_assistant.agent.orchestrator import X`` 与测试
``patch("smart_assistant.agent.orchestrator.X")`` 的语义保持不变。
"""

from ..intent_classifier import (
    classify_intent,
    generate_answer,
    generate_general_answer,
    generate_tool_empty_answer,
)
from ..tool_chain_planner import generate_tool_chain_plan
from ...tools.registry import ToolRegistry
from ...cache import (
    get_cached_intent,
    cache_intent,
    get_cached_tool_result,
    cache_tool_result,
    get_cached_answer,
    cache_answer,
    set_confirmation_draft,
)
from ..sse_contract import (
    ERROR_KIND_HINTS as ERROR_KIND_HINTS,
    FORMAT_VERSION as FORMAT_VERSION,
    annotate_error_kind as annotate_error_kind,
    classify_error_kind as classify_error_kind,
    sse_event as sse_event,
)
from ..orchestrator_helpers import _dict_to_query as _dict_to_query, _scope_cache_sig
from ...hooks.wiring import execute_guarded as execute_guarded
from .entry import AgentOrchestrator

__all__ = [
    "ERROR_KIND_HINTS",
    "FORMAT_VERSION",
    "AgentOrchestrator",
    "_dict_to_query",
    "_scope_cache_sig",
    "annotate_error_kind",
    "cache_answer",
    "cache_intent",
    "cache_tool_result",
    "classify_error_kind",
    "classify_intent",
    "generate_answer",
    "generate_general_answer",
    "generate_tool_empty_answer",
    "generate_tool_chain_plan",
    "get_cached_answer",
    "get_cached_intent",
    "get_cached_tool_result",
    "set_confirmation_draft",
    "sse_event",
    "ToolRegistry",
]
