"""smart_assistant.extractors.llm_helpers — extractor 共享 LLM 调用助手

封装三类 memo extractor(create/update/delete)共用的:
- LLM 路由调用(失败兜底 None)
- JSON 块提取(LLM 输出非纯 JSON 时用正则抓首个 {…} 块)

失败路径全部返回 None,由各 extractor 决定降级策略。
"""

from __future__ import annotations

import re

from observability import get_logger

logger = get_logger(__name__, "smart_assistant")


def call_extractor_llm(system_prompt: str, user_prompt: str) -> str | None:
    """调用 LLM 路由,失败返回 None(不抛异常)。"""
    try:
        from llm_service.router import get_router

        response, _usage = get_router(app_name="smart_assistant").generate(
            prompt=user_prompt,
            system_message=system_prompt,
            stream=False,
        )
        return response
    except Exception as e:
        logger.warning(
            "smart_assistant.llm_helpers.call_failed",
            extra={
                "event": "smart_assistant.llm_helpers.call_failed",
                "error": str(e),
            },
        )
        return None


def extract_json_block(text: str) -> str | None:
    """从 LLM 输出里用正则抓首个 {…} JSON 块,失败 None。"""
    match = re.search(r"\{[\s\S]*?\}", text)
    return match.group(0) if match else None
