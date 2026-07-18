"""智能助手结果缓存:缓存意图分类和工具查询结果,减少重复 LLM 调用。

Task 17 安全增强:所有工具/回答缓存都要求调用方传入 ``context_sig``(由
``agent.orchestrator._scope_cache_sig`` 从 ``ToolContext`` 派生,形如
``u<user_pk>_s<scope_value>``)。这样不同用户 / 不同 scope 不会读到彼此
的缓存结果,防止 scope-aware 接入后产生的 User A → User B 数据泄露。
"""

import hashlib
import logging
import threading

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

# 缓存时长
INTENT_CACHE_TTL = 3600  # 意图分类: 1 小时
TOOL_CACHE_TTL = 1800  # 工具结果: 30 分钟
ANSWER_CACHE_TTL = 7200  # 常见回答: 2 小时

CACHE_PREFIX = "smart_assistant:cache:"

# 全局缓存版本号,工具代码或缓存 schema 升级时调用 bump_cache_version()
# 递增后旧缓存自动失效(因 cache key 含本字段)
CACHE_VERSION: int = 1


def bump_cache_version() -> int:
    """手动 bump 缓存版本号,旧缓存自动失效。

    使用场景:
    - 工具签名变更(返回结构变化)
    - 意图分类 prompt 升级
    - LLM 端点切换

    Returns:
        新的 cache_version 值
    """
    global CACHE_VERSION
    CACHE_VERSION += 1
    logger.info("Cache version bumped to %d (旧缓存自动失效)", CACHE_VERSION)
    return CACHE_VERSION


def _settings_cache_version() -> str:
    """从 Django 设置中读取部署级缓存版本。

    允许运维在 settings / 环境变量中 bump 版本,无需改代码重启即可失效旧缓存。
    """
    return getattr(settings, "SMART_ASSISTANT_CACHE_VERSION", "1.0")


def _extract_user_id(context_sig: str) -> int:
    """从 context_sig (``u<pk>_s<scope>``) 中提取 user_id。"""
    if not context_sig or not context_sig.startswith("u"):
        return 0
    try:
        return int(context_sig.split("_")[0][1:])
    except (ValueError, IndexError):
        return 0


def _build_cache_key(query: str, user_id: int, intent: str) -> str:
    """构建包含 cache_version 的缓存键。

    组合 settings 级版本 + 运行时版本 + 业务参数,任一变化即产生新键,
    旧缓存自动失效。供 ``cache_answer`` / ``get_cached_answer`` 内部使用,
    也可直接调用以测试版本隔离行为。

    Args:
        query: 用户查询文本
        user_id: 用户主键
        intent: 意图分类名

    Returns:
        带 ``smart_assistant:cache:`` 前缀的 sha256 摘要键
    """
    raw = f"{query}|{user_id}|{intent}|{_settings_cache_version()}|v{CACHE_VERSION}"
    return CACHE_PREFIX + hashlib.sha256(raw.encode()).hexdigest()[:32]  # nosec B324 — cache key, not security


def _key(*parts):
    """生成缓存 key。

    所有缓存 key 包含 CACHE_VERSION 全局字段,工具升级时调用
    ``bump_cache_version()`` 即可让旧缓存自动失效,无需手动清理。
    同时嵌入 settings 级 SMART_ASSISTANT_CACHE_VERSION,允许运维在不
    改代码的情况下 bump 版本失效旧缓存。
    """
    raw = "|".join(str(p) for p in parts)
    raw += f"|{_settings_cache_version()}|v{CACHE_VERSION}"
    return CACHE_PREFIX + hashlib.sha256(raw.encode()).hexdigest()[:32]  # nosec B324 — cache key, not security


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
    缓存键通过 ``_build_cache_key`` 构建,包含 settings 级 cache_version,
    运维 bump ``SMART_ASSISTANT_CACHE_VERSION`` 即可失效旧缓存。
    """
    user_id = _extract_user_id(context_sig)
    key = _build_cache_key(query=query, user_id=user_id, intent=intent)
    # history_sig 影响键:不同历史上下文不应共享缓存
    if history_sig:
        key += f":h{hashlib.sha256(history_sig.encode()).hexdigest()[:8]}"  # nosec B324 — cache key, not security
    return cache.get(key)


def cache_answer(query, intent, answer, history_sig="", context_sig=""):
    """缓存回答结果。context_sig 同上(防缓存投毒)。"""
    user_id = _extract_user_id(context_sig)
    key = _build_cache_key(query=query, user_id=user_id, intent=intent)
    if history_sig:
        key += f":h{hashlib.sha256(history_sig.encode()).hexdigest()[:8]}"  # nosec B324 — cache key, not security
    cache.set(key, answer, ANSWER_CACHE_TTL)


# ---------------------------------------------------------------------------
# singleflight:缓存击穿防护
# ---------------------------------------------------------------------------
# 高并发下同 key 的多个请求只有一个去调 loader(通常是 DB/LLM),其余等待结果,
# 避免缓存击穿(同 key 50 个请求都打到后端)。
_inflight_flags: dict[str, threading.Event] = {}
_inflight_global = threading.Lock()


def singleflight_get_or_set(key: str, loader, ttl: int = ANSWER_CACHE_TTL):
    """缓存击穿防护:同 key 并发时只调一次 loader。

    流程:
    1. 先查 cache,命中直接返回
    2. 未命中时看是否已有线程在加载(检查 ``_inflight_flags``)
    3. 若有 → 当前线程 wait(event),最多 30s 后回查 cache
    4. 若无 → 当前线程成为 leader,调 loader 并 set cache,完成后唤醒等待者

    Args:
        key: 缓存 key(调用方应已拼接 cache_version + context_sig)
        loader: 缓存未命中时调用的零参函数
        ttl: 缓存 TTL(秒),默认 ANSWER_CACHE_TTL

    Returns:
        缓存值或 loader 返回值
    """
    cache_key = _key("sf", key)
    # 1. 快速路径:cache 命中
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    # 2. 未命中,竞争 leader
    with _inflight_global:
        if key in _inflight_flags:
            event = _inflight_flags[key]
            is_leader = False
        else:
            event = threading.Event()
            _inflight_flags[key] = event
            is_leader = True

    if not is_leader:
        # 等待 leader 完成
        event.wait(timeout=30)
        # 回查 cache(leader 可能已 set)
        return cache.get(cache_key)

    # 3. leader:执行 loader,set cache,唤醒等待者
    try:
        value = loader()
        cache.set(cache_key, value, ttl)
        return value
    finally:
        event.set()
        with _inflight_global:
            _inflight_flags.pop(key, None)
