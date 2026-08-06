import os
import time

import pytest
from django.conf import settings
from django.core.cache import cache

from smart_assistant.tools_io import (
    attachment_cache_key,
    cache_attachment,
    cleanup_expired_files,
    create_download_token,
    file_sha256,
    get_attachment,
    resolve_download_token,
    save_tmp_office_file,
)


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
