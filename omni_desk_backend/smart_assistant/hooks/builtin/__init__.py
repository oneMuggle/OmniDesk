"""内置 Hook 实现

已落地:
- AuditLogHook: 统一写 AgentLog(工具级审计,含 risk_level)+ AgentEvent(任务级审计)
- PiiMaskingHook: 对工具输出中的手机号/身份证/邮箱做掩码(post_execute)
- TimeoutGuardHook: 工具超时熔断(配置入口 + 执行包装层,详见模块文档)

规划中:
- SensitiveDataGateHook: 权限门控(替代硬编码 required_auth=True)
"""

from .audit_log import AuditLogHook
from .pii_masking import PiiMaskingHook
from .timeout_guard import TimeoutGuardHook

__all__ = [
    "AuditLogHook",
    "PiiMaskingHook",
    "TimeoutGuardHook",
]
