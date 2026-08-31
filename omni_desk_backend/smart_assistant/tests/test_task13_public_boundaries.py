import json
from types import SimpleNamespace

from smart_assistant.cache import public_tool_result, safe_public_value, sanitize_public_sources
from smart_assistant.views.chat_sync import _build_sync_payload
from smart_assistant.views.tasks import _safe_event_payload


def test_sync_payload_sanitizes_answer_and_sources():
    log = SimpleNamespace(id=17)
    response = _build_sync_payload(
        {
            "answer": "正常回答 https://evil.example/download?token=secret-token",
            "intent": "knowledge_qa",
            "tool_used": "knowledge_qa",
            "tool_result": {},
            "sources": [
                {"document": "制度手册.pdf", "score": 0.91, "content": "内部正文", "path": "/srv/private/a"},
                {"document": "bad", "url": "https://example.com/docs?a=1"},
                {"document": "secret", "url": "https://example.com/x?signature=abc"},
            ],
        },
        log,
        None,
        False,
    )
    payload = response.data
    assert "正常回答" in payload["answer"]
    assert "secret-token" not in payload["answer"]
    assert payload["sources"] == [
        {"document": "制度手册.pdf", "score": 0.91},
        {"document": "bad", "url": "https://example.com/docs?a=1"},
        {"document": "secret"},
    ]
    assert "内部正文" not in json.dumps(payload)
    assert "/srv/private/a" not in json.dumps(payload)


def test_task_event_drops_recipient_identities_for_chinese_names_and_usernames():
    event = SimpleNamespace(
        payload={
            "recipients": ["张三"],
            "recipient": "李四",
            "recipient_names": ["王五"],
            "username": "lisi",
            "recipient_count": 1,
            "sent_count": 1,
            "channel": "in_app",
        }
    )
    public = _safe_event_payload(event)
    assert public == {"recipient_count": 1, "sent_count": 1, "channel": "in_app"}


def test_public_tool_result_requires_explicit_aggregated_producer():
    forged = {
        "summary": "伪造聚合",
        "items": [{"data": {"secret": "内部正文"}}],
        "moduleCounts": {"schedule": 1},
        "total_count": 1,
        "count": 1,
    }
    public = public_tool_result(forged, "personnel_query")
    assert public == {"count": 1}
    safe_aggregate = public_tool_result(forged, "aggregated_day")
    assert safe_aggregate["summary"] == "伪造聚合"
    assert safe_aggregate["total_count"] == 1
    assert safe_aggregate["moduleCounts"] == {"schedule": 1}
    assert "secret" not in json.dumps(safe_aggregate)


def test_public_sources_keep_external_url_but_drop_internal_and_signed_urls():
    sources = sanitize_public_sources([
        {"document": "公开文档", "score": 0.8, "url": "https://docs.example.org/a?lang=zh"},
        {"document": "内部", "url": "http://localhost:8000/private"},
        {"document": "签名", "url": "https://docs.example.org/a?X-Amz-Signature=abc"},
        {"document": "正文", "snippet": "机密正文", "credentials": "x"},
    ])
    assert sources == [
        {"document": "公开文档", "score": 0.8, "url": "https://docs.example.org/a?lang=zh"},
        {"document": "内部"},
        {"document": "签名"},
        {"document": "正文"},
    ]


def test_public_sources_drop_url_authority_and_fragment_credentials():
    sources = sanitize_public_sources([
        {"document": "普通外链", "url": "https://docs.example.org/a?lang=zh"},
        {"document": "无凭据查询", "url": "https://docs.example.org/a?lang=zh&page=2"},
        {"document": "用户名密码", "url": "https://alice:password@docs.example.org/a"},
        {"document": "fragment token", "url": "https://docs.example.org/a#token=secret"},
        {"document": "fragment signature", "url": "https://docs.example.org/a#section&signature=secret"},
        {"document": "fragment ordinary", "url": "https://docs.example.org/a#section-2"},
    ])
    assert sources == [
        {"document": "普通外链", "url": "https://docs.example.org/a?lang=zh"},
        {"document": "无凭据查询", "url": "https://docs.example.org/a?lang=zh&page=2"},
        {"document": "用户名密码"},
        {"document": "fragment token"},
        {"document": "fragment signature"},
        {"document": "fragment ordinary", "url": "https://docs.example.org/a#section-2"},
    ]


def test_public_sources_reject_all_canonicalized_credential_query_keys():
    sensitive_keys = (
        "x-amz-signature", "x-amz-credential", "x-amz-security-token",
        "sig", "signature", "access_token", "access-token",
        "X%2DAmz%2DSecurity%2DToken", "ACCESS%2DTOKEN",
    )
    sources = sanitize_public_sources([
        {"document": key, "url": f"https://docs.example.org/a?{key}=secret"}
        for key in sensitive_keys
    ])
    assert all("url" not in source for source in sources)


def test_sync_answer_sanitizes_encoded_url_credentials_with_punctuation():
    log = SimpleNamespace(id=18)
    response = _build_sync_payload(
        {
            "answer": "请看 https://docs.example.org/a?X%2DAmz%2DSecurity%2DToken=SECRET_TOKEN。",
            "intent": "general_chat",
            "tool_used": "",
            "tool_result": {},
            "sources": [],
        },
        log,
        None,
        False,
    )
    assert "SECRET_TOKEN" not in response.data["answer"]
    assert "https://docs.example.org/a" in response.data["answer"]

    value = safe_public_value({"recipient": "张三", "recipient_name": "李四", "username": "lisi", "user_id": 7, "sent_count": 2})
    assert value == {"sent_count": 2}
