# 智能助手优化 — 第五段交接(本会话产出)

> 📅 **截止时间:2026-06-06 20:50**
> **本会话从 `docs/notes/2026-06-06_smart-assistant-optimization-handoff-4.md` 继续**
> **下次会话从这里开始**

## 一句话状态

`feature/smart-assistant-optimization` 分支,**P1 + P2 任务全部完成**!本会话总共 3 个 commit 落地:

| Commit | 类型 | 描述 |
|--------|------|------|
| `f972fe1` | test | 补 agent orchestrator 边界 + tool_chain_executor 循环依赖 (+5 测试) |
| `321a34b` | docs | 第四段交接(P1-1 + P1-2 全部完成) |
| `29c5e95` | ci | 新增专项覆盖率周报 workflow(P2) |

**测试基线**:201 passed + 11 xpassed = 212 实际通过,0 回归
**模块覆盖率**:smart_assistant 纯生产代码 **78%**(1320 行,286 行未覆盖)

## 本会话重大突破:覆盖率报告本地可用

handoff-3/handoff-4 都说覆盖率环境陷阱(202 errors)无法跑报告。本会话**意外发现**绕开方法:

```bash
# WRONG(触发 202 errors):
cd omni_desk_backend
coverage run --source=omni_desk_backend.smart_assistant -m pytest smart_assistant/ --no-cov

# RIGHT(本地 + CI 都能跑):
cd omni_desk_backend
rm -f .coverage
coverage run -m pytest smart_assistant/ --no-cov
coverage report --include='smart_assistant/*' --omit='smart_assistant/tests/*,smart_assistant/migrations/*'
```

**关键差异**:
- 不指定 `--source=`(避免覆盖范围触发 settings 导入链冲突)
- 用相对路径 `--include='smart_assistant/*'`(在 `omni_desk_backend/` 目录下)
- 排除 `tests/*` 和 `migrations/*`(只看生产代码)

## P2 任务详情(本会话产出)

### 新增 `.github/workflows/smart-assistant-coverage.yml`(86 行)

**触发器**:
- `schedule: cron: '7 9 * * 1'` — 每周一 9:07 UTC(17:07 北京时间),避整点
- `workflow_dispatch` — 允许手动触发

**执行步骤**(5 步):
1. Checkout
2. Set up Python 3.10 + pip cache
3. Install requirements-dev.txt
4. **Run smart_assistant tests with module coverage** — 核心
   - `coverage run -m pytest smart_assistant/ --no-cov -q`
   - `coverage report --include='smart_assistant/*' --omit='smart_assistant/tests/*,smart_assistant/migrations/*' --fail-under=75 --show-missing`
   - `coverage xml -o smart_assistant_coverage.xml`
5. Upload coverage report(artifact,90 天留存)

**关键设计**:
- **不动** `pytest.ini`(避免影响所有模块)
- **独立** workflow,不与主 `ci.yml` 冲突(主 CI 仍跑全项目)
- 用 PostgreSQL service 绕开 settings 导入陷阱
- 阈值 75% 起步,留 3% 缓冲(实际 78%)

### 当前覆盖率明细(2026-06-06 实测)

**纯生产代码 78%**(排除 tests + migrations):

| 文件 | 覆盖率 | 备注 |
|------|--------|------|
| `tools/document_tool.py` | 100% | 完美 |
| `tools/event_tool.py` | 100% | 完美 |
| `tools/meeting_room_tool.py` | 100% | 完美 |
| `tools/sensor_tool.py` | 100% | 完美 |
| `tools/schedule_tool.py` | 100% | 完美 |
| `tools/personnel_tool.py` | 100% | 完美 |
| `tools/memo_tool.py` / `news_tool.py` / `project_tool.py` | 100% | |
| `views/chat.py` | 96% | 52, 137-138, 153 缺 |
| `views/llm_config.py` | 89% | |
| `views/logs.py` | 89% | |
| `views/sessions.py` | 100% | 完美 |
| `agent/orchestrator.py` | 88% | |
| `agent/tool_chain_planner.py` | 78% | |
| `agent/tool_chain_executor.py` | 67% | 还有空间 |
| `agent/conversation_context.py` | 37% | 主要缺口 |
| `agent/rag_router.py` | 13% | 主要缺口 |
| `agent/prompt_builder.py` | 24% | 主要缺口 |
| `views/knowledge_base.py` | 65% | |
| `views/stats.py` | 42% | 重点补 |
| `tools/base.py` | 48% | |
| `tools/registry.py` | 83% | |
| **TOTAL** | **78%** | 1320 行,286 行未覆盖 |

## 立刻可继续的任务(下次会话第一件事)

### 任务 P3:补齐覆盖率到 85%(路线图 W3+ 目标)

按 handoff-4 路线图,从 78% → 85% 需补约 90 行覆盖。重点:

**优先级 1(高 ROI)**:
- `views/stats.py` 42% → 80%(+~16 行覆盖)
- `agent/conversation_context.py` 37% → 80%(+~30 行覆盖)
- `agent/rag_router.py` 13% → 60%(+~50 行覆盖)
- `tools/base.py` 48% → 80%(+~10 行覆盖)

**优先级 2**:
- `views/knowledge_base.py` 65% → 85%
- `agent/prompt_builder.py` 24% → 70%
- `agent/tool_chain_executor.py` 67% → 85%

**ROI:** 高 — 接近 85% 项目级目标,推高覆盖率门槛到 85%

### 任务 P4:阶段 3 新工具(announcement/compliance/external_link)

按 plan 文档阶段 3,实现 3 个高频业务工具 + 24 测试 + E2E 覆盖。

**ROI:** 极高 — 直接业务价值,但工作量大(2 周)

### 任务 P5:CI 门槛渐进提升

- W2(2026-06 第 3 周):workflow 阈值 75% → 80%
- W3+(2026-06 第 4 周起):80% → 85%

每次推阈值前需确认 P3 任务完成。

## 已完成的工作(本会话)

### Commit 链(3 个)
```
29c5e95 ci(smart-assistant): 新增专项覆盖率周报 workflow(P2 任务完成)
321a34b docs(notes): 智能助手优化第四段交接(P1-1 + P1-2 全部完成)
f972fe1 test(smart-assistant): 补 agent orchestrator 边界测试 + tool_chain_executor 循环依赖 (+5)
```

### Workflow 文件(1 个,86 行)
- `.github/workflows/smart-assistant-coverage.yml`:完整 5 步定义,含 PG service + coverage 命令

### 测试代码(2 个文件,共 +191 行,沿用 handoff-4)
- `test_orchestrator.py` (+156):意图缓存命中 / has_history / 多工具链 / fallback 结构
- `test_middleware_chain_coverage.py` (+35):循环依赖检测

## 已知坑(下次会话不要踩)

### 覆盖率命令(本会话发现)
- **WRONG:** `coverage run --source=omni_desk_backend.smart_assistant ...` → 202 errors
- **RIGHT:** `coverage run -m pytest smart_assistant/ --no-cov` + `--include='smart_assistant/*'`
- 关键:不指定 `--source=`,用相对路径 `--include`

### settings 导入陷阱(沿用 memory)
- `omni_desk_backend.settings/__init__.py:5` 默认走 `from .development import *`
- `DJANGO_ENV=test` **不会**阻止(因为 if 条件只检查 production)
- 解决:CI 用 PG service 走 settings.development,本地走 settings.test(SQLite)

### mock patch 位置(沿用)
- **WRONG:** `@patch('smart_assistant.agent.orchestrator.AgentOrchestrator')`
- **RIGHT:** `@patch('smart_assistant.views.chat.AgentOrchestrator')`

### pytest.ini 不要动(本会话决策)
- 改全局 `addopts=--cov=. --cov-fail-under=80` 会影响所有模块
- P2 已用独立 workflow 绕开,**不需要**改 pytest.ini

## 启动检查清单(下次会话第一分钟)

```bash
# 1. 切到正确分支
cd /home/fz/project/OmniDesk
git checkout feature/smart-assistant-optimization

# 2. 确认基线测试通过(201 + 11 xpassed)
cd omni_desk_backend
/home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest smart_assistant/ --no-cov -q
# 期望: 201 passed, 11 xpassed, 1 warning

# 3. 跑覆盖率(本会话发现的正确方法)
cd omni_desk_backend
rm -f .coverage
/home/fz/anaconda3/envs/OmniDesk/bin/coverage run -m pytest smart_assistant/ --no-cov -q
/home/fz/anaconda3/envs/OmniDesk/bin/coverage report --include='smart_assistant/*' --omit='smart_assistant/tests/*,smart_assistant/migrations/*' --show-missing
# 期望: TOTAL 78%,1320 行,286 行未覆盖

# 4. 读本交接文件第 47-90 行(P3 任务细节)

# 5. 决定本会话从哪个任务开始
#    - P3 补覆盖率到 85%(中高,推荐)
#    - P4 阶段 3 新工具(高,大工作量)
#    - P5 CI 门槛渐进(需先完成 P3)
```

## 关联文档
- 📋 [阶段 1+2 完整计划](../plans/2026-06-06_smart-assistant-optimization.md)
- 📋 [上次会话交接(4 段)](2026-06-06_smart-assistant-optimization-handoff-4.md)
- 📋 [上上次会话交接(3 段)](2026-06-06_smart-assistant-optimization-handoff-3.md)
- 📐 [技术架构](../technical/16-smart-assistant.md)
- 📈 [覆盖率路线图](../technical/28-smart-assistant-coverage-roadmap.md) §3.2-3.3
- 👤 [用户手册](../user-manual/08-smart-assistant-usage.md)
- 🧠 [覆盖率环境陷阱记忆](file:///home/fz/.claude/projects/-home-fz-project-OmniDesk/memory/smart-assistant-coverage-env-trap.md)
- 🆕 [本会话新增文档:覆盖率命令正确用法](本文件第 13-30 行)
