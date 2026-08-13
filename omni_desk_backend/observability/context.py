"""Context variables for cross-cutting observability concerns.

Provides the ``request_id_var`` ContextVar, currently injected by the
``RequestIdMiddleware`` during the HTTP request lifecycle and by asyncio
task scenarios. Celery cross-task propagation is implemented via
``omni_desk_backend.celery.RequestIdTask`` (apply_async captures the
current contextvar into task headers; the ``task_prerun`` signal restores
it on the worker side).
"""

from __future__ import annotations

from contextvars import ContextVar

request_id_var: ContextVar[str | None] = ContextVar(
    "request_id",
    default=None,
)
