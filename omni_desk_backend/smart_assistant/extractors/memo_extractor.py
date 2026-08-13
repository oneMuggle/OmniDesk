"""smart_assistant.extractors.memo_extractor — 备忘录创建的 LLM 提取器

LLM 解析"中文 query → CreateParams",失败兜底为 None(由调用方
返回 found=False,不降级到规则)。

鲁棒性:
- LLM 不可用 / 抛异常 → None
- LLM 返回非 JSON 文本 → 用正则提取首个 {…} 块再试
- 解析后必填字段(title)缺失 → None

参考 smart_assistant.extractors.swap_extractor 的同款 stub 接口。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date as date_cls

from .llm_helpers import call_extractor_llm, extract_json_block
from .prompts.memo_create_prompt import (
    MEMO_CREATE_SYSTEM_PROMPT,
    build_create_user_prompt,
)

from observability import get_logger

logger = get_logger(__name__, "smart_assistant")


@dataclass
class CreateParams:
    """备忘录创建参数(从 query 提取)"""

    title: str
    content: str = ""
    reminder_time: str | None = None  # ISO 8601 字符串


def _call_llm(query: str, today_str: str | None = None) -> str | None:
    """调用 LLM 抽取参数,失败兜底 None。today_str 供测试注入(默认今日)。"""
    if today_str is None:
        today_str = date_cls.today().isoformat()
    return call_extractor_llm(
        MEMO_CREATE_SYSTEM_PROMPT,
        build_create_user_prompt(query, today_str),
    )


def _extract_json_block(text: str) -> str | None:
    """兼容入口:委托 llm_helpers.extract_json_block。"""
    return extract_json_block(text)


def extract_create_params(query: str, today_str: str | None = None) -> CreateParams | None:
    """从自然语言 query 抽取 CreateParams。失败返回 None。

    Args:
        query: 用户的自然语言
        today_str: 可选 ISO 字符串(YYYY-MM-DD),供单测注入;
                  默认 None → _call_llm 内部用今日日期

    Returns:
        CreateParams | None
    """
    raw = _call_llm(query, today_str)
    if raw is None:
        return None

    json_text = _extract_json_block(raw)
    if json_text is None:
        logger.debug("memo_extractor 未能从 LLM 输出提取 JSON: %s", raw[:200])
        return None

    try:
        data = json.loads(json_text)
    except json.JSONDecodeError:
        logger.debug("memo_extractor JSON 解析失败: %s", json_text[:200])
        return None

    title = (data.get("title") or "").strip()
    if not title:
        return None

    reminder = data.get("reminder_time")
    if reminder in (None, "", "null"):
        reminder = None

    return CreateParams(
        title=title[:200],  # 防御性 truncate 到模型字段上限
        content=(data.get("content") or "").strip(),
        reminder_time=reminder if isinstance(reminder, str) else None,
    )
