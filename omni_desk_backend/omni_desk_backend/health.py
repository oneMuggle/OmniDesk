from observability import get_logger
from datetime import datetime, timezone

import redis as redis_lib
from django.conf import settings
from django.db import connections
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

logger = get_logger(__name__, "omni_desk_backend.health")


def _get_redis_client():
    """构造 Redis 探针客户端(独立函数便于测试 mock)。"""
    return redis_lib.Redis.from_url(settings.CELERY_BROKER_URL, socket_timeout=0.5)


@api_view(["GET"])
@permission_classes([AllowAny])
def health_check(request):
    """健康检查端点(livenessProbe):DB 与 Redis 为硬依赖,Celery 为软依赖。

    - 全部健康:200 {"status": "ok", ...}
    - DB 或 Redis 失败:503 {"status": "error", "<component>": "unreachable"}
    - Celery 失败:不阻断(仍 200),响应体附加 "celery": "degraded"
    """
    health = {
        "status": "ok",
        "database": "ok",
        "version": getattr(settings, "APP_VERSION", "0.0.0-dev"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    status_code = 200

    # 1. Database 硬探针
    try:
        db_conn = connections["default"]
        db_conn.ensure_connection()
    except Exception as e:
        logger.error("Database health check failed: %s", e)
        # SECURITY: 对外返回固定文案,避免向未认证调用方泄露数据库连接细节(详情仅入日志)
        health["status"] = "error"
        health["database"] = "unreachable"
        status_code = 503

    # 2. Redis 硬探针(broker 连通性;失败 → 503)
    try:
        client = _get_redis_client()
        client.ping()
        health["redis"] = "ok"
    except Exception as e:
        logger.error("Redis health check failed: %s", e)
        health["status"] = "error"
        health["redis"] = "unreachable"
        status_code = 503

    # 3. Celery 软探针(worker 存活;失败仅降级,不阻断 200)
    try:
        from omni_desk_backend.celery import app as celery_app

        workers = celery_app.control.ping(timeout=0.5)
        if not workers:
            raise RuntimeError("no celery workers responded")
    except Exception as e:
        logger.warning("Celery health probe degraded: %s", e)
        if status_code == 200:
            health["status"] = "degraded"
        health["celery"] = "degraded"

    return Response(health, status=status_code)
