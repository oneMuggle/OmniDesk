"""Git 操作工具模块 — 用于版本发布时分析提交历史."""

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

# 项目根目录 (core/git_utils.py -> project root)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

CONVENTIONAL_TYPES = {
    "feat": "新增功能",
    "fix": "修复问题",
    "refactor": "重构",
    "docs": "文档",
    "build": "构建",
    "test": "测试",
    "chore": "日常维护",
    "perf": "性能优化",
    "ci": "CI/CD",
    "security": "安全",
}

CHANGELOG_SECTIONS = {
    "feat": "### 新增",
    "fix": "### 修复",
    "security": "### 修复",
    "perf": "### 变更",
    "refactor": "### 变更",
}


@dataclass
class CommitInfo:
    """解析后的提交信息."""

    hash: str
    type: str
    scope: str
    description: str
    is_breaking: bool
    raw: str


def _run_git(*args: str, cwd: Path = PROJECT_ROOT) -> str:
    """执行 git 命令并返回 stdout."""
    result = subprocess.run(
        ["git", "-C", str(cwd)] + list(args),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git 命令失败: {' '.join(args)}\n{result.stderr.strip()}")
    return result.stdout


def find_last_version_commit() -> str:
    """查找最近一次修改 VERSION 文件的 commit hash."""
    try:
        output = _run_git(
            "log",
            "--max-count=1",
            "--format=%H",
            "--",
            "deployment/docker/VERSION",
        )
        return output.strip()
    except RuntimeError:
        return ""


def get_commits_since(commit_hash: str) -> list[CommitInfo]:
    """获取指定 commit 之后的所有提交（不含该 commit 本身）."""
    if not commit_hash:
        log_format = "%H|||%s|||%b"
        output = _run_git("log", "--format=" + log_format, "--reverse")
    else:
        log_format = "%H|||%s|||%b"
        output = _run_git(
            "log",
            "--format=" + log_format,
            f"{commit_hash}..HEAD",
            "--reverse",
        )

    commits = []
    for line in output.strip().split("\n"):
        if not line:
            continue
        parts = line.split("|||", 2)
        commit_hash_val = parts[0]
        subject = parts[1] if len(parts) > 1 else ""
        body = parts[2] if len(parts) > 2 else ""
        info = parse_commit_message(commit_hash_val, subject, body)
        commits.append(info)
    return commits


def parse_commit_message(commit_hash: str, subject: str, body: str = "") -> CommitInfo:
    """解析 Conventional Commit 格式的提交信息."""
    cleaned = re.sub(r"^[\U0001F300-\U0001F9FF✀-➿☀-⛿️\s]+", "", subject).strip()

    pattern = r"^(\w+)(?:\(([^)]+)\))?(!)?\s*:\s*(.+)$"
    match = re.match(pattern, cleaned)

    if match:
        commit_type = match.group(1)
        scope = match.group(2) or ""
        breaking_marker = match.group(3) == "!"
        description = match.group(4).strip()
    else:
        commit_type = "chore"
        scope = ""
        breaking_marker = False
        description = cleaned

    is_breaking = breaking_marker or "BREAKING CHANGE" in body

    return CommitInfo(
        hash=commit_hash,
        type=commit_type,
        scope=scope,
        description=description,
        is_breaking=is_breaking,
        raw=subject,
    )


def get_commit_diff_stats(commit_hash: str) -> dict:
    """获取提交影响的文件范围，用于区分前端/后端变更."""
    try:
        output = _run_git("diff-tree", "--no-commit-id", "-r", "--name-only", commit_hash)
        files = [f for f in output.strip().split("\n") if f]

        backend = any(f.startswith("omni_desk_backend/") for f in files)
        frontend = any(f.startswith("omni_desk_frontend/") for f in files)
        deployment = any(f.startswith("deployment/") for f in files)

        return {
            "files": files,
            "backend": backend,
            "frontend": frontend,
            "deployment": deployment,
        }
    except RuntimeError:
        return {"files": [], "backend": False, "frontend": False, "deployment": False}
