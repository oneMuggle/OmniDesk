# generate_release 工具两 Bug 修复 设计规范

**日期:** 2026-07-19
**项目:** OmniDesk
**作者:** Claude
**状态:** 待用户审阅

---

## 1. 背景与目标

### 1.1 问题

2026-07-14 发布 v0.6.0 stable、2026-07-19 发布 v0.7.0-alpha.1 时,`generate_release` 工具两处自动化逻辑失灵,需人工绕过:

| # | 触发场景 | 现象 | 实际绕过方式 |
|---|---|---|---|
| Bug 1 | `python manage.py generate_release` 自动插 CHANGELOG 条目 | 新条目被错误追加到文件末尾 | 手工编辑 CHANGELOG.md,把条目移至正确位置 |
| Bug 2 | main 分支进入新 minor 周期 (`0.6.0-alpha.X` → `0.7.0-alpha.1`) | 工具返回 `0.6.0-alpha.3`,而非 `0.7.0-alpha.1` | 手工编辑 `deployment/docker/VERSION` 设基线 |

两 Bug 的根因已定位:

- **Bug 1** 在 `generate_release.py:301-312`:`_update_changelog` 调用 `compare_versions → parse_version`,后者正则 `^\d+\.\d+\.\d+(?:-(?:alpha|beta|rc)\.\d+)?$` 严格拒绝 `v` 前缀(`## [v0.6.0-alpha.2]`)和中文后缀(`## [0.5.9 修复]`)。绝大多数历史 header 解析失败 → `insert_pos` 始终 None → 落入"追加末尾"分支(行 316)。
- **Bug 2** 在 `generate_release.py:211-214`:`_bump_version_with_channel` 在 `parsed.channel == internal_channel`(同渠道预发布)分支只做 `seq + 1`,完全忽略 `bump` 参数。`0.6.0-alpha.2 + bump=minor` 错误返回 `0.6.0-alpha.3`,正确应为 `0.7.0-alpha.1`(semver:minor 推进必重置 seq)。

### 1.2 目标

**彻底修复** `generate_release` 工具两处自动化逻辑,使从下一次 alpha 发布开始无需任何人工绕道。

### 1.3 范围(明确做与不做)

| 做 | 不做 |
|---|---|
| `version_utils.py` 新增 `try_parse_version` 和 `normalize_changelog_header` | 改动 `parse_version` 的严格契约(已有测试 `test_invalid(["v1.2.3"])` 锁定) |
| 修 `_update_changelog` 用新 helper 做容错解析 | 重构 CHANGELOG 整体格式 |
| 修 `_bump_version_with_channel` 加 same-channel-major/minor 分支 | 改动 `_calculate_bump`(其逻辑正确) |
| 新增 `normalize_changelog_headers` management command 一次性规范化历史 header | 引入新依赖或第三方 semver 库 |
| 一次性运行 migration 改写 CHANGELOG.md(`## [vX.Y.Z]` → `## [X.Y.Z]`,约 10 行) | 大批量重写 CHANGELOG 历史中文标题行(`0.5.9 修复` 等保留原样) |
| 单元测试覆盖两 bug 的所有边界 | E2E 测试(发布流程是手动命令,无 E2E 必要) |

---

## 2. 设计方案

### 2.1 架构总览

```
omni_desk_backend/core/version_utils.py
  ├─ parse_version(s)            [不变,契约保持]
  ├─ try_parse_version(s)       [新增] 严格版本的容错包装,失败返 None
  ├─ normalize_changelog_header(raw) [新增] CHANGELOG header 文本 → 干净 SemVer 字符串
  ├─ _CHANGELOG_HEADER_VERSION_RE    [新增] 模块级 regex 常量
  └─ _rank_tuple(p)              [新增] ParsedVersion → 可比较元组(stable > rc > beta > alpha)

omni_desk_backend/core/management/commands/generate_release.py
  ├─ _update_changelog()        [改] 用 normalize + try_parse 替代裸 parse_version
  └─ _bump_version_with_channel() [改] 同渠道预发布 + major/minor → MAJOR/MINOR bump + seq=1

omni_desk_backend/core/management/commands/normalize_changelog_headers.py [新增]
  └─ 一次性迁移命令:扫描 CHANGELOG.md,规范化为新格式(--dry-run 支持)

omni_desk_backend/core/tests/
  ├─ test_version_utils.py       [改] 新增 TestTryParseVersion + TestNormalizeChangelogHeader
  └─ test_generate_release.py    [改] 新增 TestBumpVersionWithChannel + TestUpdateChangelog 容错

deployment/docker/CHANGELOG.md   [一次性改] 约 10 行去掉 v 前缀(由 migration 命令执行)
```

### 2.2 `version_utils.py` 新增函数

#### 2.2.1 `try_parse_version`

```python
def try_parse_version(version: object) -> Optional[ParsedVersion]:
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

#### 2.2.2 `normalize_changelog_header`

```python
_CHANGELOG_HEADER_VERSION_RE = re.compile(
    r"^(\d+\.\d+\.\d+(?:-(?:alpha|beta|rc)\.\d+)?)"
)

def normalize_changelog_header(raw: str) -> Optional[str]:
    """把 CHANGELOG header 中 [] 内的原始文本规范化为 SemVer 字符串.

    处理历史异构格式:
      - 'v0.6.0-alpha.2' → '0.6.0-alpha.2'  (去前导 v)
      - '0.5.9 修复'     → '0.5.9'           (去中文/空格后缀)
      - 'V0.4.0'         → '0.4.0'           (大小写不敏感)
      - '渠道机制引入'   → None               (纯文本非版本)
      - '0.7.0-alpha.1'  → '0.7.0-alpha.1'   (已规范,原样返回)
    """
    if not isinstance(raw, str):
        return None
    cleaned = raw.strip()
    if not cleaned:
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

### 2.3 `_update_changelog` 改造(行 300-312)

```python
# 改造前:直接 compare_versions,失败抛 ValueError
# 改造后:
new_parsed = try_parse_version(new_version)
# ... 在循环里:
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
    if new_parsed is None:
        continue  # 新条目版本号格式异常,跳过比较
    # 用 SemVer 元组比较(stable > rc > beta > alpha,序号大者靠后)
    if _rank_tuple(new_parsed) > _rank_tuple(existing_parsed):
        insert_pos = match.start()
        break
```

辅助函数 `_rank_tuple`(放置于 `version_utils.py`,与 `_CHANGELOG_HEADER_VERSION_RE` 一同作为 CHANGELOG 解析工具):
```python
_CHANNEL_RANK = {"alpha": 0, "beta": 1, "rc": 2, None: 3}

def _rank_tuple(p: ParsedVersion) -> tuple:
    return (p.major, p.minor, p.patch, _CHANNEL_RANK[p.channel], p.channel_num or 0)
```

排序语义与现有 `compare_versions` 一致(stable 排在 alpha 之后,即更大)。`_rank_tuple` 与 `compare_versions` 的返回结果在所有输入下完全一致(可由单元测试断言保证),仅形式上前者返回元组便于比较,后者返回 int。

### 2.4 `_bump_version_with_channel` 改造(行 211-214)

```python
# 同渠道预发布(alpha/beta/rc)
if parsed.channel == internal_channel:
    if bump in ("major", "minor"):
        # MAJOR/MINOR bump 同时触发新序列,seq 重置为 1
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

四种场景对照表(同渠道预发布):

| current | bump | channel | new | 理由 |
|---|---|---|---|---|
| 0.6.0-alpha.2 | patch | alpha | 0.6.0-alpha.3 | 同 alpha 内增量修补 |
| 0.6.0-alpha.2 | minor | alpha | 0.7.0-alpha.1 | 新 minor 周期,seq 重置 |
| 0.6.0-alpha.2 | major | alpha | 1.0.0-alpha.1 | 新 major 周期,seq 重置 |
| 0.6.0-beta.3 | minor | beta | 0.7.0-beta.1 | 同 beta,新 minor 周期 |

跨渠道 / 同渠道 stable 行为不变(已在现有测试覆盖)。

### 2.5 新增 `normalize_changelog_headers` 命令

```python
# omni_desk_backend/core/management/commands/normalize_changelog_headers.py
class Command(BaseCommand):
    help = "一次性规范化 CHANGELOG.md 历史 header: 去掉 v 前缀 / 跳过非版本标题"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true",
                            help="仅打印变更,不写文件")

    def handle(self, *args, **options):
        content = CHANGELOG_FILE.read_text()
        pattern = re.compile(r"^## \[([^\]]+)\]", re.MULTILINE)
        changes, skipped = [], []

        def replace(match):
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
            self.stdout.write(self.style.WARNING("=== DRY RUN ==="))
        else:
            CHANGELOG_FILE.write_text(new_content)

        self.stdout.write(f"已规范化 {len(changes)} 个 header:")
        for old, new in changes:
            self.stdout.write(f"  - [{old}] → [{new}]")
        self.stdout.write(f"跳过 {len(skipped)} 个非版本标题:")
        for s in skipped:
            self.stdout.write(f"  - [{s}]")
```

### 2.6 数据流(整体发布流程,不变)

```
generate_release.handle()
  → _read_version()                     [不变]
  → _detect_channel_from_git()          [不变]
  → get_commits_since()                 [不变]
  → _calculate_bump()                   [不变]
  → _bump_version_with_channel()        [改:同渠道 + major/minor 正确处理]
  → _generate_changelog()               [不变]
  → _write_version()                    [不变]
  → _update_changelog()                 [改:容错解析历史 header]
```

---

## 3. 错误处理

| 场景 | 行为 |
|---|---|
| `try_parse_version` 输入非 str(如 None) | 返回 None,不抛异常 |
| `normalize_changelog_header` 输入空串或纯中文 | 返回 None,调用方显式 continue |
| 历史 header 含未预料的特殊字符(如 emoji) | 走正则前缀匹配,失败返 None,不抛 |
| `normalize_changelog_headers` 遇到未识别 header | 跳过,记入 skipped 列表,不影响其他行 |
| `normalize_changelog_headers --dry-run` | 只打印,不写文件 |
| `_bump_version_with_channel` 新分支无新异常路径 | 只调 `format_version`,已有校验覆盖 |

---

## 4. 测试策略

### 4.1 `test_version_utils.py` 新增

| 测试类 | 用例数 | 覆盖 |
|---|---|---|
| `TestTryParseVersion` | 8 | 5 valid + 3 invalid(None / 非 str / `v1.2.3` / `1.2.3-alpha`) |
| `TestNormalizeChangelogHeader` | 12(参数化) | `vX.Y.Z` / `V0.5.0` / `0.5.9 修复` / `0.4.0 hotfix` / `渠道机制引入` / 空串 / `未发布` / 中文带空格 / 大小写混合 |

### 4.2 `test_generate_release.py` 新增

| 测试类 | 用例数 | 覆盖 |
|---|---|---|
| `TestBumpVersionWithChannel` | 8(参数化) | 同渠道 stable × 3 / 同渠道 alpha × 4(patch/minor/major/cross)/ 同渠道 beta × 1(minor) |
| `TestUpdateChangelog` | 6 | 含 `未发布` 跳过 / 含 `vX.Y.Z` 容错 / 含中文标题跳过 / 含 `渠道机制引入` 跳过 / 末尾追加兜底 / 顶部插入主路径 |

测试用 `tmp_path` fixture 写临时 CHANGELOG,避免污染 `deployment/docker/CHANGELOG.md`。
覆盖率目标:`version_utils.py` ≥ 90%,`generate_release.py` 中被改动函数 100% 行覆盖。

### 4.3 集成验证(发布前 smoke test)

实施完成后,执行:
```bash
python manage.py normalize_changelog_headers --dry-run   # 预演:应显示 9 处变化
python manage.py normalize_changelog_headers             # 实际执行
git diff deployment/docker/CHANGELOG.md | head -50       # 人工核对
python manage.py generate_release --preview --channel alpha  # 模拟下次 alpha 发布,验证新版本号推算与 CHANGELOG 插入位置
```

---

## 5. 实施步骤(高层)

1. **创建分支** `fix/generate-release-parse-bumps` (按 feature-branch-workflow)
2. **新增 helper** 在 `version_utils.py` (`try_parse_version` + `normalize_changelog_header` + `_rank_tuple` + `_CHANGELOG_HEADER_VERSION_RE`),附单元测试
3. **修改 `_bump_version_with_channel`**,附参数化测试
4. **修改 `_update_changelog`**,附 `tmp_path` 集成测试
5. **新增 `normalize_changelog_headers.py` 命令**,附 `--dry-run` 测试
6. **本地验证**:`pytest` 全绿 + `python manage.py normalize_changelog_headers --dry-run` 输出符合预期
7. **运行 migration**:`python manage.py normalize_changelog_headers`,commit CHANGELOG.md 改动
8. **PR + CI**,review,merge

---

## 6. 风险与依赖

| 风险 | 缓解 |
|---|---|
| 修 `_update_changelog` 引入回归(原本能解析的现在不能) | 参数化测试覆盖所有现有能解析的格式 + 异构格式 |
| 修 `_bump_version_with_channel` 误改其他分支 | 仅动行 211-214 一个分支,其他三个分支行为不变;加 8 个参数化用例覆盖所有同渠道矩阵 |
| 一次性 migration 误改非版本标题行 | `normalize_changelog_header` 对非 SemVer 标题返回 None,migration 命令显式跳过 |
| 新增 management command 与现有命令命名冲突 | `core/management/commands/` 下现有命令: `backup_db / check_migrations / create_admin / generate_release / list_versions / restore_db`,新名 `normalize_changelog_headers` 无冲突 |

**依赖:** 无外部依赖,纯 Python 标准库 + Django base;不需要更新 requirements。

---

## 7. 不在范围

- ❌ 不做 CHANGELOG 整体格式重构(如迁移到 Keep a Changelog 英文标准版)
- ❌ 不动 `parse_version` 契约(已有 `test_invalid(["v1.2.3"])` 测试锁定)
- ❌ 不引入第三方 semver 库(标准库 + 自有 30 行 regex 足够)
- ❌ 不动 `_generate_changelog` / `_calculate_bump` / `_read_version`(均工作正确)
- ❌ 不动 `git_utils.py`(commit 解析逻辑无 bug)
- ❌ 不修 E2E 发布流程(目前无 E2E,手动命令流程足够)
