import logging
from datetime import datetime, timezone

from django.conf import settings
from django.db import connections
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

logger = logging.getLogger(__name__)


@api_view(["GET"])
@permission_classes([AllowAny])
def health_check(request):
    """健康检查端点：检查数据库连通性和版本信息"""
    health = {
        "status": "ok",
        "database": "ok",
        "version": getattr(settings, "APP_VERSION", "0.0.0-dev"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    status_code = 200

    try:
        db_conn = connections["default"]
        db_conn.ensure_connection()
    except Exception as e:
        logger.error("Database health check failed: %s", e)
        health["status"] = "error"
        health["database"] = "error"
        health["database_error"] = str(e)
        status_code = 503

    return Response(health, status=status_code)
