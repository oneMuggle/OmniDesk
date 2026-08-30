"""AuditLogHook 生命周期行为测试。

AuditLogHook 仅负责工具级 AgentLog 审计；AgentEvent 由
PersistentEventBus 统一写入。因此生命周期方法保留公开接口，但不会自行
创建 AgentEvent，也不维护独立的内存 sequence。
"""

from unittest.mock import MagicMock

import pytest
from asgiref.sync import async_to_sync

from smart_assistant.hooks.builtin.audit_log import AuditLogHook


@pytest.fixture
def agent_task(db):
    """创建 AgentTask 实例。"""
    from smart_assistant.models import AgentTask
    from users.models import CustomUser
    import uuid

    user = CustomUser.objects.create_user(
        username="test_user_audit",
        email="audit_test@example.com",
        password="testpass123",
    )
    return AgentTask.objects.create(
        task_id=uuid.uuid4(),
        user=user,
        objective="测试任务",
        execution_mode="pipeline",
        status="running",
    )


@pytest.fixture
def agent_subtask(agent_task):
    """创建 AgentSubTask 实例。"""
    from smart_assistant.models import AgentSubTask

    return AgentSubTask.objects.create(
        task=agent_task,
        subtask_id="test_subtask_1",
        role="researcher",
        objective="测试子任务",
        status="running",
    )


@pytest.fixture
def audit_hook(agent_task):
    """创建带任务 ID 的 AuditLogHook。"""
    return AuditLogHook(agent_task_id=str(agent_task.task_id))


@pytest.mark.django_db
class TestAuditLogHookLifecycle:
    """生命周期接口不再直接持久化 AgentEvent。"""

    @pytest.mark.parametrize(
        "method_name,args",
        [
            ("on_task_started", ()),
            ("on_task_completed", ()),
            ("on_task_failed", ()),
        ],
    )
    def test_task_lifecycle_does_not_create_agent_event(
        self, audit_hook, agent_task, method_name, args
    ):
        from smart_assistant.models import AgentEvent

        event = MagicMock(payload={})
        async_to_sync(getattr(audit_hook, method_name))(event, *args)

        assert not AgentEvent.objects.filter(task=agent_task).exists()

    @pytest.mark.parametrize(
        "method_name",
        ["on_subtask_started", "on_subtask_completed", "on_subtask_failed"],
    )
    def test_subtask_lifecycle_does_not_create_agent_event(
        self, audit_hook, agent_task, agent_subtask, method_name
    ):
        from smart_assistant.models import AgentEvent

        event = MagicMock(payload={})
        async_to_sync(getattr(audit_hook, method_name))(event, agent_subtask)

        assert not AgentEvent.objects.filter(task=agent_task).exists()

    def test_hook_has_no_independent_sequence_state_or_reset_method(self, audit_hook):
        """AgentEvent 的 sequence 不再由 Hook 在内存中维护。"""
        assert not hasattr(audit_hook, "_sequence_counter")
        assert not hasattr(audit_hook, "reset_sequence")

    def test_lifecycle_methods_remain_public(self, audit_hook):
        """保留 executor 依赖的公开生命周期方法。"""
        assert all(
            callable(getattr(audit_hook, method_name))
            for method_name in (
                "on_subtask_started",
                "on_subtask_completed",
                "on_subtask_failed",
                "on_task_started",
                "on_task_completed",
                "on_task_failed",
            )
        )
