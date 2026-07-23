"""关键事件常量定义。

所有事件名采用 snake_case,分四类:
- auth: 认证(登录、刷新、登出)
- permission: 权限校验
- celery_task: 异步任务
- system: 系统级(启动、关闭)

新增事件请遵循:
- 命名: <category>.<action>.<result> 例: auth.login.success
- 必填字段见 docstring
"""

from __future__ import annotations


class AuthEvent:
    """认证相关事件。"""

    LOGIN_SUCCESS = "auth.login.success"  # user_id, ip
    LOGIN_FAILURE = "auth.login.failure"  # username, reason, ip
    LOGOUT = "auth.logout"  # user_id
    JWT_REFRESH_SUCCESS = "auth.jwt.refresh.success"  # user_id
    JWT_REFRESH_FAILURE = "auth.jwt.refresh.failure"  # user_id, reason


class PermissionEvent:
    """权限相关事件。"""

    PERMISSION_DENIED = "permission.denied"  # user_id, resource, action


class CeleryEvent:
    """Celery 任务事件。"""

    TASK_START = "celery.task.start"  # task_name, task_id
    TASK_SUCCESS = "celery.task.success"  # task_name, task_id, duration_ms
    TASK_FAILURE = "celery.task.failure"  # task_name, task_id, error, retry_count
    TASK_RETRY = "celery.task.retry"  # task_name, task_id, reason
