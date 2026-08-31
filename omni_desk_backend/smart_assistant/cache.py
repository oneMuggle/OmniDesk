"""智能助手结果缓存:缓存意图分类和工具查询结果,减少重复 LLM 调用。

Task 17 安全增强:所有工具/回答缓存都要求调用方传入 ``context_sig``(由
``agent.orchestrator._scope_cache_sig`` 从 ``ToolContext`` 派生,形如
``u<user_pk>_s<scope_value>``)。这样不同用户 / 不同 scope 不会读到彼此
的缓存结果,防止 scope-aware 接入后产生的 User A → User B 数据泄露。
"""

import copy
import hashlib
import json
import ipaddress
import re
import threading
from urllib.parse import parse_qsl, urlsplit

from django.conf import settings
from django.core.cache import cache

from observability import get_logger

logger = get_logger(__name__, "smart_assistant")

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


def _build_cache_key(
    query: str,
    user_id: int,
    intent: str,
    *,
    tool_call_path: str = "none",
    cache_version: int | None = None,
) -> str:
    """构建包含 cache_version + tool_call_path 的缓存键。

    组合 settings 级版本 + 运行时版本 + 业务参数,任一变化即产生新键,
    旧缓存自动失效。供 ``cache_answer`` / ``get_cached_answer`` 内部使用,
    也可直接调用以测试版本隔离行为。

    Args:
        query: 用户查询文本
        user_id: 用户主键
        intent: 意图分类名
        tool_call_path: 工具调用路径(``"native"`` / ``"json"`` / ``"none"``)。
            Task 7 of feat/sa-office-files:A/B 评估期间 native 与 JSON 两条
            路径下的回答缓存必须隔离,避免切换后读到旧路径的脏缓存。
        cache_version: 运行时版本号;默认走全局 ``CACHE_VERSION``,测试时可注入。

    Returns:
        带 ``smart_assistant:cache:`` 前缀的 sha256 摘要键
    """
    version = CACHE_VERSION if cache_version is None else cache_version
    raw = f"{query}|{user_id}|{intent}|{tool_call_path}|{_settings_cache_version()}|v{version}"
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


def get_cached_answer(
    query,
    intent,
    history_sig="",
    context_sig="",
    *,
    tool_call_path: str = "none",
):
    """尝试从缓存获取回答。

    context_sig(Task 17 起):同工具缓存,按 user/scope 隔离。
    tool_call_path(Task 7 of feat/sa-office-files):按 native/json/none 路径隔离,
    避免 A/B 切换时读到旧路径的脏缓存。
    缓存键通过 ``_build_cache_key`` 构建,包含 settings 级 cache_version,
    运维 bump ``SMART_ASSISTANT_CACHE_VERSION`` 即可失效旧缓存。
    """
    user_id = _extract_user_id(context_sig)
    key = _build_cache_key(
        query=query,
        user_id=user_id,
        intent=intent,
        tool_call_path=tool_call_path,
    )
    # history_sig 影响键:不同历史上下文不应共享缓存
    if history_sig:
        key += f":h{hashlib.sha256(history_sig.encode()).hexdigest()[:8]}"  # nosec B324 — cache key, not security
    return cache.get(key)


def cache_answer(
    query,
    intent,
    answer,
    history_sig="",
    context_sig="",
    *,
    tool_call_path: str = "none",
):
    """缓存回答结果。context_sig 同上(防缓存投毒)。

    tool_call_path:与 ``get_cached_answer`` 对称,保证读写使用同一维度。
    """
    user_id = _extract_user_id(context_sig)
    key = _build_cache_key(
        query=query,
        user_id=user_id,
        intent=intent,
        tool_call_path=tool_call_path,
    )
    if history_sig:
        key += f":h{hashlib.sha256(history_sig.encode()).hexdigest()[:8]}"  # nosec B324 — cache key, not security
    cache.set(key, answer, ANSWER_CACHE_TTL)


# ---------------------------------------------------------------------------
# singleflight:缓存击穿防护
# ---------------------------------------------------------------------------
# 高并发下同 key 的多个请求只有一个去调 loader(通常是 DB/LLM),其余等待结果,
# 避免缓存击穿(同 key 50 个请求都打到后端)。
_inflight_flags: dict[str, threading.Event] = {}
_inflight_exceptions: dict[str, BaseException] = {}  # 存储 leader 的异常供等待者读取
_inflight_global = threading.Lock()


def singleflight_get_or_set(key: str, loader, ttl: int = ANSWER_CACHE_TTL):
    """缓存击穿防护:同 key 并发时只调一次 loader。

    流程:
    1. 先查 cache,命中直接返回
    2. 未命中时看是否已有线程在加载(检查 ``_inflight_flags``)
    3. 若有 → 当前线程 wait(event),最多 30s 后回查 cache
    4. 若无 → 当前线程成为 leader,调 loader 并 set cache,完成后唤醒等待者
    5. 异常传播:leader 的 loader 抛异常时,等待者也会收到同一异常

    Args:
        key: 缓存 key(调用方应已拼接 cache_version + context_sig)
        loader: 缓存未命中时调用的零参函数
        ttl: 缓存 TTL(秒),默认 ANSWER_CACHE_TTL

    Returns:
        缓存值或 loader 返回值

    Raises:
        BaseException: 若 loader 抛出异常,所有等待者都会收到该异常
    """
    cache_key = _key("sf", key)

    # 清理上一次调用的残留异常(若有)
    with _inflight_global:
        _inflight_exceptions.pop(key, None)

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
        # 检查 leader 是否存储了异常
        with _inflight_global:
            exc = _inflight_exceptions.get(key)
        if exc is not None:
            raise exc
        # 回查 cache(leader 可能已 set)
        return cache.get(cache_key)

    # 3. leader:执行 loader,set cache,唤醒等待者
    try:
        value = loader()
        cache.set(cache_key, value, ttl)
        return value
    except BaseException as e:
        # 存储异常供等待者读取
        with _inflight_global:
            _inflight_exceptions[key] = e
        raise
    finally:
        event.set()
        with _inflight_global:
            _inflight_flags.pop(key, None)


# ---------------------------------------------------------------------------
# confirm-replay:draft 短期缓存
# ---------------------------------------------------------------------------
# 工具标记 require_confirmation=True 时,orchestrator 在 execute 前拦截,
# 把工具的"预演"结果(draft)存入短期缓存,返回 confirmation_token 给前端。
# 用户在前端点确认后,二次请求带 token 触发 replay,跳过 pre-hook 直接执行。
# TTL 10 分钟:用户从看到弹窗到点确认通常 < 1 分钟,10 分钟足够容错。
CONFIRMATION_DRAFT_TTL = 600  # 秒


class ConfirmationDraftConsumeError(RuntimeError):
    """确认草稿缓存无法可靠消费时抛出的受控异常。"""

    def __init__(self, failure_kind: str):
        self.failure_kind = failure_kind
        super().__init__(failure_kind)


def _draft_key(token: str) -> str:
    """confirmation draft 缓存 key。

    与业务缓存隔离(前缀 "confirm_draft"),避免与 tool/intent/answer 缓存冲突。
    token 由调用方生成(uuid4),key 内已含 CACHE_VERSION 与 settings 级版本,
    升级自动失效。
    """
    return _key("confirm_draft", token)


def set_confirmation_draft(
    token: str,
    draft: dict,
    ttl: int = CONFIRMATION_DRAFT_TTL,
) -> None:
    """存 confirmation draft。token 由调用方生成(uuid4)。

    Args:
        token: 唯一标识(replay 时前端带回)
        draft: draft 字典(工具预演结果 + 上下文)
        ttl: 过期秒数,默认 10 分钟

    注意:调用方负责保证 token 唯一(用 uuid4 即可)。本函数不校验参数类型,
    异常时由 Django cache 层吞错(与 cache.set 行为一致)。
    """
    key = _draft_key(token)
    backend = cache._connections["default"]
    module = backend.__class__.__module__
    if module.startswith("django.core.cache.backends.locmem"):
        with _inflight_global:
            cache.set(key, draft, ttl)
        return
    cache.set(key, draft, ttl)


def consume_confirmation_draft(token: str, validator=None) -> dict | None:
    """在一致性保护内校验并一次性消费确认草稿。

    validator 必须在消费保护范围内执行。Redis 使用 Lua 对原始值执行
    compare-and-delete；locmem 在进程锁内重新读取并比较，避免校验期间的替换
    draft 被误删。任何删除失败都 fail closed。
    """
    key = _draft_key(token)

    def prepare(value):
        if value is None:
            return None
        candidate = copy.deepcopy(value)
        validated = validator(candidate) if callable(validator) else candidate
        if not isinstance(validated, dict):
            return None
        return validated

    try:
        backend = cache._connections["default"]
        module = backend.__class__.__module__
        if module.startswith("django_redis"):
            client = backend.get_client(write=True)
            redis_key = backend.make_key(key)
            lock = backend.lock(f"{key}:consume", timeout=30, blocking_timeout=5)
            # 只在读取/最终 CAS 的短临界区持锁；validator 不得占用固定锁超时。
            with lock:
                raw_value = client.get(redis_key)
            if raw_value is None:
                return None
            original = backend.decode(raw_value)
            prepared = prepare(original)
            if prepared is None:
                return None
            with lock:
                result = client.eval(
                    "local current = redis.call('GET', KEYS[1]); "
                    "if current == ARGV[1] then return redis.call('DEL', KEYS[1]) else return 0 end",
                    1,
                    redis_key,
                    raw_value,
                )
            if result != 1:
                return None
            return prepared
        if module.startswith("django.core.cache.backends.locmem"):
            with _inflight_global:
                original = cache.get(key)
            prepared = prepare(original)
            if prepared is None:
                return None
            # validator 在锁外执行；锁内重新读取实际值，替换 token 时 fail closed。
            with _inflight_global:
                if cache.get(key) != original:
                    return None
                delete_result = cache.delete(key)
                if delete_result is not True:
                    raise ConfirmationDraftConsumeError("delete_failed")
                return prepared
    except ConfirmationDraftConsumeError:
        raise
    except Exception as exc:
        logger.warning(
            "confirmation draft consume backend failure: backend=%s exc_type=%s",
            type(backend).__name__ if "backend" in locals() else "unknown",
            type(exc).__name__,
        )
        raise ConfirmationDraftConsumeError("backend_failure") from exc
    logger.warning(
        "confirmation draft consume unsupported backend: backend=%s",
        type(backend).__name__,
    )
    raise ConfirmationDraftConsumeError("unsupported_backend")

def get_confirmation_draft(token: str) -> dict | None:
    """取 confirmation draft。过期/不存在返回 None。"""
    return cache.get(_draft_key(token))


_SECRET_TEXT_RE = re.compile(
    r"(?is)(?:bearer\s+[a-z0-9._~+/=-]+|"
    r"(?:api[_ -]?key|apikey|credential|token|password|secret|authorization|access[_ -]?token)"
    r"\s*(?:=|:|：)\s*(?:\"[^\"]*\"|'[^']*'|[^\s,;，；。}]+))"
)
_PII_TEXT_RE = (
    re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}"),
    re.compile(r"(?<!\d)1\d{10}(?!\d)"),
    re.compile(r"(?<!\d)(?:\d{15}|\d{17}[\dXx])(?!\d)"),
)
_URL_RE = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
_URL_CREDENTIAL_KEYS = {
    "x-amz-signature", "x-amz-credential", "x-amz-security-token",
    "token", "credential", "sig", "signature", "access-token", "access_token",
}


def _canonical_url_query_key(value):
    """统一 URL query key 的大小写、分隔符及百分号编码形式。"""
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


_URL_CREDENTIAL_CANONICAL_KEYS = {
    _canonical_url_query_key(key) for key in _URL_CREDENTIAL_KEYS
}


def _sanitize_url_credentials(value):
    """替换文本中 URL query 的凭据值，同时保留普通外链。"""
    def replace(match):
        raw_url = match.group(0)
        trailing = ""
        while raw_url and raw_url[-1] in ".,;!?，。；！）":
            trailing = raw_url[-1] + trailing
            raw_url = raw_url[:-1]
        try:
            parsed = urlsplit(raw_url)
            pairs = parse_qsl(parsed.query, keep_blank_values=True)
            if not pairs:
                return raw_url + trailing
            changed = False
            safe_pairs = []
            for key, item in pairs:
                if _canonical_url_query_key(key) in _URL_CREDENTIAL_CANONICAL_KEYS:
                    item = "[已隐藏]"
                    changed = True
                safe_pairs.append((key, item))
            if not changed:
                return raw_url + trailing
            from urllib.parse import urlencode
            sanitized = parsed._replace(query=urlencode(safe_pairs)).geturl()
            return sanitized + trailing
        except ValueError:
            return raw_url + trailing

    return _URL_RE.sub(replace, value)


_PUBLIC_SAFE_KEYS = {
    "operation_id", "operation", "phase", "scope", "status", "count", "total",
    "recipient_count", "sent_count", "failed_count", "channel", "channels",
}
_PUBLIC_SENSITIVE_KEYS = {
    "content", "body", "recipients", "recipient", "recipient_name", "recipient_names", "username",
    "email", "phone", "prompt",
    "prompt_text", "credentials", "credential", "credential_blob", "token", "token_value",
    "bearer_token", "secret", "password", "authorization", "authorization_header",
    "api_key", "access_token", "private_key", "client_secret", "arguments", "args",
    "session", "session_id",
}


def _canonical_public_key(value):
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


_PUBLIC_SENSITIVE_CANONICAL_KEYS = {
    _canonical_public_key(item) for item in _PUBLIC_SENSITIVE_KEYS
}
_PUBLIC_SENSITIVE_MARKERS = (
    "password", "credential", "secret", "token", "prompt", "apikey",
    "authorization", "privatekey", "sessionid", "userid", "recipientid",
    "username", "recipientname", "name",
)


def _is_public_sensitive_key(value):
    canonical = _canonical_public_key(value)
    return canonical in _PUBLIC_SENSITIVE_CANONICAL_KEYS or any(
        marker in canonical for marker in _PUBLIC_SENSITIVE_MARKERS
    )


def sanitize_public_text(value, limit=2000):
    """脱敏公开文本中的 secret/PII，兼容 JSON、quoted、key:value 和 Bearer。"""
    raw = str(value or "")
    try:
        parsed = json.loads(raw[:limit])
    except (TypeError, ValueError):
        parsed = None
    if isinstance(parsed, (dict, list)):
        return str(safe_public_value(parsed))[:limit]

    protected_urls = []

    def protect_url(match):
        protected_urls.append(_sanitize_url_credentials(match.group(0)))
        return f"__PUBLIC_URL_{len(protected_urls) - 1}__"

    result = _URL_RE.sub(protect_url, raw)
    result = _SECRET_TEXT_RE.sub("[已隐藏]", result)
    for pattern in _PII_TEXT_RE:
        result = pattern.sub("[已隐藏]", result)
    for index, url in enumerate(protected_urls):
        result = result.replace(f"__PUBLIC_URL_{index}__", url)
    return result[:limit]


def _is_public_url(value):
    """只允许普通外链；拒绝内网地址和签名/凭据 query。"""
    if not isinstance(value, str) or len(value) > 2048:
        return False
    try:
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return False
        hostname = parsed.hostname.lower().rstrip(".")
        if hostname in {"localhost", "localhost.localdomain"} or hostname.endswith((".localhost", ".local", ".internal")):
            return False
        try:
            address = ipaddress.ip_address(hostname)
            if address.is_private or address.is_loopback or address.is_link_local or address.is_reserved:
                return False
        except ValueError:
            pass
        if parsed.username is not None or parsed.password is not None:
            return False
        blocked_query = {
            _canonical_url_query_key(key)
            for key in (
                "x-amz-signature", "x-amz-credential", "x-amz-security-token",
                "token", "credential", "sig", "signature", "access_token", "access-token",
            )
        }
        if any(
            _canonical_url_query_key(key) in blocked_query
            for key, _ in parse_qsl(parsed.query, keep_blank_values=True)
        ):
            return False
        fragment = parsed.fragment.lower()
        if any(marker in fragment for marker in ("token", "signature", "credential", "access_token")):
            return False
    except ValueError:
        return False
    return True


def sanitize_public_sources(sources):
    """把来源转换成安全 DTO，保留文档名/评分和普通外链。"""
    if not isinstance(sources, list):
        return [] if sources is not None else None
    safe = []
    for source in sources[:20]:
        if not isinstance(source, dict):
            continue
        item = {}
        for key in ("document", "title", "score", "source_id"):
            if key in source and isinstance(source[key], (str, int, float)):
                item[key] = sanitize_public_text(source[key], 200) if isinstance(source[key], str) else source[key]
        if _is_public_url(source.get("url")):
            item["url"] = source["url"]
        if item:
            safe.append(item)
    return safe


def safe_public_value(value, depth=0):
    """递归生成公开摘要；过滤敏感键，限制深度、集合大小和文本长度。"""
    if depth >= 3:
        return "[已隐藏]"
    if isinstance(value, str):
        return sanitize_public_text(value)
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    if isinstance(value, list):
        return [safe_public_value(item, depth + 1) for item in value[:20]]
    if isinstance(value, dict):
        return {
            str(key): safe_public_value(item, depth + 1)
            for key, item in list(value.items())[:30]
            if not _is_public_sensitive_key(key)
        }
    return "[已隐藏]"


def public_tool_arguments(arguments):
    """生成对外 tool_calls_meta.arguments；审计原始参数不在此公开。"""
    if not isinstance(arguments, dict):
        return {}
    return {
        str(key): safe_public_value(value)
        for key, value in list(arguments.items())[:30]
        if not _is_public_sensitive_key(key)
    }


def public_confirmation_draft(draft: dict, tool_name: str = "") -> dict:
    """把 server-side replay draft 转为统一的最小安全公开摘要。"""
    if not isinstance(draft, dict):
        return {"summary": "请确认以下操作", "fields": {}}
    fields = draft.get("fields") if isinstance(draft.get("fields"), dict) else {}
    operation_id = fields.get("operation_id")
    public_fields = {"operation_id": sanitize_public_text(operation_id, 128)} if operation_id else {}
    if tool_name == "agent_notify":
        recipient_ids = fields.get("recipient_ids")
        public_fields.update({
            "operation": "agent_notify",
            "recipient_count": len(recipient_ids) if isinstance(recipient_ids, list) else 0,
            "title": sanitize_public_text(fields.get("title"), 80),
        })
    else:
        for key in ("operation", "phase", "scope", "status", "count", "total"):
            if key in fields and not _is_public_sensitive_key(key):
                public_fields[key] = safe_public_value(fields[key])
    if tool_name == "agent_notify":
        summary = (
            f"待执行站内通知（操作：agent_notify；收件人数：{public_fields['recipient_count']}；"
            f"标题：{public_fields['title']}）"
        )
    else:
        # server-side draft.summary 可能包含原始 query 或业务正文；绝不透传。
        summary = "请确认工具操作"
    return {"summary": summary[:180], "fields": public_fields}


def public_tool_calls_meta(meta):
    """统一过滤对外 tool_calls_meta；保留执行状态而不暴露原始参数。"""
    if not isinstance(meta, list):
        return []
    result = []
    for item in meta[:30]:
        if not isinstance(item, dict):
            continue
        entry = {
            str(key): safe_public_value(value)
            for key, value in item.items()
            if key != "arguments" and not _is_public_sensitive_key(key)
        }
        if "arguments" in item:
            entry["arguments"] = public_tool_arguments(item["arguments"])
        result.append(entry)
    return result
def _public_status_fields(source):
    """从工具结果提取跨工具共享的公开状态字段。"""
    allowed = {
        "found", "status", "message", "date", "error_code", "operation_id", "operation",
        "phase", "count", "total", "channel", "channels", "recipient_count", "sent_count",
        "failed_count",
    }
    public = {}
    for key in allowed:
        if key not in source or _is_public_sensitive_key(key):
            continue
        value = source[key]
        public[key] = sanitize_public_text(value) if key == "message" else safe_public_value(value)
    return public


def _public_rag_result(source):
    """RAG 专用安全 DTO；绝不把 context 或原始来源字段递归公开。"""
    public = _public_status_fields(source)
    sources = sanitize_public_sources(source.get("sources"))
    if sources is not None:
        public["sources"] = sources
        public.setdefault("count", len(sources))
    return public


def public_tool_result(result, tool_name="", *, intent=""):
    """生成公开 ToolResult；基础状态白名单和聚合生产者均显式声明。"""
    if not isinstance(result, dict):
        return {}
    source = result.get("result") if isinstance(result.get("result"), dict) else result
    if not isinstance(source, dict):
        return {}
    if tool_name == "knowledge_qa" or intent == "knowledge_qa":
        return _public_rag_result(source)

    public = _public_status_fields(source)
    if "count" not in public:
        for detail_key in ("personnel", "schedules", "documents", "events", "memos", "projects", "posts", "issues", "links", "articles"):
            if isinstance(source.get(detail_key), list):
                public["count"] = len(source[detail_key])
                break
    if tool_name == "aggregated_day" or intent == "aggregated_day":
        # 只有聚合器可以公开这些已经聚合的结构化摘要字段。
        for key in ("summary", "items", "moduleCounts", "total_count"):
            if key in source:
                public[key] = safe_public_value(source[key])
    elif "summary" in source and not {"items", "moduleCounts", "total_count"}.intersection(source):
        public["summary"] = sanitize_public_text(source["summary"])
    return public


def clear_confirmation_draft(token: str) -> None:
    """replay 成功后清理 draft,防止 token 重放。

    失败安全:token 不存在时静默(不抛异常),与 cache.delete 行为一致。
    """
    cache.delete(_draft_key(token))
