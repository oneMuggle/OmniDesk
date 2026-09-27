"""写工具的通用参数提取器（S3-1）。

走意图分类路径时，写工具只拿到用户原话；这里用 LLM 按字段说明抽取结构化参数。
原生函数调用路径已给出结构化参数，不会调用这里。失败返回 None。
"""

from __future__ import annotations

import json
from datetime import date as date_cls

from observability import get_logger

from .llm_helpers import call_extractor_llm, extract_json_block

logger = get_logger(__name__, "smart_assistant")


def build_system_prompt(task: str, fields: dict[str, str], today_str: str) -> str:
    lines = "\n".join(f"- {name}: {desc}" for name, desc in fields.items())
    return (
        f"你是参数提取器。从用户的中文请求中提取「{task}」所需的字段，只输出一个 JSON 对象，不要解释。\n"
        f"字段：\n{lines}\n"
        f"无法确定的字段填 null。今天是 {today_str}；时间一律用 YYYY-MM-DDTHH:MM 格式（本地时间）。"
    )


def extract_fields(query: str, *, task: str, fields: dict[str, str], today_str: str | None = None) -> dict | None:
    """返回只含 ``fields`` 中键的字典；LLM 不可用或输出无法解析时返回 None。"""
    if not (query or "").strip():
        return None
    today_str = today_str or date_cls.today().isoformat()
    raw = call_extractor_llm(build_system_prompt(task, fields, today_str), query)
    if not raw:
        return None
    block = extract_json_block(raw)
    if block is None:
        logger.debug("write_fields_extractor 未能从 LLM 输出提取 JSON: %s", raw[:200])
        return None
    try:
        data = json.loads(block)
    except json.JSONDecodeError:
        logger.debug("write_fields_extractor JSON 解析失败: %s", block[:200])
        return None
    if not isinstance(data, dict):
        return None
    return {key: data.get(key) for key in fields}
