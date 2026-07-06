"""SemVer 2.0 后缀解析与渠道工具.

支持格式: MAJOR.MINOR.PATCH[-CHANNEL.N]
其中 CHANNEL ∈ {alpha, beta, rc},stable 不带后缀。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

CHANNELS: tuple[str, ...] = ("alpha", "beta", "rc")

CHANNEL_NAMES: dict[str, str] = {
    "alpha": "alpha",
    "beta": "beta",
    "rc": "preview (RC)",
    "stable": "stable",
    "hotfix": "hotfix (stable)",
}

_BRANCH_TO_CHANNEL: dict[str, str] = {
    "main": "alpha",
    "beta": "beta",
    "rc": "preview",
    "release": "stable",
}

# 版本号正则:接受 1.2.3 / 1.2.3-alpha.1 / 1.2.3-beta.3 / 1.2.3-rc.2
_VERSION_RE = re.compile(
    r"^(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)"
    r"(?:-(?P<channel>alpha|beta|rc)\.(?P<cnum>\d+))?$"
)


@dataclass(frozen=True)
class ParsedVersion:
    """解析后的 SemVer 版本."""

    major: int
    minor: int
    patch: int
    channel: str | None = None
    channel_num: int | None = None

    @property
    def is_stable(self) -> bool:
        return self.channel is None


def parse_version(version: str) -> ParsedVersion:
    """解析 SemVer 字符串,失败抛 ValueError."""
    m = _VERSION_RE.match(version.strip())
    if not m:
        raise ValueError(f"Invalid version: {version!r}")
    return ParsedVersion(
        major=int(m["major"]),
        minor=int(m["minor"]),
        patch=int(m["patch"]),
        channel=m["channel"],
        channel_num=int(m["cnum"]) if m["cnum"] else None,
    )


def format_version(
    major: int,
    minor: int,
    patch: int,
    channel: str | None = None,
    channel_num: int | None = None,
) -> str:
    """从分段构造 SemVer 字符串."""
    base = f"{major}.{minor}.{patch}"
    if channel is None and channel_num is None:
        return base
    if channel is None or channel_num is None:
        raise ValueError(
            f"channel and channel_num must both be set or both be None "
            f"(got channel={channel!r}, channel_num={channel_num!r})"
        )
    if channel not in CHANNELS:
        raise ValueError(f"Invalid channel: {channel!r}")
    return f"{base}-{channel}.{channel_num}"


def derive_channel_from_branch(branch: str) -> str:
    """从 git 分支名推导发布渠道.

    已知映射: main=alpha, beta=beta, rc=preview, release=stable.
    其他分支(包括 feat/* fix/* chore/*)返回 "none".
    """
    return _BRANCH_TO_CHANNEL.get(branch, "none")


def compare_versions(a: str, b: str) -> int:
    """按 SemVer 排序规则比较两个版本字符串.

    返回 -1 (a<b), 0 (相等), 1 (a>b).
    排序优先级: stable > rc > beta > alpha,序号大者靠后。
    """
    pa, pb = parse_version(a), parse_version(b)
    if (pa.major, pa.minor, pa.patch) != (pb.major, pb.minor, pb.patch):
        return -1 if (pa.major, pa.minor, pa.patch) < (pb.major, pb.minor, pb.patch) else 1
    # MAJOR.MINOR.PATCH 相同,按渠道排序
    if pa.channel == pb.channel:
        if pa.channel_num == pb.channel_num:
            return 0
        return -1 if (pa.channel_num or 0) < (pb.channel_num or 0) else 1
    # 不同渠道:stable > rc > beta > alpha
    order = {"alpha": 0, "beta": 1, "rc": 2, None: 3}
    a_rank = order[pa.channel]
    b_rank = order[pb.channel]
    return -1 if a_rank < b_rank else 1
