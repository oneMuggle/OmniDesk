"""smart_assistant.extractors.swap_extractor — 换班查询的 LLM 提取器

LLM 解析"中文 query → CreateParams / DecideParams",失败兜底为 None(由调用方
返回 found=False,不降级到规则)。

鲁棒性:
- LLM 不可用 / 抛异常 → None
- LLM 返回非 JSON 文本 → 用正则提取首个 {…} 块再试
- 解析后字段缺失 → None

``_call_llm`` 经 ``llm_service.router`` 的降级链(DB LlmAppConfig → Ollama 兜底)
调用真实 LLM;单元测试既可 patch ``_call_llm`` 做纯解析测试,也可用
``mock_llm_router`` fixture 走真实接线(见 test_swap_extractor.py)。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from django.utils import timezone as dj_timezone
from django.db.models import Q
from django.db import models

from events.models import ScheduleSwapRequest

from .prompts.swap_create_prompt import (
    SWAP_CREATE_SYSTEM_PROMPT,
    build_create_user_prompt,
)
from .prompts.swap_decide_prompt import (
    SWAP_DECIDE_SYSTEM_PROMPT,
    build_decide_user_prompt,
)

from observability import get_logger

VALID_ACTIONS = frozenset({"accept", "reject", "cancel"})

logger = get_logger(__name__, "smart_assistant")

# 匹配 <think>...</think> 推理块(DeepSeek/qwen 等模型会输出推理过程),
# 剥离以避免干扰 JSON 抽取。
_THINK_RE = re.compile(r"<think>[\s\S]*?</think>\s*", re.IGNORECASE)


def _strip_think_tags(response: str) -> str:
    """去除 LLM 响应中的 <think>...</think> 推理块,保留正文。"""
    return _THINK_RE.sub("", response or "").strip()


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
    """调用项目 LLM 客户端(LLMRouter 降级链)。

    经 ``llm_service.router.get_router()`` 调用(DB LlmAppConfig 优先级链 →
    Ollama 本地兜底)。本函数作为 swap_extractor 与 LLM 客户端的唯一接触点,
    便于测试 mock。任何异常向上抛,由 ``_call_llm_for_json`` 兜底为 None。

    实现要点:
    - 低温(temperature=0)以获得确定性的 JSON 抽取结果;
    - 剥离 ``<think>`` 推理块,避免干扰后续 JSON 解析;
    - 延迟 import get_router:既避免应用加载期 extractors ↔ llm_service 的
      import 耦合,也让测试对 ``llm_service.router.get_router`` 的 patch 生效。
    """
    from llm_service.router import get_router  # 延迟导入,见 docstring

    client = get_router()
    content, _usage = client.generate(prompt=prompt, options={"temperature": 0})
    return _strip_think_tags(content)


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
        logger.debug(
            "smart_assistant.swap_extractor.json_parse_failed",
            extra={"event": "smart_assistant.swap_extractor.json_parse_failed", "raw": raw[:200]},
        )
    m = re.search(r"\{[\s\S]*\}", raw)
    if not m:
        logger.warning("_call_llm_for_json: 找不到 JSON 块. raw=%r", raw[:200])
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        logger.warning("_call_llm_for_json: 提取后仍非 JSON. raw=%r", raw[:200])
        return None


def extract_create_params(query: str, requester) -> CreateParams | None:
    """从 query 提取创建 swap 所需参数。

    Returns:
        CreateParams 实例;LLM 失败/缺字段 → None
    """
    requester_name = getattr(requester, "name", "未知")
    today = str(dj_timezone.now().date())
    user_prompt = build_create_user_prompt(query, requester_name, today)
    full_prompt = f"{SWAP_CREATE_SYSTEM_PROMPT}\n\n{user_prompt}"
    data = _call_llm_for_json(full_prompt)
    if data is None:
        return None
    target_name = data.get("target_name")
    duty_date = data.get("duty_date")
    if not target_name or not duty_date:
        logger.warning("extract_create_params: 缺字段. data=%s", data)
        return None
    return CreateParams(
        target_name=target_name,
        duty_date=duty_date,
        reason=data.get("reason") or "",
    )


def _get_pending_swaps_for_actor(actor) -> list:
    """收集 actor 作为 target_personnel 或 requester 的 pending 申请。

    返回 list of dict,每项含 swap_id / requester_name / target_name / duty_date。
    """
    personnel = getattr(actor, "personnel", None)
    if personnel is None or not isinstance(personnel, models.Model):
        return []
    qs = (
        ScheduleSwapRequest.objects.filter(status=ScheduleSwapRequest.STATUS_PENDING)
        .filter(Q(target_personnel=personnel) | Q(requester=personnel))
        .select_related("requester", "target_personnel", "original_schedule")[:20]
    )
    return [
        {
            "swap_id": s.id,
            "requester_name": s.requester.name,
            "target_name": s.target_personnel.name,
            "duty_date": str(s.original_schedule.duty_date),
        }
        for s in qs
    ]


def extract_decide_params(query: str, actor) -> DecideParams | None:
    """从 query 提取 decide 参数。

    Returns:
        DecideParams 实例;LLM 失败/缺字段/action 不合法 → None
    """
    personnel = getattr(actor, "personnel", None)
    actor_name = personnel.name if isinstance(personnel, models.Model) else "未知"
    pending_swaps = _get_pending_swaps_for_actor(actor)
    user_prompt = build_decide_user_prompt(query, actor_name, pending_swaps)
    full_prompt = f"{SWAP_DECIDE_SYSTEM_PROMPT}\n\n{user_prompt}"
    data = _call_llm_for_json(full_prompt)
    if data is None:
        return None
    action = data.get("action")
    if action not in VALID_ACTIONS:
        logger.warning("extract_decide_params: action 非法. data=%s", data)
        return None
    swap_id = data.get("swap_id")
    if swap_id is not None and not isinstance(swap_id, int):
        try:
            swap_id = int(swap_id)
        except (TypeError, ValueError):
            swap_id = None
    return DecideParams(
        action=action,
        swap_id=swap_id,
        note=data.get("note") or "",
    )
