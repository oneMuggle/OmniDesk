"""smart_assistant.extractors.memo_update_extractor — 备忘录修改的 LLM 提取器

LLM 解析"中文 query → UpdateParams",失败兜底为 None(由调用方
返回 found=False)。校验:target_title 必填、至少一个 new_* 字段有值。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date as date_cls

from .llm_helpers import call_extractor_llm, extract_json_block
from .prompts.memo_update_prompt import MEMO_UPDATE_SYSTEM_PROMPT, build_update_user_prompt

from observability import get_logger

logger = get_logger(__name__, "smart_assistant")


@dataclass
class UpdateParams:
    """备忘录修改参数(从 query 提取)"""

    target_title: str
    new_title: str | None = None
    new_content: str | None = None
    new_reminder_time: str | None = None  # ISO 8601 字符串


def _as_str(value) -> str | None:
    """字符串值归一化:非 str 返回 None,str 去空白后空串也返回 None。"""
    if not isinstance(value, str):
        return None
    s = value.strip()
    return s or None


def _call_update_llm(query: str, today_str: str | None = None) -> str | None:
    """调用 LLM 抽取参数,失败兜底 None。today_str 供测试注入(默认今日)。"""
    if today_str is None:
        today_str = date_cls.today().isoformat()
    return call_extractor_llm(
        MEMO_UPDATE_SYSTEM_PROMPT,
        build_update_user_prompt(query, today_str),
    )


def extract_update_params(query: str, today_str: str | None = None) -> UpdateParams | None:
    """从自然语言 query 抽取 UpdateParams。失败返回 None。"""
    raw = _call_update_llm(query, today_str)
    if raw is None:
        return None

    json_text = extract_json_block(raw)
    if json_text is None:
        logger.debug("memo_update_extractor 未能从 LLM 输出提取 JSON: %s", raw[:200])
        return None

    try:
        data = json.loads(json_text)
    except json.JSONDecodeError:
        logger.debug("memo_update_extractor JSON 解析失败: %s", json_text[:200])
        return None

    target = _as_str(data.get("target_title"))
    if not target:
        return None

    new_title = _as_str(data.get("new_title"))
    new_content = _as_str(data.get("new_content"))
    reminder = data.get("new_reminder_time")
    if reminder in (None, "", "null"):
        reminder = None
    new_reminder_time = reminder if isinstance(reminder, str) else None

    if new_title is None and new_content is None and new_reminder_time is None:
        return None  # 未指定任何修改

    return UpdateParams(
        target_title=target[:200],  # 防御性 truncate 到模型字段上限
        new_title=new_title[:200] if new_title else None,
        new_content=new_content,
        new_reminder_time=new_reminder_time,
    )
