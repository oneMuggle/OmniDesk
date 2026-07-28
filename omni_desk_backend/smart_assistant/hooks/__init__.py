"""Hook 系统

借鉴 claw-code 的 PreToolUse / PostToolUse / PostToolUseFailure 钩子设计,
实现工具执行的插件化扩展。

Hook 可以在工具执行前/后/失败时介入,用于:
- 审计日志(AuditLogHook,含工具风险等级 risk_level)
- PII 脱敏(PiiMaskingHook,post_execute 掩码手机号/身份证/邮箱)
- 工具超时熔断(TimeoutGuardHook,配置入口 + 执行包装层计时)
- 敏感数据门控(SensitiveDataGateHook,规划中)

通过 HookRegistry(全局单例)集中注册和管理,由执行器
(AgentOrchestrator / ToolChainExecutor)在工具调用前后经
``hooks.wiring`` 的同步入口触发。
内置实现见 hooks/builtin/;生产注册与同步调用入口见 hooks/wiring.py。
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
from .wiring import (
    apply_failure_hooks,
    apply_post_execute_hooks,
    execute_guarded,
    register_builtin_hooks,
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
    "apply_failure_hooks",
    "apply_post_execute_hooks",
    "execute_guarded",
    "register_builtin_hooks",
]
