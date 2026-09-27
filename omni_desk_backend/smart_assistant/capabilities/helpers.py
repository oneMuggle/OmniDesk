"""各 app 声明工具时可复用的小工具函数。"""

from __future__ import annotations

from typing import Any


def context_user(context: Any) -> Any | None:
    """从 ToolContext 或旧路径 dict 上下文中取出已登录用户；取不到返回 ``None``。

    新工具一律 fail-closed：拿不到服务端用户就不查询任何数据。
    """
    if context is None:
        return None
    user = context.get("user") if isinstance(context, dict) else getattr(context, "user", None)
    if user is None or not getattr(user, "is_authenticated", False):
        return None
    return user


def tool_params(params: Any) -> dict:
    """原生工具调用路径传入 dict；旧意图路径为 ``None``。统一成 dict。"""
    return params if isinstance(params, dict) else {}


def clamp_limit(value: Any, default: int = 10, maximum: int = 20) -> int:
    """把 LLM 给出的 ``limit`` 规范到 ``[1, maximum]``，非法值回退默认值。"""
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(1, min(number, maximum))


def truncate(text: str | None, length: int = 200) -> str:
    text = text or ""
    return text[:length] + ("..." if len(text) > length else "")
