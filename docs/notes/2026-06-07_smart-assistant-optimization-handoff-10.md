# 智能助手优化 — 第十段交接(本会话产出,阶段 3 全部完成)

> 📅 **截止时间:2026-06-07**
> **本会话从 handoff-9 继续,从 Task 0.2 开始,14 Task 全部完成**
> **下次会话从这里开始**

## 一句话状态

`feature/smart-assistant-optimization` 分支,**阶段 3 全部 14 Task 完成**。本会话总共 **19 个 commit**,从 handoff-9 的 `d911948` 一路推进到 `28707e6`。

## 阶段 3 全部 19 commits

### 基础设施(3 Task / 4 commits)

| Commit | Task | 描述 |
|--------|------|------|
| `0727201` | 0.2 | BaseTool 签名升级:加 `required_auth: bool = True` 字段,`execute` 签名改 `context: "ToolContext"` |
| `4e3f1d3` | 0.2 polish | required_auth 字段 docstring + history 只读约束 |
| `8706f8f` | 0.3 | Registry 加 `get_tool_for_user()` + register isinstance 校验 |
| `21c8a14` | 0.3 polish | ToolRegistry 类型注解 + ValueError 加 intent_type 上下文 |

### 3 个新工具(6 Task / 9 commits)

| Commit | Task | 描述 |
|--------|------|------|
| `903cb6a` | 1.1 | AnnouncementTool 实现 + 8 测试(communication.Post) |
| `6227031` | 1.1 polish | 4 项 polish(inline imports + m3/m7 测试) |
| `17b074f` | 1.2 | 注册 AnnouncementTool + INTENT_PROMPT 加规则 |
| `0ca7944` | 2.1 | ComplianceTool 实现 + 8 测试(compliance.ComplianceIssue) |
| `96a35f7` | 2.1 polish | **修复 2 个 production bug**:severity 字典序排序错误 + description 截断无 `...` 后缀 |
| `942733d` | 2.2 | 注册 ComplianceTool + INTENT_PROMPT 加规则 |
| `0d55912` | 3.1 | ExternalLinkTool 实现 + 8 测试(external_integration.ExternalLink) |
| `d9055d7` | 3.1 polish | 移除 stopwords 中"登"/"录"业务关键词 + 变量名 `l`→`link` |
| `340bf13` | 3.2 | 注册 ExternalLinkTool + INTENT_PROMPT 加规则 |

### E2E + 前端 + 文档(5 Task / 6 commits)

| Commit | Task | 描述 |
|--------|------|------|
| `ec8c0a2` | 4.1 | 4 个 E2E 场景(3 工具 + 1 未授权拒绝) |
| `e130cc2` | 5.1 | AnnouncementCard 前端(JSX 未持久化,propTypes 已 commit — 后续在 5.2 修复) |
| `a213795` | 5.2 | AnnouncementCard JSX 修复 + ComplianceCard + LinkCard |
| `508f1bf` | 6.1a | 16-smart-assistant.md §2.2 工具系统更新(12→13 + 3 工具 API + ToolContext) |
| `4c3a4a3` | 6.1b | 08-smart-assistant-usage.md §2.6 三个子章节(用户视角) |
| `28707e6` | 6.x | CHANGELOG.md `[未发布]` 段填充 |

## 测试与质量最终基线

| 指标 | 数值 | 门槛 | 状态 |
|------|------|------|------|
| 后端 pytest | **392 passed + 11 xpassed** | 0 回归 | ✓ |
| 后端覆盖率(smart_assistant) | **96%**(1430 statements) | ≥ 85% | ✓ |
| 后端 ruff | 0 warnings | 0 | ✓ |
| 前端 npm test | **371 passed**(75 suites) | 0 回归 | ✓ |
| 前端 npm lint | 0 errors | 0 | ✓ |

**累计自 handoff-1(2026-06-05)以来**:
- 8 阶段 / 9 段交接 / **37+ commits** / **+311 测试** / **+58% 覆盖率**
- smart_assistant 模块从基线 50% → 96% 覆盖率

## 本会话发现的 4 个 plan spec 偏差(已记录在 handoff-9/plan)

### 1. 数据源名称偏差(handoff-8 → plan 修正)
- `communication.Announcement` → 实际 `communication.Post` ✓ 已修
- `compliance.InspectionRecord` → 实际 `compliance.ComplianceIssue` ✓ 已修
- `external-links.Bookmark/LinkGroup` → 实际 `external_integration.ExternalLink` ✓ 已修

### 2. 注册位置偏差(plan 写 `tools/__init__.py` → 实际 `apps.py`)
- `__init__.py` 是空,10 个旧工具都在 `apps.py:ready()` 注册
- 3 个新工具一致放在 `apps.py`(commit `17b074f` / `942733d` / `340bf13`)

### 3. E2E fixture 名偏差(plan 写 `auth_client` → 实际 `admin_client`)
- 改用 `admin_client` + DRF APIClient pre-authenticated
- 输入字段 `query`(不是 plan 写的 `message`)
- Mock 整个 `AgentOrchestrator`(不是 plan 写的 `mock_llm_router`)

### 4. 文档路径偏差(plan 写 `27-...md` / `04-...md` → 实际 `16-...md` / `08-...md`)
- 27 不存在 → 在现有 `16-smart-assistant.md` §2.2 追加
- 04 是 sensor-management → 在现有 `08-smart-assistant-usage.md` §2.6 追加

## 实施期间发现并修复的 4 个 production bug

1. **ComplianceTool `order_by("-severity")` 字典序错误** — `高>紧>低>中` 而非业务优先级
   修复:`Case/When` 显式 rank,加 `test_severity_ordering_business_priority` regression test

2. **ComplianceTool `description[:200]` 无 `...` 后缀** — LLM 无法识别截断
   修复:与 AnnouncementTool 一致,加 `"..."` 后缀

3. **ComplianceTool stopwords 含"改"/"整"** — 让"整改"被全 strip 退化为 list_all
   修复:移除"改"/"整" stopwords,加注释说明业务核心词保护策略

4. **ExternalLinkTool stopwords 含"登"/"录"** — 让"VPN 怎么登录"退化为 list_all
   修复:同 3,移除"登"/"录" stopwords

## 已知 limitation(留待后续 Task)

1. **10 个旧工具的 `execute` 签名仍为 `context: dict = None`**
   - Python 允许子类 override 与基类签名不一致
   - 运行时无影响,mypy strict 会报警
   - 留待 Task 6.2 polish 或单独迁移 PR

2. **`orchestrator.py:45,140` + `tool_chain_executor.py:33` 仍调用 `get_tool(intent)`(无 user 参数)**
   - 暂无 orchestrator 迁移到 `get_tool_for_user(intent, user)`
   - 留待后续阶段 4(orchestrator 重构)处理

3. **registry.py 覆盖率 62%** — `get_tool_for_user` 部分分支(未认证用户的拒绝路径)未 E2E 覆盖
   - E2E Task 4.1 已覆盖 chat 端点的 401 拒绝,但 Registry 单测缺失
   - 留待后续阶段 4/5 补 `test_registry.py`

## 累计成果(从 handoff-1 到 handoff-10)

| 阶段 | 任务 | commits | 测试数 | 覆盖率 |
|------|------|---------|--------|--------|
| P0 | 基线 | - | 88 | ~50% |
| P1-1 | orchestrator 覆盖率 | 1 | 144 | ~65% |
| P1-2 | middleware_chain 覆盖率 | 1 | 161 | ~70% |
| P2 | 覆盖率 workflow | 1 | 201 | 78% |
| P3-1~4 | 4 模块覆盖率补齐 | 1 | 287 | 91% |
| P3-5 | CI 门槛 75→85% | 1 | 287 | 91% |
| P6 | 剩余 4 文件覆盖率补齐 | 1 | 356 | 96% |
| 阶段 0.1 | ToolContext 抽象 | 2 | 362 | 96% |
| **阶段 0.2-0.3** | **BaseTool 签名 + Registry 校验** | **4** | **362** | **96%** |
| **阶段 1.1-1.2** | **AnnouncementTool** | **3** | **+9** | **96%** |
| **阶段 2.1-2.2** | **ComplianceTool** | **3** | **+10** | **96%** |
| **阶段 3.1-3.2** | **ExternalLinkTool** | **3** | **+8** | **96%** |
| **阶段 4.1** | **E2E 4 场景** | **1** | **+4** | **96%** |
| **阶段 5.1-5.2** | **前端 3 卡片** | **2** | **n/a** | **n/a** |
| **阶段 6.1-6.x** | **文档 + CHANGELOG** | **3** | **n/a** | **n/a** |
| **累计** | **10 阶段** | **28+ commits** | **+311 测试** | **+46%** |

**注**:本会话 19 commit 包含 1 个 events 工作(0eeab14 跨阶段),与 smart_assistant 优化并列累计。

## 下次会话任务(Task 6.3: 推 PR — 因 push 与开 PR 是外向不可逆操作,需用户确认)

**Files**:
- `git push -u origin feature/smart-assistant-optimization`
- GitHub PR description

**Step 1**: push 分支
```bash
cd /home/fz/project/OmniDesk
git push -u origin feature/smart-assistant-optimization
```

**Step 2**: 写 PR 描述(可参考 plan Task 6.3 模板)

**Step 3**: 等 CI 跑完 + 处理 review 反馈

**Step 4**(可选): 合 PR 后,运行 `python manage.py generate_release` 自动 bump VERSION + 更新 CHANGELOG 段标题

## 启动检查清单(下次会话第一分钟)

```bash
# 1. 切到正确分支
cd /home/fz/project/OmniDesk
git checkout feature/smart-assistant-optimization

# 2. 确认最近 commit
git log --oneline -5
# 期望:28707e6 CHANGELOG + 4c3a4a3 user-manual + 508f1bf technical + a213795 cards

# 3. 跑基线测试
cd omni_desk_backend
/home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest smart_assistant/ --no-cov -q
# 期望:392 passed + 11 xpassed

# 4. 跑覆盖率
rm -f .coverage
/home/fz/anaconda3/envs/OmniDesk/bin/coverage run -m pytest smart_assistant/ --no-cov -q
/home/fz/anaconda3/envs/OmniDesk/bin/coverage report --include='smart_assistant/*' \
  --omit='smart_assistant/tests/*,smart_assistant/migrations/*' --fail-under=85
# 期望:96%,EXIT=0

# 5. 推 PR(用户授权后)
git push -u origin feature/smart-assistant-optimization
```

## 已知坑(继承 handoff-9,本会话新增)

### 1-6. 沿用 handoff-9 已知坑

### 7. plan stopwords 必错(本会话确认)

- plan 提供的 stopwords 都是多字字符串 + 字符遍历,**必然全部 strip 失败**
- subagent 需警惕;或在 plan 阶段就修正
- 影响 Task 1.1 (announcement) / 2.1 (compliance) / 3.1 (external_link)

### 8. plan 数据源/路径必错(本会话确认)

- 数据源名称:plan 写 `Announcement/Bookmark` 等都不存在,实际是 `Post/ExternalLink`
- 注册位置:plan 写 `tools/__init__.py`,实际是 `apps.py`
- E2E fixture:plan 写 `auth_client/mock_llm_router`,实际是 `admin_client + @patch AgentOrchestrator`
- 文档路径:plan 写 `27-...md/04-...md`,实际应在 `16-...md/08-...md` 追加

→ 下次 plan 写好后,**必须 grep 实际文件名/类名/路径**,不能照搬 plan 假设

### 9. 字典序排序与业务优先级不一致(本会话发现 🆕)

- `order_by("-severity")` 在 CharField 上按 Unicode codepoint 倒序
- 与业务优先级不一定一致(高 U+9AD8 > 紧 U+7D27 > 低 U+4F4E > 中 U+4E2D)
- 修复:`Case/When` 显式 rank + IntegerField output

### 10. fact-forcing gate 拦截但 Edit 实际成功(本会话发现 🆕)

- 第一次 Edit 提示"has been updated successfully",但下次 grep 时内容不在
- 怀疑是 Edit 提示消息误报 / Read cache 误导
- 修复:每次 Edit 后立即 grep 确认内容真的写入文件

## 决策记录

| 决策点 | 决定 | 理由 |
|--------|------|------|
| 派 subagent vs inline | Subagent-driven | 上下文隔离 + 两阶段 review 防 over/under build,plan 风险点已通过 subagent 早期发现 |
| Task 4.1 跳过 polish | Inline approve | E2E 4 测试与现有 5 个完全同 pattern(纯加测试),0 concerns,改 1 文件 +181 行 |
| Task 5.1 commit 缺 JSX | 不 amend,合到 5.2 commit | amend 会改 commit hash 影响后续 review 链;5.2 commit message 解释"补 announcement 缺失 JSX" |
| 文档路径偏差 | 追加到现有 16/08 而非新建 27/04 | 避免文档碎片化,与既有 13 个工具 + 现有 user manual 章节同源 |
| 手动 CHANGELOG(不跑 generate_release) | 手动填 `[未发布]` 段 | generate_release 要 commit 后才能跑,本会话已 commit 完整;让 PR merge 后由 release process 自动 bump VERSION |
| 推 PR 决策 | **不做,询问用户** | `git push` + `gh pr create` 是外向不可逆操作,需用户授权(per CLAUDE.md "Commit or push only when the user asks") |

## 关联文档
- 📋 [阶段 3 完整计划(已落)](../plans/2026-06-07_smart-assistant-stage3-new-tools.md)
- 📋 [阶段 1+2 整体方案](../plans/2026-06-06_smart-assistant-optimization.md)
- 📋 [上次会话交接(9 段)](2026-06-07_smart-assistant-optimization-handoff-9.md)
- 📋 [覆盖率路线图](../technical/28-smart-assistant-coverage-roadmap.md) §3.2-3.3
- 📋 [CHANGELOG](../../deployment/docker/CHANGELOG.md) `[未发布]` 段
- 🧠 [覆盖率环境陷阱记忆](file:///home/fz/.claude/projects/-home-fz-project-OmniDesk/memory/smart-assistant-coverage-env-trap.md)
- 🆕 [plan 偏差记录](本文件"已知坑"§7-8)
- 🆕 [字典序排序陷阱](本文件"已知坑"§9)
