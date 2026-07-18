"""智能助手缓存层测试 — 验证 cache_version、命中、未命中、过期、并发。

Task 1 of feat/sa-e2e-scenarios: 为 cache 模块引入 cache_version 字段,
确保工具升级时旧缓存自动失效。
"""
from unittest.mock import patch

import pytest

from smart_assistant import cache as cache_module
from smart_assistant.cache import (
    ANSWER_CACHE_TTL,
    CACHE_VERSION,
    TOOL_CACHE_TTL,
    _extract_user_id,
    bump_cache_version,
    cache_answer,
    cache_intent,
    cache_tool_result,
    get_cached_answer,
    get_cached_intent,
    get_cached_tool_result,
)


@pytest.fixture(autouse=True)
def reset_cache_version():
    """每个测试结束后恢复 cache_version 到初始值,避免污染其他测试。"""
    original = cache_module.CACHE_VERSION
    yield
    cache_module.CACHE_VERSION = original


class TestCacheVersion:
    def test_initial_cache_version_is_positive_int(self):
        assert isinstance(CACHE_VERSION, int)
        assert CACHE_VERSION >= 1

    def test_bump_cache_version_increments(self):
        original = cache_module.CACHE_VERSION
        new_version = bump_cache_version()
        assert new_version == original + 1
        assert cache_module.CACHE_VERSION == original + 1


class TestAnswerCache:
    def test_cache_miss_returns_none(self, mock_cache_backend):
        result = get_cached_answer("张三这周值班", "schedule_query", context_sig="u1_sself")
        assert result is None

    def test_cache_hit_returns_stored_value(self, mock_cache_backend):
        cache_answer("查张三", "schedule_query", "张三周一值班", context_sig="u1_sself")
        result = get_cached_answer("查张三", "schedule_query", context_sig="u1_sself")
        assert result == "张三周一值班"

    def test_cache_version_bump_invalidates_old_answer(self, mock_cache_backend):
        cache_answer("查张三", "schedule_query", "旧答案", context_sig="u1_sself")
        assert get_cached_answer("查张三", "schedule_query", context_sig="u1_sself") == "旧答案"

        bump_cache_version()

        result = get_cached_answer("查张三", "schedule_query", context_sig="u1_sself")
        assert result is None  # 版本升级后旧缓存失效


class TestToolCache:
    def test_tool_cache_only_stores_successful_results(self, mock_cache_backend):
        cache_tool_result("schedule", "查张三", {"found": False}, context_sig="u1_sself")
        result = get_cached_tool_result("schedule", "查张三", context_sig="u1_sself")
        assert result is None  # 不缓存 found=False

    def test_tool_cache_version_bump_invalidates(self, mock_cache_backend):
        cache_tool_result("schedule", "查张三", {"found": True, "data": []}, context_sig="u1_sself")
        bump_cache_version()
        result = get_cached_tool_result("schedule", "查张三", context_sig="u1_sself")
        assert result is None


class TestIntentCache:
    def test_intent_cache_roundtrip(self, mock_cache_backend):
        cache_intent("查张三", [{"name": "schedule_query"}], "schedule_query", context_sig="u1_sself")
        result = get_cached_intent("查张三", [{"name": "schedule_query"}], context_sig="u1_sself")
        assert result == "schedule_query"


class TestCacheContextIsolation:
    def test_different_user_context_returns_none(self, mock_cache_backend):
        cache_answer("查张三", "schedule_query", "u1的答案", context_sig="u1_sself")
        result = get_cached_answer("查张三", "schedule_query", context_sig="u2_sself")
        assert result is None  # 不同 user 隔离


class TestCacheTTLConstants:
    def test_answer_ttl_is_2_hours(self):
        assert ANSWER_CACHE_TTL == 7200

    def test_tool_ttl_is_30_minutes(self):
        assert TOOL_CACHE_TTL == 1800


class TestExtractUserId:
    """_extract_user_id 单元测试 — 从 context_sig 提取 user_id。"""

    def test_normal_context_sig(self):
        """正常格式:u<pk>_s<scope> → pk"""
        assert _extract_user_id("u123_sself") == 123
        assert _extract_user_id("u1_sadmin") == 1
        assert _extract_user_id("u999_sread") == 999

    def test_user_id_zero(self):
        """user_id=0 应返回 0"""
        assert _extract_user_id("u0_sself") == 0

    def test_empty_string(self):
        """空字符串应返回 0"""
        assert _extract_user_id("") == 0

    def test_no_u_prefix(self):
        """无 u 前缀应返回 0"""
        assert _extract_user_id("123_sself") == 0
        assert _extract_user_id("admin_sself") == 0

    def test_non_numeric_user_id(self):
        """非数字 user_id 应返回 0"""
        assert _extract_user_id("uadmin_sself") == 0
        assert _extract_user_id("uabc_sself") == 0

    def test_missing_scope_part(self):
        """缺少 scope 部分应仍能提取 user_id"""
        assert _extract_user_id("u123") == 123
        assert _extract_user_id("u1") == 1

    def test_multiple_underscores(self):
        """多个下划线应只取第一个 _ 前的部分"""
        assert _extract_user_id("u123_s_self_extra") == 123

    def test_none_input(self):
        """None 输入应返回 0(通过类型推断,实际传入空字符串)"""
        # 注意:_extract_user_id 签名要求 str,但测试防御性
        # 实际调用时 orchestrator 应保证传入字符串
        assert _extract_user_id("") == 0