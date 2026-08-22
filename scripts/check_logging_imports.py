#!/usr/bin/env python3
"""R5-B7 AST 守卫:禁止业务代码直接用 stdlib logging 构造 logger。

遍历 omni_desk_backend 下非测试 .py 文件,发现
``logging.getLogger(...)`` / ``from logging import getLogger`` 即报错退出 1,
输出违规文件与行号列表。业务代码必须走 ``observability.get_logger``,
由 LoggerAdapter 自动注入 request_id 与 event 字段。

白名单(命令行 ``--whitelist file`` 或脚本内常量):observability 自身、
第三方集成等确需 stdlib logging 的文件。

用法(CI / 本地):
    python scripts/check_logging_imports.py
    python scripts/check_logging_imports.py --whitelist scripts/logging_whitelist.txt
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TARGET_DIR = REPO_ROOT / "omni_desk_backend"

# 脚本内常量白名单:相对 omni_desk_backend 的 POSIX 路径。
# observability 自身是 logger 工厂,必须直接操作 stdlib logging。
WHITELIST = {
    "observability/__init__.py",
    "observability/context.py",
    "observability/events.py",
    "observability/formatters.py",
}

# 测试文件保留 stdlib logging(断言/fixture 更直观),不迁移。
TEST_MARKERS = ("tests", "test_")
TEST_FILENAMES = {"tests.py", "conftest.py"}


def _is_test_file(path: Path) -> bool:
    parts = path.parts
    if any(marker in parts for marker in TEST_MARKERS):
        return True
    return path.name in TEST_FILENAMES


def _load_whitelist_file(path: Path) -> set[str]:
    entries = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            entries.add(line)
    return entries


def _violations_in_file(path: Path) -> list[tuple[int, str]]:
    """AST 解析单文件,返回 (行号, 描述) 违规列表。"""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
    except SyntaxError as exc:
        # 解析失败的文件不静默放过,报告为潜在违规
        return [(exc.lineno or 0, f"syntax error prevents analysis: {exc.msg}")]

    violations: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        # 形如 logging.getLogger(...) 的属性调用(含 logging.getLogger(__name__))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            func = node.func
            if (
                func.attr == "getLogger"
                and isinstance(func.value, ast.Name)
                and func.value.id == "logging"
            ):
                violations.append((node.lineno, "logging.getLogger(...) call"))
        # from logging import getLogger(含别名)
        elif isinstance(node, ast.ImportFrom) and node.module == "logging":
            for alias in node.names:
                if alias.name == "getLogger":
                    bound = alias.asname or alias.name
                    violations.append(
                        (node.lineno, f"from logging import getLogger (bound as {bound})")
                    )
    return violations


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--whitelist",
        type=Path,
        default=None,
        help="可选白名单文件,每行一个相对 omni_desk_backend 的 POSIX 路径,# 开头为注释",
    )
    args = parser.parse_args(argv)

    whitelist = WHITELIST
    if args.whitelist is not None:
        whitelist = whitelist | _load_whitelist_file(args.whitelist)

    offenders: dict[str, list[tuple[int, str]]] = {}
    scanned = 0
    for py in sorted(DEFAULT_TARGET_DIR.rglob("*.py")):
        rel = py.relative_to(DEFAULT_TARGET_DIR).as_posix()
        parts = py.parts
        if "__pycache__" in parts or "migrations" in parts or _is_test_file(py):
            continue
        scanned += 1
        if rel in whitelist:
            continue
        hits = _violations_in_file(py)
        if hits:
            offenders[rel] = hits

    if offenders:
        print("stdlib logging usage found outside whitelist (use observability.get_logger):\n")
        for rel in sorted(offenders):
            for lineno, desc in offenders[rel]:
                print(f"  {rel}:{lineno}: {desc}")
        print(f"\n{len(offenders)} file(s), exit 1.")
        return 1

    print(f"OK: no stdlib logging.getLogger outside whitelist ({scanned} files scanned).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
