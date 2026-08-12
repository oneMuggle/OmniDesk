"""Context variables for cross-cutting observability concerns.

Provides the ``request_id_var`` ContextVar, currently injected by the
``RequestIdMiddleware`` during the HTTP request lifecycle and by asyncio
task scenarios. Celery cross-task propagation via a ``RequestIdTask``
base task is planned (Task 7 of the logging-enhancement plan) but not yet
implemented.
"""
from __future__ import annotations

from contextvars import ContextVar

request_id_var: ContextVar[str | None] = ContextVar(
    "request_id",
    default=None,
)
