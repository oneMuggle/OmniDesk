# generate_release 工具两 Bug 修复 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 `generate_release.py` 两处自动化 bug——CHANGELOG 历史 header 解析失败 (Bug 1) + 同渠道 minor/major bump 推进错误 (Bug 2)——并提供一次性 migration 命令规范化 CHANGELOG 历史。

**Architecture:** 在 `version_utils.py` 新增三个容错 helper (`try_parse_version` / `normalize_changelog_header` / `_rank_tuple` + 一个模块级 regex 常量);修改 `generate_release.py` 中两个方法使用新 helper;新增 Django management command `normalize_changelog_headers` 做一次性迁移(支持 `--dry-run`)。

**Tech Stack:** Python 3.10, Django 4.2, pytest, 标准库 `re`。

---

## Global Constraints

- **Python 3.10 统一** (per CLAUDE.md)
- **Conda 环境** `omni_desk`,Python 解释器绝对路径 `/home/fz/anaconda3/envs/omni_desk/bin/python` (Bash 工具不持久化 conda activate)
- **测试 settings** 用 `--ds=omni_desk_backend.settings.test` (in-memory SQLite, MD5 hasher)
- **不动 `parse_version` 契约** (已有 `test_invalid(["v1.2.3"])` 测试锁定其严格行为)
- **不引入新依赖** (纯标准库)
- **命名规范:** camelCase 函数与变量,模块级私有常量前导 `_` (`_CHANGELOG_HEADER_VERSION_RE` / `_rank_tuple` / `_CHANNEL_RANK`)
- **类型注解:** 用 `Optional[T]` (与 `version_utils.py` 现有 dataclass 风格一致)
- **进度报告中文** (per language.md),代码注释中文,代码标识符英文
- **覆盖率目标:** `version_utils.py` ≥ 90%, `generate_release.py` 中被改动函数 100% 行覆盖
- **Commit message 走 conventional commits 格式** (feat/fix/docs/test/chore/refactor)
- **Feature 分支命名** `fix/generate-release-parse-bumps`,走 PR 流程 (per feature-branch-workflow.md)
- **Push 前 `pytest` 必须全绿**,CI 监控由 executing-plans 子 skill 处理

---

## File Structure

| File | Role | Action |
|---|---|---|
| `omni_desk_backend/core/version_utils.py` | SemVer 工具 + CHANGELOG header 解析 | 新增 4 个符号 |
| `omni_desk_backend/core/management/commands/generate_release.py` | 版本发布主命令 | 改 2 个方法 + 扩 import |
| `omni_desk_backend/core/management/commands/normalize_changelog_headers.py` | 一次性 CHANGELOG 迁移命令 | 新建 |
| `omni_desk_backend/core/tests/test_version_utils.py` | version_utils 测试 | 新增 2 个测试类 (25 用例) |
| `omni_desk_backend/core/tests/test_generate_release.py` | generate_release 测试 | 新增 3 个测试类 (20 用例) |
| `deployment/docker/CHANGELOG.md` | CHANGELOG 历史文件 | 一次性 ~10 行去 v 前缀 |

---

## Task 0: Setup — 创建 feature 分支

**Files:**
- No file changes; git operation only

- [ ] **Step 1: 确认工作区干净**

Run: `git status`
Expected: "无文件要提交，干净的工作区"

- [ ] **Step 2: 同步 main**

Run: `git fetch origin main && git pull --rebase origin main`
Expected: "Already up to date." 或 fast-forward

- [ ] **Step 3: 创建并切换到 feature 分支**

Run: `git switch -c fix/generate-release-parse-bumps`
Expected: "切换到一个新分支 'fix/generate-release-parse-bumps'"

---

## Task 1: 新增 `try_parse_version` helper

**Files:**
- Modify: `omni_desk_backend/core/version_utils.py` (在 `compare_versions` 之后追加)
- Modify: `omni_desk_backend/core/tests/test_version_utils.py` (追加 TestTryParseVersion 类)

**Interfaces:**
- Produces: `try_parse_version(version: object) -> Optional[ParsedVersion]`
  - 接受任意类型输入;非 str 或无法解析返 None;成功返 ParsedVersion
  - 行为: `try: return parse_version(s.strip()) except ValueError: return None`

- [ ] **Step 1: Write failing test**

在 `omni_desk_backend/core/tests/test_version_utils.py` **末尾追加**:

```python
class TestTryParseVersion:
    def test_valid_stable(self):
        from core.version_utils import try_parse_version
        assert try_parse_version("1.2.3") == ParsedVersion(1, 2, 3, None, None)

    def test_valid_alpha(self):
        from core.version_utils import try_parse_version
        assert try_parse_version("0.6.0-alpha.2") == ParsedVersion(0, 6, 0, "alpha", 2)

    def test_valid_beta(self):
        from core.version_utils import try_parse_version
        assert try_parse_version("0.5.9-beta.3") == ParsedVersion(0, 5, 9, "beta", 3)

    def test_valid_rc(self):
        from core.version_utils import try_parse_version
        assert try_parse_version("1.2.0-rc.2") == ParsedVersion(1, 2, 0, "rc", 2)

    def test_strips_whitespace(self):
        from core.version_utils import try_parse_version
        assert try_parse_version("  0.5.9  ") == ParsedVersion(0, 5, 9, None, None)

    def test_invalid_returns_none(self):
        from core.version_utils import try_parse_version
        assert try_parse_version("v1.2.3") is None  # 前导 'v' 仍被拒绝(契约不变)

    def test_chinese_returns_none(self):
        from core.version_utils import try_parse_version
        assert try_parse_version("渠道机制引入") is None

    def test_non_string_returns_none(self):
        from core.version_utils import try_parse_version
        assert try_parse_version(None) is None
        assert try_parse_version(123) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
/home/fz/anaconda3/envs/omni_desk/bin/python -m pytest omni_desk_backend/core/tests/test_version_utils.py::TestTryParseVersion -v --ds=omni_desk_backend.settings.test
```
Expected: FAIL with `ImportError: cannot import name 'try_parse_version' from 'core.version_utils'`

- [ ] **Step 3: Implement helper**

修改 `omni_desk_backend/core/version_utils.py`:确认文件顶部已有 `from __future__ import annotations` (若没有则在 `import re` 之前添加);然后在 `compare_versions` 函数定义之后追加:

```python
def try_parse_version(version: object) -> "Optional[ParsedVersion]":
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
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
/home/fz/anaconda3/envs/omni_desk/bin/python -m pytest omni_desk_backend/core/tests/test_version_utils.py::TestTryParseVersion -v --ds=omni_desk_backend.settings.test
```
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add omni_desk_backend/core/version_utils.py omni_desk_backend/core/tests/test_version_utils.py
git commit -m "feat(version_utils): add try_parse_version for lenient CHANGELOG parsing"
```

---

## Task 2: 新增 `normalize_changelog_header` + `_CHANGELOG_HEADER_VERSION_RE`

**Files:**
- Modify: `omni_desk_backend/core/version_utils.py` (在 `try_parse_version` 之后追加)
- Modify: `omni_desk_backend/core/tests/test_version_utils.py` (追加 TestNormalizeChangelogHeader 类)

**Interfaces:**
- Produces: `_CHANGELOG_HEADER_VERSION_RE` (模块级 `re.Pattern`)
- Produces: `normalize_changelog_header(raw: object) -> Optional[str]`
  - 去前导 `v`/`V` → 整串 `try_parse_version` → 失败则正则前缀截取 → 仍失败返 None
  - 特殊: `"未发布"` 直接返 None (占位段不视为版本)

- [ ] **Step 1: Write failing test**

在 `omni_desk_backend/core/tests/test_version_utils.py` 末尾追加:

```python
class TestNormalizeChangelogHeader:
    @pytest.mark.parametrize("raw,expected", [
        # 已规范
        ("0.7.0-alpha.1", "0.7.0-alpha.1"),
        ("0.5.9", "0.5.9"),
        # 去 v 前缀
        ("v0.6.0-alpha.2", "0.6.0-alpha.2"),
        ("V0.4.0", "0.4.0"),
        # 去中文/英文后缀
        ("0.5.9 修复", "0.5.9"),
        ("0.4.0 hotfix", "0.4.0"),
        ("0.6.0-rc.5 release", "0.6.0-rc.5"),
        # 空白处理
        ("  0.6.0-beta.1  ", "0.6.0-beta.1"),
        # 非版本
        ("渠道机制引入", None),
        ("未发布", None),
        ("", None),
        ("v", None),
        ("1.2", None),
        # 复合
        ("v0.5.0-rc.1 hotfix", "0.5.0-rc.1"),
    ])
    def test_normalize(self, raw, expected):
        from core.version_utils import normalize_changelog_header
        assert normalize_changelog_header(raw) == expected

    def test_non_string_returns_none(self):
        from core.version_utils import normalize_changelog_header
        assert normalize_changelog_header(None) is None
        assert normalize_changelog_header(123) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
/home/fz/anaconda3/envs/omni_desk/bin/python -m pytest omni_desk_backend/core/tests/test_version_utils.py::TestNormalizeChangelogHeader -v --ds=omni_desk_backend.settings.test
```
Expected: FAIL with `ImportError: cannot import name 'normalize_changelog_header'`

- [ ] **Step 3: Implement**

在 `omni_desk_backend/core/version_utils.py` `compare_versions` 函数之前追加模块级 regex:

```python
# 用于从 CHANGELOG header 文本中提取 SemVer 前缀
_CHANGELOG_HEADER_VERSION_RE = re.compile(
    r"^(\d+\.\d+\.\d+(?:-(?:alpha|beta|rc)\.\d+)?)"
)
```

然后在 `try_parse_version` 之后追加:

```python
def normalize_changelog_header(raw: object) -> "Optional[str]":
    """把 CHANGELOG header 中 [] 内的原始文本规范化为 SemVer 字符串.

    处理历史异构格式:
      - 'v0.6.0-alpha.2' → '0.6.0-alpha.2'  (去前导 v)
      - '0.5.9 修复'     → '0.5.9'           (去中文/空格后缀)
      - 'V0.4.0'         → '0.4.0'           (大小写不敏感)
      - '渠道机制引入'   → None               (纯文本非版本)
      - '未发布'         → None               (占位段,不视为版本)
      - '0.7.0-alpha.1'  → '0.7.0-alpha.1'   (已规范,原样返回)

    返回 None 表示该 header 不是 SemVer,调用方应跳过而非尝试解析。
    """
    if not isinstance(raw, str):
        return None
    cleaned = raw.strip()
    if not cleaned or cleaned == "未发布":
        return None
    # 1. 去前导 v/V
    if cleaned[0] in ("v", "V"):
        cleaned = cleaned[1:]
    # 2. 整串尝试解析
    if try_parse_version(cleaned):
        return cleaned
    # 3. 截取以 \d+\.\d+\.\d+ 开头的最长前缀
    m = _CHANGELOG_HEADER_VERSION_RE.match(cleaned)
    if m:
        return m.group(1)
    return None
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
/home/fz/anaconda3/envs/omni_desk/bin/python -m pytest omni_desk_backend/core/tests/test_version_utils.py::TestNormalizeChangelogHeader -v --ds=omni_desk_backend.settings.test
```
Expected: 13 参数化 + 1 non-string = 14 passed

- [ ] **Step 5: Commit**

```bash
git add omni_desk_backend/core/version_utils.py omni_desk_backend/core/tests/test_version_utils.py
git commit -m "feat(version_utils): add normalize_changelog_header for mixed-format header parsing"
```

---

## Task 3: 新增 `_rank_tuple` + `_CHANNEL_RANK` helpers

**Files:**
- Modify: `omni_desk_backend/core/version_utils.py` (追加)
- Modify: `omni_desk_backend/core/tests/test_version_utils.py` (追加 TestRankTuple 类)

**Interfaces:**
- Produces: `_CHANNEL_RANK` (模块级 dict 常量, `{"alpha": 0, "beta": 1, "rc": 2, None: 3}`)
- Produces: `_rank_tuple(p: ParsedVersion) -> tuple`
  - 返回 `(major, minor, patch, channel_rank, channel_num_or_0)`
  - 与现有 `compare_versions` 在所有输入下同向

- [ ] **Step 1: Write failing test**

在 `omni_desk_backend/core/tests/test_version_utils.py` 末尾追加:

```python
class TestRankTuple:
    """`_rank_tuple` 必须与 `compare_versions` 在所有 SemVer 排序规则下同向."""

    @pytest.mark.parametrize("a,b", [
        # stable vs stable
        ("1.2.4", "1.2.3"),
        ("1.3.0", "1.2.9"),
        ("2.0.0", "1.99.99"),
        # stable > pre-release
        ("1.2.0", "1.2.0-rc.2"),
        ("1.2.0", "1.2.0-beta.1"),
        ("1.2.0", "1.2.0-alpha.99"),
        # channel ordering
        ("1.2.0-rc.1", "1.2.0-beta.1"),
        ("1.2.0-beta.1", "1.2.0-alpha.1"),
        # same channel, different seq
        ("1.2.0-alpha.2", "1.2.0-alpha.1"),
        ("1.2.0-beta.3", "1.2.0-beta.2"),
    ])
    def test_rank_agrees_with_compare(self, a, b):
        from core.version_utils import _rank_tuple, try_parse_version
        pa, pb = try_parse_version(a), try_parse_version(b)
        assert pa is not None and pb is not None
        assert _rank_tuple(pa) > _rank_tuple(pb)
        assert _rank_tuple(pb) < _rank_tuple(pa)
        # 与 compare_versions 同向
        assert compare_versions(a, b) == 1
        assert compare_versions(b, a) == -1

    @pytest.mark.parametrize("version,expected_rank", [
        ("1.2.0-alpha.3", (1, 2, 0, 0, 3)),
        ("1.2.0", (1, 2, 0, 3, 0)),
        ("1.2.0-rc.5", (1, 2, 0, 2, 5)),
        ("0.0.1-alpha.1", (0, 0, 1, 0, 1)),
    ])
    def test_rank_format(self, version, expected_rank):
        from core.version_utils import _rank_tuple
        assert _rank_tuple(parse_version(version)) == expected_rank
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
/home/fz/anaconda3/envs/omni_desk/bin/python -m pytest omni_desk_backend/core/tests/test_version_utils.py::TestRankTuple -v --ds=omni_desk_backend.settings.test
```
Expected: FAIL with `ImportError: cannot import name '_rank_tuple'`

- [ ] **Step 3: Implement**

在 `omni_desk_backend/core/version_utils.py` `normalize_changelog_header` 之后追加:

```python
# channel 排序权重:stable 最高,alpha 最低(与 compare_versions 同向)
_CHANNEL_RANK: dict[str | None, int] = {"alpha": 0, "beta": 1, "rc": 2, None: 3}


def _rank_tuple(p: ParsedVersion) -> tuple:
    """ParsedVersion → 可比较元组,顺序与 compare_versions 完全一致.

    排序:MAJOR.MINOR.PATCH 升序 → channel rank 升序(alpha < beta < rc < stable) → channel_num 升序。

    与 compare_versions 区别:本函数返回元组便于直接比较,后者返回 -1/0/1。
    所有输入下二者同向(由 TestRankTuple.test_rank_agrees_with_compare 保证)。
    """
    return (p.major, p.minor, p.patch, _CHANNEL_RANK[p.channel], p.channel_num or 0)
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
/home/fz/anaconda3/envs/omni_desk/bin/python -m pytest omni_desk_backend/core/tests/test_version_utils.py::TestRankTuple -v --ds=omni_desk_backend.settings.test
```
Expected: 10 参数化 (test_rank_agrees_with_compare) + 4 参数化 (test_rank_format) = 14 passed

- [ ] **Step 5: Commit**

```bash
git add omni_desk_backend/core/version_utils.py omni_desk_backend/core/tests/test_version_utils.py
git commit -m "feat(version_utils): add _rank_tuple for tuple-based SemVer comparison"
```

---

## Task 4: 修 `_bump_version_with_channel` 支持同渠道 major/minor bump

**Files:**
- Modify: `omni_desk_backend/core/management/commands/generate_release.py:211-214` (仅 1 个分支)
- Modify: `omni_desk_backend/core/tests/test_generate_release.py` (追加 TestBumpVersionWithChannel 类)

**Interfaces:**
- Modifies: `Command._bump_version_with_channel(current_version: str, bump: str, channel: str) -> str`
- 行为变更: 同渠道预发布 (`parsed.channel == internal_channel`) + bump 是 `minor`/`major` 时,推进 MAJOR/MINOR 并重置 seq=1;bump 是 `patch` 时保持旧行为 (seq+1)

- [ ] **Step 1: Write failing test**

在 `omni_desk_backend/core/tests/test_generate_release.py` 末尾追加:

```python
class TestBumpVersionWithChannel:
    """测试 Command._bump_version_with_channel 跨渠道与同渠道矩阵."""

    def _cmd(self):
        from core.management.commands.generate_release import Command
        return Command()

    # ── 同渠道预发布 + patch: seq+1 (行为不变) ──
    def test_same_alpha_patch(self):
        result = self._cmd()._bump_version_with_channel("0.6.0-alpha.2", "patch", "alpha")
        assert result == "0.6.0-alpha.3"

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

    def test_hotfix_patch(self):
        """hotfix 内部映射到 stable channel,patch +1"""
        result = self._cmd()._bump_version_with_channel("0.6.0", "patch", "hotfix")
        assert result == "0.6.1"

    # ── 跨渠道 (行为不变) ──
    def test_cross_channel_to_alpha(self):
        """跨渠道切换,bump 被忽略,seq 重置为 1,MAJOR.MINOR.PATCH 沿用"""
        result = self._cmd()._bump_version_with_channel("0.6.0", "minor", "alpha")
        assert result == "0.6.0-alpha.1"

    def test_cross_channel_preview_to_rc(self):
        """preview 内部映射到 rc"""
        result = self._cmd()._bump_version_with_channel("0.6.0-beta.2", "minor", "preview")
        assert result == "0.6.0-rc.1"
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
/home/fz/anaconda3/envs/omni_desk/bin/python -m pytest omni_desk_backend/core/tests/test_generate_release.py::TestBumpVersionWithChannel -v --ds=omni_desk_backend.settings.test
```
Expected: 3 个 FAIL:
- `test_same_alpha_minor_resets_seq`: `'0.6.0-alpha.3' != '0.7.0-alpha.1'`
- `test_same_beta_minor_resets_seq`: `'0.6.0-beta.4' != '0.7.0-beta.1'`
- `test_same_alpha_major_resets_seq`: `'0.6.0-alpha.3' != '1.0.0-alpha.1'`

其余 6 个通过(行为不变)。

- [ ] **Step 3: Fix `_bump_version_with_channel`**

修改 `omni_desk_backend/core/management/commands/generate_release.py` 行 211-214:

**旧代码 (删除):**
```python
        # 同渠道预发布(alpha/beta/rc):序号段 +1, MAJOR.MINOR.PATCH 不变
        if parsed.channel == internal_channel:
            new_seq = (parsed.channel_num or 0) + 1
            return format_version(major, minor, patch, internal_channel, new_seq)
```

**新代码 (替换):**
```python
        # 同渠道预发布(alpha/beta/rc):
        #   - bump=patch: 序号段 +1, MAJOR.MINOR.PATCH 不变 (同序列迭代)
        #   - bump=minor/major: MAJOR/MINOR 推进, PATCH 归零, 序号段重置为 1 (新开发周期)
        if parsed.channel == internal_channel:
            if bump in ("major", "minor"):
                if bump == "major":
                    major += 1
                    minor = 0
                    patch = 0
                else:  # minor
                    minor += 1
                    patch = 0
                new_seq = 1
            else:  # patch
                new_seq = (parsed.channel_num or 0) + 1
            return format_version(major, minor, patch, internal_channel, new_seq)
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
/home/fz/anaconda3/envs/omni_desk/bin/python -m pytest omni_desk_backend/core/tests/test_generate_release.py::TestBumpVersionWithChannel -v --ds=omni_desk_backend.settings.test
```
Expected: 9 passed

- [ ] **Step 5: Commit**

```bash
git add omni_desk_backend/core/management/commands/generate_release.py omni_desk_backend/core/tests/test_generate_release.py
git commit -m "fix(generate_release): same-channel minor/major bump resets seq

Bug2 fix: 0.6.0-alpha.X + bump=minor + channel=alpha 现在返回 0.7.0-alpha.1,
而非错误地把序号段 +1 得到 0.6.0-alpha.(X+1)。

semver 规则:推进 MAJOR/MINOR 必重置 pre-release 序号段;patch bump 保持
同序列迭代(seq+1)。"
```

---

## Task 5: 修 `_update_changelog` 容错解析历史 header

**Files:**
- Modify: `omni_desk_backend/core/management/commands/generate_release.py` (扩 import + 重写行 278-318 `_update_changelog`)
- Modify: `omni_desk_backend/core/tests/test_generate_release.py` (追加 TestUpdateChangelog 类)

**Interfaces:**
- Consumes: `try_parse_version`, `normalize_changelog_header`, `_rank_tuple` from `core.version_utils`
- Modifies: `Command._update_changelog(new_entry: str) -> None` (签名不变,内部用容错 helper)
- 测试通过 monkeypatch 模块级 `CHANGELOG_FILE` 常量指向 tmp_path

- [ ] **Step 1: Write failing test**

在 `omni_desk_backend/core/tests/test_generate_release.py` 末尾追加:

```python
class TestUpdateChangelog:
    """测试 _update_changelog 对历史异构 header 的容错插入."""

    def _cmd(self):
        from core.management.commands.generate_release import Command
        return Command()

    def _write_changelog(self, tmp_path, content):
        """把 CHANGELOG_FILE monkeypatch 到 tmp_path/CHANGELOG.md,写初始内容。返回 (fake_path, original_CHANGELOG_FILE)。"""
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
            assert "## [0.6.0]" in lines[-3:], "新条目应被追加到末尾"
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
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
/home/fz/anaconda3/envs/omni_desk/bin/python -m pytest omni_desk_backend/core/tests/test_generate_release.py::TestUpdateChangelog -v --ds=omni_desk_backend.settings.test
```
Expected: 4 个 FAIL:
- `test_skips_unreleased_placeholder`: 因 v 前缀 → compare_versions 抛 ValueError → 追加到末尾
- `test_tolerates_v_prefix_in_history`: 同上,新条目不在 v0.6.0 之前
- `test_tolerates_chinese_suffix_header`: 中文后缀 → 跳过 → 误判 insert_pos

`test_skips_chinese_non_version_header` 与 `test_falls_back_to_append_when_no_comparable` 与 `test_inserts_at_top_after_unreleased` 可能在旧代码下也通过(回归保护)。

- [ ] **Step 3: Fix `_update_changelog`**

**Step 3a:** 修改 `omni_desk_backend/core/management/commands/generate_release.py` 行 24-29 import 块,从:

```python
from core.version_utils import (
    CHANNEL_NAMES,
    compare_versions,
    format_version,
    parse_version,
)
```

改为:

```python
from core.version_utils import (
    CHANNEL_NAMES,
    compare_versions,
    format_version,
    parse_version,
    try_parse_version,
    normalize_changelog_header,
    _rank_tuple,
)
```

**Step 3b:** 替换 `_update_changelog` 方法 (行 278-318):

**旧代码 (删除):**
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
                CHANGELOG_FILE.write_text(content[:pos] + "\n" + new_entry + "\n" + content[pos:])
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
            CHANGELOG_FILE.write_text(content[:insert_pos] + new_entry + "\n\n" + content[insert_pos:])
```

**新代码 (替换):**
```python
    def _update_changelog(self, new_entry: str) -> None:
        """在 CHANGELOG.md 中按 SemVer 顺序插入新条目.

        排序规则:stable > rc > beta > alpha,序号大者靠后。
        [未发布] 段保留在顶部,新条目插在它与所有历史版本之间(按 SemVer 倒序)。

        容错:历史 header 中的 v 前缀、中文/英文后缀、非版本标题行
        (如 '## [渠道机制引入]')都会被 normalize_changelog_header 处理或跳过,
        不让单个 header 解析失败导致整次插入走兜底分支。
        """
        content = CHANGELOG_FILE.read_text()

        # 提取新条目的版本号(同样容错)
        m = re.match(r"## \[([^\]]+)\]", new_entry)
        new_version: str | None = None
        if m:
            new_version = normalize_changelog_header(m.group(1))
        if not new_version:
            # 新条目无法提取版本号,走兜底:插到 [未发布] 之后
            pattern = r"(## \[未发布\][^\n]*\n)"
            match = re.search(pattern, content)
            if match:
                pos = match.end()
                CHANGELOG_FILE.write_text(content[:pos] + "\n" + new_entry + "\n" + content[pos:])
            else:
                CHANGELOG_FILE.write_text(content.rstrip() + "\n\n" + new_entry + "\n")
            return
        new_parsed = try_parse_version(new_version)
        if new_parsed is None:
            # 新条目本身也无法解析,走兜底
            CHANGELOG_FILE.write_text(content.rstrip() + "\n\n" + new_entry + "\n")
            return

        # 扫描所有 ## [...] header,跳过 [未发布] 和无法解析的,找第一个比 new 大的位置插入
        existing_pattern = re.compile(r"^## \[([^\]]+)\]", re.MULTILINE)
        insert_pos = None
        for match in existing_pattern.finditer(content):
            raw = match.group(1)
            if raw == "未发布":
                continue
            normalized = normalize_changelog_header(raw)
            if not normalized:
                continue  # 非版本标题(如 '渠道机制引入'),跳过
            existing_parsed = try_parse_version(normalized)
            if not existing_parsed:
                continue  # 规范化后仍无法解析,跳过
            if _rank_tuple(new_parsed) > _rank_tuple(existing_parsed):
                insert_pos = match.start()
                break

        if insert_pos is None:
            CHANGELOG_FILE.write_text(content.rstrip() + "\n\n" + new_entry + "\n")
        else:
            CHANGELOG_FILE.write_text(content[:insert_pos] + new_entry + "\n\n" + content[insert_pos:])
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
/home/fz/anaconda3/envs/omni_desk/bin/python -m pytest omni_desk_backend/core/tests/test_generate_release.py::TestUpdateChangelog -v --ds=omni_desk_backend.settings.test
```
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add omni_desk_backend/core/management/commands/generate_release.py omni_desk_backend/core/tests/test_generate_release.py
git commit -m "fix(generate_release): _update_changelog tolerates mixed header formats

Bug1 fix: 历史 ## [vX.Y.Z] / ## [X.Y.Z 中文] / ## [非版本标题] 等
异构格式不再让 compare_versions 抛 ValueError;通过 normalize_changelog_header
统一规范化,无法规范化的非版本标题(如 '## [渠道机制引入]')显式跳过。"
```

---

## Task 6: 新增 `normalize_changelog_headers` management command

**Files:**
- Create: `omni_desk_backend/core/management/commands/normalize_changelog_headers.py`
- Modify: `omni_desk_backend/core/tests/test_generate_release.py` (追加 TestNormalizeChangelogCommand 类)

**Interfaces:**
- Produces: `Command.handle(*args, **options) -> None`
- Consumes: 模块级常量 `CHANGELOG_FILE` (从 generate_release 复用)
- Consumes: `normalize_changelog_header` from `core.version_utils`
- CLI flag: `--dry-run` (打印变更,不写文件)

- [ ] **Step 1: Write failing test**

在 `omni_desk_backend/core/tests/test_generate_release.py` 末尾追加:

```python
class TestNormalizeChangelogCommand:
    """测试一次性迁移命令 normalize_changelog_headers."""

    def _setup_changelog(self, tmp_path, content):
        from core.management.commands import generate_release as gr_module
        fake = tmp_path / "CHANGELOG.md"
        fake.write_text(content)
        original = gr_module.CHANGELOG_FILE
        gr_module.CHANGELOG_FILE = fake
        return fake, original

    def _restore_changelog(self, original):
        from core.management.commands import generate_release as gr_module
        gr_module.CHANGELOG_FILE = original

    def test_dry_run_does_not_modify_file(self, tmp_path):
        from io import StringIO
        from django.core.management import call_command
        initial = "# Log\n\n## [未发布]\n\n## [v0.6.0-alpha.1] - 2026-07-14\n\n## [0.5.0 修复] - 2026-07-06\n"
        fake, original = self._setup_changelog(tmp_path, initial)
        out = StringIO()
        try:
            call_command("normalize_changelog_headers", "--dry-run", stdout=out)
            assert fake.read_text() == initial, "dry-run 不应修改文件"
            assert "DRY RUN" in out.getvalue()
            assert "[v0.6.0-alpha.1]" in out.getvalue()
        finally:
            self._restore_changelog(original)

    def test_normalize_removes_v_prefix(self, tmp_path):
        from io import StringIO
        from django.core.management import call_command
        fake, original = self._setup_changelog(tmp_path,
            "# Log\n\n## [未发布]\n\n## [v0.6.0] - 2026-07-14\n")
        out = StringIO()
        try:
            call_command("normalize_changelog_headers", stdout=out)
            content = fake.read_text()
            assert "## [0.6.0]" in content
            assert "## [v0.6.0]" not in content
        finally:
            self._restore_changelog(original)

    def test_normalize_strips_chinese_suffix(self, tmp_path):
        """'## [0.5.0 修复]' 应被 normalize 为 '## [0.5.0]'。"""
        from io import StringIO
        from django.core.management import call_command
        fake, original = self._setup_changelog(tmp_path,
            "# Log\n\n## [未发布]\n\n## [v0.6.0] - 2026-07-14\n\n## [0.5.0 修复] - 2026-07-06\n")
        out = StringIO()
        try:
            call_command("normalize_changelog_headers", stdout=out)
            content = fake.read_text()
            assert "## [0.6.0]" in content
            assert "## [0.5.0]" in content  # 中文后缀被截
            assert "[0.5.0 修复]" not in content
        finally:
            self._restore_changelog(original)

    def test_skips_non_version_header(self, tmp_path):
        """'## [渠道机制引入]' 这类非版本标题行原样保留。"""
        from io import StringIO
        from django.core.management import call_command
        fake, original = self._setup_changelog(tmp_path,
            "# Log\n\n## [未发布]\n\n## [渠道机制引入] - 2026-07-06\n")
        out = StringIO()
        try:
            call_command("normalize_changelog_headers", stdout=out)
            content = fake.read_text()
            assert "## [渠道机制引入]" in content, "非版本标题应原样保留"
            assert "跳过 1 个非版本标题" in out.getvalue()
        finally:
            self._restore_changelog(original)

    def test_keeps_unreleased_unchanged(self, tmp_path):
        from io import StringIO
        from django.core.management import call_command
        fake, original = self._setup_changelog(tmp_path, "# Log\n\n## [未发布]\n")
        out = StringIO()
        try:
            call_command("normalize_changelog_headers", stdout=out)
            content = fake.read_text()
            assert "## [未发布]" in content
            assert "已规范化 0 个 header" in out.getvalue()
        finally:
            self._restore_changelog(original)
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
/home/fz/anaconda3/envs/omni_desk/bin/python -m pytest omni_desk_backend/core/tests/test_generate_release.py::TestNormalizeChangelogCommand -v --ds=omni_desk_backend.settings.test
```
Expected: 全部 FAIL,首条错误为 `Unknown command: 'normalize_changelog_headers'`

- [ ] **Step 3: Create command file**

新建 `omni_desk_backend/core/management/commands/normalize_changelog_headers.py`:

```python
"""Django 管理命令 — 一次性规范化 CHANGELOG.md 历史 header.

处理:
  - '## [vX.Y.Z]' → '## [X.Y.Z]'  (去除 v 前缀)
  - '## [X.Y.Z 中文]' → '## [X.Y.Z]'  (去除中文/空格后缀)
  - '## [渠道机制引入]' 这类非版本标题行原样保留(显式跳过)

典型用法:
  python manage.py normalize_changelog_headers --dry-run   # 预演
  python manage.py normalize_changelog_headers             # 实际执行
"""

import re

from django.core.management.base import BaseCommand

from core.management.commands.generate_release import CHANGELOG_FILE
from core.version_utils import normalize_changelog_header


class Command(BaseCommand):
    help = "一次性规范化 CHANGELOG.md 历史 header: 去掉 v 前缀 / 跳过非版本标题"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="仅打印变更,不写文件",
        )

    def handle(self, *args, **options):
        content = CHANGELOG_FILE.read_text()
        pattern = re.compile(r"^## \[([^\]]+)\]", re.MULTILINE)
        changes: list[tuple[str, str]] = []
        skipped: list[str] = []

        def replace(match: "re.Match[str]") -> str:
            raw = match.group(1)
            if raw == "未发布":
                return match.group(0)
            normalized = normalize_changelog_header(raw)
            if normalized is None:
                skipped.append(raw)
                return match.group(0)
            if normalized != raw:
                changes.append((raw, normalized))
            return f"## [{normalized}]"

        new_content = pattern.sub(replace, content)

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("=== DRY RUN (未修改文件) ==="))
        else:
            CHANGELOG_FILE.write_text(new_content)

        self.stdout.write(f"已规范化 {len(changes)} 个 header:")
        for old, new in changes:
            self.stdout.write(f"  - [{old}] → [{new}]")
        self.stdout.write(f"跳过 {len(skipped)} 个非版本标题:")
        for s in skipped:
            self.stdout.write(f"  - [{s}]")
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
/home/fz/anaconda3/envs/omni_desk/bin/python -m pytest omni_desk_backend/core/tests/test_generate_release.py::TestNormalizeChangelogCommand -v --ds=omni_desk_backend.settings.test
```
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add omni_desk_backend/core/management/commands/normalize_changelog_headers.py omni_desk_backend/core/tests/test_generate_release.py
git commit -m "feat(core): add normalize_changelog_headers management command

一次性迁移命令:扫描 CHANGELOG.md 历史 headers,通过 normalize_changelog_header
去除 'v' 前缀和中文/英文后缀。非版本标题(如 '## [渠道机制引入]')原样保留
并记入 skipped 列表。支持 --dry-run 预演。"
```

---

## Task 7: 实际运行 migration 改写 deployment/docker/CHANGELOG.md

**Files:**
- Modify: `deployment/docker/CHANGELOG.md` (~10 行去 v 前缀,部分中文后缀行被截)

- [ ] **Step 1: 预演 migration**

Run:
```bash
/home/fz/anaconda3/envs/omni_desk/bin/python manage.py normalize_changelog_headers --dry-run --settings=omni_desk_backend.settings.test
```
Expected: 列出约 8-10 个变化 (主要是 `## [v0.6.0-alpha.X]` → `## [0.6.0-alpha.X]` 等),并显示跳过的非版本标题 (如 `## [渠道机制引入]`)

- [ ] **Step 2: 实际执行 migration**

Run:
```bash
/home/fz/anaconda3/envs/omni_desk/bin/python manage.py normalize_changelog_headers --settings=omni_desk_backend.settings.test
```
Expected: 写入新内容到 `deployment/docker/CHANGELOG.md`,stdout 打印 "已规范化 N 个 header"

- [ ] **Step 3: 用 git diff 核对变更**

Run:
```bash
git diff deployment/docker/CHANGELOG.md
```
Expected: 显示约 8-12 行变化:
- `## [vX.Y.Z]` → `## [X.Y.Z]` (约 8 处,主要是 v0.6.0-alpha 系列)
- `## [X.Y.Z 中文]` → `## [X.Y.Z]` (1-2 处,如 `## [0.5.9 修复]` → `## [0.5.9]`)
- `## [渠道机制引入]` 不变 (normalize 返回 None,跳过)

- [ ] **Step 4: 手动复核所有 header**

Run:
```bash
grep -n "^## " deployment/docker/CHANGELOG.md
```
Expected:
- `## [未发布]` 不变 (第 14 行)
- `## [0.7.0-alpha.1]` 不变 (已是新格式)
- 所有历史 `## [vX.Y.Z]` 现在是 `## [X.Y.Z]`
- `## [渠道机制引入]` 保留(非版本标题)
- 中文后缀行(如 `## [0.5.9 修复]`)已变为 `## [0.5.9]`

如发现任何标题被错误处理(例如某个有意义的 `## [0.5.9 修复]` 不该被简化为 `## [0.5.9]`),用 `git checkout deployment/docker/CHANGELOG.md` 回滚,然后修改 `normalize_changelog_header` 的中文后缀处理逻辑(让其保留原样而非截前缀)再重新跑。

- [ ] **Step 5: Commit**

```bash
git add deployment/docker/CHANGELOG.md
git commit -m "chore(changelog): normalize historical headers via normalize_changelog_headers

按 generate_release 新解析器要求,去除历史 header 中的 'v' 前缀
(如 '## [v0.6.0-alpha.2]' → '## [0.6.0-alpha.2]')。非版本标题
(如 '## [渠道机制引入]')原样保留。"
```

---

## Task 8: 全量回归测试 + Push + PR

**Files:**
- No code changes; CI + git operations

- [ ] **Step 1: 运行 core 模块全量测试 + 覆盖率**

Run:
```bash
/home/fz/anaconda3/envs/omni_desk/bin/python -m pytest omni_desk_backend/core/tests/ -v --ds=omni_desk_backend.settings.test \
  --cov=omni_desk_backend.core.version_utils \
  --cov=omni_desk_backend.core.management.commands.generate_release \
  --cov=omni_desk_backend.core.management.commands.normalize_changelog_headers \
  --cov-report=term-missing
```
Expected: 所有测试 PASS,coverage:
- `version_utils.py` ≥ 90%
- `generate_release.py` 中 `_update_changelog` / `_bump_version_with_channel` 100% 行覆盖

- [ ] **Step 2: 运行项目全量测试,确认无回归**

Run:
```bash
/home/fz/anaconda3/envs/omni_desk/bin/python -m pytest omni_desk_backend/ -v --ds=omni_desk_backend.settings.test -x --ignore=omni_desk_backend/external_integration
```
Expected: 全 PASS。若有失败,先修复再继续。

- [ ] **Step 3: 推送 feature 分支到 origin**

Run:
```bash
git push -u origin fix/generate-release-parse-bumps
```
Expected: 推送成功,显示新远程分支

- [ ] **Step 4: 创建 PR**

Run:
```bash
gh pr create \
  --title "fix(generate_release): 修复 CHANGELOG 历史 header 解析失败 + 同渠道 minor/major bump 推进错误" \
  --body "## 背景

generate_release 工具在 2026-07-19 发布 v0.7.0-alpha.1 时暴露两处自动化 bug,需人工绕过:

- **Bug 1**: \`_update_changelog\` 对历史 \`## [vX.Y.Z]\` / \`## [X.Y.Z 中文]\` / \`## [非版本标题]\` 等异构 header 解析失败,新条目被错误追加到文件末尾
- **Bug 2**: \`_bump_version_with_channel\` 在同渠道预发布(alpha/beta/rc)+ bump=minor 时未应用 MAJOR/MINOR bump 且未重置 seq,导致 \`0.6.0-alpha.2 + minor → 0.6.0-alpha.3\` 而非预期的 \`0.7.0-alpha.1\`

## 修复内容

- \`version_utils.py\` 新增 4 个符号:
  - \`try_parse_version(s)\`: 容错版 parse_version,失败返 None
  - \`normalize_changelog_header(raw)\`: 把 CHANGELOG header 中 [] 内文本规范化为 SemVer,处理 v 前缀 / 中文后缀
  - \`_rank_tuple(p)\`: ParsedVersion → 可比较元组
  - \`_CHANGELOG_HEADER_VERSION_RE\`: 模块级 regex 常量
- \`generate_release.py\`:
  - \`_update_changelog\` 改用新 helper,容错解析历史 header
  - \`_bump_version_with_channel\` 加 same-channel-major/minor 分支:应用 MAJOR/MINOR bump + seq=1
- 新增 \`normalize_changelog_headers\` management command,一次性改写 CHANGELOG 历史(去 v 前缀),支持 --dry-run

## 测试

- 新增 \`TestTryParseVersion\` (8) / \`TestNormalizeChangelogHeader\` (15) / \`TestRankTuple\` (14)
- 新增 \`TestBumpVersionWithChannel\` (9) / \`TestUpdateChangelog\` (6) / \`TestNormalizeChangelogCommand\` (5)
- 覆盖率: version_utils.py ≥ 90%, generate_release.py 改动函数 100%

## 验证步骤

\`\`\`bash
python manage.py normalize_changelog_headers --dry-run --settings=omni_desk_backend.settings.test
\`\`\`
输出已确认 ~10 处变化(主要是 v 前缀去除)。" \
  --base main
```
Expected: PR URL printed

- [ ] **Step 5: 监控 CI**

Run:
```bash
gh pr checks <PR_NUMBER> --watch
```
Expected: 所有 checks 通过(若失败,按 ci-cd-workflow 规则 STOP 报告用户)

- [ ] **Step 6: 报告完成**

如 CI 绿,报告 PR URL 给用户;若用户合并,按 feature-branch-workflow 清理分支:
```bash
git push origin --delete fix/generate-release-parse-bumps
git branch -d fix/generate-release-parse-bumps
```
