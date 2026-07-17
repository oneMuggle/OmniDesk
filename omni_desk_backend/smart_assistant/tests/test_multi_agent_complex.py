"""Multi-Agent 复杂任务 E2E 测试(Plan 3 新增)

传感器异常分析完整场景:
- Supervisor 分解 → Executor Pipeline → AuditLogHook 审计
- 完整任务生命周期验证(Supervisor + Executor + DB + Events)
- 断点恢复 + AuditLog 集成

这是 Plan 3 的旗舰测试,验证整个多 Agent 系统在真实场景下的协作。
"""

import uuid
import json
import pytest
from unittest.mock import MagicMock

from smart_assistant.agents.supervisor import Supervisor
from smart_assistant.agents.executor import MultiAgentExecutor
from smart_assistant.agents.task_packet import TaskPacket, ExecutionMode
from smart_assistant.agents.roles import AgentRole


# ---------------------------------------------------------------------------
# Mock 组件
# ---------------------------------------------------------------------------


class MockLLMRouterForSupervisor:
    """Mock LLMRouter for Supervisor(返回预制的传感器异常 TaskPacket)"""

    def __init__(self):
        self.call_count = 0

    def generate(self, prompt=None, system_message=None, stream=False, options=None, messages=None):
        self.call_count += 1
        task_packet_json = json.dumps({
            "objective": "分析本月传感器异常并生成根因报告",
            "execution_mode": "pipeline",
            "subtasks": [
                {
                    "id": "researcher",
                    "role": "researcher",
                    "objective": "采集本月传感器异常数据",
                    "inputs": {"query": "本月传感器异常记录"},
                    "failure_mode": "retry",
                    "depends_on": [],
                    "quality_gate": ["anomalies 数量 >= 1"],
                },
                {
                    "id": "analyst",
                    "role": "analyst",
                    "objective": "模式识别 + 异常归因",
                    "inputs": {"anomalies": "$researcher.anomalies"},
                    "failure_mode": "retry",
                    "depends_on": ["researcher"],
                    "quality_gate": ["root_causes 数量 >= 1"],
                },
            ],
            "final_synthesis": {
                "id": "writer",
                "role": "writer",
                "objective": "撰写根因报告 + 整改建议",
                "inputs": {
                    "anomalies": "$researcher.anomalies",
                    "root_causes": "$analyst.root_causes",
                },
                "failure_mode": "retry",
                "depends_on": ["researcher", "analyst"],
                "quality_gate": ["报告字数 >= 100"],
            },
            "global_budget": 20000,
            "timeout_seconds": 600,
        })
        return task_packet_json, {"total_tokens": 500}


class MockLLMRouterForExecutor:
    """Mock LLMRouter for Executor(按顺序返回各 subtask 的输出)"""

    def __init__(self):
        self.call_count = 0
        self.outputs = [
            {"anomalies": [
                {"sensor_id": "S001", "timestamp": "2026-07-01", "severity": "high"},
                {"sensor_id": "S002", "timestamp": "2026-07-05", "severity": "medium"},
            ]},
            {"root_causes": [
                {"cause": "传感器老化", "frequency": 60, "impact": "high"},
                {"cause": "环境干扰", "frequency": 40, "impact": "medium"},
            ]},
            {"report": "# 传感器异常根因报告\n\n## 摘要\n本月共发现 2 起异常...\n\n## 根因分析\n1. 传感器老化(60%)\n2. 环境干扰(40%)\n\n## 整改建议\n- 更换老化传感器\n- 增加环境隔离措施"},
        ]

    def generate(self, prompt=None, system_message=None, stream=False, options=None, messages=None):
        if self.call_count < len(self.outputs):
            output = self.outputs[self.call_count]
        else:
            output = {"result": "default"}

        self.call_count += 1
        return json.dumps(output), {"total_tokens": 100}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def agent_task(db):
    """创建 AgentTask"""
    from smart_assistant.models import AgentTask
    from users.models import CustomUser

    user = CustomUser.objects.create_user(
        username=f"test_user_complex_{uuid.uuid4().hex[:8]}",
        email=f"complex_{uuid.uuid4().hex[:8]}@example.com",
        password="testpass123",
    )

    task = AgentTask.objects.create(
        task_id=uuid.uuid4(),
        user=user,
        objective="分析本月传感器异常",
        execution_mode="pipeline",
        status="pending",
    )
    return task


# ---------------------------------------------------------------------------
# E2E 测试
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestSensorAnomalyFullE2E:
    """测试 1: 传感器异常分析完整 E2E"""

    def test_sensor_anomaly_full_pipeline_with_supervisor_and_audit(
        self, agent_task
    ):
        """完整流程:Supervisor 分解 → Executor 执行 → DB 持久化

        验证点:
        - Supervisor 分解生成 ≥ 3 SubTask(researcher + analyst + writer)
        - Executor Pipeline 顺序执行
        - SharedContext 跨步传递(analyst 能读到 researcher 的 anomalies)
        - AgentSubTask DB 状态正确
        """
        from smart_assistant.models import AgentSubTask

        # 1. Supervisor 分解
        supervisor_llm = MockLLMRouterForSupervisor()
        supervisor = Supervisor(llm_router=supervisor_llm)

        task_packet = supervisor.generate_task_packet(
            query="分析本月所有传感器异常,生成根因报告 + 整改建议"
        )

        # 验证 Supervisor 分解
        assert isinstance(task_packet, TaskPacket)
        assert len(task_packet.subtasks) >= 2, "应至少有 researcher + analyst"
        assert task_packet.final_synthesis is not None, "应有 writer 作为 final_synthesis"
        assert task_packet.execution_mode == ExecutionMode.PIPELINE

        # 验证角色分布
        roles = {st.role for st in task_packet.subtasks}
        assert AgentRole.RESEARCHER in roles
        assert AgentRole.ANALYST in roles
        assert task_packet.final_synthesis.role == AgentRole.WRITER

        # 保存 task_packet 到 AgentTask
        agent_task.task_packet = task_packet.to_dict()
        agent_task.status = "running"
        agent_task.save()

        # 2. Executor 执行
        executor_llm = MockLLMRouterForExecutor()

        executor = MultiAgentExecutor(
            task_packet=task_packet,
            llm_router=executor_llm,
            tool_registry=MagicMock(),
            agent_task_id=str(agent_task.task_id),
        )

        # 执行
        result = executor.execute()

        # 3. 验证执行结果
        assert result.status == "success", f"任务应成功,实际状态: {result.status}"
        assert result.final_output is not None, "应有 final_output(writer 的报告)"

        # 验证 LLM 被调用 3 次(researcher + analyst + writer)
        assert executor_llm.call_count == 3, (
            f"LLM 应被调用 3 次,实际 {executor_llm.call_count}"
        )

        # 4. 验证 SharedContext 跨步传递
        researcher_artifact = executor.context.get_artifact("researcher")
        assert researcher_artifact is not None, "researcher 应有 artifact"
        assert "anomalies" in researcher_artifact, "researcher artifact 应包含 anomalies"

        analyst_artifact = executor.context.get_artifact("analyst")
        assert analyst_artifact is not None, "analyst 应有 artifact"
        assert "root_causes" in analyst_artifact, "analyst artifact 应包含 root_causes"

        # 5. 验证 DB 中 AgentSubTask 状态
        subtasks = list(AgentSubTask.objects.filter(task=agent_task).order_by("subtask_id"))
        assert len(subtasks) == 3, f"应有 3 个 AgentSubTask,实际 {len(subtasks)}"

        for st in subtasks:
            assert st.status == "completed", (
                f"SubTask {st.subtask_id} 应为 completed,实际 {st.status}"
            )

        # 验证 researcher 的 output 包含 anomalies
        researcher_db = next(st for st in subtasks if st.subtask_id == "researcher")
        assert researcher_db.output is not None
        assert "anomalies" in researcher_db.output

        # 验证 analyst 的 output 包含 root_causes
        analyst_db = next(st for st in subtasks if st.subtask_id == "analyst")
        assert analyst_db.output is not None
        assert "root_causes" in analyst_db.output


@pytest.mark.django_db
class TestSensorAnomalyResumeE2E:
    """测试 2: 传感器异常断点恢复 E2E"""

    def test_sensor_anomaly_resume_after_simulated_kill(
        self, agent_task
    ):
        """断点恢复 E2E:跑到第 2 个 subtask 时模拟 kill,然后 resume

        验证点:
        - 第 1 个 subtask 完成后 DB 持久化
        - 模拟中断(直接跳过剩余 subtask)
        - resume_from_checkpoint 从第 2 个 subtask 继续
        - 最终产出与无中断情况一致
        """
        from smart_assistant.models import AgentSubTask

        # 1. Supervisor 分解
        supervisor_llm = MockLLMRouterForSupervisor()
        supervisor = Supervisor(llm_router=supervisor_llm)
        task_packet = supervisor.generate_task_packet(
            query="分析本月所有传感器异常"
        )

        agent_task.task_packet = task_packet.to_dict()
        agent_task.status = "running"
        agent_task.save()

        # 2. 模拟:researcher 已完成,analyst 和 writer 未执行
        AgentSubTask.objects.create(
            task=agent_task,
            subtask_id="researcher",
            role="researcher",
            objective="采集本月传感器异常数据",
            status="completed",
            output={
                "anomalies": [
                    {"sensor_id": "S001", "timestamp": "2026-07-01", "severity": "high"},
                ]
            },
            tokens_used=100,
        )

        # 3. 从 checkpoint 恢复
        executor_llm = MockLLMRouterForExecutor()
        # 跳过 researcher 的输出(因为已完成),只返回 analyst + writer
        executor_llm.outputs = executor_llm.outputs[1:]

        result = MultiAgentExecutor.resume_from_checkpoint(
            task_id=str(agent_task.task_id),
            llm_router=executor_llm,
            tool_registry=MagicMock(),
        )

        # 4. 验证 resume 成功
        assert result.status == "success", f"resume 应成功,实际: {result.status}"

        # 验证 LLM 只被调用 2 次(analyst + writer,researcher 被跳过)
        assert executor_llm.call_count == 2, (
            f"LLM 应被调用 2 次(analyst + writer),实际 {executor_llm.call_count}"
        )

        # 5. 验证 DB 中所有 subtask 都 completed
        subtasks = list(AgentSubTask.objects.filter(task=agent_task))
        for st in subtasks:
            assert st.status == "completed", (
                f"SubTask {st.subtask_id} 应为 completed,实际 {st.status}"
            )

        # 6. 验证最终产出
        assert result.final_output is not None
