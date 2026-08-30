"""confirmation draft 缓存单元测试(confirm-replay 框架 Phase A)。

覆盖:
- set/get 正常往返
- TTL 过期后 get 返回 None
- 不同 token 隔离
- clear 后 get 返回 None
- clear 不存在的 token 不抛异常
- cache key 隔离(draft 与业务缓存不冲突)
"""

import time
from unittest.mock import MagicMock, patch

import pytest

from smart_assistant.cache import (
    CONFIRMATION_DRAFT_TTL,
    _draft_key,
    clear_confirmation_draft,
    get_confirmation_draft,
    set_confirmation_draft,
)


@pytest.mark.django_db
class TestDraftKey:
    """_draft_key 内部 helper。"""

    def test_draft_key_deterministic(self):
        """同 token 产生相同 key"""
        assert _draft_key("abc") == _draft_key("abc")

    def test_draft_key_different_tokens_isolate(self):
        """不同 token 产生不同 key"""
        assert _draft_key("abc") != _draft_key("def")

    def test_draft_key_prefix_smart_assistant(self):
        """key 前缀符合全局缓存命名空间"""
        key = _draft_key("abc")
        assert key.startswith("smart_assistant:cache:")


@pytest.mark.django_db
class TestSetGetConfirmationDraft:
    """set/get 往返。"""

    def test_set_then_get_returns_draft(self):
        """set 后 get 返回同 draft"""
        draft = {
            "tool_name": "mock_tool",
            "user_query": "test query",
            "context_sig": "u1_sself",
            "draft": {"summary": "test", "fields": {"k": "v"}},
        }
        set_confirmation_draft("token-1", draft)

        assert get_confirmation_draft("token-1") == draft

    def test_get_nonexistent_token_returns_none(self):
        """不存在的 token → None"""
        assert get_confirmation_draft("never-existed") is None

    def test_set_overwrites_existing_draft(self):
        """同 token 重复 set → 新 draft 覆盖旧 draft"""
        set_confirmation_draft("token-2", {"v": 1})
        set_confirmation_draft("token-2", {"v": 2})

        assert get_confirmation_draft("token-2") == {"v": 2}

    def test_set_with_custom_ttl(self):
        """显式传 ttl 参数 → 使用自定义 TTL"""
        with patch("smart_assistant.cache.cache") as mock_cache:
            set_confirmation_draft("token-3", {"v": 1}, ttl=60)
            mock_cache.set.assert_called_once()
            _, _, ttl_arg = mock_cache.set.call_args[0]
            assert ttl_arg == 60

    def test_set_default_ttl_600(self):
        """默认 TTL = CONFIRMATION_DRAFT_TTL (600s)"""
        with patch("smart_assistant.cache.cache") as mock_cache:
            set_confirmation_draft("token-4", {"v": 1})
            mock_cache.set.assert_called_once()
            _, _, ttl_arg = mock_cache.set.call_args[0]
            assert ttl_arg == CONFIRMATION_DRAFT_TTL == 600


@pytest.mark.django_db
class TestClearConfirmationDraft:
    """clear 清理。"""

    def test_clear_then_get_returns_none(self):
        """set + clear + get → None"""
        set_confirmation_draft("token-5", {"v": 1})
        clear_confirmation_draft("token-5")

        assert get_confirmation_draft("token-5") is None

    def test_clear_nonexistent_token_no_error(self):
        """clear 不存在的 token 不抛异常"""
        # 应该静默
        clear_confirmation_draft("never-existed-2")

    def test_clear_calls_cache_delete_with_correct_key(self):
        """clear 内部调 cache.delete,key 与 set/get 一致"""
        with patch("smart_assistant.cache.cache") as mock_cache:
            clear_confirmation_draft("token-6")
            mock_cache.delete.assert_called_once_with(_draft_key("token-6"))


@pytest.mark.django_db
class TestDraftCacheIsolation:
    """缓存隔离:不同 token / 不同业务。"""

    def test_different_tokens_isolated(self):
        """不同 token 的 draft 相互隔离"""
        set_confirmation_draft("token-A", {"who": "A"})
        set_confirmation_draft("token-B", {"who": "B"})

        assert get_confirmation_draft("token-A") == {"who": "A"}
        assert get_confirmation_draft("token-B") == {"who": "B"}

    def test_consume_locmem_gets_and_deletes_once(self):
        from smart_assistant.cache import consume_confirmation_draft

        with patch("smart_assistant.cache.cache") as mock_cache:
            mock_cache._connections = {"default": MagicMock()}
            mock_cache._connections["default"].__class__.__module__ = (
                "django.core.cache.backends.locmem"
            )
            mock_cache.get.return_value = {"value": 1}
            assert consume_confirmation_draft("token-consume") == {"value": 1}
            mock_cache.get.assert_called_once_with(_draft_key("token-consume"))
            mock_cache.delete.assert_called_once_with(_draft_key("token-consume"))

    def test_locmem_repeated_consume_has_at_most_one_success(self):
        from smart_assistant.cache import consume_confirmation_draft

        backend = MagicMock()
        backend.__class__.__module__ = "django.core.cache.backends.locmem"
        values = [{"value": 1}, None]
        backend_get = lambda key: values.pop(0)
        with patch("smart_assistant.cache.cache") as mock_cache:
            mock_cache._connections = {"default": backend}
            mock_cache.get.side_effect = backend_get
            assert consume_confirmation_draft("token-repeat") == {"value": 1}
            assert consume_confirmation_draft("token-repeat") is None
            assert mock_cache.delete.call_count == 1

    def test_unknown_backend_fails_closed(self):
        from smart_assistant.cache import ConfirmationDraftConsumeError, consume_confirmation_draft

        with patch("smart_assistant.cache.cache") as mock_cache:
            mock_cache._connections = {"default": MagicMock()}
            mock_cache._connections["default"].__class__.__module__ = "custom.cache"
            with pytest.raises(ConfirmationDraftConsumeError) as exc_info:
                consume_confirmation_draft("token-unknown")
            assert exc_info.value.failure_kind == "unsupported_backend"
            mock_cache.get.assert_not_called()
            mock_cache.delete.assert_not_called()

    def test_redis_backend_uses_lock_before_get_and_delete(self):
        from smart_assistant.cache import consume_confirmation_draft

        events = []
        lock = MagicMock()
        lock.__enter__.side_effect = lambda: events.append("lock-enter") or lock
        lock.__exit__.side_effect = lambda *args: events.append("lock-exit")
        backend = MagicMock()
        backend.__class__.__module__ = "django_redis.cache"
        backend.lock.side_effect = lambda *args, **kwargs: events.append("lock") or lock
        backend.get.side_effect = lambda key: events.append("get") or {"value": 1}
        backend.delete.side_effect = lambda key: events.append("delete")

        with patch("smart_assistant.cache.cache") as mock_cache:
            mock_cache._connections = {"default": backend}
            assert consume_confirmation_draft("token-redis") == {"value": 1}

        assert events == ["lock", "lock-enter", "get", "delete", "lock-exit"]

    def test_cache_lock_failure_is_not_treated_as_replay(self):
        from smart_assistant.cache import ConfirmationDraftConsumeError, consume_confirmation_draft

        backend = MagicMock()
        backend.__class__.__module__ = "django_redis.cache"
        backend.lock.side_effect = TimeoutError("lock unavailable")
        with patch("smart_assistant.cache.cache") as mock_cache:
            mock_cache._connections = {"default": backend}
            with pytest.raises(ConfirmationDraftConsumeError) as exc_info:
                consume_confirmation_draft("token-lock-error")
            assert exc_info.value.failure_kind == "backend_failure"
            backend.get.assert_not_called()
            backend.delete.assert_not_called()

    def test_draft_key_uses_cache_version(self):
        """draft key 包含 CACHE_VERSION,bump 后旧 draft 自动失效(同 token 不同 key)"""
        from smart_assistant import cache as cache_module

        original_version = cache_module.CACHE_VERSION
        try:
            key_v1 = _draft_key("token-X")
            cache_module.bump_cache_version()
            key_v2 = _draft_key("token-X")

            assert key_v1 != key_v2  # 版本变化 → key 变化 → 旧 draft 不可达
        finally:
            cache_module.CACHE_VERSION = original_version
