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


def try_parse_version(version: object) -> ParsedVersion | None:
    """解析 SemVer 字符串,失败返回 None(不抛异常).

    与 parse_version 的区别:此函数吞掉所有 ValueError/AttributeError,
    用于 CHANGELOG 扫描等"宽松解析"场景。
    """
    if not isinstance(version, str):
        return None
    try:
        return parse_version(version.strip())
    except ValueError:
        return None


_CHANGELOG_HEADER_VERSION_RE = re.compile(r"^(\d+\.\d+\.\d+(?:-(?:alpha|beta|rc)\.\d+)?)")


def normalize_changelog_header(raw: object) -> str | None:
    """把 CHANGELOG header 中 [] 内的原始文本规范化为 SemVer 字符串.

    用于 `_update_changelog` 在扫描历史 header 时做 SemVer 排序。Lenient 提取:
    即使 header 含中文/英文后缀 (如 hotfix 标识 '0.5.9 修复'),也提取出 SemVer 前缀
    '0.5.9' 用于排序 (Bug1 修复关键路径 — 跳过会丢排序锚点)。

    处理历史异构格式:
      - 'v0.6.0-alpha.2' → '0.6.0-alpha.2'  (去前导 v)
      - 'V0.4.0'         → '0.4.0'           (大小写不敏感)
      - '0.7.0-alpha.1'  → '0.7.0-alpha.1'   (已规范,原样返回)
      - '0.5.9 修复'     → '0.5.9'           (提取 SemVer 前缀,中文后缀保留在原始 header)
      - 'v0.5.9 修复'    → '0.5.9'           (去 v + 提取 SemVer 前缀)
      - '渠道机制引入'   → None               (纯文本非版本)
      - '未发布'         → None               (占位段,不视为版本)

    返回 None 表示该 header 不含 SemVer 前缀,调用方应跳过。
    """
    if not isinstance(raw, str):
        return None
    cleaned = raw.strip()
    if not cleaned or cleaned == "未发布":
        return None
    # 1. 去前导 v/V
    if cleaned[0] in ("v", "V"):
        cleaned = cleaned[1:]
    # 2. 整串尝试解析(已规范形式)
    if try_parse_version(cleaned):
        return cleaned
    # 3. 截取 SemVer 前缀(适配 '0.5.9 修复' 这类带后缀的版本 header)
    m = _CHANGELOG_HEADER_VERSION_RE.match(cleaned)
    if m:
        return m.group(1)
    return None


def strip_changelog_v_prefix(raw: object) -> str | None:
    """只剥离 CHANGELOG header 中前导的 'v'/'V' 前缀,其余内容原样保留.

    用于 `normalize_changelog_headers` migration 命令。其职责是清理明显的
    格式不一致 (v 前缀),绝不修改承载语义信息的中文/英文后缀 (如 hotfix
    标识 '0.5.9 修复' 保留不动)。

    处理格式:
      - 'v0.6.0-alpha.1' → '0.6.0-alpha.1'  (剥 v 前缀)
      - 'V0.5.9'         → '0.5.9'           (剥 V 前缀)
      - 'v0.5.9 修复'    → '0.5.9 修复'       (剥 v 前缀,中文后缀保留)
      - '0.5.9 修复'     → None               (无 v 前缀,不修改)
      - '0.5.9'          → None               (无 v 前缀,不修改)
      - '渠道机制引入'   → None               (非版本)
      - '未发布'         → None               (占位段)
      - 'v'              → None               (剥后为空,不修改)

    返回 None 表示该 header 不需要修改。
    """
    if not isinstance(raw, str):
        return None
    cleaned = raw.strip()
    if not cleaned or cleaned == "未发布":
        return None
    if cleaned[0] not in ("v", "V"):
        return None
    result = cleaned[1:]
    if not result:
        return None  # 剥 v 后为空字符串 (如 raw="v"),不返回避免下游误用
    return result


# channel 排序权重:stable 最高,alpha 最低(与 compare_versions 同向)
_CHANNEL_RANK: dict[str | None, int] = {"alpha": 0, "beta": 1, "rc": 2, None: 3}


def _rank_tuple(p: ParsedVersion) -> tuple:
    """ParsedVersion → 可比较元组,顺序与 compare_versions 完全一致.

    排序:MAJOR.MINOR.PATCH 升序 → channel rank 升序(alpha < beta < rc < stable) → channel_num 升序。

    与 compare_versions 区别:本函数返回元组便于直接比较,后者返回 -1/0/1。
    所有输入下二者同向(由 TestRankTuple.test_rank_agrees_with_compare 保证)。
    """
    return (p.major, p.minor, p.patch, _CHANNEL_RANK[p.channel], p.channel_num or 0)
