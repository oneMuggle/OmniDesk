import pytest

from smart_assistant.agent.sse_contract import (
    ERROR_KIND_HINTS,
    FORMAT_VERSION,
    annotate_error_kind,
    classify_error_kind,
    sse_event,
)


def test_sse_event_carries_format_version_and_frame():
    raw = sse_event({"type": "done", "error": False})
    assert raw.startswith("data: ")
    assert raw.endswith("\n\n")
    assert f'"format_version": {FORMAT_VERSION}' in raw


def test_sse_event_keeps_ensure_ascii_false():
    raw = sse_event({"type": "chunk", "content": "中文回答"})
    assert "中文回答" in raw


def test_classify_error_kind_none_for_success():
    assert classify_error_kind({"error": False, "answer": "ok"}) is None


@pytest.mark.django_db
def test_classify_error_kind_internal_error_fallback():
    kind = classify_error_kind({"error": True, "answer": "某失败", "tool_used": None})
    assert kind in ERROR_KIND_HINTS


@pytest.mark.django_db
def test_annotate_error_kind_adds_hint():
    payload = annotate_error_kind({}, "某失败", tool_used="memo")
    assert "kind" in payload
    assert "hint" in payload
    assert payload["hint"] == ERROR_KIND_HINTS.get(payload["kind"])


def test_orchestrator_reexports_sse_contract_symbols():
    # 外部消费者(views/chat.py, test_doctor.py)仍从 orchestrator import
    from smart_assistant.agent.orchestrator import (
        ERROR_KIND_HINTS,
        FORMAT_VERSION,
        annotate_error_kind,
        classify_error_kind,
        sse_event,
    )

    assert FORMAT_VERSION == 1
    assert "no_llm_endpoint" in ERROR_KIND_HINTS
    assert callable(sse_event)
    assert callable(classify_error_kind)
    assert callable(annotate_error_kind)
