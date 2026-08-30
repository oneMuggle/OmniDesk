"""PersistentEventBus 阶段 1 持久化测试。"""

import uuid
from unittest.mock import patch

import pytest

from smart_assistant.agents.dataclasses import PersistentEventBus
from smart_assistant.models import AgentEvent, AgentSubTask, AgentTask
from smart_assistant.agents.checkpoint import CheckpointManager
from smart_assistant.agents.packet import SubTask
from smart_assistant.agents.roles import AgentRole
from smart_assistant.agents.dataclasses import SubTaskResult
from users.models import CustomUser


@pytest.fixture
def agent_task(db):
    user = CustomUser.objects.create_user(
        username=f"persistent-event-{uuid.uuid4().hex[:8]}",
        password="testpass123",
    )
    return AgentTask.objects.create(
        task_id=uuid.uuid4(),
        user=user,
        objective="持久化测试",
        execution_mode="pipeline",
    )


@pytest.mark.django_db
def test_emit_keeps_memory_event_and_persists_subtask_foreign_key(agent_task):
    subtask = AgentSubTask.objects.create(
        task=agent_task,
        subtask_id="research",
        role="researcher",
        objective="检索",
    )
    bus = PersistentEventBus(agent_task_id=str(agent_task.task_id))

    bus.emit("subtask.completed", {"subtask_id": "research", "tokens_used": 12})

    memory_events = bus.get_events()
    persisted = AgentEvent.objects.get(task=agent_task)
    assert memory_events[0].event_type == "subtask.completed"
    assert memory_events[0].payload == {"subtask_id": "research", "tokens_used": 12}
    assert persisted.sequence == 1
    assert persisted.subtask == subtask
    assert persisted.payload == memory_events[0].payload
    assert bus.persistence_failure_count == 0


@pytest.mark.django_db
def test_emit_uses_max_existing_sequence_plus_one(agent_task):
    AgentEvent.objects.create(task=agent_task, sequence=4, event_type="task.started", payload={})
    bus = PersistentEventBus(agent_task_id=str(agent_task.task_id))

    bus.emit("task.completed", {"status": "success"})

    assert AgentEvent.objects.get(task=agent_task, sequence=5).event_type == "task.completed"


@pytest.mark.django_db
def test_emit_db_failure_does_not_interrupt_or_count_as_memory_failure(agent_task):
    bus = PersistentEventBus(agent_task_id=str(agent_task.task_id))
    with patch.object(AgentEvent.objects, "create", side_effect=RuntimeError("db unavailable")):
        bus.emit("task.started", {"task_id": str(agent_task.task_id)})

    assert [event.event_type for event in bus.get_events()] == ["task.started"]
    assert bus.persistence_failure_count == 1


@pytest.mark.django_db
def test_resume_claim_loss_does_not_persist_subtask(agent_task):
    from uuid import uuid4

    agent_task.status = "running"
    agent_task.resume_claim_id = uuid4()
    agent_task.save(update_fields=["status", "resume_claim_id", "updated_at"])
    subtask = SubTask(id="research", role=AgentRole.RESEARCHER, objective="检索")
    result = SubTaskResult(
        subtask_id="research", role=AgentRole.RESEARCHER, output={"new": "stale"},
        artifacts={"new": "stale"}, tokens_used=99,
    )

    persisted = CheckpointManager(str(agent_task.task_id)).persist_subtask(
        subtask, result, resume_claim_id=str(uuid4())
    )

    assert persisted is False
    assert not AgentSubTask.objects.filter(task=agent_task, subtask_id="research").exists()


@pytest.mark.django_db
def test_resume_claim_loss_event_stays_memory_only(agent_task):
    from uuid import uuid4

    agent_task.status = "running"
    agent_task.resume_claim_id = uuid4()
    agent_task.save(update_fields=["status", "resume_claim_id", "updated_at"])
    bus = PersistentEventBus(
        agent_task_id=str(agent_task.task_id), resume_claim_id=str(uuid4())
    )

    bus.emit("subtask.completed", {"subtask_id": "research", "output": "stale"})

    assert len(bus.get_events()) == 1
    assert not AgentEvent.objects.filter(task=agent_task).exists()
    assert bus.persistence_failure_count == 0


@pytest.mark.django_db
def test_emit_without_task_id_keeps_memory_event_and_counts_persistence_failure():
    bus = PersistentEventBus()

    bus.emit("task.started")

    assert len(bus.get_events()) == 1
    assert bus.persistence_failure_count == 1
