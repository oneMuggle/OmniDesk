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

# Ensure Mineru API Key is not left as default placeholder
_MINERU_KEY = os.getenv("MINERU_API_KEY", "")
if not _MINERU_KEY or _MINERU_KEY == "YOUR_MINERU_API_KEY":
    raise ImproperlyConfigured(
        "Production settings require a valid MINERU_API_KEY. "
        "Set it in your environment, do not use the default placeholder."
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

# HTTPS settings
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_HTTPONLY = True

# Security headers
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/3.2/howto/static-files/
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")

# Migration safety — migrations must be run explicitly via management commands
# and are not auto-applied on app startup.
