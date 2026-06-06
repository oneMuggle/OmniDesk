# 智能助手优化 — 第二段交接(本会话产出)

> 📅 **截止时间:2026-06-06 18:30**
> **本会话从 `docs/notes/2026-06-06_smart-assistant-optimization-handoff.md` 继续**
> **下次会话从这里开始**

## 一句话状态

`feature/smart-assistant-optimization` 分支,**4 个新 commit 落库**,基线 `81 → 196 passed + 11 xfailed`(+115 passed)。**任务 A(B 工具测试)全部完成,还顺手做了阶段 2.2/2.3/2.6 三个子任务**。

## 立刻可继续的任务(下次会话第一件事)

### 任务 P0-1:修复 `generate_answer` tuple bug(生产级)

**位置:** `omni_desk_backend/smart_assistant/agent/intent_classifier.py:generate_answer()`

**症状:** 函数只 `return answer.strip()`(str),但 `agent/orchestrator.py:80` 用 `answer, usage = generate_answer(...)` unpack,生产中触发 `ValueError: too many values to unpack (expected 2)`。

**E2E 测试暴露:** `tests/test_e2e_smart_chat.py` — 第一次跑(无 mock orchestrator)时崩在这里。

**修复方向(2 选 1):**
- A. 改 `generate_answer` 返回 `(answer, usage)` 元组(对齐 `generate_general_answer` 风格)
- B. 改 `orchestrator.process` 用 `answer = generate_answer(...)`(单值接收)

**ROI:** 极高 — 这是生产 bug,影响所有走工具链的查询。

### 任务 P0-2:修复 13+ 个 tool 字段名 bug

**位置:**
- `tools/sensor_tool.py`: `is_active` 字段不存在 + `select_related("category", "storage_location")` 字段名错(实际 `sensor_category` / `location`)
- `tools/meeting_room_tool.py`: `is_active` / `date` / `select_related("room")` / `room_id` / `floor` 5 处错误(实际 `meeting_room` / 无 date 字段 / `meeting_room_id` / 无 floor)
- `tools/document_tool.py`: `experiment_type` / `owner` / `created_at` / `name` / `created_at` 5 处错误(实际 `template_type` / 无 owner / `generated_at` 等)

**测试状态:** 已写 xfail strict 标注,bug 修复后变 xpass。修复期间需同步更新测试。

**ROI:** 极高 — 3 个工具实际不可用(任何调用会崩),但代码已部署在生产路径上。

### 任务 P1-1:agent 测试补齐(覆盖 60-78% 区间)

按 plan 文档:
- `agent/orchestrator.py` 边界测试(+6)
- `agent/tool_chain_planner.py` JSON 解析失败、单工具降级为多工具(+3)
- `agent/tool_chain_executor.py` `$variable` 解析、依赖缺失、循环依赖检测(+4)

### 任务 P1-2:阶段 2.5 rate_limit 中间件测试(计划 +4)

中间件当前覆盖率 100%,但只有 3 个现有测试,按 plan 文档加 4 个边界:
- 30/min 上限
- TTL 续期
- 未认证放行(已有)
- 多用户独立计数

### 任务 P2:CI 门槛(任务 C,阶段 2.7)

`pytest.ini` 当前用全局 `addopts = --cov=. --cov-fail-under=80`。smart_assistant 单跑覆盖率 12%(因 `--cov=.` 扫全项目)。设置 smart_assistant 专项门槛需:
- 添加 `cov` 配置区段,区分全局与 smart_assistant 跑
- 写 `.github/workflows/smart-assistant-coverage.yml` 每周一跑专项

**风险:** 改全局 pytest.ini 影响所有模块测试,需谨慎。

## 已完成的工作(本会话)

### Commit 链(4 个,新增)
```
b2f8e8d test(smart-assistant): v0.6.0 阶段 2.6 E2E 测试(+5)
f72d65d test(smart-assistant): v0.6.0 阶段 2.3 LLM 配置视图测试补齐(+11)
3c9cbfa test(smart-assistant): v0.6.0 阶段 2.2 chat 视图测试补齐(+6)
4d6ccae test(smart-assistant): v0.6.0 阶段 2.4 工具测试补齐(7 工具 +93 测试)
```

### 文档
- 本交接文件(本会话成果)
- 记忆沉淀:`~/.claude/projects/.../memory/smart-assistant-coverage-env-trap.md`(覆盖率环境陷阱根因)

### 代码修复(额外)
- `tests/test_views.py`:8 个 chat test 的 `@patch` 位置从 `smart_assistant.agent.orchestrator.AgentOrchestrator` 改为 `smart_assistant.views.chat.AgentOrchestrator`
  - 根因:Python `from X import Y` 缓存 Y 引用,`@patch` 模块属性不影响 view 已加载的引用
  - 原 5 个 chat test pass 是因为断言宽松(只检查 status_code)

### 测试基础设施
- 复用上次会话的 `tests/conftest.py` 6 个 fixture
- 新增 8 个测试文件:
  - `test_event_tool.py`(21 passed)
  - `test_sensor_tool.py`(17 passed + 4 xfailed)
  - `test_meeting_room_tool.py`(14 passed + 4 xfailed)
  - `test_document_tool.py`(12 passed + 3 xfailed)
  - `test_memo_news_project_tools.py`(29 passed)
  - `test_llm_config_extended.py`(11 passed)
  - `test_e2e_smart_chat.py`(5 passed)
  - `test_views.py`(扩展 +6 passed)

### 覆盖率当前快照
- 196 passed + 11 xfailed,无失败
- 工具覆盖率:event 100% / sensor 65% / meeting_room 50% / document 35%(其他暂未跑覆盖率)
- views 覆盖率:chat ~90% / llm_config ~95%(其他暂未跑)

## 已知坑(下次会话不要踩)

### 覆盖率环境陷阱(已记录到 memory)
```bash
# 触发 82 errors:
pytest smart_assistant/ --cov=omni_desk_backend.smart_assistant

# 正确做法(临时绕开):
pytest smart_assistant/ --no-cov  # 81+ 测试,验证功能
# 或用 --override-ini="addopts=--cov=omni_desk_backend.smart_assistant --cov-report=term --cov-fail-under=0"
```

根因:`omni_desk_backend/__init__.py:3` `from .celery import app` → `celery.py:8` `os.environ.setdefault("DJANGO_SETTINGS_MODULE", "omni_desk_backend.settings")` → 覆盖率模式下,`omni_desk_backend.settings` 包未在 sys.modules 缓存,触发 `__init__.py` 默认 `from .development import *` → `DATABASES=postgresql + NAME=None` → `TypeError`。

### mock patch 位置(已在本会话修复)
- **WRONG:** `@patch('smart_assistant.agent.orchestrator.AgentOrchestrator')`
- **RIGHT:** `@patch('smart_assistant.views.chat.AgentOrchestrator')`
- 原因:`view` 中 `from ..agent.orchestrator import AgentOrchestrator` 缓存了类引用,patch 模块属性不影响 view 已加载的引用

### MagicMock 切片陷阱
- `mock_qs.__getitem__.return_value = mock_qs`(让 `qs[:10]` 返回 mock_qs)
- `mock_qs.__iter__` 用 `side_effect=lambda: iter([...])` 而非 `return_value=iter(...)`(避免 exhausted iterator 共享)

### 已知 6 个坑(沿用上次会话交接)
1. `smart_assistant.agent.orchestrator` 没有 `get_router` 顶层符号
2. `get_router` 在 `tool_chain_executor` 函数内 import
3. `classify_intent` 在 `tool_chain_planner` 函数内 import
4. Django locmem `cache.ttl` 不存在
5. SQLite 不支持 JSONField `__contains` lookup
6. StreamingHttpResponse 必须用 `list(resp.streaming_content)` 强制消费

## 启动检查清单(下次会话第一分钟)

```bash
# 1. 切到正确分支
cd /home/fz/project/OmniDesk
git checkout feature/smart-assistant-optimization

# 2. 确认基线测试通过(196 + 11 xfailed)
/home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest smart_assistant/ --no-cov -q
# 期望: 196 passed, 11 xfailed, 1 warning

# 3. 读本交接文件第 15-50 行(P0-1/P0-2 任务)

# 4. 决定本会话从哪个 P0/P1 开始
#    - 修复 generate_answer bug(P0-1,小)
#    - 修复 13+ tool bug(P0-2,大但 ROI 高)
#    - agent 测试(P1-1)
```

## 关联文档
- 📋 [阶段 1+2 完整计划](../plans/2026-06-06_smart-assistant-optimization.md)
- 📋 [上次会话交接](2026-06-06_smart-assistant-optimization-handoff.md)
- 📐 [技术架构](../technical/16-smart-assistant.md)
- 📈 [覆盖率路线图](../technical/28-smart-assistant-coverage-roadmap.md)
- 👤 [用户手册](../user-manual/08-smart-assistant-usage.md)
- 🧠 [覆盖率环境陷阱记忆](file:///home/fz/.claude/projects/-home-fz-project-OmniDesk/memory/smart-assistant-coverage-env-trap.md)
