"""
CI-only Django settings for `manage.py check --deploy`.

目的:让 CI runner 在不依赖真实数据库 / Redis / 外部 API 的前提下,跑 Django
内置的 `--deploy` 检查并暴露 W004/W008/W012/W016 等安全警告。

用法(CI step):
    env:
      SECRET_KEY: ci-check-only-secret-key-not-used-for-runtime-1234567890
    run: |
      DJANGO_SETTINGS_MODULE=omni_desk_backend.settings.check \\
      python manage.py check --deploy --fail-level WARNING

注意:
- SECRET_KEY 必须在 shell 层设(通过 `env:` 而非 Python 内的 os.environ.setdefault)。
  原因:settings/__init__.py 在被 import 时会立即 from .base import *,触发 base.py
  顶层读取 SECRET_KEY。如果 SECRET_KEY 仅在 check.py 内 setdefault,会晚于 __init__.py
  触发的 base.py 加载,导致 RuntimeWarning。
- 此文件只用于 CI 静态检查,**禁止**在任何运行时/WSGI 入口中引用它。
"""

from .base import *

DEBUG = False

# 允许任意 host(deploy 检查不关心 host)。
ALLOWED_HOSTS = ["*"]

# 用 SQLite 避免部署检查要求 PostgreSQL 环境变量。
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# 关闭 CORS / CSRF 来源列表(避免空字符串触发 corsheaders E013 / csrf E001)。
CORS_ALLOWED_ORIGINS = []
CSRF_TRUSTED_ORIGINS = []

# 部署检查默认假定的安全配置状态(check --deploy 默认假设生产 HTTPS 部署)。
# 故意把这些置为 False / 0 以触发 W004/W008/W012/W016 等安全警告,
# 让 CI 真正能"发现"潜在配置问题(也即本 step 的目的)。
USE_HTTPS = False
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SECURE = False
SECURE_SSL_REDIRECT = False
SECURE_HSTS_SECONDS = 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False

# 关闭 Celery(部署检查不需要连接 broker)。
# base.py 已声明 CELERY_BROKER_URL,这里只置 EAGER 避免 import 时检查 worker。
CELERY_TASK_ALWAYS_EAGER = True

