from .base import *

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['*']

# Database
# https://docs.djangoproject.com/en/3.2/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# CSRF and CORS settings for development
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

CSRF_TRUSTED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

# 在非HTTPS环境下, SAMESITE='None' 会被浏览器拒绝, 且 SECURE 必须为 False
CSRF_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SECURE = False # Allow CSRF cookie over HTTP for development
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_SECURE = False # Allow session cookie over HTTP for development
CSRF_COOKIE_HTTPONLY = False # Allow JS to read CSRF token for SPA
SESSION_COOKIE_HTTPONLY = True