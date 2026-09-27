"""AI 能力注册中心（S1）。

各业务 app 在 ``ai_tools.py`` 中用 ``@toolset`` + ``ToolSpec`` 声明自己的 AI 工具，
``smart_assistant`` 在 ``ready()`` 中调用 ``capabilities.discover()`` 自动发现、
自检并注册到 ``ToolRegistry``。详见 ``docs/plans/2026-09-27_ai-capability-registry-s1.md``。
"""

from .registry import CapabilityRegistry, ResolvedToolSpec, capabilities, validate_spec
from .spec import LOGIN_ONLY, ConfirmPolicy, DataScope, PageContext, QuickPrompt, Toolset, ToolSpec, toolset

__all__ = [
    "LOGIN_ONLY",
    "CapabilityRegistry",
    "ConfirmPolicy",
    "DataScope",
    "PageContext",
    "QuickPrompt",
    "ResolvedToolSpec",
    "ToolSpec",
    "Toolset",
    "capabilities",
    "toolset",
    "validate_spec",
]
