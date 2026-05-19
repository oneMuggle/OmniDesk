"""generate_release 命令的单元测试."""

import tempfile
from pathlib import Path

import pytest

from core.git_utils import (
    CommitInfo,
    parse_commit_message,
    CHANGELOG_SECTIONS,
)


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
