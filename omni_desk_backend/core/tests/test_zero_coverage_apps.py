"""Each zero-coverage app must now have at least one observability logger."""
from __future__ import annotations

import pathlib

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]

ZERO_COVERAGE_APPS = [
    "office_assistant", "meeting_rooms", "dify_apps", "projects",
    "memos", "communication", "news", "ebooks", "config",
]
TARGET_FILES = ("views.py", "tasks.py", "services.py")


@pytest.mark.parametrize("app", ZERO_COVERAGE_APPS)
def test_app_has_observability_logger(app):
    app_dir = REPO_ROOT / app
    found = False
    for fname in TARGET_FILES:
        path = app_dir / fname
        if path.exists() and "from observability import get_logger" in path.read_text(encoding="utf-8"):
            found = True
            break
    assert found, f"{app}: no observability logger in {TARGET_FILES}"
