import base64
import os
import threading
import time
from unittest import mock

import pytest
from django.conf import settings
from django.core.cache import cache
from django.test.utils import override_settings

from smart_assistant.tools_io import (
    _sign,
    attachment_cache_key,
    cache_attachment,
    cleanup_expired_files,
    create_download_token,
    file_sha256,
    get_attachment,
    resolve_download_token,
    save_tmp_office_file,
)


def _make_token(relative_path: str, expiry: int) -> str:
    """按指定过期时间手工构造一个签名合法的 token（用于测试过期分支）。"""
    payload = base64.urlsafe_b64encode(f"{relative_path}:{expiry}".encode()).decode()
    return f"{payload}.{_sign(payload)}"


@pytest.fixture(autouse=True)
def _media_root(tmp_path):
    old = settings.MEDIA_ROOT
    settings.MEDIA_ROOT = str(tmp_path)
    yield
    settings.MEDIA_ROOT = old
    cache.clear()


class TestToolsIO:
    def test_file_sha256_stable(self):
        assert file_sha256(b"abc") == file_sha256(b"abc")
        assert file_sha256(b"abc") != file_sha256(b"abd")

    def test_attachment_cache_roundtrip(self):
        cache_attachment(1, "h1", {"text": "内容", "filename": "a.docx"})
        got = get_attachment(1, "h1")
        assert got["text"] == "内容"

    def test_attachment_cache_miss(self):
        assert get_attachment(999, "nope") is None

    def test_save_and_resolve_token(self):
        rel = save_tmp_office_file("测试.docx", b"bytes")
        assert rel.startswith("tmp_office/")
        full = os.path.join(settings.MEDIA_ROOT, rel)
        assert os.path.exists(full)
        token = create_download_token(rel)
        assert resolve_download_token(token) == rel
        # 一次性
        assert resolve_download_token(token) is None

    def test_resolve_bad_token_none(self):
        assert resolve_download_token("forged.token.value") is None

    def test_cleanup_expired_files(self):
        rel = save_tmp_office_file("过期.docx", b"old")
        full = os.path.join(settings.MEDIA_ROOT, rel)
        old = time.time() - 1200  # 20 分钟前
        os.utime(full, (old, old))
        cleaned = cleanup_expired_files()
        assert not os.path.exists(full)
        assert cleaned >= 1

    def test_token_expired_returns_none(self):
        """签名合法但已过期的 token 必须被拒绝。"""
        rel = save_tmp_office_file("过期token.docx", b"x")
        token = _make_token(rel, int(time.time()) - 1)  # 1 秒前过期
        assert resolve_download_token(token) is None

    def test_token_not_yet_expired_ok(self):
        """边界对照：仍在有效期内的手工 token 可正常解析。"""
        rel = save_tmp_office_file("有效token.docx", b"x")
        token = _make_token(rel, int(time.time()) + 60)
        assert resolve_download_token(token) == rel

    def test_token_signature_tampered_returns_none(self):
        """篡改签名末位字符后必须校验失败。"""
        rel = save_tmp_office_file("篡改.docx", b"x")
        token = create_download_token(rel)
        last = token[-1]
        flipped = "0" if last != "0" else "1"  # 保证确实改变了 1 个字符
        assert resolve_download_token(token[:-1] + flipped) is None

    def test_token_payload_tampered_returns_none(self):
        """篡改 payload（换成别的路径）在签名不变时必须失败。"""
        rel = save_tmp_office_file("原始.docx", b"x")
        token = create_download_token(rel)
        _, sig = token.rsplit(".", 1)
        evil = base64.urlsafe_b64encode(f"../../etc/passwd:{int(time.time()) + 600}".encode()).decode()
        assert resolve_download_token(f"{evil}.{sig}") is None

    def test_token_different_secret_returns_none(self):
        """SECRET_KEY 必须真正参与签名：换 key 后旧 token 失效。"""
        rel = save_tmp_office_file("换key.docx", b"x")
        token = create_download_token(rel)
        with override_settings(SECRET_KEY="另一个完全不同的密钥-for-test"):
            assert resolve_download_token(token) is None
        # 换回原 key 后仍可用，证明失效由 key 差异导致而非 token 本身损坏
        assert resolve_download_token(token) == rel

    def test_concurrent_replay_second_returns_none(self):
        """一次性保护：cache.add() 原子登记，第二次 resolve 必须被拒绝。"""
        rel = save_tmp_office_file("重放.docx", b"x")
        token = create_download_token(rel)
        assert resolve_download_token(token) == rel  # 首次成功
        assert resolve_download_token(token) is None  # 重放被拒
        assert resolve_download_token(token) is None  # 再次重放仍被拒

    def test_replay_rejected_even_with_fresh_equivalent_token(self):
        """同 payload 的等价 token 也被一次性记录挡住（防重复签名绕过）。"""
        rel = save_tmp_office_file("等价.docx", b"x")
        expiry = int(time.time()) + 600
        first = _make_token(rel, expiry)
        second = _make_token(rel, expiry)  # payload 完全相同 → 同一 used key
        assert first == second
        assert resolve_download_token(first) == rel
        assert resolve_download_token(second) is None

    def test_one_shot_uses_atomic_cache_add(self):
        """一次性保护必须走原子 cache.add()，不能退回 get-then-set。

        纯顺序测试无法观测竞态（旧的 get→set 实现同样能通过重放断言），
        因此这里直接断言用到的缓存原语：add 被调用、且不依赖 get 的判断结果。
        """
        rel = save_tmp_office_file("原子.docx", b"x")
        token = create_download_token(rel)
        calls = []
        real_add = cache.add

        def spy_add(key, value, timeout=None, **kwargs):
            calls.append(key)
            return real_add(key, value, timeout, **kwargs)

        # 让 get 恒返回 None：若实现依赖 get 判重（旧实现），重放将不再被拦截
        with mock.patch.object(cache, "add", side_effect=spy_add), mock.patch.object(cache, "get", return_value=None):
            assert resolve_download_token(token) == rel
            assert resolve_download_token(token) is None  # 仅 add 的原子性能挡住

        assert any(c.startswith("smart_assistant:office:used:") for c in calls), "未调用 cache.add 登记一次性 key"

    def test_concurrent_resolve_only_one_winner(self):
        """并发场景：多线程同时 resolve 同一 token，有且仅有一个拿到路径。"""
        rel = save_tmp_office_file("并发.docx", b"x")
        token = create_download_token(rel)
        barrier = threading.Barrier(8)
        results = []
        lock = threading.Lock()

        def worker():
            barrier.wait()  # 尽量让 8 个线程同时进入 resolve
            got = resolve_download_token(token)
            with lock:
                results.append(got)

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert results.count(rel) == 1, f"应恰好 1 个成功，实际 {results.count(rel)}"
        assert results.count(None) == 7
