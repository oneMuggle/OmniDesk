# omni_desk_backend/omni_desk_backend/celery.py
"""Celery application factory with request_id propagation."""

from __future__ import annotations

import os
from typing import Any

from celery import Celery, Task, signals
from django.conf import settings

from observability.context import request_id_var

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "omni_desk_backend.settings.local")

app = Celery("omni_desk_backend")


class RequestIdTask(Task):
    """Task base class that propagates request_id to the worker.

    On ``apply_async`` it snapshots the current request_id from
    ``request_id_var`` and embeds it into the task headers so the worker
    can re-establish the context via :class:`RequestIdTaskMiddleware`.
    """

    abstract = True

    def apply_async(self, args=None, kwargs=None, **options):
        options.setdefault("headers", {})
        rid = request_id_var.get()
        if rid and "request_id" not in options["headers"]:
            options["headers"]["request_id"] = rid
        return super().apply_async(args=args, kwargs=kwargs, **options)


class RequestIdTaskMiddleware:
    """Celery signal handlers that propagate request_id into contextvar.

    Registered via the module-level signal connect functions below. Kept as
    a class so the propagation logic has a single implementation, directly
    testable without a broker. It manages context only -- it never calls
    ``task.run`` (the worker executes the task; calling ``run`` here would
    double-execute it).
    """

    def before_task_publish(self, sender=None, headers=None, body=None, **kwargs: Any) -> None:
        rid = request_id_var.get()
        if rid and headers is not None and "request_id" not in headers:
            headers["request_id"] = rid

    def process_task(self, task, args, kwargs):
        # token 存 task.request(每次执行独立的 Context),而非共享的 task 实例;
        # 否则 --pool=threads/eventlet/gevent 下同一实例并发执行会互相覆盖 token。
        rid = (getattr(task.request, "headers", None) or {}).get("request_id")
        if rid:
            token = request_id_var.set(rid)
            task.request._omni_request_id_token = token
        else:
            task.request._omni_request_id_token = None

    def process_after_return(self, state=None, task=None, **kwargs: Any) -> None:
        token = getattr(task.request, "_omni_request_id_token", None) if getattr(task, "request", None) else None
        if token is not None:
            request_id_var.reset(token)


@signals.before_task_publish.connect
def _on_before_task_publish(sender=None, headers=None, body=None, **kwargs):
    RequestIdTaskMiddleware().before_task_publish(sender=sender, headers=headers, body=body, **kwargs)


@signals.task_prerun.connect
def _on_task_prerun(sender=None, task_id=None, task=None, args=None, kwargs=None, **extra):
    if sender is not None:
        RequestIdTaskMiddleware().process_task(sender, args, kwargs)


@signals.task_postrun.connect
def _on_task_postrun(sender=None, task_id=None, task=None, args=None, kwargs=None, retval=None, state=None, **extra):
    if sender is not None:
        RequestIdTaskMiddleware().process_after_return(state=state, task=sender)


app.Task = RequestIdTask  # type: ignore[misc]

# 链式任务(chain/group)的 request_id 继承由 RequestIdTask.apply_async 的
# contextvar 快照承担:worker 内父任务执行时 request_id_var 已持有 rid,
# 子任务 publish 时自动注入 headers。

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()

# --- 联培生考核批次自动创建 (2026-08-19 从归档分支恢复) ---
# 每月 N 号 02:00 触发(N 来自 settings.JOINT_STUDENT_CYCLE_DAY)；
# 使用 update() 而非赋值,保留 settings.CELERY_BEAT_SCHEDULE 或其他模块追加的条目。
app.conf.beat_schedule.update(
    {
        "create-monthly-assessment-cycle": {
            "task": "joint_students.check_and_create_assessment_cycle",
            "cron": f"0 2 {settings.JOINT_STUDENT_CYCLE_DAY} * *",
            "kwargs": {"trigger_source": "auto"},
        },
    }
)
