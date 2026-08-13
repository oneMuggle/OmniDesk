# omni_desk_backend/core/tests/test_silent_exceptions.py
"""Guard against growth of silent exception swallowing.

Counts ``except ...: pass`` blocks in each app under
``omni_desk_backend/`` and asserts the count does not exceed the
baseline recorded in :mod:`core.tests.baselines`.
"""
from __future__ import annotations

import ast
import json
import pathlib

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
BASELINE_PATH = (
    pathlib.Path(__file__).resolve().parent / "baselines" / "except_pass_count.json"
)


def _count_except_pass(app_dir: pathlib.Path) -> int:
    count = 0
    for py_file in app_dir.rglob("*.py"):
        if "migrations" in py_file.parts:
            continue
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
                    count += 1
    return count


def _current_counts() -> dict[str, int]:
    out: dict[str, int] = {}
    for app_dir in sorted(REPO_ROOT.iterdir()):
        if not app_dir.is_dir():
            continue
        if app_dir.name.startswith(".") or app_dir.name == "__pycache__":
            continue
        out[app_dir.name] = _count_except_pass(app_dir)
    return out


def test_except_pass_count_does_not_grow():
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    actual = _current_counts()
    regressions = {
        app: (actual.get(app, 0), baseline[app])
        for app in baseline
        if actual.get(app, 0) > baseline[app]
    }
    assert not regressions, (
        f"except:pass count grew in: "
        + ", ".join(f"{app} ({a} > {b})" for app, (a, b) in regressions.items())
    )

    # 新增目录守卫:任何不在 baseline 且含 except:pass 的目录直接 FAIL
    # (新增 app 或向非 baseline 目录写入 except:pass 时,需刷新 baseline)
    new_dirs = {
        app: count
        for app, count in actual.items()
        if app not in baseline and count > 0
    }
    assert not new_dirs, (
        "except:pass found in directories not in baseline: "
        + ", ".join(f"{app} ({count})" for app, count in sorted(new_dirs.items()))
    )
