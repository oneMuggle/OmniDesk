"""多 Agent 协作层

提供角色体系、任务包、执行器、质量门禁、故障自愈、Supervisor 调度等能力,
用于支持"文献调研 / 数据分析 / 报告整理 / 代码开发"等长任务场景。

与现有单 Agent 管道(`smart_assistant.agent.AgentOrchestrator`)并行工作,
通过 IntentClassifier 分流:
- 简单查询 → 现有 AgentOrchestrator(< 5s)
- 复杂任务 → MultiAgentExecutor(10s - 10min)

包结构:
- roles.py: AgentRole 枚举 + RoleProfile + ROLE_PROFILES 注册表
- task_packet.py: TaskPacket / SubTask / ExecutionMode / FailureMode + TaskPacketValidator
- shared_context.py: SharedContext 跨 agent 共享上下文 + Decision + ErrorRecord
- executor.py: MultiAgentExecutor 主执行器(待实现)
- pipeline.py / fanout.py / hierarchical.py: 三种执行模式(待实现)
- quality_gate.py: 质量门禁(待实现)
- recovery.py: Recovery Recipes 故障自愈(待实现)
- supervisor.py: Supervisor LLM 任务分解(待实现)
"""

from .roles import AgentRole, RoleProfile, ROLE_PROFILES, get_profile
from .task_packet import (
    ExecutionMode,
    FailureMode,
    SubTask,
    TaskPacket,
    TaskPacketValidator,
)
from .shared_context import Decision, ErrorRecord, SharedContext

__all__ = [
    # roles.py
    "AgentRole",
    "RoleProfile",
    "ROLE_PROFILES",
    "get_profile",
    # task_packet.py
    "ExecutionMode",
    "FailureMode",
    "SubTask",
    "TaskPacket",
    "TaskPacketValidator",
    # shared_context.py
    "Decision",
    "ErrorRecord",
    "SharedContext",
]
