"""StreamRunner 模块轻量冒烟(R3-A1 Task 6)。"""

from smart_assistant.agent.stream_runner import StreamRunner


def test_stream_runner_is_importable():
    assert callable(StreamRunner)


def test_orchestrator_process_stream_is_generator():
    from smart_assistant.agent.orchestrator import AgentOrchestrator

    assert hasattr(AgentOrchestrator, "process_stream")


def test_stream_event_sanitizer_keeps_public_chunk_content():
    from smart_assistant.views.chat_stream import _sanitize_stream_event

    event = _sanitize_stream_event(
        {"type": "chunk", "content": "普通回答 alice@example.com token=secret"}
    )

    assert event["content"].startswith("普通回答")
    assert "alice@example.com" not in event["content"]
    assert "secret" not in event["content"]


def test_stream_event_sanitizer_keeps_fixed_failure_prefix():
    from smart_assistant.agent.conversation_context import FAILED_ANSWER_STREAM_PREFIX
    from smart_assistant.views.chat_stream import _sanitize_stream_event

    event = _sanitize_stream_event(
        {"type": "chunk", "content": f"{FAILED_ANSWER_STREAM_PREFIX}: 流式生成中断"}
    )

    assert event["content"].startswith(FAILED_ANSWER_STREAM_PREFIX)
    assert "流式生成中断" in event["content"]


def test_stream_event_sanitizer_does_not_expose_exception_fields():
    from smart_assistant.views.chat_stream import _sanitize_stream_event

    event = _sanitize_stream_event(
        {
            "type": "done",
            "error": True,
            "exception": "token=secret https://internal.example/a",
            "message": "authorization: Bearer raw-token",
        }
    )

    assert event["error"] is True
    assert "secret" not in str(event)
    assert "internal.example" not in str(event)
    assert "raw-token" not in str(event)
    assert "exception" not in event
    assert "message" not in event


def test_stream_event_sanitizer_uses_trusted_format_version_and_rejects_nested_values():
    from smart_assistant.agent.orchestrator import FORMAT_VERSION
    from smart_assistant.views.chat_stream import _sanitize_stream_event

    event = _sanitize_stream_event(
        {
            "type": "meta",
            "format_version": {
                "url": "https://internal.example/secret",
                "token": "nested-token",
            },
            "tool_result": {
                "nested": [{"authorization": "Bearer raw-token"}],
            },
        }
    )

    assert event["format_version"] == FORMAT_VERSION
    assert isinstance(event["format_version"], int)
    assert event["tool_result"] == {}
    assert "nested" not in event["tool_result"]
    assert "authorization" not in str(event["tool_result"])


def test_consume_stream_events_skips_non_string_type_and_processes_following_events():
    from smart_assistant.views.chat_stream import _consume_stream_events

    class Orchestrator:
        def process_stream(self, *args, **kwargs):
            yield 'data: {"type": ["done"], "format_version": 1}\n\n'
            yield 'data: {"type": "chunk", "content": "合法回答"}\n\n'
            yield 'data: {"type": "done", "error": false}\n\n'

    state = {
        "full_answer": [],
        "meta": {},
        "done_error": False,
        "done_seen": False,
        "stream_error_code": None,
        "stream_retry_after": None,
    }

    output = list(_consume_stream_events(state, Orchestrator(), "问题", [], None))

    assert len(output) == 2
    assert '"type": "chunk"' in output[0]
    assert '"type": "done"' in output[1]
    assert state["done_seen"] is True
    assert state["done_error"] is False
