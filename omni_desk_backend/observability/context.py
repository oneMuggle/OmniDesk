"""Context variables for cross-cutting observability concerns.

Provides ContextVar that flows through HTTP request lifecycle,
Celery task execution, and Python asyncio tasks.
"""
from __future__ import annotations

from contextvars import ContextVar

request_id_var: ContextVar[str | None] = ContextVar(
    "request_id",
    default=None,
)
