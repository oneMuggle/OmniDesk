"""AI 写操作的公共部件（S3）。

- ``preview``：确认卡片预览（服务端根据数据库记录生成，公开前做字段白名单过滤）
- ``write_log``：统一写 ``AgentWriteLog``
- ``revert``：按目标模型注册的撤销处理器
- ``confirmations``：确认 / 取消的服务函数（视图与旧 chat 接口共用）

流程说明见 ``docs/technical/47-ai-write-actions.md``。
"""
