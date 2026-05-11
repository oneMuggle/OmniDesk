"""离线缓存模块 — 使用本地 JSON 文件缓存 API 数据"""
import json
import os
from datetime import datetime
from typing import Optional

CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", ".cache")
CACHE_TTL_SECONDS = 3600  # 缓存有效期 1 小时


def _cache_file(key: str) -> str:
    os.makedirs(CACHE_DIR, exist_ok=True)
    safe_key = key.replace("/", "_").replace(":", "_")
    return os.path.join(CACHE_DIR, f"{safe_key}.json")


def save(key: str, data: dict):
    """将数据写入缓存，附带时间戳"""
    path = _cache_file(key)
    payload = {
        "cached_at": datetime.now().isoformat(),
        "data": data,
    }
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    except OSError as e:
        print(f"Cache write failed: {e}")


def load(key: str) -> Optional[dict]:
    """
    从缓存读取数据。
    如果缓存过期或不存在，返回 None。
    """
    path = _cache_file(key)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        cached_at = datetime.fromisoformat(payload["cached_at"])
        age = (datetime.now() - cached_at).total_seconds()
        if age > CACHE_TTL_SECONDS:
            os.remove(path)
            return None
        return payload["data"]
    except (OSError, json.JSONDecodeError, KeyError, ValueError):
        return None


def clear(key: str = None):
    """清除缓存。key 为 None 时清除全部"""
    if not os.path.exists(CACHE_DIR):
        return
    if key:
        path = _cache_file(key)
        if os.path.exists(path):
            os.remove(path)
    else:
        for fname in os.listdir(CACHE_DIR):
            os.remove(os.path.join(CACHE_DIR, fname))
