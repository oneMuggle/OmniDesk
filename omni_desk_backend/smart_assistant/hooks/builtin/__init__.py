"""内置 Hook 实现

Phase 1: 空包,仅做占位
Phase 2: 实现以下内置 Hook
- AuditLogHook: 统一写 AgentLog
- PIISanitizerHook: 脱敏用户输入中的手机号/身份证/银行卡
- SensitiveDataGateHook: 权限门控(替代硬编码 required_auth=True)
- ToolTimeoutHook: 工具超时重试
"""
