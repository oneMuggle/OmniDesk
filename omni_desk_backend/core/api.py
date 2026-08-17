"""Version info, changelog, and migration status API endpoints."""

import logging
import re
from pathlib import Path

from django.conf import settings
from django.db import connection, connections
from django.db import migrations as django_migrations
from django.db.migrations.loader import MigrationLoader
from django.db.utils import OperationalError
from rest_framework import status as http_status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from core.throttles import ClientErrorAnonThrottle

logger = logging.getLogger(__name__)

# 服务端字段脱敏白名单:仅保留这些字段,其余键直接丢弃,防止前端漏脱敏或恶意 payload
_CLIENT_ERROR_ALLOWED_KEYS = {"kind", "message", "stack", "source", "url", "ua", "extra", "request_id"}
# 这些 key 即使出现在 extra 字典里也要清掉(防止嵌套泄露)
_CLIENT_ERROR_SENSITIVE_KEYS = re.compile(
    r"(password|passwd|token|refresh|secret|authorization|cookie|session|api[_-]?key)",
    re.IGNORECASE,
)
# URL 查询串里的敏感参数(登录/重置/OAuth 回调常带)。url 字段整值打码,
# 清单与前端 logger.js 的 SENSITIVE_URL_PARAMS 保持一致(defense in depth)。
_URL_SENSITIVE_QUERY = re.compile(
    r"([?&])(access_token|refresh_token|token|password|passwd|secret|api[_-]?key|code|sessionid)=[^&]*",
    re.IGNORECASE,
)


def _scrub_url(url: str) -> str:
    return _URL_SENSITIVE_QUERY.sub(r"\1\2=<redacted>", url)


def _sanitize_client_error_payload(payload: dict) -> dict:
    """服务端兜底脱敏:仅保留白名单键,递归清理敏感嵌套键。

    前端 logger.report() 已经过滤了 password/token 等字段,但服务端必须再做一次兜底,
    防止前端被改坏或恶意构造 payload 写日志。
    """
    if not isinstance(payload, dict):
        return {}
    cleaned = {}
    for k, v in payload.items():
        if k not in _CLIENT_ERROR_ALLOWED_KEYS:
            continue
        if isinstance(v, str):
            # 字符串值做长度截断,防止恶意大 payload 撑爆日志;url 额外做敏感参数打码
            truncated = v[:5000] if k == "stack" else v[:500]
            cleaned[k] = _scrub_url(truncated) if k == "url" else truncated
        elif isinstance(v, dict):
            # extra 字段:递归清敏感键
            cleaned[k] = {ek: ev for ek, ev in v.items() if not _CLIENT_ERROR_SENSITIVE_KEYS.search(str(ek))}
        else:
            cleaned[k] = v
    return cleaned


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([ClientErrorAnonThrottle])
def client_error_report(request):
    """前端错误上报端点(浏览器侧 ErrorBoundary / window.onerror / unhandledrejection)。

    设计要点:
    - AllowAny:覆盖未登录错误(登录页崩溃、网络层错误、初始化错误)
    - 10/min/IP 限流:防止错误循环/异常刷屏
    - 服务端兜底脱敏:不依赖前端正确实现
    - 走 logger.error + extra=event=client_error,与后端日志统一格式(可被 SafeTextFormatter 关联 request_id)
    """
    payload = _sanitize_client_error_payload(request.data or {})
    request_id = getattr(request, "request_id", "-")
    logger.error(
        "client_error: kind=%s message=%s source=%s rid=%s",
        payload.get("kind", "unknown"),
        payload.get("message", ""),
        payload.get("source", ""),
        request_id,
        extra={
            "event": "client_error",
            "request_id": request_id,
            "stack": payload.get("stack", ""),
            "ua": payload.get("ua", ""),
            "url": payload.get("url", ""),
            "extra": payload.get("extra", {}),
        },
    )
    return Response(status=http_status.HTTP_204_NO_CONTENT)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def version_info(request):
    import django

    raw_version = getattr(settings, "APP_VERSION", "0.0.0-dev")
    # 解析渠道(从 VERSION 后缀),失败 fallback 到 stable
    channel = "stable"
    try:
        from core.version_utils import parse_version

        parsed = parse_version(raw_version)
        if parsed.channel == "rc":
            channel = "preview"
        elif parsed.channel in ("alpha", "beta"):
            channel = parsed.channel
    except (ValueError, ImportError):
        pass

    return Response(
        {
            "version": raw_version,
            "channel": channel,
            "build_time": getattr(settings, "BUILD_TIME", "unknown"),
            "django_version": f"{django.VERSION[0]}.{django.VERSION[1]}.{django.VERSION[2]}",
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def changelog(request):
    # 与 core/version.py 同样采用多路径 fallback,按优先级排序:
    #   1. 生产容器标准位置 /etc/omnidesk/CHANGELOG.md(由 Dockerfile COPY,不受 compose bind mount 影响)
    #   2. 开发环境相对路径(项目根在 parent.parent.parent)
    #   3. 生产容器备用相对路径(项目根在 parent.parent,所有代码位于 /usr/src/app/)
    #      注:若 compose 用 bind mount 覆盖 /usr/src/app,此路径会失效,优先使用 /etc/omnidesk/
    candidates = [
        Path("/etc/omnidesk/CHANGELOG.md"),
        Path(__file__).resolve().parent.parent.parent / "deployment" / "docker" / "CHANGELOG.md",
        Path(__file__).resolve().parent.parent / "deployment" / "docker" / "CHANGELOG.md",
    ]
    changelog_path = next((p for p in candidates if p.is_file()), None)
    if changelog_path:
        content = changelog_path.read_text(encoding="utf-8")
    else:
        content = "# 更新日志\n\n暂无更新日志。"
    return Response({"changelog": content})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def migration_status(request):
    """枚举 migration graph,返回 applied / pending / has_destructive。

    数据源: MigrationLoader.graph.nodes(而非 apps.get_app_configs() + app_config.migrations),
    保证对第三方 app 与无 migrations 模块属性的 app 同样生效。

    destructive 操作: DeleteModel / RemoveField / RemoveConstraint。
    """
    loader = MigrationLoader(connection)
    loader.build_graph()

    applied_list = []
    for app, name in sorted(loader.applied_migrations):
        applied_list.append({"app": app, "name": name})

    pending_list = []
    destructive = False
    for node_key, migration in loader.graph.nodes.items():
        app_label, migration_name = node_key
        if node_key in loader.applied_migrations:
            continue
        # 跳过包标记(如 __init__.py)
        if migration.name.startswith("__"):
            continue

        ops = []
        for op in migration.operations:
            op_type = type(op).__name__
            if isinstance(op, django_migrations.DeleteModel):
                ops.append({"type": op_type, "model": op.name, "destructive": True})
                destructive = True
            elif isinstance(op, django_migrations.RemoveField):
                ops.append(
                    {
                        "type": op_type,
                        "model": op.model_name,
                        "field": op.name,
                        "destructive": True,
                    }
                )
                destructive = True
            elif isinstance(op, django_migrations.RemoveConstraint):
                ops.append(
                    {
                        "type": op_type,
                        "model": op.model_name,
                        "name": getattr(op, "name", None),
                        "destructive": True,
                    }
                )
                destructive = True
            elif isinstance(op, django_migrations.AddField):
                ops.append({"type": op_type, "model": op.model_name, "field": op.name})
            elif isinstance(op, django_migrations.AlterField):
                ops.append({"type": op_type, "model": op.model_name, "field": op.name})
            elif isinstance(op, django_migrations.CreateModel):
                ops.append({"type": op_type, "model": op.name})
            else:
                ops.append({"type": op_type})

        pending_list.append(
            {
                "app": app_label,
                "name": migration_name,
                "operations": ops,
            }
        )

    return Response(
        {
            "applied": applied_list,
            "applied_count": len(applied_list),
            "pending": pending_list,
            "pending_count": len(pending_list),
            "has_destructive": destructive,
        }
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def readiness_check(request):
    """就绪检查端点：检查 DB / Redis / Celery 是否就绪(用于 K8s/容器 readinessProbe)。

    与 /api/health/ 区别:
    - /api/health/  → 进程是否存活(livenessProbe)
    - /api/system/ready/ → 业务依赖是否就绪(readinessProbe)

    返回 200 表示就绪,503 表示未就绪;任一依赖失败不影响其他依赖的检测。
    """
    checks = {}
    overall_ok = True

    # 1. Database
    try:
        db_conn = connections["default"]
        db_conn.ensure_connection()
        with db_conn.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        checks["database"] = {"status": "ok"}
    except (OperationalError, Exception) as e:
        overall_ok = False
        checks["database"] = {"status": "error", "error": str(e)}
        logger.error("Readiness check: database unreachable: %s", e)

    # 2. Redis (django-redis cache)
    try:
        from django.core.cache import cache

        cache.set("readiness_probe", "1", timeout=5)
        cached = cache.get("readiness_probe")
        if cached == "1":
            checks["cache"] = {"status": "ok"}
        else:
            overall_ok = False
            checks["cache"] = {"status": "error", "error": "cache round-trip failed"}
    except Exception as e:
        overall_ok = False
        checks["cache"] = {"status": "error", "error": str(e)}
        logger.error("Readiness check: cache unreachable: %s", e)

    # 3. Celery worker (best-effort ping, 不阻塞)
    try:
        from django.conf import settings

        if getattr(settings, "CELERY_BROKER_URL", None):
            from omni_desk_backend.celery import app as celery_app

            inspector = celery_app.control.inspect(timeout=1.0)
            ping_result = inspector.ping()
            if ping_result:
                worker_count = sum(len(v) for v in ping_result.values() if v)
                checks["celery"] = {"status": "ok", "workers": worker_count}
            else:
                # 静默:N 个 worker 可能暂时空闲,仅记录 debug 日志
                checks["celery"] = {"status": "warning", "workers": 0}
                logger.debug("Readiness check: no celery workers responded to ping")
        else:
            checks["celery"] = {"status": "skipped", "reason": "CELERY_BROKER_URL not configured"}
    except Exception as e:
        # Celery 检查失败不阻塞(可能是网络抖动)
        checks["celery"] = {"status": "error", "error": str(e)}
        logger.warning("Readiness check: celery probe failed: %s", e)

    status_code = 200 if overall_ok else 503
    return Response(
        {
            "status": "ready" if overall_ok else "not_ready",
            "checks": checks,
        },
        status=status_code,
    )
