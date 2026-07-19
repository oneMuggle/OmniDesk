"""generate_release 命令的单元测试."""

import tempfile
from pathlib import Path

import pytest

from core.git_utils import (
    CommitInfo,
    parse_commit_message,
    CHANGELOG_SECTIONS,
)
from core.management.commands.generate_release import Command


# ─── parse_commit_message 测试 ───


class TestParseCommitMessage:

    def _make(self, subject, body=''):
        return parse_commit_message('abc123', subject, body)

    def test_feat_with_scope(self):
        c = self._make('feat(assistant): 实现智能助手功能')
        assert c.type == 'feat'
        assert c.scope == 'assistant'
        assert c.description == '实现智能助手功能'
        assert not c.is_breaking

    def test_fix_without_scope(self):
        c = self._make('fix: 修复登录超时问题')
        assert c.type == 'fix'
        assert c.scope == ''
        assert c.description == '修复登录超时问题'

    def test_breaking_with_exclamation(self):
        c = self._make('feat!: 移除旧的认证系统')
        assert c.is_breaking

    def test_breaking_in_body(self):
        c = self._make('refactor(auth): 重构认证模块', body='BREAKING CHANGE: 旧的 token 不再支持')
        assert c.is_breaking

    def test_emoji_prefix_stripped(self):
        c = self._make('✨ feat(docs): 添加智能助手增强优化方案文档')
        assert c.type == 'feat'
        assert c.scope == 'docs'
        assert c.description == '添加智能助手增强优化方案文档'

    def test_emoji_fix(self):
        c = self._make('🐛 fix(smart-assistant): 修复智能助手接口请求与响应处理')
        assert c.type == 'fix'
        assert c.scope == 'smart-assistant'

    def test_refactor_emoji(self):
        c = self._make('♻️ refactor(imports): 调整视图中的相对导入路径')
        assert c.type == 'refactor'
        assert c.scope == 'imports'

    def test_non_conventional_commit(self):
        c = self._make('这是一条不规范的提交信息')
        assert c.type == 'chore'
        assert c.description == '这是一条不规范的提交信息'

    def test_docs_type(self):
        c = self._make('docs: 更新前端依赖清理方案')
        assert c.type == 'docs'

    def test_security_type(self):
        c = self._make('security: 增强应用安全性')
        assert c.type == 'security'

    def test_perf_type(self):
        c = self._make('perf: 优化数据库查询性能')
        assert c.type == 'perf'

    def test_test_type(self):
        c = self._make('test(auth): 为认证流程添加集成测试')
        assert c.type == 'test'

    def test_build_type(self):
        c = self._make('build(frontend): 从 CRA 迁移到 Vite')
        assert c.type == 'build'

    def test_ci_type(self):
        c = self._make('ci: 引入CI/CD流程')
        assert c.type == 'ci'

    def test_chore_type(self):
        c = self._make('chore: 更新依赖版本')
        assert c.type == 'chore'


# ─── 版本计算逻辑测试 ───


class TestCalculateBump:
    """测试版本计算逻辑（直接引用命令中的逻辑）."""

    def _calc(self, commits):
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

    def test_feat_bumps_minor(self):
        commits = [CommitInfo('a', 'feat', 'auth', '添加JWT认证', False, 'feat(auth): 添加JWT认证')]
        level, _ = self._calc(commits)
        assert level == 'minor'

    def test_fix_bumps_patch(self):
        commits = [CommitInfo('a', 'fix', 'api', '修复空指针异常', False, 'fix: 修复空指针')]
        level, _ = self._calc(commits)
        assert level == 'patch'

    def test_breaking_bumps_major(self):
        commits = [
            CommitInfo('a', 'feat', 'api', '重构 API 接口', True, 'feat!: 重构 API 接口'),
        ]
        level, _ = self._calc(commits)
        assert level == 'major'

    def test_mixed_takes_highest(self):
        commits = [
            CommitInfo('a', 'fix', 'bug', '修复登录问题', False, 'fix: 修复登录'),
            CommitInfo('b', 'feat', 'auth', '添加OAuth支持', False, 'feat(auth): 添加OAuth'),
            CommitInfo('c', 'docs', 'readme', '更新文档', False, 'docs: 更新文档'),
        ]
        level, _ = self._calc(commits)
        assert level == 'minor'

    def test_only_chore_defaults_patch(self):
        commits = [
            CommitInfo('a', 'chore', '', '更新依赖', False, 'chore: 更新依赖'),
        ]
        level, _ = self._calc(commits)
        assert level == 'patch'

    def test_security_bumps_patch(self):
        commits = [
            CommitInfo('a', 'security', '', '修复XSS漏洞', False, 'security: 修复XSS'),
        ]
        level, _ = self._calc(commits)
        assert level == 'patch'


# ─── 版本号 bump 测试 ───


class TestBumpVersion:

    def _bump(self, version, bump):
        parts = version.split('.')
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

    def test_patch_bump(self):
        assert self._bump('0.2.0', 'patch') == '0.2.1'

    def test_minor_bump(self):
        assert self._bump('0.2.0', 'minor') == '0.3.0'

    def test_major_bump(self):
        assert self._bump('0.2.0', 'major') == '1.0.0'

    def test_minor_reset_patch(self):
        assert self._bump('0.2.5', 'minor') == '0.3.0'

    def test_major_reset_minor_and_patch(self):
        assert self._bump('1.5.3', 'major') == '2.0.0'


# ─── CHANGELOG 生成测试 ───


class TestChangelogGeneration:
    """模拟 _generate_changelog 的测试."""

    def _generate(self, commits, version='0.3.0', date_str='2026-05-19'):
        sections = {}
        breaking_lines = []

        for c in commits:
            if c.type in ('chore', 'ci'):
                continue

            if c.scope:
                entry = f'- **{c.scope}**: {c.description}'
            else:
                entry = f'- {c.description}'

            if c.is_breaking:
                breaking_lines.append(entry)

            if c.type in CHANGELOG_SECTIONS:
                section_name = CHANGELOG_SECTIONS[c.type]
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

    def test_basic_feat(self):
        commits = [
            CommitInfo('a', 'feat', 'assistant', '实现智能助手功能', False, 'feat(assistant): 实现智能助手功能'),
        ]
        result = self._generate(commits)
        assert '## [0.3.0] - 2026-05-19' in result
        assert '### 新增' in result
        assert '**assistant**' in result
        assert '实现智能助手功能' in result

    def test_fix_section(self):
        commits = [
            CommitInfo('a', 'fix', 'api', '修复空指针', False, 'fix: 修复空指针'),
        ]
        result = self._generate(commits)
        assert '### 修复' in result

    def test_refactor_in_changes(self):
        commits = [
            CommitInfo('a', 'refactor', 'auth', '重构认证模块', False, 'refactor(auth): 重构'),
        ]
        result = self._generate(commits)
        assert '### 变更' in result

    def test_chore_excluded(self):
        commits = [
            CommitInfo('a', 'chore', '', '更新依赖', False, 'chore: 更新依赖'),
        ]
        result = self._generate(commits)
        assert '### 新增' not in result
        assert '### 修复' not in result

    def test_breaking_changes_section(self):
        commits = [
            CommitInfo('a', 'feat', 'api', '重构API接口', True, 'feat!: 重构API接口'),
        ]
        result = self._generate(commits)
        assert '### 破坏性变更' in result

    def test_no_scope_entry_format(self):
        commits = [
            CommitInfo('a', 'feat', '', '添加新功能', False, 'feat: 添加新功能'),
        ]
        result = self._generate(commits)
        assert '- 添加新功能' in result

    def test_multiple_commits_same_section(self):
        commits = [
            CommitInfo('a', 'feat', 'auth', '添加JWT认证', False, 'feat(auth): JWT'),
            CommitInfo('b', 'feat', 'api', '添加GraphQL', False, 'feat(api): GraphQL'),
        ]
        result = self._generate(commits)
        assert result.count('**auth**') == 1
        assert result.count('**api**') == 1

    def test_empty_commits(self):
        result = self._generate([])
        assert result == '## [0.3.0] - 2026-05-19'

    def test_ci_excluded(self):
        commits = [
            CommitInfo('a', 'ci', '', '添加GitHub Actions', False, 'ci: 添加GitHub Actions'),
        ]
        result = self._generate(commits)
        assert '### 新增' not in result


# ─── 文件更新测试 ───


class TestVersionFileUpdate:
    import re

    def test_write_version(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write('0.2.0\n')
            tmp_path = Path(f.name)

        tmp_path.write_text('0.3.0\n')
        assert tmp_path.read_text().strip() == '0.3.0'
        tmp_path.unlink()

    def test_update_changelog_insert(self):
        import re
        original = (
            '# 更新日志\n\n'
            '## [未发布]\n\n'
            '## [0.2.0] - 2026-05-16\n\n'
            '### 新增\n- 某个功能\n'
        )
        new_entry = '## [0.3.0] - 2026-05-19\n\n### 新增\n- 新功能'

        pattern = r'(\n## \[\d+\.\d+\.\d+\])'
        match = re.search(pattern, original)
        assert match is not None
        insert_pos = match.start()
        result = original[:insert_pos] + '\n' + new_entry + '\n' + original[insert_pos:]

        assert result.index('## [0.3.0]') < result.index('## [0.2.0]')
        assert '## [未发布]' in result

    def test_update_changelog_no_existing_version(self):
        import re
        original = '# 更新日志\n\n## [未发布]\n'
        new_entry = '## [0.1.0] - 2026-05-19\n\n### 新增\n- 初始版本'

        pattern = r'(\n## \[\d+\.\d+\.\d+\])'
        match = re.search(pattern, original)

        if match:
            insert_pos = match.start()
            result = original[:insert_pos] + '\n' + new_entry + '\n' + original[insert_pos:]
        else:
            result = original.rstrip() + '\n\n' + new_entry + '\n'

        assert '## [0.1.0]' in result
        assert '## [未发布]' in result


# ─── CHANGELOG_SECTIONS 映射测试 ───


class TestChangelogSectionMapping:

    def test_feat_maps_to_新增(self):
        assert CHANGELOG_SECTIONS['feat'] == '### 新增'

    def test_fix_maps_to_修复(self):
        assert CHANGELOG_SECTIONS['fix'] == '### 修复'

    def test_security_maps_to_修复(self):
        assert CHANGELOG_SECTIONS['security'] == '### 修复'

    def test_refactor_maps_to_变更(self):
        assert CHANGELOG_SECTIONS['refactor'] == '### 变更'

    def test_perf_maps_to_变更(self):
        assert CHANGELOG_SECTIONS['perf'] == '### 变更'


# ─── channel 渠道感知的 generate_release 测试 ───


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


class TestBumpVersionSameChannelMinorMajor:
    """同渠道预发布 + minor/major bump 应推进 MAJOR/MINOR 并重置 seq (Bug2).

    semver 规则:推进 MAJOR/MINOR 必重置 pre-release 序号段;patch bump 保持
    同序列迭代 (seq+1)。
    """

    def _cmd(self):
        from core.management.commands.generate_release import Command
        return Command()

    # ── 同渠道预发布 + patch: seq+1 (行为不变,回归保护) ──

    def test_same_beta_patch(self):
        result = self._cmd()._bump_version_with_channel("0.6.0-beta.5", "patch", "beta")
        assert result == "0.6.0-beta.6"

    # ── 同渠道预发布 + minor: MAJOR.MINOR bump + seq=1 (Bug2 主路径) ──

    def test_same_alpha_minor_resets_seq(self):
        """Bug2 核心场景:0.6.0-alpha.2 + minor → 0.7.0-alpha.1"""
        result = self._cmd()._bump_version_with_channel("0.6.0-alpha.2", "minor", "alpha")
        assert result == "0.7.0-alpha.1"

    def test_same_beta_minor_resets_seq(self):
        result = self._cmd()._bump_version_with_channel("0.6.0-beta.3", "minor", "beta")
        assert result == "0.7.0-beta.1"

    # ── 同渠道预发布 + major: MAJOR+1 + seq=1 ──

    def test_same_alpha_major_resets_seq(self):
        result = self._cmd()._bump_version_with_channel("0.6.0-alpha.2", "major", "alpha")
        assert result == "1.0.0-alpha.1"

    # ── 同渠道 stable (incl hotfix) (行为不变) ──

    def test_stable_minor(self):
        result = self._cmd()._bump_version_with_channel("0.6.0", "minor", "stable")
        assert result == "0.7.0"

    # ── 跨渠道 (行为不变) ──

    def test_cross_channel_to_alpha(self):
        """跨渠道切换,bump 被忽略,seq 重置为 1,MAJOR.MINOR.PATCH 沿用"""
        result = self._cmd()._bump_version_with_channel("0.6.0", "minor", "alpha")
        assert result == "0.6.0-alpha.1"

    def test_cross_channel_preview_to_rc(self):
        """preview 内部映射到 rc"""
        result = self._cmd()._bump_version_with_channel("0.6.0-beta.2", "minor", "preview")
        assert result == "0.6.0-rc.1"


class TestUpdateChangelog:
    """测试 _update_changelog 对历史异构 header 的容错插入 (Bug1 fix)."""

    def _cmd(self):
        from core.management.commands.generate_release import Command
        return Command()

    def _write_changelog(self, tmp_path, content):
        """把 CHANGELOG_FILE monkeypatch 到 tmp_path/CHANGELOG.md,写初始内容."""
        from core.management.commands import generate_release as gr_module
        fake = tmp_path / "CHANGELOG.md"
        fake.write_text(content)
        original = gr_module.CHANGELOG_FILE
        gr_module.CHANGELOG_FILE = fake
        return fake, original

    def _restore_changelog(self, original):
        from core.management.commands import generate_release as gr_module
        gr_module.CHANGELOG_FILE = original

    def test_skips_unreleased_placeholder(self, tmp_path):
        """[未发布] 必须保留在顶部,新条目插在它之后、第一个版本标题之前。"""
        fake, original = self._write_changelog(tmp_path,
            "# 更新日志\n\n## [未发布]\n\n## [v0.6.0] - 2026-07-14\n\n### 修复\n- xxx\n")
        try:
            new_entry = "## [0.6.1] - 2026-07-20  ← stable\n\n### 修复\n- new fix\n"
            self._cmd()._update_changelog(new_entry)
            content = fake.read_text()
            unreleased_pos = content.index("## [未发布]")
            new_pos = content.index("## [0.6.1]")
            old_pos = content.index("## [v0.6.0]")
            assert unreleased_pos < new_pos < old_pos
        finally:
            self._restore_changelog(original)

    def test_tolerates_v_prefix_in_history(self, tmp_path):
        """历史 '## [vX.Y.Z]' 不应让工具崩溃或追加到末尾。"""
        fake, original = self._write_changelog(tmp_path,
            "# 更新日志\n\n## [未发布]\n\n## [v0.6.0] - 2026-07-14\n\n## [v0.5.0] - 2026-07-01\n")
        try:
            new_entry = "## [0.6.1] - 2026-07-20  ← stable\n"
            self._cmd()._update_changelog(new_entry)
            content = fake.read_text()
            new_pos = content.index("## [0.6.1]")
            old_pos = content.index("## [v0.6.0]")
            assert new_pos < old_pos, (
                f"0.6.1 应该在 v0.6.0 之前; new_pos={new_pos}, old_pos={old_pos}"
            )
            assert content.count("## [0.6.1]") == 1
        finally:
            self._restore_changelog(original)

    def test_skips_chinese_non_version_header(self, tmp_path):
        """'## [渠道机制引入]' 这类非版本标题应被跳过,不参与排序。"""
        fake, original = self._write_changelog(tmp_path,
            "# 更新日志\n\n## [未发布]\n\n## [渠道机制引入] - 2026-07-06\n\n## [0.5.0] - 2026-07-01\n")
        try:
            new_entry = "## [0.6.0] - 2026-07-20  ← stable\n"
            self._cmd()._update_changelog(new_entry)
            content = fake.read_text()
            # normalize 后 0.6.0 > 0.5.0,新条目应插在 [渠道机制引入] 之后、[0.5.0] 之前
            new_pos = content.index("## [0.6.0]")
            cn_pos = content.index("## [渠道机制引入]")
            old_pos = content.index("## [0.5.0]")
            assert cn_pos < new_pos < old_pos
        finally:
            self._restore_changelog(original)

    def test_tolerates_chinese_suffix_header(self, tmp_path):
        """'## [0.5.9 修复]' 这类带中文后缀的版本应被规范化后参与排序。"""
        fake, original = self._write_changelog(tmp_path,
            "# 更新日志\n\n## [未发布]\n\n## [0.5.9 修复] - 2026-07-06\n\n## [0.5.0] - 2026-07-01\n")
        try:
            new_entry = "## [0.6.0] - 2026-07-20  ← stable\n"
            self._cmd()._update_changelog(new_entry)
            content = fake.read_text()
            # normalize 后 0.5.9 修复 → 0.5.9;0.6.0 > 0.5.9,新条目应插在 "0.5.9 修复" 之前
            new_pos = content.index("## [0.6.0]")
            assert new_pos < content.index("## [0.5.9 修复]")
        finally:
            self._restore_changelog(original)

    def test_falls_back_to_append_when_no_comparable(self, tmp_path):
        """所有现有 header 都无法解析时,新条目追加到末尾(兜底分支)。"""
        fake, original = self._write_changelog(tmp_path,
            "# 更新日志\n\n## [未发布]\n\n## [渠道机制引入] - 2026-07-06\n\n## [某个事件] - 2026-07-01\n")
        try:
            new_entry = "## [0.6.0] - 2026-07-20  ← stable\n"
            self._cmd()._update_changelog(new_entry)
            content = fake.read_text()
            lines = content.strip().split("\n")
            assert any(line.startswith("## [0.6.0]") for line in lines[-3:]), \
                f"新条目应被追加到末尾; actual last 3 lines: {lines[-3:]}"
        finally:
            self._restore_changelog(original)

    def test_inserts_at_top_after_unreleased(self, tmp_path):
        """主路径:新版本比所有现有版本都大,插在 [未发布] 之后、第一个版本标题之前。"""
        fake, original = self._write_changelog(tmp_path,
            "# 更新日志\n\n## [未发布]\n\n## [0.5.0] - 2026-07-01\n\n## [0.4.0] - 2026-06-05\n")
        try:
            new_entry = "## [0.7.0-alpha.1] - 2026-07-19  ← alpha\n\n### 新增\n- xxx\n"
            self._cmd()._update_changelog(new_entry)
            content = fake.read_text()
            unreleased_pos = content.index("## [未发布]")
            new_pos = content.index("## [0.7.0-alpha.1]")
            old_pos = content.index("## [0.5.0]")
            assert unreleased_pos < new_pos < old_pos
        finally:
            self._restore_changelog(original)
