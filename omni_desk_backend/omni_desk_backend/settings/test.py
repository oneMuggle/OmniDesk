import tempfile

from .base import *

# Use an in-memory SQLite database for testing
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

# Use in-memory cache for tests (Redis may not be available)
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    },
    'ratelimit': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    },
}
RATELIMIT_USE_CACHE = 'ratelimit'

# To speed up tests
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]

# Disable logging during tests to clean up output
LOGGING = {}

MEDIA_ROOT = tempfile.mkdtemp()
STATIC_ROOT = tempfile.mkdtemp()

# Disable rate limiting during tests
RATELIMIT_ENABLE = False

# Silence django-ratelimit cache backend checks (LocMemCache is fine for tests)
SILENCED_SYSTEM_CHECKS = ['django_ratelimit.E003', 'django_ratelimit.W001']
