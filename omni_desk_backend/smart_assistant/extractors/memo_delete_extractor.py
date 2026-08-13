"""smart_assistant.extractors.memo_delete_extractor — 备忘录删除的 LLM 提取器

LLM 解析"中文 query → DeleteParams",失败兜底为 None(由调用方
返回 found=False)。校验:target_title 必填。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date as date_cls

from .llm_helpers import call_extractor_llm, extract_json_block
from .prompts.memo_delete_prompt import MEMO_DELETE_SYSTEM_PROMPT, build_delete_user_prompt

from observability import get_logger

logger = get_logger(__name__, "smart_assistant")


@dataclass
class DeleteParams:
    """备忘录删除参数(从 query 提取)"""

    target_title: str


def _as_str(value) -> str | None:
    """字符串值归一化:非 str 返回 None,str 去空白后空串也返回 None。"""
    if not isinstance(value, str):
        return None
    s = value.strip()
    return s or None


def _call_delete_llm(query: str, today_str: str | None = None) -> str | None:
    """调用 LLM 抽取参数,失败兜底 None。today_str 供测试注入(默认今日)。"""
    if today_str is None:
        today_str = date_cls.today().isoformat()
    return call_extractor_llm(
        MEMO_DELETE_SYSTEM_PROMPT,
        build_delete_user_prompt(query, today_str),
    )


def extract_delete_params(query: str, today_str: str | None = None) -> DeleteParams | None:
    """从自然语言 query 抽取 DeleteParams。失败返回 None。"""
    raw = _call_delete_llm(query, today_str)
    if raw is None:
        return None

    json_text = extract_json_block(raw)
    if json_text is None:
        logger.debug("memo_delete_extractor 未能从 LLM 输出提取 JSON: %s", raw[:200])
        return None

    try:
        data = json.loads(json_text)
    except json.JSONDecodeError:
        logger.debug("memo_delete_extractor JSON 解析失败: %s", json_text[:200])
        return None

    target = _as_str(data.get("target_title"))
    if not target:
        return None

    return DeleteParams(target_title=target[:200])
