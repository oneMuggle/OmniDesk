"""确认卡片预览（S3-1）。

写工具在 dry_run 阶段调用 ``build_preview`` 生成 ``draft["preview"]``。预览必须由
服务端根据数据库记录生成，**不能拼接用户原话**；公开给前端前再经
``public_preview`` 做字段白名单与长度截断。
"""

from __future__ import annotations

from typing import Any

MAX_TEXT = 120
MAX_CHANGES = 10
MAX_ITEMS = 5

PERMISSION_SELF = "本人"


def _text(value: Any, limit: int = MAX_TEXT) -> str:
    from smart_assistant.cache import sanitize_public_text

    if value is None or value == "":
        return "—"
    return sanitize_public_text(str(value), limit)[:limit]


def change(field: str, label: str, before: Any, after: Any) -> dict:
    """一项字段变化。``before`` 为 None 表示新建。"""
    return {"field": field, "label": label, "before": before, "after": after}


def build_preview(
    *,
    action: str,
    target_type: str,
    target_label: str,
    changes: list[dict] | None = None,
    affected_count: int = 1,
    affected_label: str = "条",
    permission_source: str = PERMISSION_SELF,
    reversible: bool = True,
    risk: str = "write",
    items: list[str] | None = None,
    warnings: list[str] | None = None,
) -> dict:
    """生成服务端预览（存入 draft，尚未公开过滤）。

    ``warnings``：需要用户在确认前留意、但不阻止确认的提示（如时段冲突、草稿不会通知）。
    """
    return {
        "action": action,
        "target": {"type": target_type, "label": target_label},
        "changes": list(changes or []),
        "affected_count": int(affected_count),
        "affected_label": affected_label,
        "permission_source": permission_source,
        "reversible": bool(reversible),
        "risk": risk,
        "items": list(items or []),
        "warnings": list(warnings or []),
    }


def public_preview(preview: Any) -> dict | None:
    """把服务端预览转为公开结构：只保留白名单字段，文本脱敏并截断。"""
    if not isinstance(preview, dict):
        return None
    target = preview.get("target") if isinstance(preview.get("target"), dict) else {}
    changes = []
    for item in (preview.get("changes") or [])[:MAX_CHANGES]:
        if not isinstance(item, dict):
            continue
        changes.append(
            {
                "field": _text(item.get("field"), 40),
                "label": _text(item.get("label"), 40),
                "before": None if item.get("before") is None else _text(item.get("before")),
                "after": None if item.get("after") is None else _text(item.get("after")),
            }
        )
    try:
        affected = max(int(preview.get("affected_count") or 0), 0)
    except (TypeError, ValueError):
        affected = 0
    risk = preview.get("risk") if preview.get("risk") in {"write", "destructive"} else "write"
    return {
        "action": _text(preview.get("action"), 40),
        "target": {"type": _text(target.get("type"), 40), "label": _text(target.get("label"))},
        "changes": changes,
        "affected_count": affected,
        "affected_label": _text(preview.get("affected_label") or "条", 20),
        "permission_source": _text(preview.get("permission_source"), 60),
        "reversible": bool(preview.get("reversible")),
        "risk": risk,
        "items": [_text(item) for item in (preview.get("items") or [])[:MAX_ITEMS]],
        "warnings": [_text(item) for item in (preview.get("warnings") or [])[:MAX_ITEMS] if item],
    }


def preview_summary(public: dict) -> str:
    """由公开预览生成一句话摘要（卡片标题 / 旧客户端的 answer）。"""
    count = public.get("affected_count") or 0
    suffix = f"（{count} {public.get('affected_label') or '条'}）" if count > 1 else ""
    return f"待确认：{public['action']} · {public['target']['label']}{suffix}"[:180]
