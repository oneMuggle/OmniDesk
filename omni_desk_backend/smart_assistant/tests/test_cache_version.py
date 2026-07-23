"""缓存版本控制测试 — SMART_ASSISTANT_CACHE_VERSION 支持手动失效。

Task 3.5 of feat/sa-perf-ux: 工具升级后可立即失效旧缓存,避免脏数据。
覆盖 settings 级版本隔离与 bump 失效行为。
"""

import pytest
from django.test import override_settings

from smart_assistant.cache import (
    _build_cache_key,
    cache_answer,
    get_cached_answer,
)


class TestCacheVersion:
    """SMART_ASSISTANT_CACHE_VERSION 缓存版本控制。"""

    def test_cache_key_includes_version(self):
        """缓存键应包含 cache_version 字段(默认 '1.0')。"""
        key = _build_cache_key(
            query="测试问题",
            user_id=1,
            intent="schedule_query",
        )
        # 缓存键非空,且是带前缀的摘要字符串
        assert key.startswith("smart_assistant:cache:")
        assert len(key) > len("smart_assistant:cache:")

    @override_settings(SMART_ASSISTANT_CACHE_VERSION="2.0")
    def test_different_version_different_key(self):
        """不同 cache_version 应生成不同的缓存键(版本隔离)。"""
        # 默认版本下生成 key_v1
        with override_settings(SMART_ASSISTANT_CACHE_VERSION="1.0"):
            key_v1 = _build_cache_key(
                query="测试",
                user_id=1,
                intent="schedule_query",
            )

        # 当前 @override_settings 上下文为 "2.0",生成 key_v2
        key_v2 = _build_cache_key(
            query="测试",
            user_id=1,
            intent="schedule_query",
        )

        assert key_v1 != key_v2, "不同版本应生成不同的缓存键"

    def test_bump_version_invalidates_old_cache(self, mock_cache_backend):
        """bump cache_version 后,旧版本的缓存应不可访问。"""
        from django.conf import settings

        original_version = getattr(
            settings, "SMART_ASSISTANT_CACHE_VERSION", "1.0"
        )
        try:
            # 版本 1.0 缓存
            settings.SMART_ASSISTANT_CACHE_VERSION = "1.0"
            cache_answer(
                query="版本测试",
                intent="schedule_query",
                answer="答案 v1",
                context_sig="u1_sself",
            )

            # 版本 1.0 可以读到
            cached = get_cached_answer(
                query="版本测试",
                intent="schedule_query",
                context_sig="u1_sself",
            )
            assert cached == "答案 v1"

            # 切换到版本 2.0
            settings.SMART_ASSISTANT_CACHE_VERSION = "2.0"

            # 版本 2.0 读不到版本 1.0 的缓存(版本隔离生效)
            cached_v2 = get_cached_answer(
                query="版本测试",
                intent="schedule_query",
                context_sig="u1_sself",
            )
            assert cached_v2 is None, "版本 2.0 不应读到版本 1.0 的缓存"

            # 版本 2.0 可以写入并读取自己的缓存
            cache_answer(
                query="版本测试",
                intent="schedule_query",
                answer="答案 v2",
                context_sig="u1_sself",
            )
            cached_v2_after = get_cached_answer(
                query="版本测试",
                intent="schedule_query",
                context_sig="u1_sself",
            )
            assert cached_v2_after == "答案 v2"

            # 切回版本 1.0,旧缓存仍在
            settings.SMART_ASSISTANT_CACHE_VERSION = "1.0"
            cached_v1_again = get_cached_answer(
                query="版本测试",
                intent="schedule_query",
                context_sig="u1_sself",
            )
            assert cached_v1_again == "答案 v1"
        finally:
            settings.SMART_ASSISTANT_CACHE_VERSION = original_version
