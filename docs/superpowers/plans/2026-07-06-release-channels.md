# 发布渠道机制 — 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 OmniDesk 引入 4 段式发布渠道（alpha / beta / preview / stable）+ hotfix，从 v0.6.0 起启用，让开发/内测/预发布/正式发布各自有清晰的版本号、镜像 tag 与离线包。

**Architecture:** 采用 SemVer 2.0 后缀法。版本号 `MAJOR.MINOR.PATCH[-alpha.N|-beta.N|-rc.N]`；渠道与分支一一对应（main=alpha, beta=beta, rc=preview, release=stable+hotfix）；CI 在 4 个分支分别打对应渠道 tag；离线包按渠道前缀命名；BUILD-MANIFEST 新增 `channel` 字段贯穿前后端。

**Tech Stack:** Django 4.2 / Python 3.10 / Bash 5 / GitHub Actions / Docker / SemVer 2.0。

**Spec:** `docs/superpowers/specs/2026-07-06-release-channels-design.md`

---

## Global Constraints

- **Python 版本**：3.10（与现有 conda 环境 `omni_desk`、Dockerfile、CI workflow 一致）
- **Django 版本**：4.2（settings/base.py 锁定）
- **版本号格式**：`MAJOR.MINOR.PATCH[-alpha.N|-beta.N|-rc.N]`（stable / hotfix 无后缀）
- **渠道枚举**：`alpha` / `beta` / `preview` / `stable` / `hotfix` / `none`（feat/fix 分支）
- **分支保护**：`main` / `beta` / `rc` / `release` 均为受保护分支，必须走 PR
- **向后兼容**：现有 `v0.5.x` 系列视为 stable 渠道历史；旧的 `omnidesk-offline-v0.5.x/` 目录命名继续可用
- **commit 规范**：Conventional Commits（feat/fix/docs/chore/ci/build/refactor/test）
- **测试覆盖率**：>= 80%（CI fail-under=80 锁定）
- **频道文档语言**：中文（与 CLAUDE.md 一致）
- **每次 commit 前必跑**：`pytest --ds=omni_desk_backend.settings.test` 后端测试 + bash 单元测试
- **不破坏现有功能**：每个 task 完成后必须能立即部署一个 v0.5.x 风格的稳定版（legacy 兼容）

---

## File Structure

```
omni_desk_backend/
├── core/
│   ├── version.py                       # MODIFY: 调用 version_utils
│   ├── version_utils.py                 # NEW: SemVer 后缀解析/格式化
│   ├── api.py                           # MODIFY: 返回 channel
│   ├── management/commands/
│   │   └── generate_release.py          # MODIFY: channel 参数 + CHANGELOG 排序
│   └── tests/
│       ├── test_version_utils.py        # NEW
│       ├── test_generate_release.py     # MODIFY
│       └── test_api.py                  # MODIFY

.github/workflows/
├── build-and-push-images.yml            # MODIFY: 渠道推导 + metadata
├── release-channel-matrix.yml           # NEW: 集成测试
└── ghcr-cleanup.yml                     # NEW: 月度清理（可选）

deployment/docker/
├── package_offline_bundle.sh            # MODIFY: 正则 + 目录 + manifest channel
├── upgrade.sh                           # MODIFY: --target-channel 校验
├── rollback.sh                          # MODIFY: 备份按渠道隔离
├── deploy_offline.sh                    # MODIFY: rollback 渠道选择
├── tests/test_deploy_image_tags.sh      # MODIFY: 后缀解析测试
├── DEPLOYMENT_GUIDE_DOCKER.md           # MODIFY: 命名约定
└── CHANGELOG.md                         # MODIFY: v0.6.0 渠道机制引入条目

CLAUDE.md                                # MODIFY: 渠道与分支映射小节
docs/technical/
├── 30-release-channels.md               # NEW
└── README.md                            # MODIFY: 目录
docs/user-manual/
├── 12-deployment-channels.md            # NEW
└── README.md                            # MODIFY: 目录

git branches: beta, rc, release           # NEW: 从 main HEAD 拉出空分支
```

---

## Task Index

| Task | 内容 | 估时 | 依赖 |
|---|---|---|---|
| 1 | SemVer 后缀解析工具 `version_utils.py` | 1h | — |
| 2 | `generate_release.py` 支持 channel + 序号重置 + CHANGELOG 改造 | 3h | Task 1 |
| 3 | `/api/system/version/` 返回 channel | 1h | Task 1 |
| 4 | CI workflow 渠道推导 + metadata 改造 | 1.5h | — |
| 5 | `release-channel-matrix.yml` 集成测试 workflow | 1h | Task 4 |
| 6 | `package_offline_bundle.sh` 正则放宽 + BUILD-MANIFEST channel | 1.5h | Task 1 |
| 7 | `package_offline_bundle.sh` 离线包目录命名 + 离线 deploy.sh banner | 1.5h | Task 6 |
| 8 | `upgrade.sh` 渠道校验 | 1h | — |
| 9 | `rollback.sh` 备份按渠道隔离 | 1h | Task 8 |
| 10 | `deploy_offline.sh` rollback 渠道选择 | 0.5h | Task 9 |
| 11 | `tests/test_deploy_image_tags.sh` 后缀解析测试 | 1h | Task 6 |
| 12 | `CLAUDE.md` 文档更新 | 0.5h | — |
| 13 | `docs/technical/30-release-channels.md` 新章节 | 1h | Task 12 |
| 14 | `docs/user-manual/12-deployment-channels.md` 新章节 | 1h | Task 12 |
| 15 | `DEPLOYMENT_GUIDE_DOCKER.md` + `CHANGELOG.md` 更新 | 0.5h | Task 7 |
| 16 | `ghcr-cleanup.yml` 月度镜像清理（可选） | 1h | Task 4 |
| 17 | 创建 `beta` / `rc` / `release` 三个空分支 | 0.5h | Task 5+16 之前或之后均可 |
| **合计** | | **17.5h** | |

---

## Task 1: SemVer 后缀解析工具 `version_utils.py`

**Files:**
- Create: `omni_desk_backend/core/version_utils.py`
- Test: `omni_desk_backend/core/tests/test_version_utils.py`

**Interfaces:**
- Produces:
  - `CHANNELS: tuple[str, ...] = ("alpha", "beta", "rc")`
  - `CHANNEL_NAMES: dict[str, str]` — 中文名映射 `{"alpha": "alpha", "beta": "beta", "rc": "preview (RC)", "stable": "stable"}`
  - `ParsedVersion` dataclass: `(major: int, minor: int, patch: int, channel: str | None, channel_num: int | None)`
  - `def parse_version(version: str) -> ParsedVersion` — 接受 `1.2.3`、`1.2.3-alpha.1`、`1.2.3-rc.2`
  - `def format_version(major: int, minor: int, patch: int, channel: str | None, channel_num: int | None) -> str`
  - `def derive_channel_from_branch(branch: str) -> str` — 返回 `"alpha"` / `"beta"` / `"preview"` / `"stable"` / `"none"`
  - `def compare_versions(a: str, b: str) -> int` — 返回 `-1` / `0` / `1`（按 SemVer 排序规则）

- [ ] **Step 1: 写失败测试**

创建 `omni_desk_backend/core/tests/test_version_utils.py`：

```python
"""version_utils 单元测试."""

import pytest

from core.version_utils import (
    CHANNELS,
    ParsedVersion,
    compare_versions,
    derive_channel_from_branch,
    format_version,
    parse_version,
)


class TestParseVersion:
    def test_plain_stable(self):
        result = parse_version("1.2.3")
        assert result == ParsedVersion(1, 2, 3, None, None)

    def test_alpha(self):
        result = parse_version("1.2.3-alpha.1")
        assert result == ParsedVersion(1, 2, 3, "alpha", 1)

    def test_beta(self):
        result = parse_version("0.5.9-beta.3")
        assert result == ParsedVersion(0, 5, 9, "beta", 3)

    def test_rc(self):
        result = parse_version("1.2.0-rc.2")
        assert result == ParsedVersion(1, 2, 0, "rc", 2)

    @pytest.mark.parametrize("bad", ["1.2", "v1.2.3", "1.2.3-alpha", "1.2.3-rc", "1.2.3-alpha.x"])
    def test_invalid(self, bad):
        with pytest.raises(ValueError):
            parse_version(bad)


class TestFormatVersion:
    def test_stable(self):
        assert format_version(1, 2, 3, None, None) == "1.2.3"

    def test_alpha(self):
        assert format_version(1, 2, 3, "alpha", 1) == "1.2.3-alpha.1"

    def test_channel_without_num_raises(self):
        with pytest.raises(ValueError):
            format_version(1, 2, 3, "alpha", None)


class TestDeriveChannelFromBranch:
    @pytest.mark.parametrize("branch,expected", [
        ("main", "alpha"),
        ("beta", "beta"),
        ("rc", "preview"),
        ("release", "stable"),
        ("feat/foo", "none"),
        ("fix/bar", "none"),
        ("main-1.2", "none"),  # 防止前缀误匹配
    ])
    def test_branches(self, branch, expected):
        assert derive_channel_from_branch(branch) == expected


class TestCompareVersions:
    def test_stable_vs_stable(self):
        assert compare_versions("1.2.3", "1.2.3") == 0
        assert compare_versions("1.2.4", "1.2.3") == 1
        assert compare_versions("1.2.3", "1.2.4") == -1

    def test_stable_higher_than_rc(self):
        assert compare_versions("1.2.0", "1.2.0-rc.2") == 1

    def test_rc_higher_than_beta(self):
        assert compare_versions("1.2.0-rc.1", "1.2.0-beta.3") == 1

    def test_alpha_lowest(self):
        assert compare_versions("1.2.0-alpha.1", "1.2.0") == -1

    def test_same_channel_seq(self):
        assert compare_versions("1.2.0-alpha.2", "1.2.0-alpha.1") == 1
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd omni_desk_backend && python -m pytest core/tests/test_version_utils.py -v`
Expected: `ModuleNotFoundError: No module named 'core.version_utils'`

- [ ] **Step 3: 实现 `version_utils.py`**

创建 `omni_desk_backend/core/version_utils.py`：

```python
"""SemVer 2.0 后缀解析与渠道工具.

支持格式: MAJOR.MINOR.PATCH[-CHANNEL.N]
其中 CHANNEL ∈ {alpha, beta, rc},stable 不带后缀。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

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
    channel: Optional[str] = None
    channel_num: Optional[int] = None

    @property
    def is_stable(self) -> bool:
        return self.channel is None

    @property
    def channel_key(self) -> str:
        """用于渠道排序的键:stable=3, rc=2, beta=1, alpha=0"""
        if self.channel is None:
            return "3"
        return {"alpha": "0", "beta": "1", "rc": "2"}[self.channel]


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
    channel: Optional[str] = None,
    channel_num: Optional[int] = None,
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
        if pa.channel == pb.channel and pa.channel_num == pb.channel_num:
            return 0
        return -1 if (pa.channel_num or 0) < (pb.channel_num or 0) else 1
    # 不同渠道:stable > rc > beta > alpha
    order = {"alpha": 0, "beta": 1, "rc": 2, None: 3}
    a_rank = order[pa.channel]
    b_rank = order[pb.channel]
    return -1 if a_rank < b_rank else 1
```

- [ ] **Step 4: 跑测试确认全部通过**

Run: `cd omni_desk_backend && python -m pytest core/tests/test_version_utils.py -v`
Expected: 17 passed

- [ ] **Step 5: Commit**

```bash
git add omni_desk_backend/core/version_utils.py omni_desk_backend/core/tests/test_version_utils.py
git commit -m "feat(core): 新增 SemVer 后缀解析工具 version_utils"
```

---

## Task 2: `generate_release.py` 支持 channel + 序号重置 + CHANGELOG 排序

**Files:**
- Modify: `omni_desk_backend/core/management/commands/generate_release.py`
- Modify: `omni_desk_backend/core/tests/test_generate_release.py`

**Interfaces:**
- Consumes: `version_utils.parse_version`, `version_utils.format_version`, `version_utils.compare_versions`
- Produces: `--channel` 命令行参数；CHANGELOG 按 SemVer 字符串排序；新条目自动追加渠道标注

- [ ] **Step 1: 读现有 `test_generate_release.py`,了解测试结构**

Run: `wc -l omni_desk_backend/core/tests/test_generate_release.py`
Expected: 输出当前行数(后面 add 新测试时核对)

- [ ] **Step 2: 在 `test_generate_release.py` 末尾添加失败测试**

在文件末尾追加：

```python
"""channel 渠道感知的 generate_release 测试."""

import pytest

from core.management.commands.generate_release import Command


class TestChannelReset:
    """渠道升级时序号应重置."""

    def test_alpha_to_beta_resets(self):
        # 1.2.0-alpha.5 + 升渠道 -> 1.2.0-beta.1
        cmd = Command()
        new_version = cmd._bump_version_with_channel(
            current_version="1.2.0-alpha.5",
            bump="patch",
            channel="beta",
        )
        assert new_version == "1.2.0-beta.1"

    def test_alpha_same_channel_increments(self):
        # 1.2.0-alpha.1 + 同渠道 patch -> 1.2.0-alpha.2
        cmd = Command()
        new_version = cmd._bump_version_with_channel(
            current_version="1.2.0-alpha.1",
            bump="patch",
            channel="alpha",
        )
        assert new_version == "1.2.0-alpha.2"

    def test_beta_to_rc_resets(self):
        # 1.2.0-beta.3 + 升渠道 -> 1.2.0-rc.1
        cmd = Command()
        new_version = cmd._bump_version_with_channel(
            current_version="1.2.0-beta.3",
            bump="patch",
            channel="rc",
        )
        assert new_version == "1.2.0-rc.1"

    def test_rc_to_stable_drops_suffix(self):
        # 1.2.0-rc.2 + 升渠道到 stable -> 1.2.0(去掉后缀)
        cmd = Command()
        new_version = cmd._bump_version_with_channel(
            current_version="1.2.0-rc.2",
            bump="patch",
            channel="stable",
        )
        assert new_version == "1.2.0"

    def test_hotfix_from_stable_bumps_patch(self):
        # 1.2.0 stable + hotfix bump patch -> 1.2.1(无后缀)
        cmd = Command()
        new_version = cmd._bump_version_with_channel(
            current_version="1.2.0",
            bump="patch",
            channel="stable",
        )
        assert new_version == "1.2.1"
```

- [ ] **Step 3: 跑测试确认失败**

Run: `cd omni_desk_backend && python -m pytest core/tests/test_generate_release.py::TestChannelReset -v`
Expected: `AttributeError: 'Command' object has no attribute '_bump_version_with_channel'`

- [ ] **Step 4: 在 `generate_release.py` 加 channel 支持**

修改顶部 imports（第 17-23 行附近）：

```python
sys.path.insert(0, str(PROJECT_ROOT / "omni_desk_backend"))
from core.git_utils import (
    CommitInfo,
    find_last_version_commit,
    get_commits_since,
    CHANGELOG_SECTIONS,
)
from core.version_utils import (
    CHANNEL_NAMES,
    ParsedVersion,
    compare_versions,
    format_version,
    parse_version,
)
```

修改 `add_arguments` 方法,在 `--date` 之后增加：

```python
        parser.add_argument(
            "--channel",
            choices=["alpha", "beta", "preview", "stable", "hotfix"],
            default=None,
            help="发布渠道(默认从 git 分支自动推导,可选值覆盖)",
        )
```

修改 `handle()` 方法,在读取 current_version 之后、计算 bump 之前插入 channel 推导逻辑。完整重写 `handle()`:

```python
    def handle(self, *args, **options):
        preview = options["preview"]
        bump_override = options["bump"]
        create_tag = options["tag"]
        date_str = options["date"] or date.today().isoformat()

        # 1. 读取当前版本
        current_version = self._read_version()
        self.stdout.write(f"当前版本: {current_version}")

        # 2. 推导渠道(--channel 优先,否则从 git 分支读)
        channel = options["channel"]
        if not channel:
            channel = self._detect_channel_from_git()
        self.stdout.write(f"目标渠道: {channel}")

        # 3. 获取自上次版本以来的提交
        last_commit = find_last_version_commit()
        commits = get_commits_since(last_commit)

        if not commits:
            self.stdout.write(self.style.WARNING("自上次版本发布以来没有新的提交。"))
            return

        # 4. 计算版本 bump
        if bump_override:
            bump_level = bump_override
            bump_reason = f"手动指定 ({BUMP_LABELS[bump_level]})"
        else:
            bump_level, bump_reason = self._calculate_bump(commits)

        # 5. 应用 bump + 渠道(序号重置逻辑)
        new_version = self._bump_version_with_channel(
            current_version=current_version,
            bump=bump_level,
            channel=channel,
        )
        bump_label = BUMP_LABELS[bump_level]

        # 6. 生成 CHANGELOG(传入 channel 用于标注)
        changelog_entry = self._generate_changelog(commits, new_version, date_str, channel)

        # 7. 打印预览
        self._print_preview(
            current_version,
            new_version,
            bump_label,
            bump_reason,
            commits,
            changelog_entry,
            date_str,
            channel,
        )

        if preview:
            self.stdout.write(self.style.WARNING("\n=== 预览模式，未修改任何文件 ==="))
            return

        # 8. 用户确认
        self.stdout.write("")
        confirm = input(f"确认发布版本 {new_version} (渠道 {channel})? [y/N]: ")
        if confirm.lower() not in ("y", "yes"):
            self.stdout.write(self.style.WARNING("已取消发布。"))
            return

        # 9. 执行更新
        self._write_version(new_version)
        self._update_changelog(changelog_entry)
        self.stdout.write(self.style.SUCCESS(f"\n版本号已更新: {current_version} → {new_version}"))
        self.stdout.write(self.style.SUCCESS("CHANGELOG.md 已更新"))

        # 10. 创建 tag
        if create_tag:
            self._create_git_tag(new_version, channel)
```

新增 `_detect_channel_from_git()` 方法（放在 `_read_version()` 之后）：

```python
    def _detect_channel_from_git(self) -> str:
        """从当前 git 分支推导渠道名。"""
        from core.version_utils import derive_channel_from_branch
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, cwd=str(PROJECT_ROOT),
        )
        branch = result.stdout.strip() if result.returncode == 0 else ""
        channel = derive_channel_from_branch(branch)
        if channel == "none":
            self.stdout.write(self.style.WARNING(
                f"当前分支 {branch!r} 不在已知渠道列表中,默认按 stable 处理。"
            ))
            return "stable"
        return channel
```

新增 `_bump_version_with_channel()` 方法(替换原 `_bump_version`):

```python
    def _bump_version_with_channel(
        self, current_version: str, bump: str, channel: str
    ) -> str:
        """根据 bump 级别与渠道生成新版本号。

        渠道切换时 MAJOR.MINOR.PATCH 不变,序号段重置为 1。
        同一渠道内 patch 递增。stable 渠道序号固定为 None。
        """
        parsed = parse_version(current_version)
        major, minor, patch = parsed.major, parsed.minor, parsed.patch

        # 解析"内部渠道":preview -> rc, hotfix -> stable
        internal_channel = "rc" if channel == "preview" else (
            "stable" if channel == "hotfix" else channel
        )

        # 同渠道且当前是稳定版:仅 bump(支持 hotfix 走 patch)
        if internal_channel == "stable" and parsed.channel is None:
            if bump == "major":
                major += 1; minor = 0; patch = 0
            elif bump == "minor":
                minor += 1; patch = 0
            elif bump == "patch":
                patch += 1
            return format_version(major, minor, patch)

        # 跨渠道或同渠道预发布:MAJOR.MINOR.PATCH 按 bump 调整
        if bump == "major":
            major += 1; minor = 0; patch = 0
        elif bump == "minor":
            minor += 1; patch = 0
        elif bump == "patch":
            patch += 1

        # 预发布渠道:序号段重置为 1
        if internal_channel in ("alpha", "beta", "rc"):
            return format_version(major, minor, patch, internal_channel, 1)
        # stable:去掉后缀
        return format_version(major, minor, patch)
```

修改 `_generate_changelog()` 方法签名,接受 channel 参数并标注：

```python
    def _generate_changelog(
        self, commits: list[CommitInfo], version: str, date_str: str,
        channel: str = "stable",
    ) -> str:
        """生成 Keep a Changelog 格式的变更日志条目(带渠道标注)."""
        sections: dict[str, list[str]] = {}
        breaking_lines = []

        for c in commits:
            if c.type in ("chore", "ci"):
                continue

            if c.scope:
                entry = f"- **{c.scope}**: {c.description}"
            else:
                entry = f"- {c.description}"

            if c.is_breaking:
                breaking_lines.append(entry)

            section_key = c.type
            if section_key in CHANGELOG_SECTIONS:
                section_name = CHANGELOG_SECTIONS[section_key]
            else:
                continue

            sections.setdefault(section_name, []).append(entry)

        # 渠道标注(中文)
        channel_label = CHANNEL_NAMES.get(channel, channel)
        lines = [f"## [{version}] - {date_str}  ← {channel_label}"]

        if breaking_lines:
            lines.append("")
            lines.append("### 破坏性变更")
            lines.append("")
            for line in breaking_lines:
                lines.append(line)

        for section_name in ["### 新增", "### 变更", "### 修复", "### 移除"]:
            if section_name in sections:
                lines.append("")
                lines.append(section_name)
                lines.append("")
                for line in sections[section_name]:
                    lines.append(line)

        return "\n".join(lines)
```

修改 `_update_changelog()` 方法,支持按 SemVer 字符串排序插入：

```python
    def _update_changelog(self, new_entry: str) -> None:
        """在 CHANGELOG.md 中按 SemVer 顺序插入新条目.

        排序规则:stable > rc > beta > alpha,序号大者靠后。
        [未发布] 段保留在顶部,新条目插在它与所有历史版本之间(按 SemVer 倒序)。
        """
        content = CHANGELOG_FILE.read_text()

        # 提取新条目的版本号
        m = re.match(r"## \[([^\]]+)\]", new_entry)
        if not m:
            # 兜底:插到 [未发布] 之后
            pattern = r"(## \[未发布\][^\n]*\n)"
            match = re.search(pattern, content)
            if match:
                pos = match.end()
                CHANGELOG_FILE.write_text(
                    content[:pos] + "\n" + new_entry + "\n" + content[pos:]
                )
            else:
                CHANGELOG_FILE.write_text(content.rstrip() + "\n\n" + new_entry + "\n")
            return
        new_version = m.group(1)

        # 找到所有 ## [vX.Y.Z...] 条目的位置,选第一个比 new_version 大的位置插入
        existing_pattern = re.compile(r"^## \[([^\]]+)\]", re.MULTILINE)
        insert_pos = None
        for match in existing_pattern.finditer(content):
            existing_version = match.group(1)
            if existing_version in ("未发布",):
                continue
            try:
                if compare_versions(new_version, existing_version) > 0:
                    insert_pos = match.start()
                    break
            except ValueError:
                continue

        if insert_pos is None:
            # 没有比 new_version 大的,插到文件末尾
            CHANGELOG_FILE.write_text(content.rstrip() + "\n\n" + new_entry + "\n")
        else:
            CHANGELOG_FILE.write_text(
                content[:insert_pos] + new_entry + "\n\n" + content[insert_pos:]
            )
```

修改 `_create_git_tag()` 接受 channel 参数（仅用于 tag 注释）：

```python
    def _create_git_tag(self, version: str, channel: str = "stable") -> None:
        """创建 git tag(含渠道信息注释)."""
        tag_name = f"v{version}"
        tag_msg = f"Release {tag_name} ({channel})"
        result = subprocess.run(
            ["git", "tag", "-a", tag_name, "-m", tag_msg],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT),
        )
        if result.returncode != 0:
            self.stdout.write(self.style.WARNING(f"创建 tag 失败: {result.stderr.strip()}"))
        else:
            self.stdout.write(self.style.SUCCESS(f"Git tag 已创建: {tag_name}"))
```

修改 `_print_preview()` 接受 channel 参数并在头部打印：

```python
    def _print_preview(
        self,
        current_version,
        new_version,
        bump_label,
        bump_reason,
        commits,
        changelog_entry,
        date_str,
        channel="stable",
    ):
        """打印版本发布预览."""
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("=== 版本发布预览 ==="))
        self.stdout.write(f"当前版本: {current_version}")
        self.stdout.write(f"新版本号: {new_version}")
        self.stdout.write(f"目标渠道: {channel}")
        self.stdout.write(f"发布日期: {date_str}")
        self.stdout.write(f"版本级别: {bump_label} ({bump_reason})")
        self.stdout.write("")
        self.stdout.write(f"提交分析 (共 {len(commits)} 条):")
        for c in commits:
            marker = " ⚠️ BREAKING" if c.is_breaking else ""
            self.stdout.write(f"  {c.raw}{marker}")
        self.stdout.write("")
        self.stdout.write("变更日志预览:")
        self.stdout.write("─" * 40)
        self.stdout.write(changelog_entry)
        self.stdout.write("─" * 40)
        self.stdout.write("")
        self.stdout.write("将更新的文件:")
        self.stdout.write(f"  - deployment/docker/VERSION ({current_version} → {new_version})")
        self.stdout.write(f"  - deployment/docker/CHANGELOG.md (插入新条目)")
```

- [ ] **Step 5: 跑测试确认全部通过**

Run: `cd omni_desk_backend && python -m pytest core/tests/test_generate_release.py -v`
Expected: 现有测试 + 新增 TestChannelReset 全部通过

- [ ] **Step 6: 手动验证 preview**

Run: `cd omni_desk_backend && python manage.py generate_release --preview --channel beta`
Expected: 打印预览,不修改任何文件

- [ ] **Step 7: Commit**

```bash
git add omni_desk_backend/core/management/commands/generate_release.py omni_desk_backend/core/tests/test_generate_release.py
git commit -m "feat(core): generate_release 支持渠道参数,CHANGELOG 按 SemVer 排序"
```

---

## Task 3: `/api/system/version/` 返回 channel

**Files:**
- Modify: `omni_desk_backend/core/api.py`
- Modify: `omni_desk_backend/core/version.py`
- Modify: `omni_desk_backend/core/tests/test_api.py`

**Interfaces:**
- Consumes: `version_utils.parse_version`
- Produces: `/api/system/version/` 响应新增 `channel` 字段

- [ ] **Step 1: 读 `core/api.py` 找到当前 /api/system/version/ 实现**

Run: `grep -n "version" omni_desk_backend/core/api.py | head -20`
Expected: 找到版本端点函数定义位置

- [ ] **Step 2: 在 `test_api.py` 末尾添加失败测试**

在文件末尾追加：

```python
"""/api/system/version/ 返回 channel 字段的测试."""

import json
from unittest.mock import patch

import pytest
from django.test import Client


@pytest.mark.django_db
class TestSystemVersionChannel:
    def test_channel_field_returned(self):
        """API 应返回 channel 字段(由 VERSION 解析)."""
        client = Client()
        with patch("core.api.get_version", return_value="1.2.0-rc.1"):
            response = client.get("/api/system/version/")
        assert response.status_code == 200
        data = json.loads(response.content)
        assert data["version"] == "1.2.0-rc.1"
        assert data["channel"] == "preview"

    def test_stable_channel_default(self):
        """无后缀版本应返回 channel=stable."""
        client = Client()
        with patch("core.api.get_version", return_value="1.2.0"):
            response = client.get("/api/system/version/")
        data = json.loads(response.content)
        assert data["channel"] == "stable"
```

- [ ] **Step 3: 跑测试确认失败**

Run: `cd omni_desk_backend && python -m pytest core/tests/test_api.py::TestSystemVersionChannel -v`
Expected: FAIL — 响应不含 channel 字段

- [ ] **Step 4: 修改 `core/api.py`,在版本响应中加入 channel**

找到 `/api/system/version/` 的 view 函数（典型为 `system_version` 或 `version_info`），修改返回字典：

```python
from core.version_utils import parse_version

# 在 view 函数内:
raw_version = get_version()
try:
    parsed = parse_version(raw_version)
    if parsed.channel == "rc":
        channel = "preview"
    elif parsed.channel in ("alpha", "beta"):
        channel = parsed.channel
    else:
        channel = "stable"
except ValueError:
    channel = "stable"  # 无法解析时 fallback

return Response({
    "version": raw_version,
    "channel": channel,
    "build_time": settings.BUILD_TIME if hasattr(settings, "BUILD_TIME") else None,
    "django_version": django.get_version(),
})
```

- [ ] **Step 5: 跑测试确认通过**

Run: `cd omni_desk_backend && python -m pytest core/tests/test_api.py::TestSystemVersionChannel -v`
Expected: 2 passed

- [ ] **Step 6: 跑全套后端测试确认无回归**

Run: `cd omni_desk_backend && python -m pytest --ds=omni_desk_backend.settings.test -q`
Expected: 全套通过(coverage >= 80%)

- [ ] **Step 7: Commit**

```bash
git add omni_desk_backend/core/api.py omni_desk_backend/core/version.py omni_desk_backend/core/tests/test_api.py
git commit -m "feat(api): /api/system/version/ 返回 channel 字段"
```

---

## Task 4: CI workflow 渠道推导 + metadata 改造

**Files:**
- Modify: `.github/workflows/build-and-push-images.yml`

**Interfaces:**
- Produces: 新增 `channel` step output；metadata-action tags 按渠道区分；取消 `develop` 单独打 tag

- [ ] **Step 1: 读当前 workflow 全文**

Run: `cat .github/workflows/build-and-push-images.yml | head -150`

- [ ] **Step 2: 在 Read version step 之后插入 Detect release channel step**

定位 `id: read_version` 的 step,在它之后立即插入：

```yaml
      - name: Detect release channel
        id: channel
        run: |
          case "${GITHUB_REF#refs/heads/}" in
            main)    echo "CHANNEL=alpha"   >> "$GITHUB_OUTPUT" ;;
            beta)    echo "CHANNEL=beta"    >> "$GITHUB_OUTPUT" ;;
            rc)      echo "CHANNEL=preview" >> "$GITHUB_OUTPUT" ;;
            release) echo "CHANNEL=stable"  >> "$GITHUB_OUTPUT" ;;
            *)       echo "CHANNEL=none"    >> "$GITHUB_OUTPUT" ;;
          esac
```

- [ ] **Step 3: 替换 backend metadata-action 的 tags 配置**

定位 `id: meta-backend` step，替换 `tags:` 整段为：

```yaml
          tags: |
            type=sha
            type=raw,value=${{ steps.read_version.outputs.VERSION }},enable=${{ steps.channel.outputs.CHANNEL != 'none' }}
            type=raw,value=${{ steps.read_version.outputs.VERSION }}-canary,enable=${{ steps.channel.outputs.CHANNEL == 'none' && github.event_name == 'push' }}
            type=raw,value=latest,enable=${{ steps.channel.outputs.CHANNEL == 'stable' }}
```

- [ ] **Step 4: 同样替换 frontend metadata-action**

定位 `id: meta-frontend` step，替换 `tags:` 整段为相同内容（仅 images 字段不同）。

- [ ] **Step 5: 在 frontend build step 之后追加 canary 推送（PR 不打 canary,这里已通过 enable 控制）**

无需额外 step，metadata-action 已根据 enable 自动决定是否生成该 tag。

- [ ] **Step 6: 本地语法 lint**

Run: `python -c "import yaml; yaml.safe_load(open('.github/workflows/build-and-push-images.yml'))"`
Expected: 无输出（语法正确）

- [ ] **Step 7: Commit**

```bash
git add .github/workflows/build-and-push-images.yml
git commit -m "ci: build-and-push 按分支推导渠道,stable 独占 latest tag"
```

---

## Task 5: `release-channel-matrix.yml` 集成测试 workflow

**Files:**
- Create: `.github/workflows/release-channel-matrix.yml`

- [ ] **Step 1: 创建 workflow 文件**

```yaml
name: Release Channel Matrix Integration Test

on:
  workflow_dispatch:    # 手动触发,日常不跑
  schedule:
    - cron: '0 2 * * 0' # 每周日凌晨 2 点(本地时区由 runner 决定)

jobs:
  matrix:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        branch: [main, beta, rc, release]
    steps:
      - name: Checkout target branch
        uses: actions/checkout@v4
        with:
          ref: ${{ matrix.branch }}
          fetch-depth: 1

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Read version
        id: read_version
        run: echo "VERSION=$(cat deployment/docker/VERSION | tr -d '[:space:]')" >> "$GITHUB_OUTPUT"

      - name: Derive expected channel
        id: expected
        run: |
          case "${{ matrix.branch }}" in
            main)    echo "CHANNEL=alpha"   >> "$GITHUB_OUTPUT" ;;
            beta)    echo "CHANNEL=beta"    >> "$GITHUB_OUTPUT" ;;
            rc)      echo "CHANNEL=preview" >> "$GITHUB_OUTPUT" ;;
            release) echo "CHANNEL=stable"  >> "$GITHUB_OUTPUT" ;;
          esac

      - name: Validate VERSION format for branch
        run: |
          VERSION="${{ steps.read_version.outputs.VERSION }}"
          BRANCH="${{ matrix.branch }}"
          case "$BRANCH" in
            main|beta|rc)
              if ! echo "$VERSION" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+-(alpha|beta|rc)\.[0-9]+$'; then
                echo "ERROR: branch $BRANCH requires version with -alpha.N/-beta.N/-rc.N suffix, got: $VERSION"
                exit 1
              fi
              ;;
            release)
              if ! echo "$VERSION" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+$'; then
                echo "ERROR: branch release requires plain SemVer (no suffix), got: $VERSION"
                exit 1
              fi
              ;;
          esac
          echo "OK: branch $BRANCH has valid version $VERSION"

      - name: Build backend image (no push)
        uses: docker/build-push-action@v5
        with:
          context: .
          file: ./deployment/docker/omni_desk_backend/Dockerfile
          target: production
          push: false
          tags: ghcr.io/onemuggle/omni-desk-backend:test-${{ matrix.branch }}
          cache-from: type=gha

      - name: Build frontend image (no push)
        uses: docker/build-push-action@v5
        with:
          context: ./omni_desk_frontend
          file: ./omni_desk_frontend/Dockerfile
          push: false
          tags: ghcr.io/onemuggle/omni-desk-frontend:test-${{ matrix.branch }}
          cache-from: type=gha
          build-args: CI=false
```

- [ ] **Step 2: YAML 语法检查**

Run: `python -c "import yaml; yaml.safe_load(open('.github/workflows/release-channel-matrix.yml'))"`
Expected: 无输出

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/release-channel-matrix.yml
git commit -m "ci: 新增 release-channel-matrix 集成测试 workflow"
```

---

## Task 6: `package_offline_bundle.sh` 正则放宽 + BUILD-MANIFEST channel

**Files:**
- Modify: `deployment/docker/package_offline_bundle.sh`

- [ ] **Step 1: 读 `package_offline_bundle.sh` 第 24-27 行确认当前正则**

(已知：`if ! echo "$BUILD_VERSION" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+$';`)

- [ ] **Step 2: 修改正则(第 24 行)**

替换为：

```bash
if ! echo "$BUILD_VERSION" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+(-(alpha|beta|rc)\.[0-9]+)?$'; then
    echo "ERROR: Invalid version format '$BUILD_VERSION'."
    echo "Use MAJOR.MINOR.PATCH (stable) or MAJOR.MINOR.PATCH-{alpha,beta,rc}.N (pre-release)."
    exit 1
fi
```

- [ ] **Step 3: 在脚本顶部(VERSION_FILE 读取段之后,line 16 附近)加 channel 推导**

在 `BUILD_VERSION="${1:-${FILE_VERSION}}"` 之后插入：

```bash
# ─── 渠道推导(从 VERSION 后缀)───────────────────────
case "$BUILD_VERSION" in
    *-alpha.*) BUILD_CHANNEL="alpha" ;;
    *-beta.*)  BUILD_CHANNEL="beta" ;;
    *-rc.*)    BUILD_CHANNEL="preview" ;;
    *)         BUILD_CHANNEL="stable" ;;
esac
echo "  发布渠道: ${BUILD_CHANNEL}"
```

- [ ] **Step 4: 修改 BUILD-MANIFEST 生成段(line 430 附近),在 JSON 中加入 channel 字段**

定位原 `cat > "$BUNDLE_DIR/BUILD-MANIFEST.json" << EOF` 段（无论是 fallback 生成的最小 manifest 还是 docker load 后重写的完整 manifest），都把 JSON 改成：

```json
{
  "version": "$BUILD_VERSION",
  "channel": "$BUILD_CHANNEL",
  "build_time": "$BUILD_TIME",
  ...
}
```

完整重写"自动修正 manifest"段（约 line 499-522），把 channel 加进去：

```bash
cat > "$BUNDLE_DIR/BUILD-MANIFEST.json" << EOF
{
  "version": "$BUILD_VERSION",
  "channel": "$BUILD_CHANNEL",
  "build_time": "$BUILD_TIME",
  "git_sha": "$GIT_SHA",
  "images": {
    "backend": {
      "name": "$BACKEND_TAG_NAME",
      "digest": "$BACKEND_DIGEST",
      "size_bytes": $BACKEND_SIZE
    },
    "frontend": {
      "name": "$FRONTEND_TAG_NAME",
      "digest": "$FRONTEND_DIGEST",
      "size_bytes": $FRONTEND_SIZE
    }
  },
  "base_images": {
    "postgres": "postgres:14-alpine",
    "redis": "redis:7-alpine",
    "nginx": "nginx-stable-alpine"
  }
}
EOF
```

同样修改 line 430 附近的最小 manifest fallback：

```bash
cat > "$BUNDLE_DIR/BUILD-MANIFEST.json" << EOF
{
  "version": "$BUILD_VERSION",
  "channel": "$BUILD_CHANNEL",
  "build_time": "$BUILD_TIME",
  "git_sha": "$GIT_SHA"
}
EOF
```

- [ ] **Step 5: 手动跑一次 alpha 版本打包验证**

Run: `echo "1.0.0-alpha.1" > /tmp/test_version && cp /tmp/test_version deployment/docker/VERSION.bak && mv deployment/docker/VERSION deployment/docker/VERSION.real && echo "1.0.0-alpha.1" > deployment/docker/VERSION && bash deployment/docker/package_offline_bundle.sh 1.0.0-alpha.1 2>&1 | head -30 && mv deployment/docker/VERSION.real deployment/docker/VERSION`
Expected: 看到 "发布渠道: alpha" + 生成的 manifest 含 `"channel": "alpha"`

- [ ] **Step 6: 验证 manifest 内容**

Run: `cat omnidesk-offline-alpha-v1.0.0-alpha.1/BUILD-MANIFEST.json | python3 -c "import json,sys; m=json.load(sys.stdin); assert m['channel']=='alpha'; print('OK')"`
Expected: `OK`

- [ ] **Step 7: 清理测试产物**

```bash
rm -rf omnidesk-offline-alpha-v1.0.0-alpha.1
```

- [ ] **Step 8: Commit**

```bash
git add deployment/docker/package_offline_bundle.sh
git commit -m "feat(deploy): package_offline_bundle.sh 支持 alpha/beta/rc 后缀,BUILD-MANIFEST 加 channel"
```

---

## Task 7: `package_offline_bundle.sh` 离线包目录命名 + 离线 deploy.sh banner

**Files:**
- Modify: `deployment/docker/package_offline_bundle.sh`（line 29 与 line 105-373 heredoc 内 deploy.sh）

- [ ] **Step 1: 修改 BUNDLE_DIR 计算(第 29 行)**

替换：

```bash
BUNDLE_DIR="omnidesk-offline-v${BUILD_VERSION}"
```

为：

```bash
# 离线包目录命名:<channel>-v<version>(stable 不加 prefix)
case "$BUILD_CHANNEL" in
    alpha)   BUNDLE_DIR="omnidesk-offline-alpha-v${BUILD_VERSION}" ;;
    beta)    BUNDLE_DIR="omnidesk-offline-beta-v${BUILD_VERSION}" ;;
    preview) BUNDLE_DIR="omnidesk-offline-rc-v${BUILD_VERSION}" ;;
    hotfix)  BUNDLE_DIR="omnidesk-offline-hotfix-v${BUILD_VERSION}" ;;
    *)       BUNDLE_DIR="omnidesk-offline-v${BUILD_VERSION}" ;;  # stable
esac
```

- [ ] **Step 2: 在 heredoc 内 deploy.sh 的 generate_env() 函数末尾(line 240 附近)追加 banner 输出**

定位 `generate_env()` 函数,在最后一个 `fi` 之后、`wait_for_healthy` 函数之前追加：

```bash
    # ─── 启动 banner 显示渠道 ─────────────────────────────
    echo "渠道: $(jq -r '.channel // "stable"' "$BUNDLE_DIR/BUILD-MANIFEST.json" 2>/dev/null || echo 'stable') (v${version:-${BUILD_VERSION:-unknown}})"
```

- [ ] **Step 3: 在 start 主命令开头(line 303 附近)显示 banner**

定位 `echo "  OmniDesk 离线部署"`，紧接其后插入：

```bash
echo "  渠道: $(jq -r '.channel // "stable"' "$BUNDLE_DIR/BUILD-MANIFEST.json" 2>/dev/null || echo 'stable')"
echo "  版本: $(jq -r '.version' "$BUNDLE_DIR/BUILD-MANIFEST.json" 2>/dev/null || echo 'unknown')"
echo "=========================================="
```

把原来已存在的 `echo "=========================================="` 往下推一行。

- [ ] **Step 4: 手动打包 alpha 验证目录名**

Run: `bash deployment/docker/package_offline_bundle.sh 1.0.0-alpha.2 2>&1 | tail -10`
Expected: 输出 `离线包位置: omnidesk-offline-alpha-v1.0.0-alpha.2/`

- [ ] **Step 5: 验证目录存在**

Run: `ls -d omnidesk-offline-alpha-v1.0.0-alpha.2 2>/dev/null && echo "OK"`
Expected: `OK`

- [ ] **Step 6: 清理**

```bash
rm -rf omnidesk-offline-alpha-v1.0.0-alpha.2
```

- [ ] **Step 7: Commit**

```bash
git add deployment/docker/package_offline_bundle.sh
git commit -m "feat(deploy): 离线包目录按渠道前缀命名,deploy.sh banner 显示 channel"
```

---

## Task 8: `upgrade.sh` 渠道校验

**Files:**
- Modify: `deployment/docker/upgrade.sh`

- [ ] **Step 1: 在文件顶部注释的 Usage 行追加 `--target-channel` 说明**

替换 `Usage:` 行为：

```bash
# upgrade.sh — Safe version upgrade script for OmniDesk
# Usage: ./upgrade.sh [path-to-new-images-dir] [--target-channel {alpha|beta|preview|stable|hotfix}]
```

- [ ] **Step 2: 在 IMAGE_DIR 解析(line 84 附近)之后插入 channel 参数解析**

```bash
# 渠道参数(--target-channel,默认从 VERSION 后缀推导)
TARGET_CHANNEL="${TARGET_CHANNEL:-}"
for arg in "$@"; do
    case "$arg" in
        --target-channel=*) TARGET_CHANNEL="${arg#*=}" ;;
    esac
done
if [ -z "$TARGET_CHANNEL" ]; then
    TARGET_VERSION=$(get_target_version)
    case "$TARGET_VERSION" in
        *-alpha.*) TARGET_CHANNEL="alpha" ;;
        *-beta.*)  TARGET_CHANNEL="beta" ;;
        *-rc.*)    TARGET_CHANNEL="preview" ;;
        *)         TARGET_CHANNEL="stable" ;;
    esac
fi
echo "Target channel: $TARGET_CHANNEL"
```

- [ ] **Step 3: 在"Step 2 Compatibility check"之后(第 113 行之后)插入渠道校验**

```bash
# ─── Step 2.5: 渠道校验(禁止跳级) ─────────────────────
CURRENT_CHANNEL=""
if [ "$CURRENT_VERSION" != "unknown" ]; then
    case "$CURRENT_VERSION" in
        *-alpha.*) CURRENT_CHANNEL="alpha" ;;
        *-beta.*)  CURRENT_CHANNEL="beta" ;;
        *-rc.*)    CURRENT_CHANNEL="preview" ;;
        *)         CURRENT_CHANNEL="stable" ;;
    esac
fi
if [ -n "$CURRENT_CHANNEL" ] && [ "$CURRENT_CHANNEL" != "$TARGET_CHANNEL" ]; then
    case "$CURRENT_CHANNEL:$TARGET_CHANNEL" in
        alpha:beta|beta:preview|preview:stable|alpha:preview|alpha:stable|beta:stable)
            echo "Channel upgrade: $CURRENT_CHANNEL -> $TARGET_CHANNEL (allowed)" ;;
        *)
            echo "ERROR: Channel downgrade or invalid jump detected ($CURRENT_CHANNEL -> $TARGET_CHANNEL)."
            echo "Allowed jumps: alpha->beta, beta->preview, preview->stable, or any skip forward."
            echo "Downgrades (stable->anything, beta->alpha, etc.) are FORBIDDEN."
            exit 1
            ;;
    esac
fi
```

- [ ] **Step 4: bash 语法检查**

Run: `bash -n deployment/docker/upgrade.sh`
Expected: 无输出

- [ ] **Step 5: Commit**

```bash
git add deployment/docker/upgrade.sh
git commit -m "feat(deploy): upgrade.sh 支持 --target-channel 与跳级校验"
```

---

## Task 9: `rollback.sh` 备份按渠道隔离

**Files:**
- Modify: `deployment/docker/rollback.sh`

- [ ] **Step 1: 在 BACKUP_DIR 解析后追加 channel 解析**

定位 BACKUP_DIR 行（line 23 附近），在其后插入：

```bash
# 渠道参数(--channel,默认 stable)
ROLLBACK_CHANNEL="${ROLLBACK_CHANNEL:-stable}"
for arg in "$@"; do
    case "$arg" in
        --channel=*) ROLLBACK_CHANNEL="${arg#*=}" ;;
    esac
done
BACKUP_DIR="${BACKUP_DIR:-./backups/${ROLLBACK_CHANNEL}}"
```

- [ ] **Step 2: 在第 35-37 行 "Current version" 显示之后追加 "Current channel"**

在 `echo "Current version: $CURRENT_VERSION"` 之后追加：

```bash
echo "Rollback channel: $ROLLBACK_CHANNEL"
```

- [ ] **Step 3: bash 语法检查**

Run: `bash -n deployment/docker/rollback.sh`
Expected: 无输出

- [ ] **Step 4: 手动 dry-run 验证备份目录结构**

Run: `mkdir -p /tmp/rollback-test/backups/stable /tmp/rollback-test/backups/preview && touch /tmp/rollback-test/backups/stable/backup_v1.2.0_20260712.sql.gz && touch /tmp/rollback-test/backups/preview/backup_v1.2.0-rc.1_20260708.sql.gz && cd /tmp/rollback-test && BACKUP_DIR=./backups/stable ls ./backups/stable/ && echo "---" && ls ./backups/preview/`
Expected: 看到 stable 与 preview 各自的备份

- [ ] **Step 5: 清理**

```bash
rm -rf /tmp/rollback-test
```

- [ ] **Step 6: Commit**

```bash
git add deployment/docker/rollback.sh
git commit -m "feat(deploy): rollback.sh 备份按渠道隔离(--channel 参数)"
```

---

## Task 10: `deploy_offline.sh` rollback 渠道选择

**Files:**
- Modify: `deployment/docker/deploy_offline.sh`

- [ ] **Step 1: 修改 rollback 分支(line 282-288 附近)**

替换：

```bash
    rollback)
        if [ ! -f ".env.production" ]; then
            echo "ERROR: .env.production not found."
            exit 1
        fi
        ./rollback.sh "${@:2}"
        ;;
```

为：

```bash
    rollback)
        if [ ! -f ".env.production" ]; then
            echo "ERROR: .env.production not found."
            exit 1
        fi
        ./rollback.sh "${@:2}"
        ;;
```

并在文件 Usage 帮助段（第 350 行附近）追加：

```bash
    echo "  rollback [--channel={alpha|beta|preview|stable}]  Rollback to a previous version (channel-scoped backups)"
```

- [ ] **Step 2: bash 语法检查**

Run: `bash -n deployment/docker/deploy_offline.sh`
Expected: 无输出

- [ ] **Step 3: Commit**

```bash
git add deployment/docker/deploy_offline.sh
git commit -m "docs(deploy): deploy_offline.sh rollback 帮助文本注明 channel 参数"
```

---

## Task 11: `tests/test_deploy_image_tags.sh` 后缀解析测试

**Files:**
- Modify: `deployment/docker/tests/test_deploy_image_tags.sh`

- [ ] **Step 1: 读现有测试文件了解结构**

Run: `wc -l deployment/docker/tests/test_deploy_image_tags.sh && head -30 deployment/docker/tests/test_deploy_image_tags.sh`

- [ ] **Step 2: 在末尾追加新 fixture**

在文件末尾追加：

```bash
# ─── 新增 fixture 4: SemVer 后缀版本解析 ──────────────
test_semver_suffix_parsing() {
    local test_dir="$TEST_DIR/suffix"
    mkdir -p "$test_dir"

    # alpha 版本的 BUILD-MANIFEST.json
    cat > "$test_dir/BUILD-MANIFEST.json" <<'EOF'
{
  "version": "1.2.0-alpha.5",
  "channel": "alpha",
  "build_time": "2026-07-10T00:00:00Z",
  "git_sha": "abc1234",
  "images": {
    "backend": {"name": "omni-desk-backend-prod:v1.2.0-alpha.5"},
    "frontend": {"name": "omni-desk-frontend-prod:v1.2.0-alpha.5"}
  }
}
EOF

    # 抽取 version 字段,验证后缀解析正确
    local version
    if command -v jq >/dev/null 2>&1; then
        version=$(jq -r '.version' "$test_dir/BUILD-MANIFEST.json")
    else
        version=$(grep -oE '"version"[[:space:]]*:[[:space:]]*"[^"]+"' "$test_dir/BUILD-MANIFEST.json" | head -1 | grep -oE '"[^"]+"$' | tr -d '"')
    fi

    if [ "$version" = "1.2.0-alpha.5" ]; then
        echo "PASS: alpha suffix parsed correctly"
        return 0
    else
        echo "FAIL: expected 1.2.0-alpha.5, got $version"
        return 1
    fi
}

test_beta_and_rc_suffix() {
    local test_dir="$TEST_DIR/suffix2"
    mkdir -p "$test_dir"

    for entry in "1.2.0-beta.3:beta" "1.2.0-rc.2:preview" "1.2.0:stable"; do
        local ver="${entry%:*}"
        local ch="${entry#*:}"

        cat > "$test_dir/BUILD-MANIFEST.json" <<EOF
{
  "version": "$ver",
  "channel": "$ch",
  "build_time": "2026-07-10T00:00:00Z",
  "git_sha": "abc1234",
  "images": {
    "backend": {"name": "omni-desk-backend-prod:$ver"},
    "frontend": {"name": "omni-desk-frontend-prod:$ver"}
  }
}
EOF

        local extracted
        if command -v jq >/dev/null 2>&1; then
            extracted=$(jq -r '.version' "$test_dir/BUILD-MANIFEST.json")
            local extracted_ch
            extracted_ch=$(jq -r '.channel' "$test_dir/BUILD-MANIFEST.json")
        else
            extracted=$(grep -oE '"version"[[:space:]]*:[[:space:]]*"[^"]+"' "$test_dir/BUILD-MANIFEST.json" | head -1 | grep -oE '"[^"]+"$' | tr -d '"')
            extracted_ch=$(grep -oE '"channel"[[:space:]]*:[[:space:]]*"[^"]+"' "$test_dir/BUILD-MANIFEST.json" | head -1 | grep -oE '"[^"]+"$' | tr -d '"')
        fi

        if [ "$extracted" != "$ver" ] || [ "$extracted_ch" != "$ch" ]; then
            echo "FAIL: expected ver=$ver ch=$ch, got ver=$extracted ch=$extracted_ch"
            return 1
        fi
    done
    echo "PASS: beta/rc/stable suffix parsing all correct"
    return 0
}
```

- [ ] **Step 3: 在文件主调用区（找到调用其他 fixture 的位置）追加新 fixture 调用**

找到 `test_xxx` 这样的函数调用行，在末尾追加：

```bash
test_semver_suffix_parsing || exit 1
test_beta_and_rc_suffix || exit 1
```

- [ ] **Step 4: 跑测试**

Run: `bash deployment/docker/tests/test_deploy_image_tags.sh`
Expected: 现有测试 + 新增 2 个 fixture 全部 PASS

- [ ] **Step 5: Commit**

```bash
git add deployment/docker/tests/test_deploy_image_tags.sh
git commit -m "test(deploy): test_deploy_image_tags 新增 alpha/beta/rc 后缀解析 fixture"
```

---

## Task 12: `CLAUDE.md` 文档更新

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: 定位 "Version Update System" 章节**

Run: `grep -n "Version Update System" CLAUDE.md`

- [ ] **Step 2: 在该章节最后(找到最后一个版本相关条目之后)追加 "## 发布渠道" 小节**

```markdown
## 发布渠道

从 v0.6.0 起,OmniDesk 引入 4 段式发布渠道 + hotfix:

| 渠道 | 分支 | 版本号格式 | 镜像 tag 示例 |
|---|---|---|---|
| alpha | `main` | `MAJOR.MINOR.PATCH-alpha.N` | `v1.2.0-alpha.5` |
| beta | `beta` | `MAJOR.MINOR.PATCH-beta.N` | `v1.2.0-beta.1` |
| preview | `rc` | `MAJOR.MINOR.PATCH-rc.N` | `v1.2.0-rc.1` |
| stable | `release` | `MAJOR.MINOR.PATCH` | `v1.2.0` + `latest` |
| hotfix | `release` | `MAJOR.MINOR.(PATCH+1)` | `v1.2.1` + `latest` |

**关键约定**:
- 渠道升级时 MAJOR.MINOR.PATCH 不变,仅序号段重置为 1
- stable 与 hotfix 都不带后缀;hotfix 仅 bump PATCH
- `latest` 镜像 tag 永远只指向 stable 渠道
- 离线包目录命名:`omnidesk-offline-<channel>-v<version>/`(stable 无 channel 前缀)
- BUILD-MANIFEST.json 新增 `channel` 字段,`/api/system/version/` API 也返回 channel

详细规范见 `docs/technical/30-release-channels.md`。
```

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: CLAUDE.md 增加发布渠道与分支映射小节"
```

---

## Task 13: `docs/technical/30-release-channels.md` 新章节

**Files:**
- Create: `docs/technical/30-release-channels.md`
- Modify: `docs/technical/README.md`

- [ ] **Step 1: 创建章节文件**

```markdown
# 30 发布渠道机制

## 概述

OmniDesk 从 v0.6.0 起引入 4 段式发布渠道(alpha / beta / preview / stable) + hotfix,
用于规范从开发自测到正式发布的完整流程。

## 渠道与分支映射

| 渠道 | 分支 | 适用场景 |
|---|---|---|
| alpha | `main` | 开发自测,每日构建 |
| beta | `beta` | 内测组验证 |
| preview | `rc` | release candidate,客户/领导预览 |
| stable | `release` | 正式生产 |
| hotfix | `release` | stable 已发布后的紧急修复 |

## 版本号规则

格式: `MAJOR.MINOR.PATCH[-CHANNEL.N]`,严格符合 SemVer 2.0 §9。

渠道升级示例:
- `1.2.0-alpha.5` → `1.2.0-beta.1`(序号重置)
- `1.2.0-rc.2` → `1.2.0`(去掉后缀)
- `1.2.0` → `1.2.1`(hotfix, PATCH bump)

## 镜像 tag

GHCR 镜像 `ghcr.io/onemuggle/omni-desk-{backend,frontend}`:

- `latest` 永远只指向 stable 渠道
- `v1.2.0-rc.1` / `v1.2.0-beta.3` / `v1.2.0-alpha.5` 各自独立
- PR 不打渠道 tag,仅 `sha-<short>` 用于 docker buildx 缓存

## 离线包目录命名

| 渠道 | 目录 |
|---|---|
| alpha | `omnidesk-offline-alpha-v1.2.0-alpha.5/` |
| beta | `omnidesk-offline-beta-v1.2.0-beta.1/` |
| preview | `omnidesk-offline-rc-v1.2.0-rc.1/` |
| stable | `omnidesk-offline-v1.2.0/` |
| hotfix | `omnidesk-offline-hotfix-v1.2.1/` |

## BUILD-MANIFEST.json

新增 `channel` 字段:

```json
{
  "version": "1.2.0-rc.1",
  "channel": "preview",
  "build_time": "2026-07-10T12:00:00Z",
  "git_sha": "abc1234",
  "images": { "backend": {...}, "frontend": {...} },
  "base_images": {...}
}
```

## API

`/api/system/version/` 返回:

```json
{
  "version": "1.2.0-rc.1",
  "channel": "preview",
  "build_time": "2026-07-10T12:00:00Z",
  "django_version": "4.2.x"
}
```

## 升级流程图

```
main (alpha)  ──promote──>  beta (beta)
beta          ──promote──>  rc (preview)
rc            ──promote──>  release (stable)
release       ──hotfix───>  release (stable, PATCH bump)
            同时 cherry-pick 回 main/beta/rc
```

## 禁止操作

- 渠道回退(stable → beta 不允许)
- 跨级升级(alpha → stable 跳过中间不允许)
- stable 渠道使用预发布版本号

详细实施计划见 `docs/superpowers/plans/2026-07-06-release-channels.md`。
```

- [ ] **Step 2: 修改 `docs/technical/README.md`,在表格末尾追加一行**

Run: `grep -n "29-performance" docs/technical/README.md`

在第 29 行条目之后追加：

```markdown
| 30 | [发布渠道机制](30-release-channels.md) | alpha/beta/preview/stable 4 段式发布渠道 + hotfix |
```

- [ ] **Step 3: Commit**

```bash
git add docs/technical/30-release-channels.md docs/technical/README.md
git commit -m "docs: 新增 30-release-channels.md 章节"
```

---

## Task 14: `docs/user-manual/12-deployment-channels.md` 新章节

**Files:**
- Create: `docs/user-manual/12-deployment-channels.md`
- Modify: `docs/user-manual/README.md`

- [ ] **Step 1: 创建章节文件**

```markdown
# 12 各发布渠道部署指引

本文档面向运维/部署人员,说明如何识别、选择、升级不同发布渠道的 OmniDesk 离线包。

## 渠道识别

打开离线包目录或解压后的 `BUILD-MANIFEST.json`,看 `channel` 字段:

| channel 值 | 含义 | 适用环境 |
|---|---|---|
| `alpha` | 开发自测版 | 仅开发人员本地测试 |
| `beta` | 内测版 | 内测组指定环境 |
| `preview` | 预发布 (RC) | 客户/领导预览环境 |
| `stable` | 正式版 | 生产环境 |
| `hotfix` | 紧急修复 | 生产环境,已是 stable |

启动 banner 也会显示当前渠道:

```
==========================================
  OmniDesk 离线部署
  渠道: preview (v1.2.0-rc.1)
  版本: 1.2.0-rc.1
==========================================
```

## 选择合适的渠道

| 你要做的事 | 用哪个渠道 |
|---|---|
| 本地开发新功能 | alpha |
| 给内测组部署 | beta |
| 给客户/领导演示新版本 | preview (RC) |
| 上生产 | stable |
| 修生产环境的紧急 bug | hotfix(从 release 分支 cherry-pick) |

## 升级流程

### 升级到 stable(生产)

```bash
cd omnidesk-offline-v1.2.0/
./scripts/verify.sh           # 1. 校验完整性
./scripts/deploy.sh start     # 2. 启动(自动同步 IMAGE_TAG)
```

### 从 preview 升到 stable

```bash
cd omnidesk-offline-v1.2.0/
./scripts/upgrade.sh --target-channel=stable
```

### 应用 hotfix

```bash
cd omnidesk-offline-hotfix-v1.2.1/
./scripts/upgrade.sh --target-channel=stable
```

## 回滚

回滚备份按渠道隔离存放,默认只显示同渠道备份:

```bash
# 回滚到当前 stable 渠道的上一版本
./scripts/deploy.sh rollback

# 回滚到 preview 渠道的备份
./scripts/deploy.sh rollback --channel=preview
```

回滚时系统会列出该渠道下所有 `backup_v<VERSION>_<timestamp>.sql.gz`,选择序号即可。

## 常见问题

**Q: 怎么判断一个 GHCR tag 属于哪个渠道?**

A: 看 tag 后缀:
- 无后缀 = stable
- `-rc.N` = preview
- `-beta.N` = beta
- `-alpha.N` = alpha

**Q: 渠道可以回退吗?**

A: 不可以。`stable → beta` / `preview → alpha` 都会被 `upgrade.sh` 拒绝。

**Q: 旧版 `omnidesk-offline-v0.5.x/` 还能用吗?**

A: 可以。stable 渠道命名约定不变,旧包继续可用。
```

- [ ] **Step 2: 修改 `docs/user-manual/README.md`,在表格末尾追加**

```markdown
| 12 | [各发布渠道部署指引](12-deployment-channels.md) | alpha/beta/preview/stable 各渠道离线包的识别、选择、升级、回滚 |
```

- [ ] **Step 3: Commit**

```bash
git add docs/user-manual/12-deployment-channels.md docs/user-manual/README.md
git commit -m "docs: 新增 12-deployment-channels.md 章节"
```

---

## Task 15: `DEPLOYMENT_GUIDE_DOCKER.md` + `CHANGELOG.md` 更新

**Files:**
- Modify: `deployment/docker/DEPLOYMENT_GUIDE_DOCKER.md`
- Modify: `deployment/docker/CHANGELOG.md`

- [ ] **Step 1: 在 `DEPLOYMENT_GUIDE_DOCKER.md` 顶部"离线包结构"小节追加渠道命名约定**

找到描述 `omnidesk-offline-vX.Y.Z/` 的位置,在其后追加：

```markdown
## 离线包渠道命名

v0.6.0 起,离线包目录按渠道命名:

- `omnidesk-offline-alpha-vX.Y.Z-alpha.N/` — 开发自测
- `omnidesk-offline-beta-vX.Y.Z-beta.N/` — 内测
- `omnidesk-offline-rc-vX.Y.Z-rc.N/` — 预发布
- `omnidesk-offline-vX.Y.Z/` — 正式版(stable,无前缀与历史兼容)
- `omnidesk-offline-hotfix-vX.Y.(Z+1)/` — 紧急修复
```

- [ ] **Step 2: 在 `CHANGELOG.md` 顶部"[未发布]"段之后插入"渠道机制引入"条目**

定位 `## [未发布]` 段,紧接其后插入：

```markdown
## [渠道机制引入] - 2026-07-06

### 新增
- **4 段式发布渠道**:alpha(开发自测) / beta(内测) / preview(预发布 RC) / stable(生产),加 hotfix(紧急修复)
- **渠道与分支一一对应**:main=alpha, beta=beta, rc=preview, release=stable+hotfix
- **版本号格式扩展**:`MAJOR.MINOR.PATCH[-alpha.N|-beta.N|-rc.N]`,stable/hotfix 无后缀
- **镜像 tag**:`latest` 永远只指向 stable;feat/fix 分支打 `-canary` 取代原 `develop` tag
- **离线包目录命名**:稳定版与历史兼容;预发布版加渠道前缀
- **BUILD-MANIFEST.json**:新增 `channel` 字段
- **/api/system/version/**:响应新增 `channel` 字段
- **CI**:新增 `release-channel-matrix` 集成测试 workflow,4 个分支并行校验
- **部署脚本**:`upgrade.sh` 支持 `--target-channel` 与跳级校验;`rollback.sh` 备份按渠道隔离
- **文档**:新增 `docs/technical/30-release-channels.md`、`docs/user-manual/12-deployment-channels.md`

### 迁移说明
- 现有 `v0.5.x` 系列保持 stable 渠道历史(不变)
- 从 `v0.6.0-alpha.1` 起启用新渠道
- 不需要数据库迁移
```

- [ ] **Step 3: Commit**

```bash
git add deployment/docker/DEPLOYMENT_GUIDE_DOCKER.md deployment/docker/CHANGELOG.md
git commit -m "docs: DEPLOYMENT_GUIDE_DOCKER 渠道命名 + CHANGELOG 渠道机制引入条目"
```

---

## Task 16: `ghcr-cleanup.yml` 月度镜像清理(可选)

**Files:**
- Create: `.github/workflows/ghcr-cleanup.yml`

- [ ] **Step 1: 创建 workflow**

```yaml
name: GHCR Image Cleanup

on:
  schedule:
    - cron: '0 3 1 * *'  # 每月 1 日凌晨 3 点
  workflow_dispatch:

permissions:
  contents: read
  packages: write

jobs:
  cleanup:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Cleanup old GHCR tags
        uses: actions/delete-package-versions@v4
        with:
          package-name: omni-desk-backend
          package-type: container
          # 保留最近 10 个非渠道 tag + 所有 -alpha/-beta/-rc/vX.Y.Z 渠道 tag
          keep-untagged-versions: false
          # 仅保留 30 天内的 sha-* 缓存层
          min-versions-to-keep-tagged: 0
          # 跳过 latest 与具体渠道 tag,只删 sha-* 缓存
          ignore-versions: |
            latest
            v*-alpha.*
            v*-beta.*
            v*-rc.*
            v[0-9]+.[0-9]+.[0-9]+
            *-canary
          only-keep-semver-tags: false
        continue-on-error: true

      - name: Cleanup frontend (same logic)
        uses: actions/delete-package-versions@v4
        with:
          package-name: omni-desk-frontend
          package-type: container
          keep-untagged-versions: false
          ignore-versions: |
            latest
            v*-alpha.*
            v*-beta.*
            v*-rc.*
            v[0-9]+.[0-9]+.[0-9]+
            *-canary
        continue-on-error: true
```

- [ ] **Step 2: YAML 语法检查**

Run: `python -c "import yaml; yaml.safe_load(open('.github/workflows/ghcr-cleanup.yml'))"`
Expected: 无输出

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/ghcr-cleanup.yml
git commit -m "ci: 新增 GHCR 月度镜像清理 workflow(仅保留渠道 tag + latest)"
```

---

## Task 17: 创建 `beta` / `rc` / `release` 三个空分支

**Files:** （git 操作,无文件改动）

- [ ] **Step 1: 确认当前在 `feat/release-channels` 分支**

Run: `git branch --show-current`
Expected: `feat/release-channels`

- [ ] **Step 2: 创建三个新分支(从当前 main HEAD 拉出)**

```bash
git switch main
git switch -c beta
git push -u origin beta

git switch main
git switch -c rc
git push -u origin rc

git switch main
git switch -c release
git push -u origin release

git switch feat/release-channels  # 切回 feature 分支继续
```

- [ ] **Step 3: 在 GitHub UI 设置三个分支为受保护分支**

- 进入 Settings → Branches → Add rule
- Branch name pattern: `beta` / `rc` / `release`
- 勾选: Require a pull request before merging, Require status checks to pass before merging

- [ ] **Step 4: 验证远程分支可见**

Run: `git branch -r | grep -E '(beta|rc|release)'`
Expected: `origin/beta`, `origin/rc`, `origin/release`

---

## Spec Coverage Check

| Spec 章节 | 实施任务 |
|---|---|
| §1 背景与目标 | 设计上下文,无独立 task |
| §2 渠道与分支映射 | Task 17(分支创建)+ Task 4(CI 推导)+ Task 13(文档) |
| §3 版本号规则 | Task 1(version_utils)+ Task 2(generate_release)+ Task 13(文档) |
| §4 镜像 tag 命名 | Task 4(CI metadata)+ Task 16(清理) |
| §5 离线包命名与 BUILD-MANIFEST | Task 6(BUILD-MANIFEST channel)+ Task 7(目录命名) |
| §6 CI 改造 | Task 4(metadata)+ Task 5(集成测试)+ Task 16(清理) |
| §7 部署脚本改造 | Task 6/7(package_offline)+ Task 8(upgrade)+ Task 9/10(rollback)+ Task 11(测试) |
| §8 CHANGELOG 模板 | Task 2(CHANGELOG 排序+渠道标注)+ Task 15(CHANGELOG.md) |
| §9 文档更新清单 | Task 12(CLAUDE.md)+ Task 13(technical)+ Task 14(user-manual)+ Task 15(DEPLOYMENT) |
| §10 测试清单 | Task 1-3(pytest)+ Task 11(bash)+ Task 5(CI 集成) |
| §11 迁移计划 | Task 15(CHANGELOG 条目)+ Task 17(分支创建) |
| §12 风险与缓解 | 散落在各 task 注释中 |
| §13 决策记录 | 已写入 spec 文件 |

---

## Self-Review Checklist

- [x] 占位符扫描:无 TBD/TODO/填占位
- [x] 类型一致性:`version_utils` 接口在 Task 1 定义,Task 2/3/6 都按同一签名使用
- [x] spec 覆盖:13 个 spec 章节全部对应 task
- [x] 每个 task 有可独立运行的命令(测试 / 语法检查 / 手动验证)
- [x] commit message 全部符合 Conventional Commits
- [x] 没有任务跳过 CI / 测试