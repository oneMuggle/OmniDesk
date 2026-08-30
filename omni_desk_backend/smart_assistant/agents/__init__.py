"""多 Agent 协作层

提供角色体系、任务包、执行器、质量门禁、故障自愈、Supervisor 调度等能力,
用于支持"文献调研 / 数据分析 / 报告整理 / 代码开发"等长任务场景。

与现有单 Agent 管道(`smart_assistant.agent.AgentOrchestrator`)并行工作,
通过 IntentClassifier 分流:
- 简单查询 → 现有 AgentOrchestrator(< 5s)
- 复杂任务 → MultiAgentExecutor(10s - 10min)

包结构:
- roles.py: AgentRole 枚举 + RoleProfile + ROLE_PROFILES 注册表
- packet.py: TaskPacket / SubTask / ExecutionMode / FailureMode 数据类
- validator.py: TaskPacketValidator 任务包校验器
- shared_context.py: SharedContext 跨 agent 共享上下文 + Decision + ErrorRecord
- dataclasses.py: SubTaskResult / TaskResult / Event / EventBus 数据类(零依赖)
- executor.py: MultiAgentExecutor 主执行器(编排层,委托 subtask_runner / pipeline / checkpoint)
- subtask_runner.py: SubTaskRunner 单子任务执行(重试 / LLM 调用 / 输出解析)
- pipeline.py: PipelineRunner 流水线编排(依赖排序 / ABORT / SKIP / resume)
- checkpoint.py: CheckpointManager 检查点持久化 / 暂停 / 恢复
- fanout.py / hierarchical.py: 另两种执行模式(待抽出)
- quality_gate.py: 质量门禁(待实现)
- recovery.py: Recovery Recipes 故障自愈(待实现)
- supervisor.py: Supervisor LLM 任务分解(待实现)
"""

from .roles import AgentRole, RoleProfile, ROLE_PROFILES, get_profile
from .packet import (
    ExecutionMode,
    FailureMode,
    SubTask,
    TaskPacket,
)
from .validator import TaskPacketValidator
from .shared_context import Decision, ErrorRecord, SharedContext
from .executor import (
    EventBus,
    Event,
    PersistentEventBus,
    MultiAgentExecutor,
    SubTaskResult,
    TaskResult,
)
from .supervisor import Supervisor

__all__ = [
    # roles.py
    "AgentRole",
    "RoleProfile",
    "ROLE_PROFILES",
    "get_profile",
    # packet.py / validator.py
    "ExecutionMode",
    "FailureMode",
    "SubTask",
    "TaskPacket",
    "TaskPacketValidator",
    # shared_context.py
    "Decision",
    "ErrorRecord",
    "SharedContext",
    # executor.py
    "Event",
    "EventBus",
    "PersistentEventBus",
    "MultiAgentExecutor",
    "SubTaskResult",
    "TaskResult",
    # supervisor.py
    "Supervisor",
]
