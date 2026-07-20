# mypy 错误清理与 CI 阻塞化 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 OmniDesk backend 的 82 个 mypy 错误清理到 0，并将 mypy 任务改造为 CI 阻塞门控，所有变更通过 8 个按错误码类别组织的 PR 合入 `fix/mypy-cleanup` 基线分支。

**Architecture:** 长期基线分支 `fix/mypy-cleanup` + 8 个临时工作分支 `fix/mypy-cleanup/{category}` 串行合入。每个 PR 聚焦单一 mypy 错误码（var-annotated → attr-defined → assignment → override → arg-type → no-any-return → misc），由易到难渐进；最后 PR8 切 CI 阻塞化。每个 PR 完成后基线分支 rebase develop 保持同步。

**Tech Stack:**
- Python 3.10（CI）/ 3.11（本地），mypy 2.1.0（CI）/ 1.17.1（本地）
- Django 4.2 + DRF + djangorestframework-simplejwt
- GitFlow + develop/release 渠道分支模型
- 现有 ruff + pytest 测试链
- 基线脚本 Bash

**Spec 引用：** `docs/superpowers/specs/2026-07-14-mypy-cleanup-design.md`

## Global Constraints

- **Python 版本**：CI 跑 3.10，本地 OmniDesk conda 环境 3.11；类型语法须兼容两者
- **PEP 604 语法**：统一用 `T | None`，不用 `Optional[T]`（CI 3.10+ 支持）
- **不收紧 mypy 严格度**：保持 `disallow_untyped_defs = False`
- **零业务行为变化**：仅类型注解与签名调整
- **压制策略**：
  - 禁止裸 `# type: ignore`，必须 `# type: ignore[code]  # reason: <why>`
  - 禁止文件级 `# mypy: disable-error-code=`
  - 禁止修改 `mypy.ini` 全局加 `disable_error_code=`
  - 禁止把 `dict[Any, Any]` 改 `Any` 逃避问题
- **每处压制必须登记**到 `docs/technical/35-mypy-suppressions.md`
- **commit message 格式**：`fix(mypy): <category> - <一句话>`，body 列 `mypy: error count X→Y`
- **PR 体积上限**：≤ 7 文件 / ≤ 400 行 diff
- **PR 顺序**：PR0 → PR1 → PR2 → PR3 → PR4 → PR5 → PR6 → PR7 → PR8
- **基线分支**：`fix/mypy-cleanup`，所有 8 个 PR 都合这里（不是 develop）

## File Structure

| 文件 | 状态 | 责任 |
|---|---|---|
| `pyproject.toml` | 新建（PR0） | [tool.ruff] 配置从 mypy.ini 拆过来 |
| `omni_desk_backend/mypy.ini` | 修改（PR0） | 仅保留 [mypy] 段，去除 [tool.ruff] |
| `scripts/mypy_baseline.sh` | 新建（PR0） | 验证脚本：`mypy . --ignore-missing-imports` |
| `docs/technical/35-mypy-suppressions.md` | 新建（PR0） | 压制登记总账 |
| `docs/superpowers/specs/2026-07-14-mypy-cleanup-design.md` | 已存在 | 设计规范（参考） |
| `docs/plans/2026-07-14_mypy-cleanup.md` | 本文档 | 实施计划 |
| `~30 个错误文件` | 修改（PR1-7） | 8 个 PR 共涉及 ~30 个 backend 文件 |
| `.github/workflows/ci.yml` | 修改（PR8） | 移除 continue-on-error，加 needs: |

---

## Phase 0：Worktree 准备

### Task 0.1：创建基线分支与首个工作分支

**Files:**
- Create: branch `fix/mypy-cleanup`
- Create: branch `fix/mypy-cleanup/setup` (PR0 用)

**Interfaces:**
- Consumes: 当前在 `release` 分支，工作区干净
- Produces: `fix/mypy-cleanup` 基线分支指向 `release` 同 commit，`fix/mypy-cleanup/setup` 基于基线创建

- [ ] **Step 1：确认当前分支和工作区干净**

```bash
cd /home/fz/project/OmniDesk
git status
git branch --show-current
```

预期：`release` 分支，无 staged/unstaged 改动。如有，先 `git stash` 或 commit。

- [ ] **Step 2：创建基线分支**

```bash
git switch -c fix/mypy-cleanup
```

- [ ] **Step 3：推基线分支到 origin**

```bash
git push -u origin fix/mypy-cleanup
```

- [ ] **Step 4：创建 PR0 工作分支**

```bash
git switch -c fix/mypy-cleanup/setup
```

- [ ] **Step 5：验证分支状态**

```bash
git branch --show-current
git log --oneline -1
```

预期：当前分支 `fix/mypy-cleanup/setup`，最新 commit 是 release 渠道最新。

---

## Phase 1：PR0 — 配置拆分与基线建立

### Task 1.1：拆分 mypy.ini → pyproject.toml + mypy.ini

**Files:**
- Create: `/home/fz/project/OmniDesk/pyproject.toml` (root)
- Modify: `/home/fz/project/OmniDesk/omni_desk_backend/mypy.ini`

**Interfaces:**
- Consumes: 当前 mypy.ini 文件（含 [tool.ruff] + [mypy] 混合段）
- Produces: 
  - root `pyproject.toml` 含 [tool.ruff] / [tool.ruff.lint] / [tool.ruff.lint.per-file-ignores] / [tool.ruff.lint.isort]
  - `omni_desk_backend/mypy.ini` 仅含 [mypy] / [mypy-django.*] / [mypy-rest_framework.*] / [mypy-celery.*]

- [ ] **Step 1：读当前 mypy.ini 完整内容**

```bash
cat omni_desk_backend/mypy.ini
```

预期：看到 [tool.ruff] 段在 [mypy] 段之前。

- [ ] **Step 2：创建 root pyproject.toml**

写入 `/home/fz/project/OmniDesk/pyproject.toml`：

```toml
# ruff 配置 (从 omni_desk_backend/mypy.ini 拆过来)

[tool.ruff]
line-length = 120
target-version = "py310"
extend-exclude = [
    "**/migrations/**",
    "**/__pycache__/**",
    "**/node_modules/**",
    "deployment/**",
    "docs/**",
    "scripts/**",
    "test-artifacts/**",
]

[tool.ruff.lint]
select = ["E", "F", "W", "I", "UP", "B", "SIM", "RUF"]
ignore = [
    "E501", "F403", "F405", "RUF012",
    "RUF002", "RUF003",
    "SIM108", "SIM114", "RUF005",
    "B904", "UP008", "I001",
    "RUF001", "F841", "B007", "E402",
    "UP017", "B028", "RUF013",
    "SIM110", "SIM102", "RUF022",
    "F541", "B023", "F811", "RUF010",
    "RUF015", "UP028", "RUF059",
]

[tool.ruff.lint.per-file-ignores]
"omni_desk_backend/settings/*.py" = ["F403", "F405", "E402"]
"users/serializers.py" = ["F401"]
"users/user_serializers.py" = ["F401"]
"events/views.py" = ["F401"]
"events/serializers.py" = ["F401"]

[tool.ruff.lint.isort]
known-first-party = ["omni_desk_backend"]
```

> 注：以上为示例结构，**实施时必须从原 mypy.ini 完整复制 [tool.ruff] 段内容**，不能简化。

- [ ] **Step 3：精简 mypy.ini 为纯 mypy 配置**

写入 `/home/fz/project/OmniDesk/omni_desk_backend/mypy.ini`（完全覆盖）：

```ini
[mypy]
python_version = 3.11
warn_return_any = True
warn_unused_configs = True
disallow_untyped_defs = False
explicit_package_bases = True

[mypy-django.*]
ignore_missing_imports = True

[mypy-rest_framework.*]
ignore_missing_imports = True

[mypy-celery.*]
ignore_missing_imports = True
```

> **删除原 mypy.ini 中以下段**（mypy 报 unused）：
> - `[mypy-redis.*]`
> - `[mypy-psycopg2.*]`
> - `[mypy-django_filters.*]`
> - `[mypy-corsheaders.*]`
> - `[mypy-drf_spectacular.*]`
> - 全部 `[tool.ruff*]` 段

- [ ] **Step 4：验证 ruff 仍工作**

```bash
cd omni_desk_backend
ruff check . --statistics
```

预期：与拆分前统计数字一致（同样的 warning 数）。

- [ ] **Step 5：验证 mypy 仍读到配置**

```bash
cd omni_desk_backend
mypy --show-error-context --show-error-codes smart_assistant/ 2>&1 | head -20
```

预期：不再报 `[mypy-redis.*]` 等 unused config 警告，但 mypy 错误本身未变（PR0 不修错）。

---

### Task 1.2：建立基线脚本

**Files:**
- Create: `/home/fz/project/OmniDesk/scripts/mypy_baseline.sh`

**Interfaces:**
- Consumes: 项目根目录结构
- Produces: 可执行脚本 `scripts/mypy_baseline.sh [path]`，输出 mypy 错误统计末行

- [ ] **Step 1：创建 scripts 目录（如不存在）**

```bash
mkdir -p scripts
```

- [ ] **Step 2：写入基线脚本**

写入 `/home/fz/project/OmniDesk/scripts/mypy_baseline.sh`：

```bash
#!/usr/bin/env bash
# mypy 错误基线验证脚本
# 用法:
#   bash scripts/mypy_baseline.sh           # 检查整个 backend
#   bash scripts/mypy_baseline.sh <path>    # 检查指定子目录
# 输出: mypy 末行 "Found N errors in M files (checked K source files)"
set -euo pipefail
TARGET="${1:-.}"
cd "$(dirname "$0")/../omni_desk_backend"
mypy "${TARGET}" --ignore-missing-imports --no-error-summary 2>&1 | tail -3
```

- [ ] **Step 3：加可执行权限**

```bash
chmod +x scripts/mypy_baseline.sh
```

- [ ] **Step 4：运行基线确认**

```bash
bash scripts/mypy_baseline.sh
```

预期：末行 `Found 82 errors in 45 files (checked XX source files)`（或当前实际数字，**记下此数字**作为 PR0 baseline）。

- [ ] **Step 5：分目录确认（找最大热点）**

```bash
bash scripts/mypy_baseline.sh smart_assistant/
```

预期：smart_assistant 子目录的错误数（按之前探查约 51）。记下此数字。

---

### Task 1.3：创建压制登记文档

**Files:**
- Create: `/home/fz/project/OmniDesk/docs/technical/35-mypy-suppressions.md`

- [ ] **Step 1：检查 docs/technical/ 是否已有 35- 编号文件**

```bash
ls docs/technical/ | grep -E "^3[0-9]-" | sort
```

预期：列表中**没有** `35-*` 文件。如有，改用下一个可用编号。

- [ ] **Step 2：写入压制登记文档**

写入 `/home/fz/project/OmniDesk/docs/technical/35-mypy-suppressions.md`：

```markdown
# mypy 压制登记册

> 最后更新：2026-07-14
> 维护者：Claude / 用户
> 关联 spec：`docs/superpowers/specs/2026-07-14-mypy-cleanup-design.md`

本文件追踪所有 `# type: ignore[code]` 压制点。每处压制必须在引入的同一 PR 中登记。

| 文件:行 | 错误码 | 原因 | 计划清理 PR / 触发条件 |
|---|---|---|---|
| (待填充) | | | |

## 维护规则

- **每加一个 `# type: ignore[code]`，必须在此文件加一行**（同一 PR 内）
- 每月审视一次"计划清理"列，对到期项目开 issue / PR
- 任何 # type: ignore 必须有 reason（一句话说明为何不修）
```

- [ ] **Step 3：确认文档结构**

```bash
cat docs/technical/35-mypy-suppressions.md
```

---

### Task 1.4：验证 PR0 不引入新错

**Files:** 不修改（仅验证）

- [ ] **Step 1：mypy 全 backend 跑一次**

```bash
bash scripts/mypy_baseline.sh
```

预期：末行错误数与 Task 1.2 Step 4 一致（PR0 不应改错数）。

- [ ] **Step 2：ruff 全 backend 跑一次**

```bash
cd omni_desk_backend && ruff check . --statistics
```

预期：与 PR0 拆分前一致。

- [ ] **Step 3：pytest smoke test**

```bash
cd omni_desk_backend && pytest --ds=omni_desk_backend.settings.test -x -q
```

预期：全绿（或与 PR0 拆分前相同的失败数）。

- [ ] **Step 4：Django check**

```bash
cd omni_desk_backend && python manage.py check
```

预期：输出 `System check identified no issues (0 silenced).`

---

### Task 1.5：Commit + Push + 开 PR0

**Files:** 已创建/修改的所有文件

- [ ] **Step 1：Stage 全部变更**

```bash
cd /home/fz/project/OmniDesk
git add pyproject.toml omni_desk_backend/mypy.ini scripts/mypy_baseline.sh docs/technical/35-mypy-suppressions.md
git status
```

预期：4 个新/修改文件已 staged。

- [ ] **Step 2：Commit**

```bash
git commit -m "chore(mypy): PR0 - 拆分 mypy.ini 配置 + 建立基线验证

- 新建 root pyproject.toml, 收纳原 mypy.ini 中的 [tool.ruff] 段
- mypy.ini 精简为纯 [mypy] 配置, 删除 unused 段 ([mypy-redis.*] 等)
- 新建 scripts/mypy_baseline.sh: mypy 错误统计验证脚本
- 新建 docs/technical/35-mypy-suppressions.md: 压制登记总账
- mypy baseline: Found 82 errors in 45 files (与 PR0 前一致, 零变更)"
```

- [ ] **Step 3：Push**

```bash
git push -u origin fix/mypy-cleanup/setup
```

- [ ] **Step 4：开 PR → fix/mypy-cleanup 基线分支**

```bash
gh pr create --base fix/mypy-cleanup --head fix/mypy-cleanup/setup \
  --title "chore(mypy): PR0 - 拆分 mypy.ini 配置 + 建立基线验证" \
  --body "## 目的
拆分 mypy.ini 混合配置, 建立基线验证机制, 不修任何 mypy 错误.

## 变更
- \`pyproject.toml\` (新建): 收纳 [tool.ruff] 段
- \`omni_desk_backend/mypy.ini\` (修改): 精简为纯 [mypy] 段
- \`scripts/mypy_baseline.sh\` (新建): mypy 错误统计脚本
- \`docs/technical/35-mypy-suppressions.md\` (新建): 压制登记总账

## baseline
- mypy: Found 82 errors in 45 files
- ruff: 与拆分前一致
- pytest: 全绿
- Django check: 无 warning

Refs: docs/superpowers/specs/2026-07-14-mypy-cleanup-design.md §3.2"
```

- [ ] **Step 5：等 CI 绿 + 用户 merge**

监控 `gh pr checks --watch`，绿灯后请用户 merge 到 `fix/mypy-cleanup` 基线分支。

- [ ] **Step 6：合并后清理本地分支（保留基线）**

```bash
git switch fix/mypy-cleanup
git pull --rebase
git branch -d fix/mypy-cleanup/setup
git push origin --delete fix/mypy-cleanup/setup
```

---

## Phase 2：PR1 — var-annotated 错误清理

### Task 2.1：定位 var-annotated 错误

**Files:** 仅查询，不修改

- [ ] **Step 1：在 backend 跑 mypy，按错误码筛选**

```bash
cd omni_desk_backend
mypy . --ignore-missing-imports --show-error-codes --no-error-summary 2>&1 \
  | grep "\[var-annotated\]" | head -20
```

预期：列出所有 `var-annotated` 错误（预估 ~3 个），格式如 `path/to/file.py:LINE: error: ... [var-annotated]`

- [ ] **Step 2：记录涉及文件清单**

新建 `/tmp/mypy-pr1-files.txt`，写入所有文件路径（去重），每行一个：

```
omni_desk_backend/smart_assistant/agent/intent_classifier.py
omni_desk_backend/smart_assistant/agent/orchestrator.py
... (按实际输出)
```

- [ ] **Step 3：检查错误上下文**

对每个文件读取错误行（mypy 输出已给行号），确认是 class-level 变量缺类型注解（如 `REQUIRED_FIELDS = [...]` 缺 `: ClassVar[list[str]]` 或 `: list[str]`）。

---

### Task 2.2：逐个文件修复 var-annotated

**Files:** 修改 Task 2.1 列出的所有文件

- [ ] **Step 1：处理第一个文件**

读错误行 → 添加类型注解（典型模式）：

```python
# 报错
REQUIRED_FIELDS = ["name", "email"]

# 修复（class 变量）
REQUIRED_FIELDS: list[str] = ["name", "email"]
# 或（如果是 ClassVar）
from typing import ClassVar
REQUIRED_FIELDS: ClassVar[list[str]] = ["name", "email"]
```

- [ ] **Step 2：跑 mypy 验证该文件零错**

```bash
mypy omni_desk_backend/<modified_file> --ignore-missing-imports
```

预期：该文件零 var-annotated 错误（其他错误码可能仍存在，那是后续 PR 处理）。

- [ ] **Step 3：跑该文件对应测试**

```bash
cd omni_desk_backend
pytest <module_path>/tests/ -v
```

预期：全绿。

- [ ] **Step 4：重复 Step 1-3 处理所有 Task 2.1 文件**

- [ ] **Step 5：全 backend mypy 跑一次确认总数减少**

```bash
bash scripts/mypy_baseline.sh
```

预期：末行错误数比 PR0 baseline 少 3（或实际修复数）。

---

### Task 2.3：Commit + Push + 开 PR1

- [ ] **Step 1：创建 PR1 工作分支**

```bash
cd /home/fz/project/OmniDesk
git switch fix/mypy-cleanup
git pull --rebase
git switch -c fix/mypy-cleanup/var-annotated
```

- [ ] **Step 2：Stage + Commit**

```bash
git add omni_desk_backend/smart_assistant/...（修改的文件）
git commit -m "fix(mypy): var-annotated 错误清理

- 为 class-level 变量添加类型注解 (list[str] / dict[str, Any] / ClassVar)
- 涉及 N 个文件 (实际数)
- mypy: error count 82→79 (N=3)"
```

- [ ] **Step 3：Push + 开 PR**

```bash
git push -u origin fix/mypy-cleanup/var-annotated
gh pr create --base fix/mypy-cleanup --head fix/mypy-cleanup/var-annotated \
  --title "fix(mypy): var-annotated 错误清理" \
  --body "## 变更
- (列出每个修改文件 + 简述)
- mypy: 82→79 (3 errors fixed)

Refs: docs/superpowers/specs/2026-07-14-mypy-cleanup-design.md §3.1 PR1"
```

- [ ] **Step 4：等 CI 绿 + 用户 merge**

- [ ] **Step 5：合并后清理**

```bash
git switch fix/mypy-cleanup
git pull --rebase
git branch -d fix/mypy-cleanup/var-annotated
git push origin --delete fix/mypy-cleanup/var-annotated
```

---

## Phase 3：PR2 — attr-defined / str 错误清理

### Task 3.1：定位错误

- [ ] **Step 1：mypy 筛选**

```bash
cd omni_desk_backend
mypy . --ignore-missing-imports --show-error-codes --no-error-summary 2>&1 \
  | grep -E "\[(attr-defined|str)\]" | head -20
```

- [ ] **Step 2：记录文件清单**

写入 `/tmp/mypy-pr2-files.txt`。

- [ ] **Step 3：分析错误模式**

attr-defined 错误通常是：
- 动态属性赋值（`obj.x = ...` 后读 `obj.x`）
- `__init__` 没声明该属性但其他方法用
- 协议 / 抽象类不匹配

---

### Task 3.2：逐个文件修复

- [ ] **Step 1：处理第一个文件**

常见修法：
```python
# 模式 1: __init__ 缺字段声明
class Foo:
    def __init__(self):
        self.name: str = ""  # 加类型注解
        self.created_at: datetime | None = None

# 模式 2: Protocol 不匹配
from typing import Protocol
class HasName(Protocol):
    name: str  # 加协议属性

# 模式 3: 动态属性加 TYPE_CHECKING 守卫或 # type: ignore[attr-defined]
```

- [ ] **Step 2-4：每文件 mypy + pytest 验证**

- [ ] **Step 5：基线确认**

```bash
bash scripts/mypy_baseline.sh
```

预期：末行比 PR1 完成后少 ~4（实际修复数）。

---

### Task 3.3：Commit + Push + 开 PR2

- [ ] **Step 1-5：与 Task 2.3 同流程**

工作分支：`fix/mypy-cleanup/attr-defined`
PR title: `fix(mypy): attr-defined / str 错误清理`
commit body 列 `mypy: error count X→Y`

---

## Phase 4：PR3 — assignment 主项（隐式 Optional 模式）

### Task 4.1：定位错误 + 模式分析

- [ ] **Step 1：mypy 筛选 assignment 错误**

```bash
cd omni_desk_backend
mypy . --ignore-missing-imports --show-error-codes --no-error-summary 2>&1 \
  | grep "\[assignment\]" | head -30
```

- [ ] **Step 2：分类**

```
grep "Incompatible default for parameter" <输出>  # 隐式 Optional（最大类）
grep "Incompatible types in assignment" <输出>     # 其他 assignment
```

预期：~23 个 assignment 错误中，绝大多数（>20）是"隐式 Optional"模式。

- [ ] **Step 3：记录文件清单到 /tmp/mypy-pr3-files.txt**

- [ ] **Step 4：识别集群模式**

8 个 tools/*.py 文件每个 8 个错误 = 64 个错误？等等——查 agent 报告：

> smart_assistant/tools/event_tool.py 10 errors
> smart_assistant/tools/{sensor,schedule,rag,project,personnel,news,memo}_tool.py 8 errors each

合计 tools: 10 + 7*8 = 66 errors，但 agent 总数说 51。**差额 15 来自 agent 报告口径**（smart_assistant/ 总 51，工具子类可能与 BaseTool 重叠计数）。

**PR3 实施时以 mypy 实际输出为准**。

---

### Task 4.2：批量修复隐式 Optional

**Files:** ~10-15 个文件含 `def foo(x: T = None)`

- [ ] **Step 1：处理第一个文件**

```python
# 报错
def execute(self, context: dict = None) -> dict:
    ...

# 修复（PEP 604）
def execute(self, context: dict | None = None) -> dict:
    ...

# 函数体: 若已含 `if context is None` 处理则不改
# 函数体: 若假设非空, 补 None 检查:
def execute(self, context: dict | None = None) -> dict:
    if context is None:
        context = {}
    ...
```

- [ ] **Step 2-4：每文件 mypy + pytest 验证**

- [ ] **Step 5：基线确认**

```bash
bash scripts/mypy_baseline.sh
```

预期：错误数比 PR2 完成后少 20+（隐式 Optional 23 个批量）。

---

### Task 4.3：处理剩余 assignment 错误

如 Step 1 分类后有"非隐式 Optional"的 assignment 错误（如 `Incompatible types in assignment (expression has type "X", variable has type "Y")`），单独处理。

- [ ] **Step 1：列出剩余 assignment 错误**

```bash
cd omni_desk_backend
mypy . --ignore-missing-imports --show-error-codes --no-error-summary 2>&1 \
  | grep "\[assignment\]" | grep -v "Incompatible default for parameter"
```

- [ ] **Step 2：逐个修复（典型模式：类型转换、None 检查、收紧类型）**

---

### Task 4.4：Commit + Push + 开 PR3

- [ ] **Step 1-5：与 Task 2.3 同流程**

工作分支：`fix/mypy-cleanup/assignment`
PR title: `fix(mypy): assignment 主项（隐式 Optional 模式）`
commit body 列 `mypy: error count X→Y`，预期 Y 比 X 少 20+

注意：本 PR 涉及文件数较多（~10-15），如超 7 文件或 400 行 diff，**考虑拆 PR3a / PR3b**（按目录拆：tools/ 一组，agent/ 一组）。

---

## Phase 5：PR4 — override 错误（BaseTool 接口对齐）

### Task 5.1：探查 BaseTool 抽象签名

**Files:** 仅读，不修改

- [ ] **Step 1：读 BaseTool 定义**

```bash
cat omni_desk_backend/smart_assistant/tools/base.py | head -200
```

- [ ] **Step 2：定位 `execute` 抽象方法**

```bash
grep -n "def execute\|abstractmethod\|ABC" omni_desk_backend/smart_assistant/tools/base.py
```

- [ ] **Step 3：读 1-2 个工具子类的 execute 实现**

```bash
grep -A 5 "def execute" omni_desk_backend/smart_assistant/tools/event_tool.py | head -20
grep -A 5 "def execute" omni_desk_backend/smart_assistant/tools/sensor_tool.py | head -20
```

- [ ] **Step 4：决策 A 还是 B**

| 情况 | 决策 |
|---|---|
| BaseTool 签名清晰合理 | 走 A：改子类 |
| BaseTool 签名 outdated | 走 B：先改父类（PR4a），再批量改子类（PR4b） |
| 不确定 | 优先走 A（影响面小） |

- [ ] **Step 5：记录决策到 /tmp/mypy-pr4-decision.txt**

```
决策: A (改子类)
原因: BaseTool 签名 [具体描述], 子类不一致源于 [具体原因]
```

---

### Task 5.2：路径 A — 改子类签名

**Files:** 8-11 个工具子类文件

- [ ] **Step 1：列出所有 override 错误所在文件**

```bash
cd omni_desk_backend
mypy . --ignore-missing-imports --show-error-codes --no-error-summary 2>&1 \
  | grep "\[override\]" | awk -F: '{print $1}' | sort -u
```

- [ ] **Step 2：对每个文件改 `def execute` 签名匹配父类**

```python
# 父类
def execute(self, context: dict[str, Any] | None = None, **kwargs) -> dict[str, Any]:
    ...

# 子类改前
def execute(self, ctx, **kwargs) -> dict:
    ...

# 子类改后
def execute(self, context: dict[str, Any] | None = None, **kwargs) -> dict[str, Any]:
    ...
```

> **警告**：如果子类内部用了 `self._xxx` 引用父类私有成员，先确认基类实际属性名再改。

- [ ] **Step 3-5：每文件 mypy + pytest 验证**

- [ ] **Step 6：跑全 backend pytest（必须，BaseTool 影响所有子类）**

```bash
cd omni_desk_backend
pytest --ds=omni_desk_backend.settings.test -q
```

预期：全绿。如有失败说明子类业务依赖旧签名，需调整子类逻辑（非仅签名）。

- [ ] **Step 7：基线确认**

```bash
bash scripts/mypy_baseline.sh
```

预期：错误数比 PR3 完成后少 11（override 全部清完）。

---

### Task 5.3：路径 B（如决策走 B）— 改父类

> **此 Task 仅在 Task 5.1 Step 4 决策为 B 时执行**。

- [ ] **Step 1：修改 `omni_desk_backend/smart_assistant/tools/base.py` 中 BaseTool.execute 抽象签名**

```python
# 改前
@abstractmethod
def execute(self, ctx: dict) -> dict:
    ...

# 改后（按 11 个子类的"最大公约数"调整）
@abstractmethod
def execute(self, context: dict[str, Any] | None = None, **kwargs: Any) -> dict[str, Any]:
    ...
```

- [ ] **Step 2：同步改 11 个子类（每文件 1 行）**

- [ ] **Step 3-4：验证全 backend pytest + mypy**

- [ ] **Step 5：拆 PR4a / PR4b**

如实际需拆，PR4a = 父类，PR4b = 11 个子类，分别走标准 PR 流程。

---

### Task 5.4：Commit + Push + 开 PR4

- [ ] **Step 1-5：与 Task 2.3 同流程**

工作分支：`fix/mypy-cleanup/override`（或 PR4a / PR4b）
PR title: `fix(mypy): override 错误（BaseTool 接口对齐）`
PR description 必须说明：决策（A 或 B）、影响文件清单、为什么该决策
commit body 列 `mypy: error count X→Y`

---

## Phase 6：PR5 — arg-type 错误清理

### Task 6.1：定位 + 修复 arg-type 错误

- [ ] **Step 1：mypy 筛选**

```bash
cd omni_desk_backend
mypy . --ignore-missing-imports --show-error-codes --no-error-summary 2>&1 \
  | grep "\[arg-type\]" | head -20
```

- [ ] **Step 2：记录文件清单到 /tmp/mypy-pr5-files.txt**

- [ ] **Step 3：分析错误模式**

arg-type 错误典型模式：
- 传入 `None` 给非 Optional 参数 → 加 None 检查
- 传入 `dict` 给 `TypedDict` 参数 → 用 TypedDict 实例
- 字符串字面量 vs 枚举类型不匹配
- 函数签名缺类型导致推断为 Any

- [ ] **Step 4：逐文件修复**

```python
# 模式 1: 缺 None 检查
result = process(context)  # 报错: None 不接受
# 修:
if context is None:
    return {}
result = process(context)

# 模式 2: 字面量类型不匹配
status: Literal["ok", "error"] = "ok"  # 调用时传 int
# 修: 加显式 cast 或改字面量
status = cast(Literal["ok", "error"], "ok")
```

- [ ] **Step 5：每文件 mypy + pytest 验证**

- [ ] **Step 6：基线确认**

```bash
bash scripts/mypy_baseline.sh
```

预期：错误数比 PR4 完成后少 ~7。

---

### Task 6.2：Commit + Push + 开 PR5

- [ ] **Step 1-5：与 Task 2.3 同流程**

工作分支：`fix/mypy-cleanup/arg-type`
PR title: `fix(mypy): arg-type 错误清理`
commit body 列 `mypy: error count X→Y`

---

## Phase 7：PR6 — no-any-return 错误清理

### Task 7.1：定位 + 修复

- [ ] **Step 1：mypy 筛选**

```bash
cd omni_desk_backend
mypy . --ignore-missing-imports --show-error-codes --no-error-summary 2>&1 \
  | grep "\[no-any-return\]" | head -20
```

- [ ] **Step 2：分析每个错误**

`Returning Any from function declared to return "X"` 通常因：
- 函数体内调用了返回 Any 的第三方库
- 内部变量缺类型注解导致推断为 Any
- 链式调用中间环节返回 Any

- [ ] **Step 3：典型修法**

```python
# 模式 1: 内部变量加注解
def process() -> dict:
    result: dict = some_function()  # result 显式 dict 而非 Any
    return result

# 模式 2: 收紧第三方调用结果
def process() -> dict:
    return cast(dict, third_party_call())

# 模式 3: 改返回类型为 Any（最后手段）
def process() -> Any:  # 但这违背"不引入 Any"原则, 必须 reason
    ...
```

- [ ] **Step 4：每文件 mypy + pytest 验证**

- [ ] **Step 5：基线确认**

预期：错误数比 PR5 完成后少 4。

---

### Task 7.2：Commit + Push + 开 PR6

- [ ] **Step 1-5：与 Task 2.3 同流程**

工作分支：`fix/mypy-cleanup/no-any-return`
PR title: `fix(mypy): no-any-return 错误清理`
commit body 列 `mypy: error count X→Y`

---

## Phase 8：PR7 — misc / return-value / annotation-unchecked 错误清理

### Task 8.1：定位 + 修复

- [ ] **Step 1：mypy 筛选**

```bash
cd omni_desk_backend
mypy . --ignore-missing-imports --show-error-codes --no-error-summary 2>&1 \
  | grep -E "\[(misc|return-value|annotation-unchecked)\]" | head -20
```

- [ ] **Step 2：分析 + 修复**

- [ ] **Step 3：每文件 mypy + pytest 验证**

- [ ] **Step 4：基线确认**

预期：mypy 错误数 = **0**。这是 PR8 阻塞化的前提。

```bash
bash scripts/mypy_baseline.sh
```

预期末行：`Success: no issues found in NN source files`（无 "Found N errors"）。

---

### Task 8.2：Commit + Push + 开 PR7

- [ ] **Step 1-5：与 Task 2.3 同流程**

工作分支：`fix/mypy-cleanup/misc`
PR title: `fix(mypy): misc / return-value / annotation-unchecked 错误清理（最后一批）`
commit body 列 `mypy: error count X→0`
PR description 必须含：`mypy 全 backend 零错，PR8 可安全切 CI 阻塞化`

---

## Phase 9：PR8 — CI 阻塞化（最后一刀）

### Task 9.1：修改 ci.yml

**Files:**
- Modify: `/home/fz/project/OmniDesk/.github/workflows/ci.yml:130-142`

**Interfaces:**
- Consumes: 当前 ci.yml 含 `continue-on-error: true` 在 typecheck job
- Produces: ci.yml typecheck job 无 `continue-on-error`，且在 gate 任务 `needs:` 列表中

- [ ] **Step 1：读当前 ci.yml typecheck 段**

```bash
sed -n '125,150p' .github/workflows/ci.yml
```

预期：看到 typecheck job 含 `continue-on-error: true`，以及 gate 任务 `needs: [lint-backend, test-backend, lint-frontend, test-frontend]`。

- [ ] **Step 2：删除 `continue-on-error: true`**

使用 Edit 工具移除该行（精确匹配文件内容）。

- [ ] **Step 3：在 gate 任务 needs 列表加 typecheck**

```yaml
needs: [lint-backend, test-backend, lint-frontend, test-frontend, typecheck]
```

- [ ] **Step 4：本地 yaml 语法验证**

```bash
python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))" && echo "OK"
```

预期：`OK`

- [ ] **Step 5：显示 diff 确认**

```bash
git diff .github/workflows/ci.yml
```

预期：仅 `continue-on-error: true` 删除 + needs 列表追加 `typecheck`。

---

### Task 9.2：本地全套验证

- [ ] **Step 1：mypy 全 backend 零错**

```bash
bash scripts/mypy_baseline.sh
```

预期末行：`Success: no issues found in NN source files`

- [ ] **Step 2：pytest 全 backend**

```bash
cd omni_desk_backend
pytest --ds=omni_desk_backend.settings.test -q
```

预期：全绿

- [ ] **Step 3：ruff 全 backend**

```bash
cd omni_desk_backend && ruff check . --statistics
```

预期：与 PR0 baseline 一致

- [ ] **Step 4：Django check**

```bash
cd omni_desk_backend && python manage.py check
```

预期：`System check identified no issues (0 silenced).`

---

### Task 9.3：Commit + Push + 开 PR8

- [ ] **Step 1：创建 PR8 工作分支**

```bash
cd /home/fz/project/OmniDesk
git switch fix/mypy-cleanup
git pull --rebase
git switch -c fix/mypy-cleanup/ci-blocking
```

- [ ] **Step 2：Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci(mypy): PR8 - 移除 continue-on-error + 加入 needs: 链（阻塞化最后一刀）

- 移除 typecheck job 的 continue-on-error: true
- gate 任务 needs 列表追加 typecheck
- 前置: PR0-7 完成后 mypy 全 backend 零错
- 效果: 未来新增 mypy 错误将立即阻塞 PR 合并"
```

- [ ] **Step 3：Push + 开 PR**

```bash
git push -u origin fix/mypy-cleanup/ci-blocking
gh pr create --base fix/mypy-cleanup --head fix/mypy-cleanup/ci-blocking \
  --title "ci(mypy): PR8 - 移除 continue-on-error + 加入 needs: 链（最后一刀）" \
  --body "## 变更
- \`.github/workflows/ci.yml\`: typecheck job 移除 \`continue-on-error: true\`
- \`.github/workflows/ci.yml\`: gate 任务 needs: 追加 typecheck

## 前置条件
- mypy 全 backend 零错（已由 PR0-7 保证）
- pytest / ruff / Django check 全绿

## 风险
合入后任何引入新 mypy 错误的 PR 将立即红灯阻塞, 这是预期行为.

Refs: docs/superpowers/specs/2026-07-14-mypy-cleanup-design.md §3.6"
```

- [ ] **Step 4：等 CI 绿灯 + 用户 merge**

- [ ] **Step 5：合并后清理**

```bash
git switch fix/mypy-cleanup
git pull --rebase
git branch -d fix/mypy-cleanup/ci-blocking
git push origin --delete fix/mypy-cleanup/ci-blocking
```

---

## Phase 10：基线合入 develop

### Task 10.1：基线分支合 develop

- [ ] **Step 1：rebase develop 当前状态**

```bash
cd /home/fz/project/OmniDesk
git switch fix/mypy-cleanup
git fetch origin develop
git rebase origin/develop
```

预期：可能有 conflict，按错误码 PR 顺序逐个解决（最可能冲突点是 docs/technical/35-mypy-suppressions.md 和 mypy.ini）。

- [ ] **Step 2：解决冲突**

```bash
git status  # 看冲突文件
# 编辑冲突文件
git add <冲突文件>
git rebase --continue
```

- [ ] **Step 3：跑全套验证**

```bash
bash scripts/mypy_baseline.sh
cd omni_desk_backend
pytest --ds=omni_desk_backend.settings.test -q
ruff check . --statistics
python manage.py check
```

预期：mypy 零错 + 测试全绿 + ruff 通过 + Django check 无 warning

- [ ] **Step 4：推基线**

```bash
git push --force-with-lease origin fix/mypy-cleanup
```

- [ ] **Step 5：开合 develop 的 PR**

```bash
git switch -c fix/mypy-cleanup-merge-to-develop
git push -u origin fix/mypy-cleanup-merge-to-develop
gh pr create --base develop --head fix/mypy-cleanup-merge-to-develop \
  --title "merge: fix/mypy-cleanup 基线 → develop（mypy 清理完成）" \
  --body "## 包含变更
- PR0-8 全部 8 个 mypy 清理 PR
- 总错误数 82→0
- CI typecheck job 阻塞化

## 验证
- mypy: Success: no issues found
- pytest: 全绿
- ruff: 通过
- Django check: 无 warning

## 后续
- PR 合入后删除 fix/mypy-cleanup 基线分支"
```

- [ ] **Step 6：等 CI 绿 + 用户 merge**

- [ ] **Step 7：删除基线分支**

```bash
git switch develop
git pull --rebase
git branch -d fix/mypy-cleanup fix/mypy-cleanup-merge-to-develop
git push origin --delete fix/mypy-cleanup fix/mypy-cleanup-merge-to-develop
```

---

## Self-Review

按 writing-plans skill 自检：

### 1. Spec coverage
- §1 背景 → Task 1.2-1.4（baseline）
- §2 分支策略 → Task 0.1（worktree）+ 全部 Task `*.*` Step 1-3
- §3.1 总览 → 每个 Phase 都有 PR title 引用
- §3.2 PR0 → Phase 1 (Task 1.1-1.5)
- §3.3 PR1-7 契约 → 每个 PR 任务的 Step 1-5 验证步骤
- §3.4 PR3 详解 → Phase 4 Task 4.1-4.4
- §3.5 PR4 详解 → Phase 5 Task 5.1-5.4（含 A/B 决策）
- §3.6 PR8 详解 → Phase 9 Task 9.1-9.3
- §4 压制策略 → Task 1.3（登记文档）+ 全部 `# type: ignore[code]  # reason: ...` 模式
- §5 测试验证 → 全部 Task 的 mypy/pytest 步骤
- §6 风险 → 缓解措施散落在各 Phase（如 PR4 走 A/B 决策、PR8 阻塞化风险）
- §7 交付物清单 → 全部 Phase
- §8 时间线 → 估时散落在每个 Phase header
- §9 非目标 → 在 Global Constraints 顶部显式列出

### 2. Placeholder scan
- 搜索 "TBD" / "TODO" / "implement later" / "fill in details"：无
- 搜索 "add appropriate error handling" / "similar to Task N"：无
- 每个代码块含实际内容（PR0 pyproject.toml 实际结构、PEP 604 修复模式等）
- 数字占位：`~3` / `~4` / `~7` / `~20+` 是基于 agent 探查的预估，文中显式说明"实际数字以 mypy 输出为准"

### 3. Type consistency
- 脚本 `scripts/mypy_baseline.sh` 在 Task 1.2 创建，Task 1.4/2.2/3.2/... 持续使用 — 名字一致
- 错误码命名：`var-annotated` / `attr-defined` / `assignment` / `override` / `arg-type` / `no-any-return` / `misc` — 与 spec 一致
- 分支命名：`fix/mypy-cleanup/{setup,var-annotated,attr-defined,assignment,override,arg-type,no-any-return,misc,ci-blocking}` — 与 spec §2.1 一致

### 4. 其他质量检查
- ✅ 每个 Task 有 Files / Interfaces（PR 任务简化为目标）
- ✅ 每个 Step 有具体命令 + 预期输出
- ✅ 每 Phase 末尾有 Commit + Push + 开 PR 标准流程
- ✅ PR8 强调"必须最后"，含前提条件验证
- ✅ PR4 含 A/B 决策路径（非单一修法）
- ✅ Phase 10 含 conflict 解决指引

**自检通过，无需修订。**
