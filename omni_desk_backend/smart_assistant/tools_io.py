"""smart_assistant/tools_io.py — 附件上下文缓存 + 生成文档临时文件 + 签名下载 token

- 附件抽取结果按 (conversation_id, file_hash) 短时缓存（TTL 10 分钟），不入库。
- 生成的 .docx 写 MEDIA_ROOT/tmp_office/，返回相对路径；下载 token 为 HMAC
  签名（含过期时间），一次性使用。
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import time

from django.conf import settings
from django.core.cache import cache

from observability import get_logger

logger = get_logger(__name__, "smart_assistant")

ATTACHMENT_CACHE_TTL = 600  # 附件抽取结果缓存：10 分钟
DOWNLOAD_TOKEN_TTL = 600  # 下载 token 有效期：10 分钟
TMP_OFFICE_DIR = "tmp_office"  # 相对 MEDIA_ROOT
_CACHE_PREFIX = "smart_assistant:office:"


def file_sha256(data: bytes) -> str:
    """计算文件内容哈希（防重复抽取的缓存 key 之一）。"""
    return hashlib.sha256(data).hexdigest()[:32]  # nosec B324 — 非加密用途


def attachment_cache_key(conversation_id, file_hash: str) -> str:
    return f"{_CACHE_PREFIX}attach:{conversation_id}:{file_hash}"


def cache_attachment(conversation_id, file_hash: str, doc: dict) -> None:
    cache.set(attachment_cache_key(conversation_id, file_hash), doc, ATTACHMENT_CACHE_TTL)


def get_attachment(conversation_id, file_hash: str) -> dict | None:
    result = cache.get(attachment_cache_key(conversation_id, file_hash))
    return result  # type: ignore[no-any-return]


def _tmp_dir() -> str:
    root = getattr(settings, "MEDIA_ROOT", "") or ""
    path = os.path.join(root, TMP_OFFICE_DIR)
    os.makedirs(path, exist_ok=True)
    return path


def save_tmp_office_file(filename: str, content: bytes) -> str:
    """写临时文件到 MEDIA_ROOT/tmp_office/，返回相对路径（防重名加时间戳）。"""
    tmp_dir = _tmp_dir()  # 确保子目录存在
    safe = os.path.basename(filename)
    rel = os.path.join(TMP_OFFICE_DIR, f"{int(time.time())}_{secrets.token_hex(4)}_{safe}")
    full = os.path.join(tmp_dir, os.path.basename(rel))
    with open(full, "wb") as f:
        f.write(content)
    return rel


def create_download_token(relative_path: str) -> str:
    """生成签名下载 token：base64(payload).signature，payload 含相对路径+过期时间。"""
    expiry = int(time.time()) + DOWNLOAD_TOKEN_TTL
    payload = base64.urlsafe_b64encode(f"{relative_path}:{expiry}".encode()).decode()
    sig = _sign(payload)
    return f"{payload}.{sig}"


def _sign(payload: str) -> str:
    secret = settings.SECRET_KEY.encode()
    return hmac.new(secret, payload.encode(), hashlib.sha256).hexdigest()[:32]


def resolve_download_token(token: str) -> str | None:
    """解析并核验下载 token。一次性：成功后立即作废。返回相对路径或 None。"""
    try:
        payload, sig = token.rsplit(".", 1)
    except (ValueError, AttributeError):
        return None
    if not hmac.compare_digest(_sign(payload), sig):
        return None
    try:
        decoded = base64.urlsafe_b64decode(payload.encode()).decode()
        relative_path, expiry_str = decoded.rsplit(":", 1)
        if int(expiry_str) < int(time.time()):
            return None
    except (ValueError, UnicodeDecodeError):
        return None
    # 一次性：用 cache.add() 原子登记（仅当 key 不存在时才写入成功），
    # 避免 get-then-set 的竞态——并发请求会有且仅有一个 add 成功。
    used_key = f"{_CACHE_PREFIX}used:{payload}"
    if not cache.add(used_key, "1", DOWNLOAD_TOKEN_TTL):
        return None  # 已被使用（或并发请求已抢先）→ 拒绝
    return relative_path


def cleanup_expired_files() -> int:
    """删除 tmp_office 下超过 10 分钟未下载的文件。返回删除数。"""
    tmp = _tmp_dir()
    if not os.path.isdir(tmp):
        return 0
    cutoff = time.time() - DOWNLOAD_TOKEN_TTL
    removed = 0
    for name in os.listdir(tmp):
        full = os.path.join(tmp, name)
        try:
            if os.path.isfile(full) and os.path.getmtime(full) < cutoff:
                os.remove(full)
                removed += 1
        except OSError as exc:  # pragma: no cover — 竞态删除
            logger.warning("清理临时文件失败 %s: %s", full, exc)
    return removed
