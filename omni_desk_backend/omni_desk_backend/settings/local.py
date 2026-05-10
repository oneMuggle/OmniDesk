from .base import *
import os

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['*']

# Enable Browsable API in local development
REST_FRAMEWORK = {
    **REST_FRAMEWORK,
    'DEFAULT_RENDERER_CLASSES': (
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ),
}

# Use local memory cache for development (Redis may not be available)
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
}

# Database
# https://docs.djangoproject.com/en/3.2/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# CSRF and CORS settings for development
# CORS: regex allows any localhost port — no config changes needed when frontend port changes
CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^https?://localhost:\d+$",
    r"^https?://127\.0\.0\.1:\d+$",
]

# CSRF: frontend uses JWT (not cookies), so CSRF is mainly for Django admin access
CSRF_TRUSTED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3002",
    "http://127.0.0.1:3002",
]

# In a non-HTTPS environment, SAMESITE='None' is rejected by browsers, and SECURE must be False
CSRF_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SECURE = False # Allow CSRF cookie over HTTP for development
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_SECURE = False # Allow session cookie over HTTP for development
CSRF_COOKIE_HTTPONLY = False # Allow JS to read CSRF token for SPA
SESSION_COOKIE_HTTPONLY = True

# Smart Assistant - LLM Configuration
# Uses OpenAI-compatible API endpoint (e.g. gcli.ggchan.dev)
SMART_ASSISTANT_LLM_ENDPOINT = os.environ.get('SMART_ASSISTANT_LLM_ENDPOINT', 'https://gcli.ggchan.dev')
SMART_ASSISTANT_LLM_API_KEY = os.environ.get('SMART_ASSISTANT_LLM_API_KEY', '')
SMART_ASSISTANT_LLM_MODEL = os.environ.get('SMART_ASSISTANT_LLM_MODEL', 'gemini-2.5-pro')

# Smart Assistant - Ragflow dataset ID for knowledge base document upload and vectorization.
# Obtain from Ragflow admin panel: Datasets -> select dataset -> copy ID.
SMART_ASSISTANT_DATASET_ID = os.environ.get('SMART_ASSISTANT_DATASET_ID', '')
