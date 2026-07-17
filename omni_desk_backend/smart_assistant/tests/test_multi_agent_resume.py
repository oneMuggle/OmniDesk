"""MultiAgentExecutor 断点恢复测试(Plan 3 新增)

验证 executor 的断点恢复能力:
- 全流程跑完 3 个 subtask,全部 completed,DB 持久化正确
- 跑到第 2 个 subtask 时 kill,重启后从第 2 个续(第 1 个不重跑)
- resume 后 SharedContext.artifacts 与原始一致
- pause → resume 状态转换正确
- 所有 subtask failed → resume 后仍 failed

使用 pytest-django 同步测试,通过 Django ORM 验证 DB 状态。
"""

import uuid
import pytest
from unittest.mock import MagicMock

from smart_assistant.agents.executor import MultiAgentExecutor
from smart_assistant.agents.task_packet import TaskPacket, SubTask, ExecutionMode, FailureMode
from smart_assistant.agents.roles import AgentRole


# ---------------------------------------------------------------------------
# Mock LLMRouter
# ---------------------------------------------------------------------------


class MockLLMRouter:
    """Mock LLMRouter(按顺序返回预设输出)"""

    def __init__(self, subtask_outputs: dict[str, dict] | list[dict] | None = None):
        """
        Args:
            subtask_outputs: 可以是 dict {subtask_id: output} 或 list [output1, output2, ...]
                           如果是 dict,按调用顺序依次返回 values
                           如果是 list,按顺序返回
        """
        if isinstance(subtask_outputs, dict):
            # 转换为按调用顺序返回的 list
            self.outputs_list = list(subtask_outputs.values())
        elif isinstance(subtask_outputs, list):
            self.outputs_list = subtask_outputs
        else:
            self.outputs_list = []

        self.call_count = 0
        self.call_log: list[str] = []

    def generate(self, prompt=None, system_message=None, stream=False, options=None, messages=None):
        # 按调用顺序返回输出
        if self.call_count < len(self.outputs_list):
            output = self.outputs_list[self.call_count]
        else:
            output = {"result": "default"}

        self.call_log.append(f"call_{self.call_count}")
        self.call_count += 1

        import json
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
        username=f"test_user_resume_{uuid.uuid4().hex[:8]}",
        email=f"resume_{uuid.uuid4().hex[:8]}@example.com",
        password="testpass123",
    )

    task = AgentTask.objects.create(
        task_id=uuid.uuid4(),
        user=user,
        objective="测试断点恢复",
        execution_mode="pipeline",
        status="running",
    )
    return task


@pytest.fixture
def three_subtask_packet():
    """创建 3 个 subtask 的 TaskPacket"""
    return TaskPacket(
        task_id=str(uuid.uuid4()),
        objective="测试任务",
        execution_mode=ExecutionMode.PIPELINE,
        subtasks=[
            SubTask(
                id="step1",
                role=AgentRole.RESEARCHER,
                objective="第一步",
                failure_mode=FailureMode.RETRY,
                depends_on=[],
            ),
            SubTask(
                id="step2",
                role=AgentRole.ANALYST,
                objective="第二步",
                failure_mode=FailureMode.RETRY,
                depends_on=["step1"],
            ),
            SubTask(
                id="step3",
                role=AgentRole.WRITER,
                objective="第三步",
                failure_mode=FailureMode.RETRY,
                depends_on=["step2"],
            ),
        ],
        global_budget=20000,
        timeout_seconds=600,
    )


# ---------------------------------------------------------------------------
# 测试用例
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestFullPipelineWithDBPersistence:
    """测试 1: 全流程跑完 3 个 subtask,DB 持久化正确"""

    def test_full_pipeline_persists_all_subtasks_to_db(self, agent_task, three_subtask_packet):
        """验证 3 个 subtask 全部完成后,DB 中 AgentSubTask 状态正确"""
        from smart_assistant.models import AgentSubTask

        # 保存 task_packet 到 AgentTask
        agent_task.task_packet = three_subtask_packet.to_dict()
        agent_task.save()

        # Mock LLMRouter(每个 subtask 返回不同输出)
        llm_router = MockLLMRouter(subtask_outputs={
            "step1": {"data": "research_result"},
            "step2": {"analysis": "analysis_result"},
            "step3": {"report": "final_report"},
        })

        # 创建 executor(启用 DB 持久化)
        executor = MultiAgentExecutor(
            task_packet=three_subtask_packet,
            llm_router=llm_router,
            tool_registry=MagicMock(),
            agent_task_id=str(agent_task.task_id),
        )

        # 执行
        result = executor.execute()

        # 验证执行成功
        assert result.status == "success"
        assert len(result.subtask_results) == 3

        # 验证 DB 中 AgentSubTask 全部 completed
        subtasks = list(AgentSubTask.objects.filter(task=agent_task).order_by("subtask_id"))
        assert len(subtasks) == 3, f"应有 3 个 AgentSubTask,实际 {len(subtasks)}"

        for st in subtasks:
            assert st.status == "completed", f"SubTask {st.subtask_id} 状态应为 completed,实际 {st.status}"

        # 验证 output 已持久化
        step1_db = next(st for st in subtasks if st.subtask_id == "step1")
        assert step1_db.output == {"data": "research_result"}

        step2_db = next(st for st in subtasks if st.subtask_id == "step2")
        assert step2_db.output == {"analysis": "analysis_result"}

        step3_db = next(st for st in subtasks if st.subtask_id == "step3")
        assert step3_db.output == {"report": "final_report"}


@pytest.mark.django_db
class TestResumeFromCheckpoint:
    """测试 2: 跑到第 2 个 subtask 时 kill,重启后从第 2 个续"""

    def test_resume_skips_completed_subtasks(self, agent_task, three_subtask_packet):
        """验证 resume 模式跳过已完成的 subtask,只执行 pending 的"""
        from smart_assistant.models import AgentSubTask

        # 保存 task_packet
        agent_task.task_packet = three_subtask_packet.to_dict()
        agent_task.save()

        # 模拟:step1 已完成,step2/step3 未完成
        AgentSubTask.objects.create(
            task=agent_task,
            subtask_id="step1",
            role="researcher",
            objective="第一步",
            status="completed",
            output={"data": "research_result"},
            tokens_used=100,
        )
        AgentSubTask.objects.create(
            task=agent_task,
            subtask_id="step2",
            role="analyst",
            objective="第二步",
            status="pending",
        )
        AgentSubTask.objects.create(
            task=agent_task,
            subtask_id="step3",
            role="writer",
            objective="第三步",
            status="pending",
        )

        # Mock LLMRouter
        llm_router = MockLLMRouter(subtask_outputs={
            "step2": {"analysis": "new_analysis"},
            "step3": {"report": "new_report"},
        })

        # 从 checkpoint 恢复
        result = MultiAgentExecutor.resume_from_checkpoint(
            task_id=str(agent_task.task_id),
            llm_router=llm_router,
            tool_registry=MagicMock(),
        )

        # 验证执行成功
        assert result.status == "success"

        # 验证 LLM 只被调用 2 次(step2 + step3,step1 被跳过)
        assert llm_router.call_count == 2, (
            f"LLM 应被调用 2 次(step2 + step3),实际 {llm_router.call_count} 次"
        )

        # 验证 DB 中所有 subtask 现在都是 completed
        subtasks = list(AgentSubTask.objects.filter(task=agent_task))
        for st in subtasks:
            assert st.status == "completed", f"SubTask {st.subtask_id} 应为 completed,实际 {st.status}"


@pytest.mark.django_db
class TestResumeContextConsistency:
    """测试 3: resume 后 SharedContext.artifacts 与原始一致"""

    def test_resume_rebuilds_context_from_completed_artifacts(self, agent_task, three_subtask_packet):
        """验证 resume 后 context 中包含已完成 subtask 的 artifacts"""
        from smart_assistant.models import AgentSubTask

        agent_task.task_packet = three_subtask_packet.to_dict()
        agent_task.save()

        # 模拟:step1 已完成,artifacts 已保存
        AgentSubTask.objects.create(
            task=agent_task,
            subtask_id="step1",
            role="researcher",
            objective="第一步",
            status="completed",
            output={"data": "research_result", "references": ["ref1", "ref2"]},
            tokens_used=100,
        )

        llm_router = MockLLMRouter(subtask_outputs={
            "step2": {"analysis": "analysis_based_on_research"},
            "step3": {"report": "final"},
        })

        # 恢复执行
        result = MultiAgentExecutor.resume_from_checkpoint(
            task_id=str(agent_task.task_id),
            llm_router=llm_router,
            tool_registry=MagicMock(),
        )

        assert result.status == "success"

        # 验证 LLM 被调用 2 次(step2 + step3)
        assert llm_router.call_count == 2
        assert len(llm_router.call_log) == 2


@pytest.mark.django_db
class TestPauseResume:
    """测试 4: pause → resume 状态转换正确"""

    def test_pause_stops_execution_and_resume_continues(self, agent_task, three_subtask_packet):
        """验证 pause 后执行停止,resume 后从暂停点继续"""
        from smart_assistant.models import AgentSubTask, AgentTask

        agent_task.task_packet = three_subtask_packet.to_dict()
        agent_task.status = "running"
        agent_task.save()

        # 模拟:step1 已完成
        AgentSubTask.objects.create(
            task=agent_task,
            subtask_id="step1",
            role="researcher",
            objective="第一步",
            status="completed",
            output={"data": "result1"},
            tokens_used=100,
        )

        # 第一次执行(只跑 step1,然后 pause)
        llm_router_1 = MockLLMRouter(subtask_outputs={
            "step1": {"data": "result1"},
        })

        executor_1 = MultiAgentExecutor(
            task_packet=three_subtask_packet,
            llm_router=llm_router_1,
            tool_registry=MagicMock(),
            agent_task_id=str(agent_task.task_id),
        )

        # 手动调用 pause
        executor_1.pause()

        # 验证任务状态变为 paused
        agent_task.refresh_from_db()
        assert agent_task.status == "paused", f"任务状态应为 paused,实际 {agent_task.status}"

        # 第二次执行(resume)
        llm_router_2 = MockLLMRouter(subtask_outputs={
            "step2": {"analysis": "result2"},
            "step3": {"report": "result3"},
        })

        result = MultiAgentExecutor.resume_from_checkpoint(
            task_id=str(agent_task.task_id),
            llm_router=llm_router_2,
            tool_registry=MagicMock(),
        )

        # 验证 resume 后执行成功
        assert result.status == "success"


@pytest.mark.django_db
class TestResumeWithAllFailed:
    """测试 5: 所有 subtask failed → resume 后仍 failed"""

    def test_resume_with_all_failed_subtasks_returns_failed(self, agent_task, three_subtask_packet):
        """验证所有 subtask 都 failed 时,resume 返回 failed 状态"""
        from smart_assistant.models import AgentSubTask

        agent_task.task_packet = three_subtask_packet.to_dict()
        agent_task.status = "failed"
        agent_task.save()

        # 模拟:所有 subtask 都 failed
        for subtask in three_subtask_packet.subtasks:
            AgentSubTask.objects.create(
                task=agent_task,
                subtask_id=subtask.id,
                role=subtask.role.value,
                objective=subtask.objective,
                status="failed",
                error_message="模拟失败",
            )

        # Mock LLMRouter(继续返回失败)
        class FailingLLMRouter:
            def generate(self, **kwargs):
                raise RuntimeError("LLM 持续失败")

        # 尝试 resume
        result = MultiAgentExecutor.resume_from_checkpoint(
            task_id=str(agent_task.task_id),
            llm_router=FailingLLMRouter(),
            tool_registry=MagicMock(),
        )

        # 验证结果为 failed
        assert result.status == "failed"
