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
import re
from dataclasses import dataclass
from datetime import date as date_cls
from typing import Optional

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
    reminder_time: Optional[str] = None  # ISO 8601 字符串


def _call_llm(query: str) -> Optional[str]:
    """调用 LLM 抽取参数,失败兜底 None。

    注:stub 接口,生产代码接入 LLM 路由在 Task 3 dry_run 路径调用方注入;
    本单元测试直接 patch 此函数,无需 mock LLM 路由层。
    """
    try:
        from llm_service.router import get_router

        today_str = date_cls.today().isoformat()
        prompt = build_create_user_prompt(query, today_str)
        response, _usage = get_router(app_name="smart_assistant").generate(
            prompt=prompt,
            system_message=MEMO_CREATE_SYSTEM_PROMPT,
            stream=False,
        )
        return response
    except Exception as e:
        logger.warning("memo_extractor._call_llm 失败: %s", e)
        return None


def _extract_json_block(text: str) -> str | None:
    """从 LLM 输出里用正则抓首个 {…} JSON 块,失败 None。"""
    match = re.search(r"\{[\s\S]*?\}", text)
    return match.group(0) if match else None


def _call_llm_with_today(query: str, today_str: str) -> str | None:
    """测试注入 today_str 的入口(避免单测依赖 date.today)。"""
    try:
        from llm_service.router import get_router

        prompt = build_create_user_prompt(query, today_str)
        response, _usage = get_router(app_name="smart_assistant").generate(
            prompt=prompt,
            system_message=MEMO_CREATE_SYSTEM_PROMPT,
            stream=False,
        )
        return response
    except Exception as e:
        logger.warning("memo_extractor._call_llm_with_today 失败: %s", e)
        return None


def extract_create_params(query: str, today_str: str | None = None) -> CreateParams | None:
    """从自然语言 query 抽取 CreateParams。失败返回 None。

    Args:
        query: 用户的自然语言
        today_str: 可选 ISO 字符串(YYYY-MM-DD),供单测注入;
                  默认 None → _call_llm 内部用今日日期

    Returns:
        CreateParams | None
    """
    raw = _call_llm(query) if today_str is None else _call_llm_with_today(query, today_str)
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