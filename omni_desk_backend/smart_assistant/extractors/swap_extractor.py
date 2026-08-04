"""smart_assistant.extractors.swap_extractor — 换班查询的 LLM 提取器

LLM 解析"中文 query → CreateParams / DecideParams",失败兜底为 None(由调用方
返回 found=False,不降级到规则)。

鲁棒性:
- LLM 不可用 / 抛异常 → None
- LLM 返回非 JSON 文本 → 用正则提取首个 {…} 块再试
- 解析后字段缺失 → None

注意:_call_llm 的真实实现依赖项目 LLM 客户端,本模块提供 stub 接口,
单元测试全部 patch 它。生产代码接入在后续 PR 单独处理(spec §1.3 YAGNI)。
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class CreateParams:
    """换班创建参数(从 query 提取)"""

    target_name: str
    duty_date: str
    reason: str = ""


@dataclass
class DecideParams:
    """换班决策参数(从 query 提取)"""

    action: str
    swap_id: int | None = None
    note: str = ""


def _call_llm(prompt: str) -> str:
    """调用项目现有 LLM 客户端。

    本函数作为 swap_extractor 与 LLM 客户端的唯一接触点,便于测试 mock。
    真实实现依赖项目 LLM 客户端(YAGNI:本任务范围只到 mock level,
    真实 LLM 接入在后续 PR 单独处理)。
    """
    raise NotImplementedError(
        "_call_llm 是 stub。请在生产环境接入项目 LLM 客户端后再使用 swap_extractor。"
    )


def _call_llm_for_json(prompt: str) -> dict | None:
    """调 LLM 拿 JSON。

    鲁棒性:
    1. LLM 抛异常/超时 → None
    2. 返回非 JSON → 用正则提取首个 {...} 块再试
    3. 仍无法解析 → None
    """
    try:
        raw = _call_llm(prompt)
    except Exception as e:
        logger.warning("_call_llm 失败: %s", e)
        return None
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{[\s\S]*\}", raw)
    if not m:
        logger.warning("_call_llm_for_json: 找不到 JSON 块. raw=%r", raw[:200])
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        logger.warning("_call_llm_for_json: 提取后仍非 JSON. raw=%r", raw[:200])
        return None
