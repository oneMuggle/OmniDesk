import pytest

from smart_assistant.agent.orchestrator_helpers import _dict_to_query, _scope_cache_sig


def test_dict_to_query_prefers_query_field():
    assert _dict_to_query({"query": "查张三", "department": "研发"}) == "查张三"


def test_dict_to_query_falls_back_to_key_value_when_no_query():
    result = _dict_to_query({"date_from": "2026-08-01", "limit": 3})
    assert "date_from: 2026-08-01" in result
    assert "limit: 3" in result


def test_dict_to_query_skips_none_and_query_key_in_fallback():
    result = _dict_to_query({"query": None, "name": "李四"})
    assert "query" not in result
    assert "name: 李四" in result


def test_dict_to_query_serializes_dict_values_as_json():
    result = _dict_to_query({"filters": {"a": 1}})
    assert "filters: {\"a\": 1}" in result


def test_dict_to_query_passthrough_string():
    assert _dict_to_query("直接字符串") == "直接字符串"


def test_scope_cache_sig_anonymous_when_no_context():
    assert _scope_cache_sig(None) == "anonymous"


def test_scope_cache_sig_anonymous_when_no_user():
    class Ctx:
        user = None
    assert _scope_cache_sig(Ctx()) == "anonymous"


def test_orchestrator_reexports_dict_to_query():
    # 兼容 test_orchestrator_tool_calls_path.py:798 的直接 import
    from smart_assistant.agent.orchestrator import _dict_to_query

    assert callable(_dict_to_query)
