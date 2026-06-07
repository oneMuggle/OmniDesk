# 智能助手优化 — 第九段交接(本会话产出)

> 📅 **截止时间:2026-06-07 00:30**
> **本会话从 `docs/notes/2026-06-06_smart-assistant-optimization-handoff-8.md` 继续**
> **下次会话从这里开始**

## 一句话状态

`feature/smart-assistant-optimization` 分支,**阶段 3 启动 + Task 0.1 完成**。本会话总共 5 个 commit 落地。

| Commit | 类型 | 描述 |
|--------|------|------|
| `d4b0bba` | test | 补 P6 任务覆盖率 91% → 96%(+69 测试) — 4 个 P6 测试文件落地 |
| `9620de2` | docs | 第八段交接 |
| `0eeab14` | feat | events: ScheduleSwapRequest 过期清理 Celery 任务(SP4) |
| `ba15a64` | feat | smart_assistant: ToolContext 类型化抽象(Task 0.1) |
| `251d230` | refactor | polish ToolContext per code review(Task 0.1 收尾) |

**测试基线**:`smart_assistant/ --no-cov -q` → **362 passed + 11 xpassed + 1 warning in 9.31s**(从 handoff-8 的 356+10 增加 6 个 ToolContext 测试)
**模块覆盖率**:预计仍 ≥ 96%(本会话未跑覆盖率,因仅加 1 个文件,生产代码 0 增长)

## 本会话完成的工作

### 1. 解决 handoff-8 与工作树不一致

**问题发现**:
- handoff-8.md 描述 P6 已 commit,但实际 4 个 P6 测试文件 + handoff-8.md 自身都未跟踪
- 另有 2 个 handoff-8 没提到的文件:`events/tasks.py` + `events/tests/test_swap_tasks.py`(ScheduleSwapRequest 过期清理)

**解决(用户选择)**:3 个 commit 一起提交
- `d4b0bba` test(4 个 P6 测试文件)
- `9620de2` docs(handoff-8)
- `0eeab14` feat(events)

### 2. 写阶段 3 实施计划

**文件**:`docs/plans/2026-06-07_smart-assistant-stage3-new-tools.md`(850+ 行)

**结构**:
- 头部:Goal / Architecture / Tech Stack / **修正说明(数据源名称对比 handoff-8)**
- 背景与目标:业务 3 工具 + 技术 4 目标
- 涉及文件与模块:17 个文件清单
- 技术方案:ToolContext 抽象 + BaseTool 签名升级 + Registry 升级 + 3 工具模式 + 注册 + E2E + 前端
- 实施步骤:6 阶段 14 Task(阶段 0-5 + 6 联调),每 Task 含 TDD 子步骤
- 风险评估:7 项风险 + 缓解
- 依赖:后端 / 前端 / 数据源(全部已有,0 新增)
- 验收标准:9 项 checklist
- 时间估算:9.5 工作日(~2 周)

**修正了 handoff-8 的 3 处数据源错误**:
- `communication.Announcement` → 实际是 `communication.Post`
- `compliance.InspectionRecord` → 实际是 `compliance.ComplianceIssue`
- `external-links.Bookmark/LinkGroup` → 实际是 `external_integration.ExternalLink`(app 名为 `external_integration`)

### 3. Subagent-Driven 模式启动 Task 0.1

**工作流**:
1. 派 implementer subagent → 写 5 测试 → 跑 FAIL → 实现 → 跑 PASS(5/5) → commit `ba15a64`
2. 派 spec reviewer subagent → ✅ 逐行对比,实现与规范完全对齐
3. 派 code quality reviewer subagent → ✅ APPROVED,但有 4 项 Important 建议
4. 派 polish subagent → 应用 4 项 fix → 6/6 测试通过 → commit `251d230`

**ToolContext 抽象最终形态**(32 行,生产代码):
- `frozen=True` dataclass,3 字段:`user` / `request_id` / `history`
- `from_request(request: Any)` classmethod 工厂
- 类 docstring 按计划 §1 完整恢复
- 设计原则:frozen 防误改 / user 必填 / request_id 自动生成 / history 可读不改

**Code Review 4 项 fix**:
1. 移除 `Optional`(history 实际永不为 None)
2. `from_request` 加 docstring + `request: Any` 类型注解
3. `ToolContext` 加类 docstring(计划 §1 原文)
4. 补 `test_from_request_preserves_existing_request_id` 测试(防 `getattr or uuid4` 回归)

## 下个会话任务(从 Task 0.2 开始)

### Task 0.2: BaseTool 签名升级

**Files:**
- Modify: `omni_desk_backend/smart_assistant/tools/base.py:1-61`

**Step 1**: 在 `BaseTool` 类新增 `required_auth: bool = True` 类属性
**Step 2**: 把 `execute(self, query: str, context: dict = None)` 签名升级为 `execute(self, query: str, context: "ToolContext")`,保留对现有 12 工具的兼容(用 TYPE_CHECKING import 避免循环)
**Step 3**: 跑全套测试,确认 0 回归(362+11 应不变)
**Step 4**: Commit `refactor(smart-assistant): add required_auth flag to BaseTool`

**风险**:必须先 grep 现有 12 个工具的 `execute` 签名,确保它们仍能通过测试(若用 `context: dict = None` 默认参数,可能不传 context 时仍兼容)

### Task 0.3: Registry 升级

**Files:**
- Modify: `omni_desk_backend/smart_assistant/tools/registry.py:1-20`

**Step 1**: 添加 `get_tool_for_user(intent_type, user)` 方法(校验 `required_auth`)
**Step 2**: `register` 方法加 `isinstance(tool, BaseTool)` 校验
**Step 3**: 跑测试,0 回归
**Step 4**: Commit `feat(smart-assistant): registry validates required_auth`

### 阶段 1-3:3 个新工具(每个工具 1-2 天)

按计划执行,每个工具都遵循同一 TDD 模式:
- Task X.1: 写 8 失败测试 → 实现 → 8 passed → commit
- Task X.2: 注册到 `__init__.py` + `prompt_builder.py` → 0 回归 → commit

## 累计成果(从 handoff-1 到 handoff-9)

| 阶段 | 任务 | commits | 测试数 | 覆盖率 |
|------|------|---------|--------|--------|
| P0 | 基线 | - | 88 | ~50% |
| P1-1 | orchestrator 覆盖率 | 1 | 144 | ~65% |
| P1-2 | middleware_chain 覆盖率 | 1 | 161 | ~70% |
| P2 | 覆盖率 workflow | 1 | 201 | 78% |
| P3-1~4 | 4 模块覆盖率补齐 | 1 | 287 | 91% |
| P3-5 | CI 门槛 75→85% | 1 | 287 | 91% |
| **P6** | **剩余 4 文件覆盖率补齐** | **1** | **356** | **96%** |
| **阶段 0.1** | **ToolContext 抽象** | **2** | **362** | **96%** |
| **累计** | **8 阶段** | **9 commits** | **+274 测试** | **+46%** |

**注意**:本会话 5 个 commit 包含 1 个 events 工作(0eeab14),与 smart_assistant 优化并列累计。

## 启动检查清单(下次会话第一分钟)

```bash
# 1. 切到正确分支
cd /home/fz/project/OmniDesk
git checkout feature/smart-assistant-optimization

# 2. 确认最近 commit
git log --oneline -5
# 期望:251d230 polish + ba15a64 ToolContext + 0eeab14 events + 9620de2 handoff-8 + d4b0bba P6

# 3. 跑基线测试
cd omni_desk_backend
/home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest smart_assistant/ --no-cov -q
# 期望:362 passed + 11 xpassed

# 4. 跑覆盖率(确认 96% 仍通过)
rm -f .coverage
/home/fz/anaconda3/envs/OmniDesk/bin/coverage run -m pytest smart_assistant/ --no-cov -q
/home/fz/anaconda3/envs/OmniDesk/bin/coverage report --include='smart_assistant/*' \
  --omit='smart_assistant/tests/*,smart_assistant/migrations/*' --fail-under=85
# 期望:96%,EXIT=0

# 5. 打开计划文档
cat docs/plans/2026-06-07_smart-assistant-stage3-new-tools.md | head -100

# 6. 从 Task 0.2 开始执行(BaseTool 签名升级)
#    注意:Task 0.2 是 REFACTOR 现有代码,需小心
#    - 必须先 grep 现有 12 个工具的 execute 签名
#    - 若发现 break,先在 plan 上记录 DONE_WITH_CONCERNS
```

## 已知坑(继承 handoff-8,本会话新增 1 个)

### 1-4. 沿用 handoff-8 已知坑(settings 导入、覆盖率命令模板、cwd 陷阱、FileField.path 只读)

### 5. Subagent 上下文隔离(本会话发现 🆕)

- subagent 派发时**必须**用 `Agent` 工具而非 `Bash`,且 `subagent_type=general-purpose`
- subagent 在 worktree 中**不会**自动切到项目根目录,需在 prompt 中明确给出 `Work from: /home/fz/project/OmniDesk`
- subagent 的环境变量继承自父会话,conda env 也继承,所以 `/home/fz/anaconda3/envs/OmniDesk/bin/python` 可直接用
- 不要让 subagent 读 plan 文件 — 在 prompt 中粘贴完整的 Task 文本(节省 subagent 上下文)

### 6. 计划 vs 实际数据源名称差异(本会话确认)

- handoff-8 描述的 `Announcement/InspectionRecord/Bookmark` 全部**不存在**于代码
- 实施时**必须**先 `grep -E "class \w+" omni_desk_backend/{communication,compliance,external_integration}/models.py` 确认实际模型名
- 计划文档 `docs/plans/2026-06-07_smart-assistant-stage3-new-tools.md` 顶部已记录修正,代码引用已用正确名称

## 决策记录

| 决策点 | 决定 | 理由 |
|--------|------|------|
| P6 + handoff-8 + events 一起 commit | 3 commit | 用户选择"把 events 工作一起 commit",避免拆分混乱 |
| Subagent-driven vs Inline | Subagent-driven | 用户选择,优点是上下文隔离 + 两阶段 review 防止 over/under build |
| Task 0.1 polish 修 4 项 | 全部修 | 4 项是 plan §1 漏掉的 spec 对齐,无理由拒绝 |
| 历史 Optional 改动 | 改为 `List[dict]` | 与 dataclass 实际契约一致(默认 `list` 永不为 None) |

## 关联文档
- 📋 [阶段 3 完整计划(已落)](../plans/2026-06-07_smart-assistant-stage3-new-tools.md)
- 📋 [阶段 1+2 整体方案](../plans/2026-06-06_smart-assistant-optimization.md)
- 📋 [上次会话交接(8 段)](2026-06-06_smart-assistant-optimization-handoff-8.md)
- 📋 [覆盖率路线图](../technical/28-smart-assistant-coverage-roadmap.md) §3.2-3.3
- 🧠 [覆盖率环境陷阱记忆](file:///home/fz/.claude/projects/-home-fz-project-OmniDesk/memory/smart-assistant-coverage-env-trap.md)
- 🆕 [本会话新增 Subagent 上下文隔离注意事项](本文件"已知坑"§5)
