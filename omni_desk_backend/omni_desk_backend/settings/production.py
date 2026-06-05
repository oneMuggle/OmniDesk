import os

from django.core.exceptions import ImproperlyConfigured

from .base import *

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False

# Ensure SECRET_KEY is set in production — fail loudly if not set
if not os.getenv("SECRET_KEY"):
    raise ImproperlyConfigured(
        "Production settings require SECRET_KEY environment variable. Set a strong, fixed SECRET_KEY for production."
    )

# MINERU_API_KEY is OPTIONAL — document parsing feature degrades gracefully
# when missing (see documents/file_processing.py for the runtime check).
# 仅当用户显式设为占位符时才报错(防止"忘了改"),其他情况(未设置/已设真实值)均允许。
_MINERU_KEY = os.getenv("MINERU_API_KEY", "")
if _MINERU_KEY in ("YOUR_MINERU_API_KEY", "<YOUR_MINERU_API_KEY>"):
    raise ImproperlyConfigured(
        "MINERU_API_KEY is set to a placeholder value. "
        "Either unset it (to disable document parsing) or provide a real key."
    )

# Ensure PostgreSQL is configured in production — fail loudly if not set
if not os.getenv("POSTGRES_DB"):
    raise ImproperlyConfigured(
        "Production settings require POSTGRES_DB environment variable. Running on SQLite in production is not allowed."
    )

ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",")

# Disable Browsable API in production
REST_FRAMEWORK = {
    **REST_FRAMEWORK,
    "DEFAULT_RENDERER_CLASSES": ("rest_framework.renderers.JSONRenderer",),
}

# Database
# https://docs.djangoproject.com/en/3.2/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("POSTGRES_DB"),
        "USER": os.getenv("POSTGRES_USER"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD"),
        "HOST": os.getenv("DB_HOST"),
        "PORT": os.getenv("DB_PORT", 5432),
        "CONN_MAX_AGE": 600,
    }
}

# CSRF and CORS settings for production
CORS_ALLOWED_ORIGINS = os.environ.get("CORS_ALLOWED_ORIGINS", "").split(",")
CSRF_TRUSTED_ORIGINS = os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(",")

# ──────────────────────────────────────────────────────────────────────
# HTTPS / Cookie security
# ──────────────────────────────────────────────────────────────────────
# USE_HTTPS 控制 HTTPS 相关 cookie / 头:
#   - "true"  → 启用 HTTPS 全套安全加固(cookie secure + HSTS + SSL redirect)
#   - "false" → 纯 HTTP 部署(默认),允许 cookie 在 HTTP 下传输,否则登录后会立即丢失会话
# 注意:USE_HTTPS=true 时,必须确保 nginx/反代正确转发 X-Forwarded-Proto 头。
USE_HTTPS = os.environ.get("USE_HTTPS", "false").lower() == "true"

CSRF_COOKIE_SECURE = USE_HTTPS
SESSION_COOKIE_SECURE = USE_HTTPS
CSRF_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_HTTPONLY = True

# Security headers
# SECURE_SSL_REDIRECT / HSTS 仅在 USE_HTTPS=True 时启用(否则 HTTP 部署会循环重定向)
SECURE_SSL_REDIRECT = USE_HTTPS
SECURE_HSTS_SECONDS = 31536000 if USE_HTTPS else 0  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = USE_HTTPS
SECURE_HSTS_PRELOAD = USE_HTTPS
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

# 让 Django 通过 nginx/反代转发的 X-Forwarded-Proto 头识别原始协议,
# 这样在 HTTPS 反向代理 + 内部 HTTP 容器架构下,Django 仍能正确判断 request.is_secure()。
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/3.2/howto/static-files/
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")

# Migration safety — migrations must be run explicitly via management commands
# and are not auto-applied on app startup.

# ──────────────────────────────────────────────────────────────────────
# Structured JSON logging (production)
# ──────────────────────────────────────────────────────────────────────
# 生产环境输出 JSON 格式日志,便于 ELK / Loki / 其它日志聚合系统消费。
# 开发环境(test/local)保留 base.py 的 verbose 格式,便于人工阅读。
# 依赖:python-json-logger==2.0.7(在 requirements.in)
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "format": "%(asctime)s %(levelname)s %(name)s %(module)s %(message)s",
            "rename_fields": {"asctime": "timestamp", "levelname": "level", "name": "logger"},
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": os.getenv("DJANGO_LOG_LEVEL", "INFO"),
            "propagate": True,
        },
        "django.request": {
            "handlers": ["console"],
            "level": "WARNING",  # 4xx 不刷屏,5xx 一定记录
            "propagate": False,
        },
    },
    "root": {
        "handlers": ["console"],
        "level": os.getenv("DJANGO_LOG_LEVEL", "INFO"),
    },
}
