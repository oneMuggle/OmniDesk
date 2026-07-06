"""Django 管理命令 — 自动生成版本号与 CHANGELOG."""

import re
import subprocess
import sys
from datetime import date
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
VERSION_FILE = PROJECT_ROOT / "deployment" / "docker" / "VERSION"
CHANGELOG_FILE = PROJECT_ROOT / "deployment" / "docker" / "CHANGELOG.md"

# 导入 git 工具
sys.path.insert(0, str(PROJECT_ROOT / "omni_desk_backend"))
from core.git_utils import (
    CommitInfo,
    find_last_version_commit,
    get_commits_since,
    CHANGELOG_SECTIONS,
)
from core.version_utils import (
    CHANNEL_NAMES,
    compare_versions,
    format_version,
    parse_version,
)

BUMP_LABELS = {
    "major": "MAJOR",
    "minor": "MINOR",
    "patch": "PATCH",
}


class Command(BaseCommand):
    help = "根据自上次版本发布以来的 git 提交，自动生成版本号与 CHANGELOG"

    def add_arguments(self, parser):
        parser.add_argument(
            "--preview",
            action="store_true",
            help="仅预览变更，不修改文件",
        )
        parser.add_argument(
            "--bump",
            choices=["major", "minor", "patch"],
            help="手动指定版本级别（覆盖自动检测）",
        )
        parser.add_argument(
            "--tag",
            action="store_true",
            help="发布后创建 git tag",
        )
        parser.add_argument(
            "--date",
            type=str,
            default=None,
            help="指定发布日期，格式 YYYY-MM-DD（默认今天）",
        )
        parser.add_argument(
            "--channel",
            choices=["alpha", "beta", "preview", "stable", "hotfix"],
            default=None,
            help="发布渠道(默认从 git 分支自动推导,可选值覆盖)",
        )

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

    def _read_version(self) -> str:
        if VERSION_FILE.is_file():
            return VERSION_FILE.read_text().strip()
        raise CommandError(f"VERSION 文件不存在: {VERSION_FILE}")

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

    def _write_version(self, version: str) -> None:
        VERSION_FILE.write_text(f"{version}\n")

    def _calculate_bump(self, commits: list[CommitInfo]) -> tuple[str, str]:
        """根据提交类型计算版本级别。返回 (major|minor|patch, 原因说明)."""
        has_breaking = any(c.is_breaking for c in commits)
        has_feat = any(c.type == "feat" for c in commits)
        has_fix_or_security = any(c.type in ("fix", "security") for c in commits)

        if has_breaking:
            return "major", "发现 BREAKING CHANGE"
        elif has_feat:
            return "minor", "发现 feat 类型提交"
        elif has_fix_or_security:
            return "patch", "发现 fix/security 类型提交"
        else:
            return "patch", "仅有日常维护类提交，默认 PATCH"

    def _bump_version_with_channel(
        self, current_version: str, bump: str, channel: str
    ) -> str:
        """根据 bump 级别与渠道生成新版本号。

        - 跨渠道切换:MAJOR.MINOR.PATCH 按 bump 调整,序号段重置为 1。
        - 同渠道预发布:序号段按 patch 递增(bump 仅 patch 生效)。
        - 同渠道 stable / hotfix:MAJOR/MINOR/PATCH 按 bump。
        """
        parsed = parse_version(current_version)
        major, minor, patch = parsed.major, parsed.minor, parsed.patch

        # 解析"内部渠道":preview -> rc, hotfix -> stable
        internal_channel = "rc" if channel == "preview" else (
            "stable" if channel == "hotfix" else channel
        )

        # 同渠道 stable(包括 hotfix):MAJOR/MINOR/PATCH 按 bump
        if internal_channel == "stable" and parsed.channel is None:
            if bump == "major":
                major += 1
                minor = 0
                patch = 0
            elif bump == "minor":
                minor += 1
                patch = 0
            elif bump == "patch":
                patch += 1
            return format_version(major, minor, patch)

        # 同渠道预发布(alpha/beta/rc):序号段 +1, MAJOR.MINOR.PATCH 不变
        if parsed.channel == internal_channel:
            new_seq = (parsed.channel_num or 0) + 1
            return format_version(major, minor, patch, internal_channel, new_seq)

        # 跨渠道切换:bump 参数被忽略(MAJOR.MINOR.PATCH 沿用当前,序号段重置为 1)
        # 因为同一份 git 提交已经被外层 _calculate_bump 计算过 bump,渠道切换本身
        # 不再触发新的 bump —— 仅切换后缀。
        if internal_channel in ("alpha", "beta", "rc"):
            return format_version(major, minor, patch, internal_channel, 1)
        # stable:去掉后缀
        return format_version(major, minor, patch)

    def _generate_changelog(
        self, commits: list[CommitInfo], version: str, date_str: str,
        channel: str = "stable",
    ) -> str:
        """生成 Keep a Changelog 格式的变更日志条目(带渠道标注)."""
        sections: dict[str, list[str]] = {}
        breaking_lines = []

        for c in commits:
            # 跳过非用户可见的提交类型
            if c.type in ("chore", "ci"):
                continue

            # 格式化条目
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
