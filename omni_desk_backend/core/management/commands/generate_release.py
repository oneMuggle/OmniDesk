"""Django 管理命令 — 自动生成版本号与 CHANGELOG."""

import re
import subprocess
import sys
from datetime import date
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
VERSION_FILE = PROJECT_ROOT / 'deployment' / 'docker' / 'VERSION'
CHANGELOG_FILE = PROJECT_ROOT / 'deployment' / 'docker' / 'CHANGELOG.md'

# 导入 git 工具
sys.path.insert(0, str(PROJECT_ROOT / 'omni_desk_backend'))
from core.git_utils import (
    CommitInfo,
    find_last_version_commit,
    get_commits_since,
    CHANGELOG_SECTIONS,
)

BUMP_LABELS = {
    'major': 'MAJOR',
    'minor': 'MINOR',
    'patch': 'PATCH',
}


class Command(BaseCommand):
    help = '根据自上次版本发布以来的 git 提交，自动生成版本号与 CHANGELOG'

    def add_arguments(self, parser):
        parser.add_argument(
            '--preview', action='store_true',
            help='仅预览变更，不修改文件',
        )
        parser.add_argument(
            '--bump', choices=['major', 'minor', 'patch'],
            help='手动指定版本级别（覆盖自动检测）',
        )
        parser.add_argument(
            '--tag', action='store_true',
            help='发布后创建 git tag',
        )
        parser.add_argument(
            '--date', type=str, default=None,
            help='指定发布日期，格式 YYYY-MM-DD（默认今天）',
        )

    def handle(self, *args, **options):
        preview = options['preview']
        bump_override = options['bump']
        create_tag = options['tag']
        date_str = options['date'] or date.today().isoformat()

        # 1. 读取当前版本
        current_version = self._read_version()
        self.stdout.write(f'当前版本: {current_version}')

        # 2. 获取自上次版本以来的提交
        last_commit = find_last_version_commit()
        commits = get_commits_since(last_commit)

        if not commits:
            self.stdout.write(self.style.WARNING('自上次版本发布以来没有新的提交。'))
            return

        # 3. 计算版本 bump
        if bump_override:
            bump_level = bump_override
            bump_reason = f'手动指定 ({BUMP_LABELS[bump_level]})'
        else:
            bump_level, bump_reason = self._calculate_bump(commits)

        new_version = self._bump_version(current_version, bump_level)
        bump_label = BUMP_LABELS[bump_level]

        # 4. 生成 CHANGELOG
        changelog_entry = self._generate_changelog(commits, new_version, date_str)

        # 5. 打印预览
        self._print_preview(
            current_version, new_version, bump_label, bump_reason,
            commits, changelog_entry, date_str,
        )

        if preview:
            self.stdout.write(self.style.WARNING('\n=== 预览模式，未修改任何文件 ==='))
            return

        # 6. 用户确认
        self.stdout.write('')
        confirm = input(f'确认发布版本 {new_version}? [y/N]: ')
        if confirm.lower() not in ('y', 'yes'):
            self.stdout.write(self.style.WARNING('已取消发布。'))
            return

        # 7. 执行更新
        self._write_version(new_version)
        self._update_changelog(changelog_entry)
        self.stdout.write(self.style.SUCCESS(f'\n版本号已更新: {current_version} → {new_version}'))
        self.stdout.write(self.style.SUCCESS('CHANGELOG.md 已更新'))

        # 8. 创建 tag
        if create_tag:
            self._create_git_tag(new_version)

    def _read_version(self) -> str:
        if VERSION_FILE.is_file():
            return VERSION_FILE.read_text().strip()
        raise CommandError(f'VERSION 文件不存在: {VERSION_FILE}')

    def _write_version(self, version: str) -> None:
        VERSION_FILE.write_text(f'{version}\n')

    def _calculate_bump(self, commits: list[CommitInfo]) -> tuple[str, str]:
        """根据提交类型计算版本级别。返回 (major|minor|patch, 原因说明)."""
        has_breaking = any(c.is_breaking for c in commits)
        has_feat = any(c.type == 'feat' for c in commits)
        has_fix_or_security = any(c.type in ('fix', 'security') for c in commits)

        if has_breaking:
            return 'major', '发现 BREAKING CHANGE'
        elif has_feat:
            return 'minor', '发现 feat 类型提交'
        elif has_fix_or_security:
            return 'patch', '发现 fix/security 类型提交'
        else:
            return 'patch', '仅有日常维护类提交，默认 PATCH'

    def _bump_version(self, version: str, bump: str) -> str:
        """按语义化版本规则 bump 版本号."""
        parts = version.split('.')
        if len(parts) != 3:
            raise CommandError(f'无效的版本号格式: {version}（应为 x.y.z）')

        major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])

        if bump == 'major':
            major += 1
            minor = 0
            patch = 0
        elif bump == 'minor':
            minor += 1
            patch = 0
        elif bump == 'patch':
            patch += 1

        return f'{major}.{minor}.{patch}'

    def _generate_changelog(self, commits: list[CommitInfo], version: str, date_str: str) -> str:
        """生成 Keep a Changelog 格式的变更日志条目."""
        sections: dict[str, list[str]] = {}
        breaking_lines = []

        for c in commits:
            # 跳过非用户可见的提交类型
            if c.type in ('chore', 'ci'):
                continue

            # 格式化条目
            if c.scope:
                entry = f'- **{c.scope}**: {c.description}'
            else:
                entry = f'- {c.description}'

            if c.is_breaking:
                breaking_lines.append(entry)

            section_key = c.type
            if section_key in CHANGELOG_SECTIONS:
                section_name = CHANGELOG_SECTIONS[section_key]
            else:
                continue

            sections.setdefault(section_name, []).append(entry)

        lines = [f'## [{version}] - {date_str}']

        if breaking_lines:
            lines.append('')
            lines.append('### 破坏性变更')
            lines.append('')
            for line in breaking_lines:
                lines.append(line)

        for section_name in ['### 新增', '### 变更', '### 修复', '### 移除']:
            if section_name in sections:
                lines.append('')
                lines.append(section_name)
                lines.append('')
                for line in sections[section_name]:
                    lines.append(line)

        return '\n'.join(lines)

    def _update_changelog(self, new_entry: str) -> None:
        """在 CHANGELOG.md 的 [未发布] 段之后插入新条目."""
        content = CHANGELOG_FILE.read_text()

        pattern = r'(\n## \[\d+\.\d+\.\d+\])'
        match = re.search(pattern, content)

        if match:
            insert_pos = match.start()
            new_content = content[:insert_pos] + '\n' + new_entry + '\n' + content[insert_pos:]
        else:
            new_content = content.rstrip() + '\n\n' + new_entry + '\n'

        CHANGELOG_FILE.write_text(new_content)

    def _create_git_tag(self, version: str) -> None:
        """创建 git tag."""
        tag_name = f'v{version}'
        result = subprocess.run(
            ['git', 'tag', '-a', tag_name, '-m', f'Release {tag_name}'],
            capture_output=True, text=True, cwd=str(PROJECT_ROOT),
        )
        if result.returncode != 0:
            self.stdout.write(self.style.WARNING(f'创建 tag 失败: {result.stderr.strip()}'))
        else:
            self.stdout.write(self.style.SUCCESS(f'Git tag 已创建: {tag_name}'))

    def _print_preview(
        self, current_version, new_version, bump_label, bump_reason,
        commits, changelog_entry, date_str,
    ):
        """打印版本发布预览."""
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=== 版本发布预览 ==='))
        self.stdout.write(f'当前版本: {current_version}')
        self.stdout.write(f'新版本号: {new_version}')
        self.stdout.write(f'发布日期: {date_str}')
        self.stdout.write(f'版本级别: {bump_label} ({bump_reason})')
        self.stdout.write('')
        self.stdout.write(f'提交分析 (共 {len(commits)} 条):')
        for c in commits:
            marker = ' ⚠️ BREAKING' if c.is_breaking else ''
            self.stdout.write(f'  {c.raw}{marker}')
        self.stdout.write('')
        self.stdout.write('变更日志预览:')
        self.stdout.write('─' * 40)
        self.stdout.write(changelog_entry)
        self.stdout.write('─' * 40)
        self.stdout.write('')
        self.stdout.write('将更新的文件:')
        self.stdout.write(f'  - deployment/docker/VERSION ({current_version} → {new_version})')
        self.stdout.write(f'  - deployment/docker/CHANGELOG.md (插入新条目)')
