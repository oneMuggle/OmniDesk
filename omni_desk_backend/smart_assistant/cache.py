"""智能助手结果缓存:缓存意图分类和工具查询结果,减少重复 LLM 调用。

Task 17 安全增强:所有工具/回答缓存都要求调用方传入 ``context_sig``(由
``agent.orchestrator._scope_cache_sig`` 从 ``ToolContext`` 派生,形如
``u<user_pk>_s<scope_value>``)。这样不同用户 / 不同 scope 不会读到彼此
的缓存结果,防止 scope-aware 接入后产生的 User A → User B 数据泄露。
"""

import hashlib
import logging

from django.core.cache import cache

logger = logging.getLogger(__name__)

# 缓存时长
INTENT_CACHE_TTL = 3600  # 意图分类: 1 小时
TOOL_CACHE_TTL = 1800  # 工具结果: 30 分钟
ANSWER_CACHE_TTL = 7200  # 常见回答: 2 小时

CACHE_PREFIX = "smart_assistant:cache:"


def _key(*parts):
    """生成缓存 key。"""
    raw = ":".join(str(p) for p in parts)
    return CACHE_PREFIX + hashlib.md5(raw.encode()).hexdigest()[:16]  # nosec B324 — cache key, not security


def get_cached_intent(query, schemas, context_sig=""):
    """尝试从缓存获取意图分类结果。

    context_sig 用于按 user/scope 隔离缓存,避免不同权限用户读到
    彼此的分类结果(防缓存投毒)。Task 17 起由 orchestrator 传入。
    """
    schemas_sig = ",".join(s["name"] for s in sorted(schemas, key=lambda x: x["name"]))
    key = _key("intent", query, schemas_sig, context_sig)
    return cache.get(key)


def cache_intent(query, schemas, intent, context_sig=""):
    """缓存意图分类结果。

    context_sig 同 ``get_cached_intent``(防缓存投毒)。
    """
    schemas_sig = ",".join(s["name"] for s in sorted(schemas, key=lambda x: x["name"]))
    key = _key("intent", query, schemas_sig, context_sig)
    cache.set(key, intent, INTENT_CACHE_TTL)


def get_cached_tool_result(tool_name, query, context_sig=""):
    """尝试从缓存获取工具结果。

    context_sig(Task 17 起):由 orchestrator 从 ToolContext 派生
    ``u<user_pk>_s<scope_value>``,加入 cache key 以实现 per-user/per-scope
    隔离。未传入时退化为空字符串(保持向后兼容)。
    """
    key = _key("tool", tool_name, query, context_sig)
    return cache.get(key)


def cache_tool_result(tool_name, query, result, context_sig=""):
    """缓存工具查询结果。

    context_sig 行为同 ``get_cached_tool_result``。未传入时缓存 key 中
    ``context_sig`` 为空串,所有用户/所有 scope 共享 — 这是 P0 安全风险,
    Task 17 后所有调用点都必须传。
    """
    if not isinstance(result, dict) or not result.get("found"):
        return  # 仅缓存成功结果
    key = _key("tool", tool_name, query, context_sig)
    cache.set(key, result, TOOL_CACHE_TTL)


def get_cached_answer(query, intent, history_sig="", context_sig=""):
    """尝试从缓存获取回答。

    context_sig(Task 17 起):同工具缓存,按 user/scope 隔离。
    """
    key = _key("answer", query, intent, history_sig, context_sig)
    return cache.get(key)


def cache_answer(query, intent, answer, history_sig="", context_sig=""):
    """缓存回答结果。context_sig 同上(防缓存投毒)。"""
    key = _key("answer", query, intent, history_sig, context_sig)
    cache.set(key, answer, ANSWER_CACHE_TTL)
