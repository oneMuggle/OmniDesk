"""Hook 系统

借鉴 claw-code 的 PreToolUse / PostToolUse / PostToolUseFailure 钩子设计,
实现工具执行的插件化扩展。

Hook 可以在工具执行前/后/失败时介入,用于:
- 审计日志(AuditLogHook)
- PII 脱敏(PIISanitizerHook,Phase 2)
- 敏感数据门控(SensitiveDataGateHook,Phase 2)
- 工具超时重试(ToolTimeoutHook,Phase 2)

通过 HookRegistry(全局单例)集中注册和管理,由 MultiAgentExecutor
在工具调用前后触发。
"""

from .base import (
    HookEvent,
    HookRegistry,
    HookResult,
    RecoveryAction,
    Reject,
    ToolHook,
    ToolHookBase,
    get_registry,
)

__all__ = [
    "HookEvent",
    "HookRegistry",
    "HookResult",
    "RecoveryAction",
    "Reject",
    "ToolHook",
    "ToolHookBase",
    "get_registry",
]
