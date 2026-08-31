"""智能助手 doctor 自检端点（借鉴 claw-code 的 doctor 命令与机器可读输出契约）。

GET /api/smart-assistant/doctor/ 对智能助手依赖的外部服务做一次只读健康自检，
返回结构化结果（``format_version=1``），供管理后台运维面板展示：

- llm_config     智能助手 LLM 应用配置是否存在且激活
- llm_endpoint:* 每个激活的 LLM 端点轻量可达性探测
- ollama_fallback Ollama 兜底服务可达性（warn 级——它只是降级兜底）
- ragflow        Ragflow 配置是否存在 + api_endpoint 可达性
- datasets       激活的知识库数据集数量
- cache_rate_limit 缓存后端类型与限流中间件启用情况（信息级）

所有网络探测统一使用短超时（3 秒）；任何检查项异常都会被捕获并转成
``status="error"`` 的检查项，端点本身不返回 500。仅 staff 可访问。
"""

import requests
from django.conf import settings
from django.utils import timezone
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import KnowledgeDataset, LlmAppConfig, LlmEndpoint
from ..ssrf import UnsafeEndpointError, safe_request

from observability import get_logger

logger = get_logger(__name__, "smart_assistant")

# 输出契约版本号（与 chat SSE 契约同源）
FORMAT_VERSION = 1
# 外部服务探测超时（秒）——自检不能拖垮请求
PROBE_TIMEOUT_SECONDS = 3
# 智能助手在 LlmAppConfig 中的应用标识
APP_NAME = "smart_assistant"

# 检查项状态
STATUS_OK = "ok"
STATUS_WARN = "warn"
STATUS_ERROR = "error"


def _probe_http(url: str, timeout: int = PROBE_TIMEOUT_SECONDS, *, requester=None, resolver=None):
    """轻量 HTTP 探测；仅返回固定安全细节，不暴露上游内容或异常文本。"""
    try:
        resp = safe_request(
            "GET", url, requester=requester, resolver=resolver,
            timeout=timeout,
        )
        return True, f"HTTP {resp.status_code}"
    except UnsafeEndpointError:
        return False, "端点地址不允许"
    except requests.Timeout:
        return False, "请求超时"
    except requests.RequestException:
        return False, "服务不可达"
    except (ValueError, OSError):
        return False, "探测失败"


def _check(name: str, status: str, kind: str, message: str, hint: str = "") -> dict:
    """构造单个检查项（字段顺序即输出契约）。"""
    return {"name": name, "status": status, "kind": kind, "message": message, "hint": hint}


# ---------------------------------------------------------------------------
# 各检查项（每个函数返回检查项列表，不抛异常由 DoctorView 统一兜底）
# ---------------------------------------------------------------------------


def _check_llm_config() -> list:
    """检查智能助手 LLM 应用配置是否存在且激活。"""
    config = LlmAppConfig.objects.filter(app_name=APP_NAME, is_active=True).select_related("endpoint").first()
    if config is None:
        return [
            _check(
                "llm_config",
                STATUS_ERROR,
                "no_llm_endpoint",
                "智能助手未配置可用的 LLM 应用配置，所有问答将失败",
                "请前往管理后台 → AI 应用配置 LLM 端点",
            )
        ]
    return [
        _check(
            "llm_config",
            STATUS_OK,
            "ok",
            f"智能助手 LLM 应用配置已就绪（模型：{config.model_name}，端点：{config.endpoint.name}）",
        )
    ]


def _check_llm_endpoints() -> list:
    """逐个探测激活的 LLM 端点可达性（优先 /v1/models，失败回退基址）。"""
    endpoints = list(LlmEndpoint.objects.filter(is_active=True).order_by("priority"))
    if not endpoints:
        return [
            _check(
                "llm_endpoints",
                STATUS_ERROR,
                "no_llm_endpoint",
                "没有任何激活的 LLM API 端点",
                "请前往管理后台 → AI 应用配置 LLM 端点",
            )
        ]
    checks = []
    for endpoint in endpoints:
        base = endpoint.api_endpoint.rstrip("/")
        reachable, detail = _probe_http(f"{base}/v1/models")
        if not reachable:
            # 部分服务不暴露 /v1/models，回退探测基址（任意 HTTP 响应即视为可达）
            fallback_reachable, fallback_detail = _probe_http(endpoint.api_endpoint)
            reachable = fallback_reachable
            detail = f"{detail}；基址探测：{fallback_detail}"
        if reachable:
            checks.append(
                _check(f"llm_endpoint:{endpoint.name}", STATUS_OK, "ok", f"端点「{endpoint.name}」可达（{detail}）")
            )
        else:
            checks.append(
                _check(
                    f"llm_endpoint:{endpoint.name}",
                    STATUS_ERROR,
                    "llm_unavailable",
                    f"端点「{endpoint.name}」不可达：{detail}",
                    "LLM 服务暂时不可用，请稍后重试或检查端点连通性",
                )
            )
    return checks


def _check_ollama_fallback() -> list:
    """探测 Ollama 兜底服务可达性（仅降级链路，不可达只告警）。"""
    base_url = getattr(settings, "OLLAMA_BASE_URL", "")
    if not base_url:
        return [
            _check(
                "ollama_fallback",
                STATUS_WARN,
                "ollama_unavailable",
                "未配置 OLLAMA_BASE_URL，LLM 端点全部失败时无兜底可用",
                "建议在环境变量中配置 OLLAMA_BASE_URL",
            )
        ]
    reachable, detail = _probe_http(base_url)
    if reachable:
        return [_check("ollama_fallback", STATUS_OK, "ok", f"Ollama 兜底服务可达（{detail}）")]
    return [
        _check(
            "ollama_fallback",
            STATUS_WARN,
            "ollama_unavailable",
            f"Ollama 兜底服务不可达：{detail}",
            "不影响主 LLM 链路；但端点全部失败时将无法降级，建议检查 Ollama 服务状态",
        )
    ]


def _check_ragflow() -> list:
    """检查 Ragflow 配置是否存在且 api_endpoint 可达。"""
    # 延迟导入：避免 smart_assistant 在 ragflow_service 未安装/未迁移时整体不可用
    from ragflow_service.models import RagflowConfig

    config = RagflowConfig.objects.filter(is_active=True).first()
    if config is None:
        return [
            _check(
                "ragflow",
                STATUS_ERROR,
                "ragflow_unavailable",
                "未配置可用的 Ragflow 配置，知识库问答（knowledge_qa）不可用",
                "请在管理后台配置 Ragflow 服务后重试",
            )
        ]
    reachable, detail = _probe_http(config.api_endpoint)
    if reachable:
        return [
            _check(
                "ragflow",
                STATUS_OK,
                "ok",
                f"Ragflow 配置「{config.name}」可达（{detail}）",
            )
        ]
    return [
        _check(
            "ragflow",
            STATUS_ERROR,
            "ragflow_unavailable",
            f"Ragflow 配置「{config.name}」不可达：{detail}",
            "知识库服务暂时不可用",
        )
    ]


def _check_datasets() -> list:
    """统计激活的知识库数据集数量（0 个只告警——知识库可为可选能力）。"""
    active_count = KnowledgeDataset.objects.filter(is_active=True).count()
    if active_count == 0:
        return [
            _check(
                "datasets",
                STATUS_WARN,
                "no_active_dataset",
                "没有激活的知识库数据集，知识库问答将无数据可查",
                "建议在知识库管理中创建并激活至少一个数据集",
            )
        ]
    return [_check("datasets", STATUS_OK, "ok", f"已激活 {active_count} 个知识库数据集")]


def _rate_limit_check(name: str, limit_const: int, env_name: str, base_hint: str) -> dict:
    """构建单个限流配置检查项(信息级,恒 ok)。

    P1A-2 新增:被 `_check_cache_rate_limit` 调用两次,分别产出
    `cache_rate_limit`(chat 阈值)与 `cache_write_rate_limit`(写工具阈值)两项。
    ``base_hint`` 沿用既有缓存/中间件状态提示,保证 doctor 端点响应字段稳定。
    """
    backend = settings.CACHES.get("default", {}).get("BACKEND", "")
    backend_short = backend.rsplit(".", 1)[-1] or "未配置"
    config = {
        "limit": limit_const,
        "window_seconds": 60,
        "env_name": env_name,
        "cache_backend": backend,
    }
    return {
        "name": name,
        "status": STATUS_OK,
        "kind": "info",
        "message": (f"速率限制配置：{backend_short} / 每用户 {config['limit']} 次/{config['window_seconds']}s"),
        "hint": base_hint,
        "config": config,
    }


def _check_cache_rate_limit() -> list:
    """信息级：缓存后端类型与限流中间件启用情况(chat + 写工具 两套同时报告)。

    P1A-2 改动:同时产出 ``cache_rate_limit`` 与 ``cache_write_rate_limit`` 两项,
    分别对应 chat 中间件阈值与 RateLimitHook(PRE_EXECUTE)写工具阈值。
    """
    backend = settings.CACHES.get("default", {}).get("BACKEND", "")
    rate_limit_enabled = any("RateLimitMiddleware" in path for path in settings.MIDDLEWARE)
    base_hint = ""
    if "LocMemCache" in backend:
        base_hint = "进程内缓存仅适用于单进程/测试环境，多进程部署请改用 Redis"
    elif not rate_limit_enabled:
        base_hint = "未检测到限流中间件，高并发场景建议启用"
    # 延迟导入避免 smart_assistant 顶层 import rate_limit 失败时拖垮整个 doctor 自检
    from smart_assistant.middleware.rate_limit import (
        SMART_ASSISTANT_WRITE_RATE_LIMIT,
        SMART_CHAT_RATE_LIMIT,
    )

    return [
        _rate_limit_check(
            "cache_rate_limit",
            SMART_CHAT_RATE_LIMIT,
            "SMART_ASSISTANT_CHAT_RATE_LIMIT",
            base_hint,
        ),
        _rate_limit_check(
            "cache_write_rate_limit",
            SMART_ASSISTANT_WRITE_RATE_LIMIT,
            "SMART_ASSISTANT_WRITE_RATE_LIMIT",
            base_hint,
        ),
    ]


# 探测原生 tool_calls 能力时使用的最小工具 schema
_PING_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "_ping",
        "description": "连通性探测用最小工具，无需参数",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
        "strict": True,
    },
}


def _check_native_tool_calls() -> list:
    """向激活 LlmEndpoint 发最小 tool_calls 探测,缓存 native_tool_calls 能力。

    契约:
    - 无激活端点 → warn/no_llm_endpoint
    - 探测成功且收到 tool_calls → ok + 缓存 ``native_tool_calls=True``
    - 探测成功但无 tool_calls → ok + 缓存 ``native_tool_calls=False``
    - 探测异常 → error/endpoint_probe_failed(不 500)

    ``model_capabilities`` 为 JSONField(default=list),历史数据是 ``list[dict]`` 形态;
    读写路径加 ``isinstance(cap, dict)`` 类型守卫确保不破坏其它键(向后兼容)。
    """
    from llm_service.router import LLMRouter

    endpoint = LlmEndpoint.objects.filter(is_active=True).order_by("priority").first()
    if endpoint is None:
        return [
            _check(
                "native_tool_calls",
                STATUS_WARN,
                "no_llm_endpoint",
                "无激活 LLM 端点,无法探测 native tool_calls 能力",
                "请在管理后台激活至少一个 LLM 端点",
            )
        ]

    try:
        router = LLMRouter()
        _content, _usage, tool_calls = router.generate_with_tools(
            messages=[{"role": "user", "content": "ping"}],
            tools=[_PING_TOOL_SCHEMA],
            tool_choice="auto",
            endpoint_url=endpoint.api_endpoint,
        )
        supports = bool(tool_calls)
    except Exception as exc:
        logger.warning("native_tool_calls 探测失败（%s）", type(exc).__name__)
        return [
            _check(
                "native_tool_calls",
                STATUS_ERROR,
                "endpoint_probe_failed",
                "探测端点 tool_calls 能力失败",
                "LLM 端点暂时不可用,AgentOrchestrator 将自动降级到 JSON 路径",
            )
        ]

    # 缓存 native_tool_calls 到 model_capabilities(``isinstance(cap, dict)`` 类型守卫)
    caps = endpoint.model_capabilities or []
    if isinstance(caps, list):
        updated = False
        for cap in caps:
            if isinstance(cap, dict):
                cap["native_tool_calls"] = supports
                updated = True
                break
        if not updated:
            caps.append({"native_tool_calls": supports})
    elif isinstance(caps, dict):
        caps["native_tool_calls"] = supports
    else:
        caps = [{"native_tool_calls": supports}]
    endpoint.model_capabilities = caps
    endpoint.save(update_fields=["model_capabilities"])

    if supports:
        return [
            _check(
                "native_tool_calls",
                STATUS_OK,
                "ok",
                f"端点「{endpoint.name}」支持 native tool_calls=True",
            )
        ]
    return [
        _check(
            "native_tool_calls",
            STATUS_OK,
            "ok",
            f"端点「{endpoint.name}」不支持 native tool_calls=False(将走 JSON 路径)",
        )
    ]


class DoctorView(APIView):
    """智能助手 doctor 自检：只读诊断，供管理后台运维面板使用。

    权限：IsAuthenticated + is_staff（非 staff 返回 403，未认证返回 401）。
    """

    permission_classes = [IsAuthenticated, IsAdminUser]

    #: 检查项函数注册表（顺序即输出顺序）
    CHECKERS = (
        _check_llm_config,
        _check_llm_endpoints,
        _check_ollama_fallback,
        _check_ragflow,
        _check_datasets,
        _check_cache_rate_limit,
        _check_native_tool_calls,
    )

    def get(self, request):
        return Response(get_doctor_status())


def get_doctor_status() -> dict:
    """构建 doctor 自检结果(P1A-2 提取,供 ``TestDoctorWriteRateLimitCheck`` 等
    直接调用,无需走 HTTP 路径)。

    复用 ``DoctorView.CHECKERS`` 注册表与 ``DoctorView.get`` 同一执行流程:
    - 顺序遍历各 checker,``checker()`` 返回 ``list[dict]`` 检查项
    - 单项异常被捕获并降级为 ``internal_error`` 检查项(端点不返回 500)
    - 汇总 ``status`` 计数后组装与 API 同构响应 dict
    """
    checks = []
    for checker in DoctorView.CHECKERS:
        checker_name = getattr(checker, "__name__", "unknown_check")
        try:
            checks.extend(checker())
        except Exception as exc:  # 防御性兜底：单项异常不拖垮整个自检
            logger.warning("doctor 检查项 %s 执行异常（%s）", checker_name, type(exc).__name__)
            checks.append(
                _check(
                    checker_name,
                    STATUS_ERROR,
                    "internal_error",
                    "检查项执行异常",
                    "服务异常，请稍后重试",
                )
            )
    summary = {STATUS_OK: 0, STATUS_WARN: 0, STATUS_ERROR: 0}
    for item in checks:
        summary[item["status"]] = summary.get(item["status"], 0) + 1
    return {
        "format_version": FORMAT_VERSION,
        "checked_at": timezone.now().isoformat(),
        "summary": summary,
        "checks": checks,
    }
