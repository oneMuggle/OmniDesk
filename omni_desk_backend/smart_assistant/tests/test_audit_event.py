"""AuditLogHook 审计事件测试(Plan 3 新增)

验证 AuditLogHook 正确写入 AgentEvent:
- subtask.completed → AgentEvent 写入且 sequence 递增
- subtask.failed → AgentEvent 写入且 payload 含 error
- 完整任务的事件流 sequence 连续无重复

使用 pytest-django 同步测试 + async_to_sync 调用异步 hook 方法。
避免 SQLite 锁问题。
"""

import pytest
from unittest.mock import MagicMock
from asgiref.sync import async_to_sync

from smart_assistant.hooks.builtin.audit_log import AuditLogHook


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def agent_task(db):
    """创建 AgentTask 实例"""
    from smart_assistant.models import AgentTask
    from users.models import CustomUser
    import uuid

    user = CustomUser.objects.create_user(
        username="test_user_audit",
        email="audit_test@example.com",
        password="testpass123",
    )

    task = AgentTask.objects.create(
        task_id=uuid.uuid4(),
        user=user,
        objective="测试任务",
        execution_mode="pipeline",
        status="running",
    )
    return task


@pytest.fixture
def agent_subtask(agent_task):
    """创建 AgentSubTask 实例"""
    from smart_assistant.models import AgentSubTask

    subtask = AgentSubTask.objects.create(
        task=agent_task,
        subtask_id="test_subtask_1",
        role="researcher",
        objective="测试子任务",
        status="running",
    )
    return subtask


@pytest.fixture
def audit_hook(agent_task):
    """创建 AuditLogHook 实例"""
    hook = AuditLogHook(agent_task_id=str(agent_task.task_id))
    return hook


# ---------------------------------------------------------------------------
# 测试用例
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestAuditEventSubtaskCompleted:
    """测试 1: subtask.completed → AgentEvent 写入且 sequence 递增"""

    def test_subtask_completed_writes_agent_event_with_incrementing_sequence(
        self, audit_hook, agent_subtask
    ):
        """验证 subtask.completed 事件写入 AgentEvent,且 sequence 递增"""
        from smart_assistant.models import AgentEvent

        # 构造 mock event
        mock_event = MagicMock()
        mock_event.payload = {"tokens_used": 500, "duration_ms": 1200}

        # 调用 hook(同步包装)
        async_to_sync(audit_hook.on_subtask_completed)(mock_event, agent_subtask)

        # 验证 AgentEvent 写入(同步查询)
        events = list(AgentEvent.objects.filter(
            task__task_id=audit_hook.agent_task_id
        ).order_by("sequence"))
        assert len(events) == 1, f"应写入 1 条 AgentEvent,实际 {len(events)} 条"

        event = events[0]
        assert event.event_type == "subtask.completed"
        assert event.subtask == agent_subtask
        assert event.sequence == 1, f"第 1 个事件 sequence 应为 1,实际 {event.sequence}"
        assert event.payload == {"tokens_used": 500, "duration_ms": 1200}

        # 再调用一次,验证 sequence 递增
        mock_event_2 = MagicMock()
        mock_event_2.payload = {"tokens_used": 300, "duration_ms": 800}
        async_to_sync(audit_hook.on_subtask_completed)(mock_event_2, agent_subtask)

        events = list(AgentEvent.objects.filter(
            task__task_id=audit_hook.agent_task_id
        ).order_by("sequence"))
        assert len(events) == 2, f"应写入 2 条 AgentEvent,实际 {len(events)} 条"
        assert events[0].sequence == 1
        assert events[1].sequence == 2, f"第 2 个事件 sequence 应为 2,实际 {events[1].sequence}"


@pytest.mark.django_db
class TestAuditEventSubtaskFailed:
    """测试 2: subtask.failed → AgentEvent 写入且 payload 含 error"""

    def test_subtask_failed_writes_agent_event_with_error_in_payload(
        self, audit_hook, agent_subtask
    ):
        """验证 subtask.failed 事件写入 AgentEvent,且 payload 包含 error 信息"""
        from smart_assistant.models import AgentEvent

        # 构造 mock event(带 error 属性)
        mock_event = MagicMock()
        mock_event.payload = {"attempt": 1}
        mock_event.error = Exception("传感器 API 超时")

        # 调用 hook
        async_to_sync(audit_hook.on_subtask_failed)(mock_event, agent_subtask)

        # 验证 AgentEvent 写入
        events = list(AgentEvent.objects.filter(
            task__task_id=audit_hook.agent_task_id
        ).order_by("sequence"))
        assert len(events) == 1, f"应写入 1 条 AgentEvent,实际 {len(events)} 条"

        event = events[0]
        assert event.event_type == "subtask.failed"
        assert event.subtask == agent_subtask
        assert event.sequence == 1

        # 验证 payload 包含 error
        assert "error" in event.payload, "payload 应包含 error 字段"
        assert "传感器 API 超时" in event.payload["error"], (
            f"error 应包含异常信息,实际: {event.payload['error']}"
        )


@pytest.mark.django_db
class TestAuditEventSequenceContinuity:
    """测试 3: 完整任务的事件流 sequence 连续无重复"""

    def test_full_task_event_stream_has_continuous_sequence(
        self, audit_hook, agent_subtask, agent_task
    ):
        """验证完整任务生命周期中,所有 AgentEvent 的 sequence 连续递增无重复"""
        from smart_assistant.models import AgentEvent, AgentSubTask

        # 模拟完整任务生命周期
        mock_event = MagicMock()
        mock_event.payload = {}

        # 1. task.started
        async_to_sync(audit_hook.on_task_started)(mock_event)

        # 2. subtask.started
        async_to_sync(audit_hook.on_subtask_started)(mock_event, agent_subtask)

        # 3. subtask.completed
        mock_event.payload = {"tokens_used": 500}
        async_to_sync(audit_hook.on_subtask_completed)(mock_event, agent_subtask)

        # 4. 第二个 subtask.started
        subtask_2 = AgentSubTask.objects.create(
            task=agent_task,
            subtask_id="test_subtask_2",
            role="analyst",
            objective="第二个子任务",
            status="running",
        )
        async_to_sync(audit_hook.on_subtask_started)(mock_event, subtask_2)

        # 5. subtask.failed
        mock_event.payload = {"attempt": 1}
        mock_event.error = Exception("分析失败")
        async_to_sync(audit_hook.on_subtask_failed)(mock_event, subtask_2)

        # 6. task.completed
        mock_event.payload = {"status": "partial"}
        async_to_sync(audit_hook.on_task_completed)(mock_event)

        # 验证所有事件
        events = list(AgentEvent.objects.filter(
            task__task_id=audit_hook.agent_task_id
        ).order_by("sequence"))

        assert len(events) == 6, f"应有 6 条事件,实际 {len(events)} 条"

        # 验证 sequence 连续递增(1, 2, 3, 4, 5, 6)
        sequences = [e.sequence for e in events]
        expected_sequences = list(range(1, 7))
        assert sequences == expected_sequences, (
            f"sequence 应连续递增 {expected_sequences},实际 {sequences}"
        )

        # 验证无重复
        assert len(set(sequences)) == len(sequences), "sequence 不应有重复"

        # 验证事件类型顺序
        event_types = [e.event_type for e in events]
        expected_types = [
            "task.started",
            "subtask.started",
            "subtask.completed",
            "subtask.started",
            "subtask.failed",
            "task.completed",
        ]
        assert event_types == expected_types, (
            f"事件类型顺序应为 {expected_types},实际 {event_types}"
        )
