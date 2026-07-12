"""Commit type filter for channel sync.

Pure logic — no I/O. Used by both unit tests and GitHub Actions workflow.
"""
from __future__ import annotations
import re
from typing import List, Tuple

# 匹配 fix / perf / refactor 类型，含 scope 和 breaking 标记
SYNC_COMMIT_RE = re.compile(
    r"^(fix|perf|refactor)(\([^)]+\))?!?:\s"
)


def filter_syncable(subjects: List[str]) -> Tuple[bool, List[int]]:
    """返回 (是否触发同步, 需要 cherry-pick 的 commit 索引列表).

    Args:
        subjects: PR 内的 commit subjects 列表

    Returns:
        (should_trigger, indices_to_cherry_pick)
        - should_trigger: 至少有一个 syncable commit
        - indices_to_cherry_pick: subjects 列表中需要 cherry-pick 的下标
    """
    indices = [
        i for i, s in enumerate(subjects)
        if SYNC_COMMIT_RE.match(s)
    ]
    return (len(indices) > 0, indices)