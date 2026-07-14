# mypy 错误清理与 CI 阻塞化 — 设计规范

**日期：** 2026-07-14
**项目：** OmniDesk
**作者：** Claude
**状态：** 待用户审阅

---

## 1. 背景与目标

### 1.1 问题

OmniDesk backend 的 mypy 类型检查自 v0.6.0 起积累 82 个错误（45 个文件），主要分布在 `smart_assistant/` 模块。CI 中 mypy 任务以 `continue-on-error: true` 跑且不加入 `needs:` 链，**纯非阻塞**，导致错误长期累积不收敛。

具体观察：

- `smart_assistant/agent/intent_classifier.py` 15 个错误，单文件最严重
- `smart_assistant/agent/orchestrator.py` 12 个
- `smart_assistant/tools/*.py` 8 个工具文件**每个 8 个**——结构化重复错误
- 总错误数 82 已 **3 周（自 2026-06-21）无任何 commit 修复**
- 错误码分布：`assignment` 23 / `override` 11 / `arg-type` 7 / `no-any-return` 4 / `var-annotated` 3 / `attr-defined` 2 / `misc` 3 / `return-value` 1
- `mypy.ini` 文件被混用为 ruff 配置（`.ini` 扩展名塞 `[tool.ruff]` 段），配置职责不清
- 本地 mypy 1.17.1，CI 装 mypy 2.1.0，存在版本差

### 1.2 目标

1. **错误归零**：`mypy omni_desk_backend/ --ignore-missing-imports` 输出 `Success: no issues found`
2. **CI 阻塞化**：mypy 任务加入 `needs:` 链、移除 `continue-on-error: true`，未来新增错误立即红灯
3. **配置职责清晰**：`pyproject.toml` 管 ruff，`mypy.ini` 纯管 mypy
4. **可追踪的压制**：每处 `# type: ignore` 必须带 code + reason，登记到追踪文档
5. **零行为变化**：修复仅涉及类型注解与签名调整，不改变业务逻辑

### 1.3 非目标

- 不收紧 mypy 严格度（保持 `disallow_untyped_defs = False`）
- 不引入 mypy 插件或自定义插件
- 不重写 `BaseTool` 等核心抽象（除非 override 修复确实需要）
- 不动 smart_assistant 之外的模块结构（仅修 mypy 错误）
- 不修复 ruff lint 警告
- 不写新 mypy 抑制的批量脚本

### 1.4 成功标准（DoD）

- [ ] 8 个 PR 全部合入 `fix/mypy-cleanup` 基线分支
- [ ] `mypy omni_desk_backend/ --ignore-missing-imports` 输出零错误
- [ ] `pytest omni_desk_backend/ --ds=omni_desk_backend.settings.test` 全绿
- [ ] `python manage.py check` 无 warning
- [ ] `ruff check omni_desk_backend/` 全绿
- [ ] PR8 移除 `continue-on-error: true` 并加入 `needs:` 链
- [ ] `docs/technical/35-mypy-suppressions.md` 列出全部压制并附清理计划
- [ ] 基线分支合到 develop 后删除

---

## 2. 分支策略

### 2.1 长期基线 + 临时工作分支

```
main (alpha 渠道, 受保护)
  ↑
develop (中保护)
  ↑
fix/mypy-cleanup  ← 长期基线（直至全部 PR 合入后销毁）
  ↑
fix/mypy-cleanup/{category}  ← 8 个临时工作分支
  ├── fix/mypy-cleanup/setup            (PR0: 配置拆分 + 基线脚本)
  ├── fix/mypy-cleanup/var-annotated    (PR1)
  ├── fix/mypy-cleanup/attr-defined     (PR2)
  ├── fix/mypy-cleanup/assignment       (PR3)
  ├── fix/mypy-cleanup/override         (PR4)
  ├── fix/mypy-cleanup/arg-type         (PR5)
  ├── fix/mypy-cleanup/no-any-return    (PR6)
  ├── fix/mypy-cleanup/misc             (PR7)
  └── fix/mypy-cleanup/ci-blocking      (PR8: 最后一刀)
```

**为什么不直接合 develop？**
- 8 个 PR 串行合入期间，其他 PR 在 develop 累积新代码 → 持续 conflict
- 基线分支让我们能"暂停时间"逐个推进，最后一次 rebase 时再处理

### 2.2 合入顺序

PR0 → PR1 → PR2 → PR3 → PR4 → PR5 → PR6 → PR7 → PR8。

每个 PR 合入 `fix/mypy-cleanup` 基线分支（**不是** develop）。所有 8 个 PR 完成后，单开一个 PR 把 `fix/mypy-cleanup` 合到 develop。

---

## 3. 错误码 PR 分解

### 3.1 总览

| PR | 标题 | 错误数 | 涉及文件 | 难度 | 估时 |
|---|---|---|---|---|---|
| 0 | chore(mypy): 修复 mypy.ini 文件归属 + 验证基线 | — | 1-2 | 易 | 0.5h |
| 1 | fix(mypy): var-annotated 错误清理 | 3 | ~3 | 易 | 0.5h |
| 2 | fix(mypy): attr-defined / str 错误清理 | 4 | ~3-4 | 中 | 1h |
| 3 | fix(mypy): assignment 主项（隐式 Optional 模式） | 23 | ~10-15 | 中-高 | 3h |
| 4 | fix(mypy): override 错误（BaseTool 接口对齐） | 11 | ~10 | 高 | 4h |
| 5 | fix(mypy): arg-type 错误清理 | 7 | ~7 | 中 | 2h |
| 6 | fix(mypy): no-any-return 错误清理 | 4 | ~4 | 中 | 2h |
| 7 | fix(mypy): misc / return-value 错误清理 | 3 | ~3 | 易 | 1h |
| 8 | ci(mypy): 移除 continue-on-error + 加入 needs: 链 | — | ci.yml | 易 | 0.5h |

> 注：以上数字基于 smart_assistant 的 51 错统计。**PR0 实施时需重新跑 `mypy omni_desk_backend/` 取全 backend 82 错的精确分布**，并相应调整各 PR 数字。smart_assistant 之外的 31 错将分散在 PR1-7 中消化。

### 3.2 PR0：基线建立

**目标**：拆分配置 + 建立验证脚本 + 确认基线错误数。

**动作**：

1. **拆分 `mypy.ini`**：
   - 新建 `pyproject.toml`，将原 `mypy.ini` 的 `[tool.ruff]` / `[tool.ruff.lint]` / `[tool.ruff.lint.per-file-ignores]` / `[tool.ruff.lint.isort]` 段搬过去
   - `mypy.ini` 只保留 `[mypy]` / `[mypy-django.*]` / `[mypy-rest_framework.*]` / `[mypy-celery.*]` 段
   - 清理 `mypy.ini` 中"unused per mypy warning" 的 `[mypy-redis.*]` `[mypy-psycopg2.*]` `[mypy-django_filters.*]` `[mypy-corsheaders.*]` `[mypy-drf_spectacular.*]` 段

2. **建立基线脚本** `scripts/mypy_baseline.sh`：

   ```bash
   #!/usr/bin/env bash
   # 用法: bash scripts/mypy_baseline.sh [path]
   # 输出最后一行 "Found N errors in M files (checked K source files)"
   set -euo pipefail
   cd "$(dirname "$0")/../omni_desk_backend"
   mypy "${1:-.}" --ignore-missing-imports --no-error-summary 2>&1 | tail -3
   ```

3. **跑基线**：确认 `Found 82 errors in 45 files`（或当前实际数字）

**约束**：不修任何 mypy 错误，仅做配置 + 脚本。

### 3.3 PR1-7：错误码清理

**每个 PR 的契约**：

| 属性 | 规则 |
|---|---|
| 错误减少量 | 必须 N→M（M<N），可量化（PR description 列变化数） |
| mypy 验证 | `mypy <changed_files> --ignore-missing-imports` 零错 |
| 测试 | 改过的文件对应测试必须全绿 |
| Django check | `python manage.py check` 无 warning |
| 提交信息格式 | `fix(mypy): <category> - <一句话>`，body 列 `mypy: error count X→Y` |
| 体积 | 单 PR ≤ 7 文件 / ≤ 400 行 diff |

### 3.4 PR3 详解：assignment 主项（23 个）

**错误模式**（绝大多数）：
```python
# 报错
def execute(self, context: dict = None) -> dict:
    ...

# 修复（统一用 PEP 604 语法）
def execute(self, context: dict | None = None) -> dict:
    ...
```

**实施细节**：
- 全部用 `T | None` 形式（不用 `Optional[T]`），CI Python 3.10+ 支持
- 函数体内若已正确处理 `if context is None`，无需调整
- 函数体内若假设 `context` 非空（隐式契约），需补 `if context is None: return ...` 或 `# type: ignore[assignment]  # reason: ...`

### 3.5 PR4 详解：override 错误（11 个）

**前置探查**（PR4 开始前 1-2h）：

读 `smart_assistant/tools/base.py` 中 `BaseTool.execute()` 抽象签名，确定：
- 父类 `context` 参数类型
- 父类返回值类型

**两种修法**：

| 路径 | 内容 | 触发条件 |
|---|---|---|
| A. 改子类签名 | 每个工具类 `execute(self, context)` 与父类对齐 | 父类签名合理 |
| B. 改父类签名 | 调整 `BaseTool.execute` 抽象签名 | 父类签名 outdated / 错 |

**默认走 A**。若探查发现父类本身需要重构，**PR4 拆为 PR4a（父类）+ PR4b（11 个子类）**。

**额外约束**：PR4 完成后必须跑全 backend pytest（不只是 smart_assistant），因为 `BaseTool` 改动可能影响所有子类。

### 3.6 PR8 详解：CI 阻塞化

**`ci.yml` 变更**（`.github/workflows/ci.yml` lines 130-142）：

```diff
   typecheck:
     runs-on: ubuntu-latest
     steps:
       - uses: actions/checkout@v4
       - uses: actions/setup-python@v5
         with:
           python-version: "3.10"
       - name: Install mypy
         run: pip install mypy types-requests types-redis types-python-dateutil
       - name: Type check
-        continue-on-error: true
         working-directory: omni_desk_backend
         run: mypy . --ignore-missing-imports
```

并在 `ci.yml` line 147 附近的 gate 任务 `needs:` 列表中追加 `typecheck`：

```diff
-  needs: [lint-backend, test-backend, lint-frontend, test-frontend]
+  needs: [lint-backend, test-backend, lint-frontend, test-frontend, typecheck]
```

**前提**：PR8 之前所有 mypy 错误必须已归零，否则此 PR 合入后 CI 立即红灯阻塞所有 PR。

---

## 4. 压制策略

### 4.1 原则

**以修为主、压制为辅**。需要压制的请逐处说明理由。

### 4.2 禁止项

- ❌ 裸 `# type: ignore`（必须带 code）
- ❌ 文件级 `# mypy: disable-error-code=` 全局压制
- ❌ 修改 `mypy.ini` 全局加 `disable_error_code=` 绕过整个类别
- ❌ 把 `dict[Any, Any]` 改成 `Any` "消除"问题（恶化类型）

### 4.3 允许项

✅ `# type: ignore[code]  # reason: <一句话原因>`

### 4.4 追踪文档

新文件 `docs/technical/35-mypy-suppressions.md` 维护总账：

```markdown
# mypy 压制登记册

> 最后更新：YYYY-MM-DD
> 维护者：Claude / 用户

| 文件:行 | 错误码 | 原因 | 计划清理 PR / 触发条件 |
|---|---|---|---|
| agents/task_packet.py:256 | misc | list comp 类型展宽 | 待 v0.7 设计回顾 |
```

**每次 PR 引入新压制 → 同步更新此文档**（同一 PR 内）。

---

## 5. 测试与验证

### 5.1 每个 PR 的本地验证

| 检查 | 命令 | 是否阻塞 |
|---|---|---|
| mypy 目标文件零错 | `mypy <changed_files> --ignore-missing-imports` | ✅ |
| 全局 mypy 错误数减少 | `bash scripts/mypy_baseline.sh` 末行数字 | ✅（必须减少） |
| 改动模块测试 | `pytest <changed_module>/tests/ -v` | ✅ |
| Django check | `python manage.py check` | ✅ |
| Ruff lint | `ruff check <changed_files>` | ✅ |

### 5.2 不重测

- 不在 PR 范围的不重测（避免其他模块干扰）
- 但 PR4 需额外跑**全 backend pytest**（BaseTool 影响所有子类）

### 5.3 CI 验证

PR 推 `fix/mypy-cleanup/{category}` 后：

- 走常规 CI 链（lint / test / frontend / backend）
- typecheck job 仍 `continue-on-error: true`（PR8 之前）
- 关注 typecheck 末行数字，必须单调下降

---

## 6. 风险与缓解

| 风险 | 缓解 |
|---|---|
| PR4 override 父类改动破坏运行时 | PR4 拆 4a/4b + 完整 pytest 跑全 backend |
| 跨 PR 同文件 conflict | 每 PR 后 `git rebase fix/mypy-cleanup` 保持线性 |
| 期间 develop 合入新代码 | 基线分支每日 rebase develop，最后阶段冲突集中处理 |
| 修了 A 类别冒 B 类别 | 每个 PR 后跑 `mypy_baseline.sh` 确认数字单调下降 |
| 真实业务语义被误改 | 改 Optional 时同步检查函数体内 None 处理逻辑 |
| PR8 阻塞化后其他 PR 全红 | 严格按顺序：PR0-7 全部绿灯后才允许 PR8 |
| 数字 82 在 PR0 探查时已变 | PR0 实际数字为准，相应调整各 PR 规模 |

---

## 7. 交付物清单

```
新增/修改：
  ├── pyproject.toml                              (PR0: 从 mypy.ini 拆分 ruff 配置)
  ├── omni_desk_backend/mypy.ini                  (PR0: 精简为纯 mypy)
  ├── scripts/mypy_baseline.sh                    (PR0: 验证脚本)
  ├── docs/technical/35-mypy-suppressions.md      (PR0 起：追踪文档)
  ├── docs/superpowers/specs/2026-07-14-mypy-cleanup-design.md  (本设计 doc)
  ├── docs/plans/2026-07-14_mypy-cleanup.md       (writing-plans 产出)
  ├── 8 个 PR 分支 (fix/mypy-cleanup/{category})
  ├── 8 个 PR 提交
  └── 1 个合 develop 的 PR（所有 8 个 PR 完成后）
```

---

## 8. 实施时间线（预估）

| 阶段 | 估时 | 累计 |
|---|---|---|
| PR0 setup | 0.5h | 0.5h |
| PR1-2 简单类 | 1.5h | 2h |
| PR3 assignment 主项 | 3h | 5h |
| PR4 override | 4h | 9h |
| PR5-7 中等类 | 5h | 14h |
| PR8 CI 阻塞化 | 0.5h | 14.5h |
| 合 develop 验证 | 1h | 15.5h |
| **总计** | **~16h 工作量** | |

按每天 2-3h 工作节奏，约 **5-7 个工作日**。

---

## 9. 不在范围内（再次强调）

- ❌ 收紧 mypy 严格度（开 strict / warn_unused_ignores 等）
- ❌ 自动版本号推导 / 自动发布
- ❌ 引入 mypy 插件
- ❌ 重构 BaseTool 抽象（除非 PR4 强制需要）
- ❌ 修复其他模块的 ruff / 测试警告（顺带不算）
- ❌ 写新 CI 任务或修改 typecheck job 之外的工作流
