import uuid
import pytest
from unittest.mock import patch

from smart_assistant.models import AgentEvent, AgentTask
from smart_assistant.views.tasks import _sanitize_value


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
def test_task_stream_and_timeline_are_isolated_by_user(api_client, regular_user_obj, admin_user_obj):
    task = AgentTask.objects.create(task_id=uuid.uuid4(), user=admin_user_obj, objective="私有任务")
    api_client.force_authenticate(regular_user_obj)

    stream = api_client.get(f"/api/smart-assistant/tasks/{task.task_id}/stream/")
    timeline = api_client.get(f"/api/smart-assistant/tasks/{task.task_id}/timeline/")

    assert stream.status_code == 404
    assert timeline.status_code == 404


@pytest.mark.django_db
def test_task_stream_clamps_negative_and_oversized_last_sequence(api_client, regular_user_obj):
    task = AgentTask.objects.create(task_id=uuid.uuid4(), user=regular_user_obj, objective="边界")
    AgentEvent.objects.create(task=task, sequence=1, event_type="task.started", payload={})
    task.status = "completed"
    task.save(update_fields=["status"])
    api_client.force_authenticate(regular_user_obj)

    negative = api_client.get(f"/api/smart-assistant/tasks/{task.task_id}/stream/?last_seq=-9")
    oversized = api_client.get(f"/api/smart-assistant/tasks/{task.task_id}/stream/?last_seq=999999999999999999999")

    negative_body = b"".join(negative.streaming_content).decode()
    oversized_body = b"".join(oversized.streaming_content).decode()
    assert '"sequence": 1' in negative_body
    assert '"type": "done"' in oversized_body
    assert '"type": "timeout"' not in negative_body + oversized_body


def test_nested_sanitizer_redacts_pii_and_sensitive_keys():
    value = {"content": "联系 a@example.com 或 13812345678", "result": {"api_key": "secret", "nested": {"id": "110105199001011234"}, "visible": "ok"}}

    sanitized = _sanitize_value(value)

    assert "a@example.com" not in str(sanitized)
    assert "13812345678" not in str(sanitized)
    assert "110105199001011234" not in str(sanitized)
    assert "api_key" not in sanitized["result"]
    assert sanitized["result"]["visible"] == "ok"

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
