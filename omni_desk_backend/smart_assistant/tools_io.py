"""smart_assistant/tools_io.py — 附件上下文缓存 + 生成文档临时文件 + 签名下载 token

- 附件抽取结果按 (conversation_id, file_hash) 短时缓存（TTL 10 分钟），不入库。
- 生成的 .docx 写 MEDIA_ROOT/tmp_office/，返回相对路径；下载 token 为 HMAC
  签名（含用户 ID、过期时间），一次性使用，仅签发者本人可下载。
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import time
from pathlib import Path

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


def _tmp_dir() -> Path:
    root = getattr(settings, "MEDIA_ROOT", "") or ""
    path = Path(root) / TMP_OFFICE_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path


def _safe_join_under_tmp(relative_path: str) -> Path | None:
    """把文件名解析到绝对路径，并校验必须落在 MEDIA_ROOT/tmp_office/ 下。

    严格只接受 basename（不含 / 或 \\ 前缀；不含 .. 段）。
    返回 None 表示路径逃逸或解析失败（应作为拒绝）。
    """
    if not isinstance(relative_path, str) or not relative_path:
        return None
    if os.path.isabs(relative_path) or "/" in relative_path or "\\" in relative_path:
        return None  # 绝对路径或含分隔符都视为越权契约
    base = _tmp_dir().resolve()
    candidate = (base / relative_path).resolve()
    try:
        candidate.relative_to(base)
    except ValueError:
        return None
    return candidate


def save_tmp_office_file(filename: str, content: bytes) -> str:
    """写临时文件到 MEDIA_ROOT/tmp_office/，返回文件名（防重名加时间戳）。

    返回值是 _tmp_dir() 下的 basename，不含 TMP_OFFICE_DIR 前缀，
    与 _safe_join_under_tmp 的 base（= _tmp_dir()）配套——避免双重前缀。
    """
    tmp_dir = _tmp_dir()  # 确保子目录存在
    safe = os.path.basename(filename)
    name = f"{int(time.time())}_{secrets.token_hex(4)}_{safe}"
    full = tmp_dir / name
    with open(full, "wb") as f:
        f.write(content)
    return name  # 仅文件名；_safe_join_under_tmp(name) → MEDIA_ROOT/tmp_office/<name>


def _pack_payload(relative_path: str, user_id: int | str, expiry: int) -> str:
    """打包 token payload：path\\x1fuser_id\\x1fexpiry（用 ASCII 单元分隔符避免路径内冒号歧义）。"""
    raw = f"{relative_path}\x1f{user_id}\x1f{expiry}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def _unpack_payload(payload: str) -> tuple[str, int | str, int] | None:
    """反向解包；任何格式异常返回 None。user_id 若可解析为 int 则还原为 int。"""
    try:
        decoded = base64.urlsafe_b64decode(payload.encode()).decode()
        relative_path, user_id_str, expiry_str = decoded.rsplit("\x1f", 2)
        try:
            user_id: int | str = int(user_id_str)
        except ValueError:
            user_id = user_id_str
        return relative_path, user_id, int(expiry_str)
    except (ValueError, UnicodeDecodeError):
        return None


def create_download_token(relative_path: str, user_id: int | str | None) -> str:
    """生成签名下载 token：base64(payload).signature，payload 含相对路径+用户 ID+过期时间。

    user_id 为 None 时抛 ValueError——下游不允许为匿名/未登录用户签发。
    """
    if user_id is None:
        raise ValueError("create_download_token requires a non-None user_id")
    expiry = int(time.time()) + DOWNLOAD_TOKEN_TTL
    payload = _pack_payload(relative_path, user_id, expiry)
    sig = _sign(payload)
    return f"{payload}.{sig}"


def _sign(payload: str) -> str:
    secret = settings.SECRET_KEY.encode()
    return hmac.new(secret, payload.encode(), hashlib.sha256).hexdigest()[:32]


def resolve_download_token(token: str, current_user_id: int | str | None) -> tuple[str, int | str] | None:
    """解析并核验下载 token。一次性：成功后立即作废。

    返回 (relative_path, owner_user_id) 或 None。

    必须传入当前用户 ID；token 内 owner 与 current_user_id 不一致时直接拒绝，
    防止 A 用户的 token 被 B 用户复用下载。
    """
    try:
        payload, sig = token.rsplit(".", 1)
    except (ValueError, AttributeError):
        return None
    if not hmac.compare_digest(_sign(payload), sig):
        return None
    unpacked = _unpack_payload(payload)
    if unpacked is None:
        return None
    relative_path, owner_user_id, expiry = unpacked
    if expiry < int(time.time()):
        return None
    if current_user_id is None or str(owner_user_id) != str(current_user_id):
        return None
    # 一次性：用 cache.add() 原子登记（仅当 key 不存在时才写入成功），
    # 避免 get-then-set 的竞态——并发请求会有且仅有一个 add 成功。
    used_key = f"{_CACHE_PREFIX}used:{payload}"
    if not cache.add(used_key, "1", DOWNLOAD_TOKEN_TTL):
        return None  # 已被使用（或并发请求已抢先）→ 拒绝
    return relative_path, owner_user_id


def cleanup_expired_files() -> int:
    """删除 tmp_office 下超过 10 分钟未下载的文件。返回删除数。"""
    tmp = _tmp_dir()
    if not tmp.is_dir():
        return 0
    cutoff = time.time() - DOWNLOAD_TOKEN_TTL
    removed = 0
    for name in os.listdir(tmp):
        full = tmp / name
        try:
            if full.is_file() and full.stat().st_mtime < cutoff:
                full.unlink()
                removed += 1
        except OSError as exc:  # pragma: no cover — 竞态删除
            logger.warning("清理临时文件失败 %s: %s", full, exc)
    return removed
