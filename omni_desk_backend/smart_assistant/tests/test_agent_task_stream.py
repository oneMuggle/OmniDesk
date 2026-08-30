import uuid
import pytest
from unittest.mock import patch

from smart_assistant.models import AgentEvent, AgentTask


@pytest.mark.django_db
def test_task_stream_resumes_from_last_sequence_and_emits_done(api_client, regular_user_obj):
    task = AgentTask.objects.create(task_id=uuid.uuid4(), user=regular_user_obj, objective="继续任务")
    AgentEvent.objects.create(task=task, sequence=1, event_type="task.started", payload={})
    AgentEvent.objects.create(task=task, sequence=2, event_type="task.completed", payload={})
    task.status = "completed"
    task.save(update_fields=["status"])
    api_client.force_authenticate(regular_user_obj)

    response = api_client.get(f"/api/smart-assistant/tasks/{task.task_id}/stream/?last_seq=1")
    chunks = b"".join(response.streaming_content).decode()

    assert '"sequence": 2' in chunks
    assert "id: 2\n" in chunks
    assert '"format_version": 1' in chunks
    assert '"type": "done"' in chunks
    assert '"type": "timeout"' not in chunks
    assert '"sequence": 1' not in chunks


@pytest.mark.django_db
def test_task_stream_invalid_last_sequence_is_safe(api_client, regular_user_obj):
    task = AgentTask.objects.create(task_id=uuid.uuid4(), user=regular_user_obj, objective="边界")
    task.status = "completed"
    task.save(update_fields=["status"])
    api_client.force_authenticate(regular_user_obj)

    response = api_client.get(f"/api/smart-assistant/tasks/{task.task_id}/stream/?last_seq=not-a-number")
    chunks = b"".join(response.streaming_content).decode()

    assert '"type": "done"' in chunks
    assert '"type": "timeout"' not in chunks


@pytest.mark.django_db
def test_task_stream_timeout_contains_resume_sequence(api_client, regular_user_obj):
    task = AgentTask.objects.create(task_id=uuid.uuid4(), user=regular_user_obj, objective="等待")
    AgentEvent.objects.create(task=task, sequence=4, event_type="task.started", payload={})
    api_client.force_authenticate(regular_user_obj)

    with patch("smart_assistant.views.tasks.time.time", side_effect=[0, 61]):
        response = api_client.get(f"/api/smart-assistant/tasks/{task.task_id}/stream/?last_seq=4")
        chunks = b"".join(response.streaming_content).decode()

    assert '"type": "timeout"' in chunks
    assert '"sequence": 4' in chunks
    assert '"format_version": 1' in chunks
