"""Version info, changelog, and migration status API endpoints."""

import logging
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.db import connection, connections
from django.db import migrations as django_migrations
from django.db.migrations.loader import MigrationLoader
from django.db.utils import OperationalError
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

logger = logging.getLogger(__name__)


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
    changelog_path = Path(__file__).resolve().parent.parent.parent.parent / "deployment" / "docker" / "CHANGELOG.md"
    if changelog_path.is_file():
        content = changelog_path.read_text(encoding="utf-8")
    else:
        content = "# 更新日志\n\n暂无更新日志。"
    return Response({"changelog": content})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def migration_status(request):
    loader = MigrationLoader(connection)
    loader.build_graph()

    applied_list = []
    for app, name in sorted(loader.applied_migrations):
        applied_list.append({"app": app, "name": name})

    pending_list = []
    destructive = False
    for app_config in apps.get_app_configs():
        app_label = app_config.label
        if not hasattr(app_config, "migrations"):
            continue
        for migration in app_config.migrations:
            if migration.name.startswith("__"):
                continue
            key = (app_label, migration.name.replace(".py", ""))
            if key in loader.applied_migrations:
                continue

            ops = []
            for op in migration.operations:
                op_type = type(op).__name__
                if isinstance(op, django_migrations.DeleteModel):
                    ops.append({"type": op_type, "model": op.name, "destructive": True})
                    destructive = True
                elif isinstance(op, django_migrations.RemoveField):
                    ops.append({"type": op_type, "model": op.model_name, "field": op.name, "destructive": True})
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
                    "name": migration.name.replace(".py", ""),
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
