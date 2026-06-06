# 智能助手优化 — 下次会话交接

> 📅 **截止时间:2026-06-06 13:30**
> **下次会话从这里开始**

## 一句话状态

`feature/smart-assistant-optimization` 分支,**3 个 commit 落库**,Phase 1 + Phase 2.1-2.3 + Phase 2.5 完成;Phase 2.4 / 2.6 / 2.7 + 全部 P1/P2 阶段待续。

## 立刻可继续的任务(下次会话第一件事)

### 任务 A:Phase 2.4 — 7 个低覆盖工具测试(预计 20-30 个测试用例)

**目标**:工具覆盖率从 ~40% 提到 ≥80%。

按 ROI 顺序:

1. `tools/event_tool.py`(32% → 85%):日期范围解析、节假日边界、空查询、跨年事件
2. `tools/sensor_tool.py`(35% → 85%):设备不存在、离线设备、超时、批量
3. `tools/meeting_room_tool.py`(33% → 85%):时间冲突、空闲查询、容量过滤
4. `tools/document_tool.py`(39% → 85%):模板不存在、权限、关键词搜索
5. `tools/memo_tool.py` / `tools/news_tool.py` / `tools/project_tool.py`(各 47% → 85%):参数解析、空结果、异常

**重要**:本次会话已抽出 `tests/conftest.py`,含 `mock_llm_router` / `mock_tool_registry` / `sample_smart_session` / `sample_agent_log` 四个 fixture 可直接复用。**不要再造**。

### 任务 B:Phase 2.6 — E2E 测试文件

新建 `tests/test_e2e_smart_chat.py`,6 个场景(排班 happy/多工具链/工具失败降级/流式中断/缓存命中/限流触发)。复用具名 fixture。

### 任务 C:Phase 2.7 — CI 门槛与 GitHub Action

`pytest.ini` 添加 smart_assistant 专项门槛(70→80→85 渐进),新建 `.github/workflows/smart-assistant-coverage.yml` 每周一跑覆盖率。

### 任务 D:Phase 3+ — 优化方案的 P1/P2 阶段(后续多会话)

详见 `docs/plans/2026-06-06_smart-assistant-optimization.md` §阶段 3-6。**这一会话不需要进入**,下次会话可以选择从 A/B/C/D 任一开始。

## 已完成的工作(下次会话不要重复做)

### Commit 链
```
46d9105 fix(smart-assistant)+test: 修复 2 个生产 bug + 10 个边界测试
9b3f078 test(smart-assistant): v0.6.0 阶段 2.1-2.3 覆盖率补齐(P0 起步)
ec990ee docs(smart-assistant): v0.6.0 阶段 1 文档同步
```

### 文档
- `docs/smart-assistant-plan.md` 顶部已加废弃声明
- `docs/technical/16-smart-assistant.md` 升级到 200+ 行
- `docs/technical/28-smart-assistant-coverage-roadmap.md` 新建
- `docs/user-manual/08-smart-assistant-usage.md` 扩到 260+ 行
- `docs/technical/README.md` 追加 28 索引

### 代码修复
- `middleware/rate_limit.py`:`cache.incr` ValueError 修复 + `cache.ttl` AttributeError 修复

### 测试基础设施
- `omni_desk_backend/smart_assistant/tests/conftest.py`:6 个 fixture(mock_llm_router / mock_tool_registry / mock_cache_backend / sample_smart_session / sample_agent_log / celery_eager_mode)
- 复用全局 conftest 提供的 `admin_client` / `admin_user_obj` / `regular_client`

### 覆盖率当前快照
- `views/chat.py`:96%
- `views/llm_config.py`:84%
- `middleware/rate_limit.py`:100%
- `agent/tool_chain_executor.py`:67%
- `agent/tool_chain_planner.py`:78%
- 模块总:**66.71%**(目标 ≥85%)

## 已知坑(下次会话不要踩)

1. **`smart_assistant.agent.orchestrator` 没有 `get_router` 顶层符号**——`mock_llm_router` fixture 中不要 patch 它。
2. **`smart_assistant.agent.tool_chain_executor` 的 `get_router` 在函数内 import**——同上,不要 patch 模块顶层。
3. **`smart_assistant.agent.tool_chain_planner` 的 `classify_intent` 在函数内 import**——需 patch `smart_assistant.agent.intent_classifier.classify_intent`(源模块),不是目标模块。
4. **Django locmem `cache.ttl` 不存在**——只能用 try/except 兜底,或换 Redis backend。
5. **SQLite 不支持 JSONField `__contains` lookup**——查 JSONField 数组要用 Python 端过滤。
6. **Django test client 对 StreamingHttpResponse**——必须用 `list(resp.streaming_content)` 强制消费完整流,否则 view 内的 session 创建代码不执行。

## 启动检查清单(下次会话第一分钟)

```bash
# 1. 切到正确分支
cd /home/fz/project/OmniDesk
git checkout feature/smart-assistant-optimization

# 2. 确认基线测试通过
/home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest omni_desk_backend/smart_assistant/ --no-cov -q
# 期望: 81 passed, 1 warning

# 3. 看覆盖率(模块基线 66.71%)
/home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest omni_desk_backend/smart_assistant/ --cov=omni_desk_backend.smart_assistant --cov-report=term --no-header -q | tail -3

# 4. 决定本会话从 A/B/C/D 哪个开始
```

## 关联文档
- 📋 [完整计划](../plans/2026-06-06_smart-assistant-optimization.md)
- 📐 [技术架构](../technical/16-smart-assistant.md)
- 📈 [覆盖率路线图](../technical/28-smart-assistant-coverage-roadmap.md)
- 👤 [用户手册](../user-manual/08-smart-assistant-usage.md)
