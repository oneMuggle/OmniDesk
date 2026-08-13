"""Enforce ``observability.get_logger`` over stdlib ``logging.getLogger``.

Business modules must obtain loggers via ``observability.get_logger`` so
request_id / event are injected. Files in BASELINE (spec §11 — not migrated
in this plan) may still use stdlib ``logging``; any NEW usage outside the
baseline fails the build. Migrating a baseline file is always green
(subset semantics, like ``test_silent_exceptions.py``).
"""
from __future__ import annotations

import pathlib
import re

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]

# spec §11: intentionally not migrated in this plan — tracked so new usage is caught.
BASELINE = {
    "compliance/tasks.py",
    "core/api.py",
    "documents/file_processing.py",
    "events/signals.py",
    "events/tasks.py",
    "events/views/schedules.py",
    "events/views/swap.py",
    "events/views/trials.py",
    "external_integration/plugin_loader.py",
    "external_integration/plugin_sandbox.py",
    "external_integration/services/plugin_service.py",
    "external_integration/views.py",
    "file_processing/ai/query.py",
    "file_processing/tasks.py",
    "llm_service/ollama_client.py",
    "llm_service/router.py",
    "notifications/signals.py",
    "omni_desk_backend/health.py",
    "paperless_proxy/services/client.py",
    "paperless_proxy/services/outbox.py",
    "paperless_proxy/tasks.py",
    "permissions/views.py",
    "personnel/fields.py",
    "personnel/models.py",
    "ragflow_service/client.py",
    "ragflow_service/views.py",
    "search_federation/views.py",
    "sensor_management/tasks.py",
    "sensor_management/views.py",
}

_LOGGING_RE = re.compile(r"logging\.getLogger|from logging import")


def _logging_files() -> set[str]:
    hits = set()
    for py in REPO_ROOT.rglob("*.py"):
        parts = py.parts
        if (
            "migrations" in parts
            or "tests" in parts
            or "__pycache__" in parts
            or py.name.startswith("test_")
            or py.name == "tests.py"
            or py.name == "conftest.py"
            or "observability" in parts
        ):
            continue
        txt = py.read_text(encoding="utf-8", errors="ignore")
        if _LOGGING_RE.search(txt):
            hits.add(str(py.relative_to(REPO_ROOT)))
    return hits


def test_no_new_logging_getlogger_outside_baseline():
    actual = _logging_files()
    new_files = actual - BASELINE
    assert not new_files, (
        "new stdlib-logging files (migrate to observability.get_logger): "
        + ", ".join(sorted(new_files))
    )
