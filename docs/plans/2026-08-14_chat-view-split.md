# R3-A4: smart_assistant/views/chat.py 拆分实施计划

> 日期:2026-08-14 | 状态:待批准 | 关联:round3 计划 `docs/plans/2026-08-14_project-optimization-round3.md` R3-A4
> 模式:参照 R3-A1(orchestrator 拆分)/ R3-A3(task_packet 拆分)同款 SDD 拆分流程 —— 拆文件 + 逐字搬运 + repoint 测试 mock + 差分验证

## 1. 背景与目标

### 背景

`smart_assistant/views/chat.py` 当前 **537 行**，含 3 处活跃 C901 复杂度告警：

| 符号 | C901 | 位置 |
|---|---|---|
| `SmartChatViewSet.create` | 17 | L116-318(同步聊天 POST) |
| `SmartChatViewSet.stream` | 22 | L321-537(SSE 流式聊天) |
| `stream` 内嵌 `event_stream` 生成器 | 16 | L359-535 |

该文件同时承担 4 类职责:会话管理、附件处理、同步编排、流式编排。与 R3-A1(1520 行 orchestrator)/ R3-A3(task_packet) 同类,是 R3-A 阶段**剩余唯一仍有活跃 C901 的大文件**。

> 注:R3-A2(validate C901=25)、R3-A5(_legacy_process C901=17)、R3-A9(F541/F811/E402/E501) 经调研已在前序重构中解决,无需处理。R3-A4 为 R3-A 剩余唯一真债。

### 目标

1. 将 `chat.py` 按职责拆为 4 个模块,`create` C901 17→<10、`stream` 22→<10、`event_stream` 16→<10
2. **对外契约零变化**:`views/__init__.py` re-export 的 `SmartChatViewSet` 集合不变,`urls.py` 路由、`views.py` re-export、前端 API 调用均不受影响
3. 拆分行为逐字一致,经全量回归 + 覆盖率验证

## 2. 涉及的文件与模块

### 新增(3 个)

| 文件 | 职责 | 预估行数 |
|---|---|---|
| `smart_assistant/views/conversation_manager.py` | 会话领域逻辑:附件抽取/注入、会话加载、成功持久化、`resolve_error`/`usage_fields` | ~200 |
| `smart_assistant/views/chat_sync.py` | 同步路径 `create` 编排:confirm-replay、orchestrator.process、AgentLog、payload | ~200 |
| `smart_assistant/views/chat_stream.py` | 流式路径 `stream` 编排:process_stream 消费、SSE 生成器、流式持久化 | ~230 |

### 修改(1 个)

| 文件 | 改动 |
|---|---|
| `smart_assistant/views/chat.py` | 从 537 行瘦身为 ViewSet 薄壳(~60 行),`create`/`stream`/`_extract_attachment`/`_inject_attachment` 委托新模块 |

### 测试 repoint(约 14 个文件)

`@patch("smart_assistant.views.chat.XXX")` 按场景改指新模块。测试**不直接引用** chat.py 内部辅助函数(grep 已确认 exit=1),仅 patch 4 个符号:

| 原 patch 目标 | create 场景 → | stream 场景 → |
|---|---|---|
| `chat.AgentOrchestrator` | `chat_sync.AgentOrchestrator` | `chat_stream.AgentOrchestrator` |
| `chat.ToolRegistry.get_tool` | `chat_sync.ToolRegistry.get_tool`(confirm-replay) | — |
| `chat.SmartAssistantSession.objects` | `chat_sync.SmartAssistantSession.objects` | `chat_stream.SmartAssistantSession.objects` |
| `chat.AgentLog.objects` | `chat_sync.AgentLog.objects` | `chat_stream.AgentLog.objects` |

涉及文件:`test_views.py`、`test_e2e_smart_chat.py`、`test_chat_coverage.py`、`test_chat_failure_persistence.py`、`test_chat_last_error.py`、`test_rolling_summary.py`、`test_perf_chat.py`、`test_doctor.py`、`test_e2e_personnel_tool.py`、`test_view_confirm_replay.py`、`test_confirm_replay_e2e.py`、`test_router_cost.py`、`test_e2e_rag_tool.py`、`test_comprehensive.py`

### 不变(3 个)

| 文件 | 说明 |
|---|---|
| `smart_assistant/views/__init__.py` | `from .chat import SmartChatViewSet` 保持,re-export 集合不变 |
| `smart_assistant/views.py` | re-export `SmartChatViewSet`,不变 |
| `smart_assistant/urls.py` | `router.register(r"chat", SmartChatViewSet)`,不变 |

## 3. 技术方案(架构/接口设计)

### 3.1 模块职责划分

```
chat.py(薄 ViewSet 壳)
  ├── SmartChatViewSet          # 保留 parser_classes/permission_classes + 路由
  │     ├── create()  → 委托 chat_sync.handle_sync_chat(self, request)
  │     ├── stream()  → 委托 chat_stream.handle_stream_chat(self, request)
  │     ├── _extract_attachment() → 委托 conversation_manager.extract_attachment
  │     └── _inject_attachment()  → 委托 conversation_manager.inject_attachment
  │
  └── (不再持有 AgentOrchestrator 等 import —— 逻辑已下移)
```

### 3.2 各模块接口设计

**`conversation_manager.py`**(纯函数,无 self 依赖):

```python
def resolve_error(result: dict) -> bool                 # 原 _resolve_error
def usage_fields(usage) -> tuple                        # 原 _usage_fields
def extract_attachment(request) -> tuple                # 原 _extract_attachment(10MB 校验 + OfficeExtractor)
def inject_attachment(history, doc_dict, conversation_id)  # 原 _inject_attachment(file_sha256 + cache_attachment)
def load_session(user, conversation_id) -> tuple        # (session, history) 或 (None, None);DoesNotExist 返回 None 而非抛
def persist_success(session, conversation_id, query, answer, user) -> tuple  # (session, cid);append/rolling_summary/create new
# 注:persist_success 第 5 参 user 为 create-new 分支必需(chat.py L255 user=request.user);brief 4 参签名无法实现,已修正
```

**`chat_sync.py`**:

```python
def handle_sync_chat(viewset, request) -> Response      # create 主体(serializer 校验 → 附件 → confirm-replay → process → 持久化 → AgentLog → payload)
def _handle_confirm_replay(request, confirm_token)       # confirm-replay 子流程(从 create 拆分,降 C901)
def _build_sync_payload(result, log, conversation_id, error)  # payload 组装 + kind/hint 追加(降 C901)
```

模块级 import:`AgentOrchestrator`、`ToolRegistry`、`get_confirmation_draft`/`clear_confirmation_draft`、`execute_guarded`、`AgentLog`、`SmartAssistantSession` 等。

**`chat_stream.py`**:

```python
def handle_stream_chat(viewset, request)                # stream 入口(serializer 校验 → 附件 → setup → StreamingHttpResponse)
def _event_stream_generator(*, query, conversation_id, session, conversation_history, tool_context, start_time)  # SSE 生成器
def _persist_stream_session(session, conversation_id, query, answer)  # 流式会话持久化(降 C901)
def _build_stream_event(log, cid, error, meta, stream_error_code, stream_retry_after)  # session_event 组装 + kind/hint
```

模块级 import:`AgentOrchestrator`、`SmartAssistantSession`、`AgentLog`、`sse_event`、`annotate_error_kind` 等。

### 3.3 C901 下降路径

| 原符号 | 原 C901 | 拆分后 |
|---|---|---|
| `create` | 17 | `handle_sync_chat` ~8 + `_handle_confirm_replay` ~6 + `_build_sync_payload` ~5 |
| `stream` | 22 | `handle_stream_chat` ~6 + `_event_stream_generator` ~9 |
| `event_stream` | 16 | `_event_stream_generator` ~9 + `_persist_stream_session` ~6 + `_build_stream_event` ~5 |

### 3.4 保持行为一致的原则

- 拆分采用**逐字搬运**(copy-paste 原代码到新模块,不改语义),再按 C901 告警最小化拆分辅助函数
- 生成器 `start_time`/`conversation_history` 等闭包捕获变量改为显式参数传入
- `create` 的 confirm-replay 上下文(`context_sig` 前缀校验、token 归属校验)逻辑不变
- `stream` 的三层 try/兜底 done、`FAILED_ANSWER_STREAM_PREFIX` 失败标记语义不变

## 4. 实施步骤

### Task 1: 新增 conversation_manager.py

- [ ] 逐字搬运 `_resolve_error` → `resolve_error`、`_usage_fields` → `usage_fields`(模块级,无 self)
- [ ] 逐字搬运 `_extract_attachment` → `extract_attachment(request)`(10MB 校验 + OfficeExtractor,去掉 self)
- [ ] 逐字搬运 `_inject_attachment` → `inject_attachment(history, doc_dict, conversation_id)`(file_sha256 + cache_attachment)
- [ ] 新增 `load_session(user, conversation_id)` → (session, history);DoesNotExist 返回 (None, None) 而非抛
- [ ] 新增 `persist_success(session, conversation_id, query, answer)` → (session, cid);append/title/rolling_summary/create new
- [ ] 接口签名与 plan §3.2 一致;不 import 任何 ViewSet 依赖,纯函数模块

### Task 2: 新增 chat_sync.py

- [ ] 逐字搬运 create 主体为 `handle_sync_chat(viewset, request)`(serializer 校验 → 附件 → confirm-replay → process → 持久化 → AgentLog → payload)
- [ ] 拆分 `_handle_confirm_replay(request, confirm_token)`(context_sig 校验 / token 归属 / execute_guarded / clear_draft)
- [ ] 拆分 `_build_sync_payload(result, log, conversation_id, error)`(payload 组装 + kind/hint 追加)
- [ ] 模块级 import:AgentOrchestrator / ToolRegistry / get_confirmation_draft / clear_confirmation_draft / execute_guarded / AgentLog / SmartAssistantSession
- [ ] create C901 17 → handle_sync_chat <10

### Task 3: 新增 chat_stream.py

- [ ] 逐字搬运 stream 主体为 `handle_stream_chat(viewset, request)`(serializer 校验 → 附件 → setup → StreamingHttpResponse)
- [ ] 提取 `_event_stream_generator(...)`(闭包捕获变量 start_time/conversation_history 改为显式参数)
- [ ] 拆分 `_persist_stream_session(session, conversation_id, query, answer)`(带 last_error='' 防御)
- [ ] 拆分 `_build_stream_event(log, cid, error, meta, stream_error_code, stream_retry_after)`(session_event + kind/hint)
- [ ] 模块级 import:AgentOrchestrator / SmartAssistantSession / AgentLog / sse_event / annotate_error_kind
- [ ] stream C901 22 → <10;event_stream 16 → <10

### Task 4: 重构 chat.py 为薄壳

- [ ] SmartChatViewSet 保留 parser_classes / permission_classes / 类 docstring
- [ ] create() → 委托 chat_sync.handle_sync_chat(self, request)
- [ ] stream() → 委托 chat_stream.handle_stream_chat(self, request)
- [ ] _extract_attachment / _inject_attachment 保留方法签名,委托 conversation_manager
- [ ] 确认 views/__init__.py + views.py + urls.py 零改动

### Task 5: repoint 测试 mock 路径

- [ ] 按 create/stream 场景改 `chat.AgentOrchestrator` → `chat_sync/chat_stream.AgentOrchestrator`
- [ ] confirm-replay 测试 `chat.ToolRegistry.get_tool` → `chat_sync.ToolRegistry.get_tool`
- [ ] `chat.SmartAssistantSession.objects` / `chat.AgentLog.objects` 按场景改指
- [ ] 涉及约 14 个测试文件,改完跑 `pytest smart_assistant/tests/` 全量

### Task 6: 验证

- [ ] `ruff check smart_assistant/views/ --select C901` 全模块 <10
- [ ] mypy 无新增 error(对比基线)
- [ ] `pytest --ds=omni_desk_backend.settings.test` 全量回归绿 + 覆盖率 ≥80%
- [ ] `ruff check` + `ruff format --check` 双绿

### Task 7: 文档更新 + PR + merge

- [ ] 更新 `docs/technical/32-smart-assistant-multi-agent.md` 模块表(chat.py 拆分)
- [ ] round3 plan 标注 R3-A4 完成
- [ ] feature 分支 push → PR → CI 监控 → merge → 清理(按先例)

## 5. 验收标准

| 标准 | 验证方式 |
|---|---|
| `chat.py` 拆分后 C901 全模块 <10 | `ruff check smart_assistant/views/ --select C901` |
| `views/__init__.py` re-export 集合不变 | diff 对比拆分前后 |
| 全部测试 repoint 后通过 | `pytest --ds=omni_desk_backend.settings.test smart_assistant/tests/` |
| mypy 无新增 error | `mypy smart_assistant/` 对比基线 |
| 全量回归绿 + 覆盖率 ≥80% | `pytest --cov --cov-fail-under=80` |
| ruff check + format 双绿 | `ruff check` + `ruff format --check` |
| CI 全绿 | PR 合并前 `gh pr checks --watch` |

## 6. 风险评估与依赖

| 风险 | 缓解 |
|---|---|
| **高**:14 个测试文件 repoint 出错导致大范围失败 | 按 create/stream 场景逐个核对 patch 目标;改完即跑 `pytest smart_assistant/tests/` 全量 |
| **中**:event_stream 生成器重构引入行为差异 | 逐字搬运 + 生成器辅助函数只做提取不改语义;stream 相关测试全量覆盖(`test_e2e_smart_chat.py` 9 处) |
| **中**:会话持久化共享(create/stream 都调 persist_success)改动行为 | persist_success 与 stream 版 `_persist_stream_session` 语义有差异(create 建新会话带 title,stream 带 last_error='') —— **保持两套实现不强行合并**,避免引入行为差异 |
| **低**:conversation_manager 抽取破坏附件缓存逻辑 | inject_attachment 中 file_sha256 + cache_attachment 逻辑逐字保留 |

## 7. 关联

- 上游:`docs/plans/2026-08-14_project-optimization-round3.md`(R3-A4)
- 同源:R3-A1(stream_runner.py 拆分,SSE 契约出处 `sse_contract.py`)、R3-A3(packet/validator 拆分)
- 技术文档:`docs/technical/32-smart-assistant-multi-agent.md`(拆分后更新模块表)
