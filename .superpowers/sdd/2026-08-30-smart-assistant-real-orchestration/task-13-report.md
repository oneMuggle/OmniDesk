# Task 13 修复报告

## 状态
已完成问题 A、问题 B 的 scoped review 修复，尚未提交前的工作区仅包含本轮目标代码/测试与本报告（另有既有 task-11 报告改动未纳入本次提交）。

## 根因调查
- `AgentLogSerializer` 的 `user_query` 使用 ModelSerializer 默认字段，直接返回模型中的原文；同一 serializer 已有 `sanitize_public_text` canonical helper 可复用。
- `chat_stream._consume_stream_events` 对完整 SSE data 调用 `safe_public_value(data)`；全局 sanitizer 将 `content` 定义为敏感键，因此正常 chunk 与固定失败 chunk 的 `content` 被删除。全局 sanitizer 不能放宽，否则会扩大其他公开出口的暴露面。
- SSE 事件由 `sse_event` 统一添加 `format_version`，因此新边界处理必须保留既有 envelope 字段契约，同时拒绝未知异常字段。

## TDD 过程
1. 先新增 `test_user_query_is_publicly_redacted`，以及三个 SSE sanitizer 回归测试。
2. 首次运行 targeted pytest 得到预期 RED：日志测试返回完整 `user_query` 原文；SSE 测试因 `_sanitize_stream_event` 尚不存在而 ImportError。
3. 以最小生产改动进入 GREEN，并重新运行 targeted 测试通过。

## 本轮修复
### 问题 A
- `omni_desk_backend/smart_assistant/serializers.py`
  - 将 `AgentLogSerializer.user_query` 改为 `SerializerMethodField`。
  - `get_user_query` 复用 `sanitize_public_text`，覆盖邮箱、手机号、token/authorization、JSON 与普通敏感文本脱敏。
  - 未改变字段白名单或其他安全元数据字段契约。
- `omni_desk_backend/smart_assistant/tests/test_agent_log_serializer.py`
  - 直接构造包含邮箱、手机号、token、authorization JSON 的 `AgentLog`，断言输出不含原文/敏感值且保留普通文本。

### 问题 B
- `omni_desk_backend/smart_assistant/views/chat_stream.py`
  - 新增 `_sanitize_stream_event`：按 `chunk`、`meta`、`done`、`confirmation` 建立明确字段 allowlist。
  - `chunk.content` 与 confirmation answer 作为用户可见文本字段，单独调用 `sanitize_public_text`，不经过会删除 `content` 的全局 envelope sanitizer。
  - 结构化字段继续使用 `safe_public_value`；`format_version` 保留；异常、`exception`、原始 `message` 等未知字段不进入客户端结果。
  - 未放宽全局 sanitizer，未透传原始异常，也未修改 `stream_runner` 的固定安全错误文案/重复拼接逻辑。
- `omni_desk_backend/smart_assistant/tests/test_stream_runner.py`
  - 覆盖普通 chunk content 保留并脱敏、固定失败前缀保留、含 token/URL 的异常字段不出现在客户端 envelope。

## 验证
- TDD RED：新增测试首次运行失败，失败原因与两个根因一致。
- targeted：`52 passed`（`--no-cov`，覆盖 serializer、stream runner、chat stream、stream failure、orchestrator、mock LLM 相关测试）。
- `git diff --check`：通过。
- 智能助手测试全集：基线中仍有既有失败（涉及确认草稿/工具结果等其他近期安全契约），未发现属于本轮 serializer 或 SSE envelope 改动的 targeted 回归；本轮不排除或修改这些无关失败。
- 测试运行产生的 SECRET_KEY 随机值 warning 为测试 settings 的既有行为。

## 提交
待提交：使用中文 conventional commit，说明 AgentLog 查询脱敏与 SSE 公开 envelope 修复。

## 遗留项
- 全量智能助手测试中仍有与本轮无关的既有契约失败，主要集中在其他确认重放/工具结果公开摘要测试；需由对应后续 scoped review 单独处理。
- 无已知与本轮改动相关的遗留疑问。

## 变更边界
未修改 `VERSION`、任何 `CHANGELOG`、用户 spec；未修改全局 sanitizer。

## 本次 Important 修复补充
- `format_version` 不再信任上游同名字段，公开事件固定使用 `FORMAT_VERSION`；嵌套 dict/list 版本值及敏感结构不会进入客户端。
- `_sanitize_stream_event` 在 `event_type` 为非字符串时提前返回空事件；`_consume_stream_events` 跳过空事件后继续消费后续合法 chunk/done，保证流收口。
- allowlist 继续保留正常 chunk content、confirmation answer、固定失败字段与 format_version，未放宽全局 `safe_public_value`。

## 本轮 15 个失败处理（2026-08-31）

### 分类与处理
- A 类安全契约测试：通知审计不再断言 recipient name/title/content，改为 `recipient_count`、`sent_count`、`failed_count` 及不泄露断言；同步 chat 的人员、排班、公告、合规、外链及 RAG 测试不再断言原始 `found`、明细或 `sources`，改为安全计数/空摘要/不泄露断言；确认 replay 测试改为安全 draft 摘要及安全执行摘要。
- B 类生产回归：确认 replay E2E 原先只 patch `get_tool`，而生产 replay 使用 `get_tool_for_user`，导致真实重放返回 500；测试补齐正确的授权 lookup patch，未放宽生产授权逻辑。
- `public_tool_result` 增补聚合结果的安全摘要字段 `summary`、`items`、`moduleCounts`、`total_count`，保持原始工具明细字段过滤。
- `except: pass` 计数回归：`views/tasks.py` schema fallback 与 `agents/supervisor.py` 两段 JSON fallback 改为显式 debug 日志；这两处均属本计划新增/修改路径。原有下载清理、日期解析及线程清理的 best-effort swallow 未改。

### 验证结果
- targeted（15 个失败场景对应测试）：`24 passed`。
- 异常基线及相关 Supervisor/任务/确认测试：`48 passed`。
- 下一步执行后端正确目录的全量 `pytest`，不排除失败。

### 最终结果
- 后端全量（`cd /home/fz/project/OmniDesk/omni_desk_backend && /home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest --ds=omni_desk_backend.settings.test -q`）：`3117 passed, 2 xfailed, 11 xpassed, 42 warnings`，耗时约 3 分 15 秒，退出码 0。
- `git diff --check`：通过。
- 警告仅包含测试环境随机 `SECRET_KEY` 及既有 Django timezone/pagination 等 warning；无失败测试。

## Task 13：公开 ToolResult 契约收口（2026-08-31）

- 读取并复现 HEAD `42906beb` 的五个失败：原测试仍断言 `tool_result == {}`，与当前安全状态 DTO 契约冲突；RAG 原实现还会把 `context` 及泛化后的原始 `sources` 带入公开结果。
- 失败优先更新测试并确认 RED/行为差异，随后最小实现：删除漂移的 `_PUBLIC_RESULT_KEYS`，增加显式基础状态 allowlist（`found/status/message/date/count` 等），`message` 经文本 sanitizer；聚合字段仅允许 `aggregated_day` intent/tool；RAG 走专用安全 DTO，仅公开 `found/count/sources` 与 `document/title/score/source_id`，不公开 `context/content/path/url`（普通外链 URL 仍由 `sanitize_public_sources` 策略控制）。
- 前端 `ToolResult` registry 现有 `knowledge_qa` 卡片可渲染安全 sources；新增失败状态与 RAG 安全 DTO 正向测试，避免安全结果静默空白。
- 原生 tool-calling 成功路径补齐按用户/scope 的工具缓存写入；未改动既有 AgentLog、replay scope/CAS、Notify、SSE 与来源 URL 安全修复。

### 验证结果

- 后端相关：`pytest --no-cov --ds=omni_desk_backend.settings.test smart_assistant/tests/test_task13_public_boundaries.py smart_assistant/tests/test_e2e_personnel_tool.py smart_assistant/tests/test_e2e_smart_chat.py smart_assistant/tests/test_e2e_rag_tool.py -q`：**25 passed, 1 failed**。
- 剩余失败：`test_e2e_cache_isolated_by_user_and_scope`；当前测试通过 `@override_settings(USE_NATIVE_TOOL_CALLS=False)` 强制 JSON 路径，但其 patch 目标仍指向已拆分前的包根 `cache_tool_result`，实际写入发生在 `persistence._root().cache_tool_result`，故捕获列表为空；该失败是测试 patch seam 与当前模块拆分不一致，非公开 DTO 回归。
- 前端：`npm test -- --watch=false src/features/smart-assistant/components/__tests__/ToolResult.test.jsx`：**1 suite, 8 tests passed**。
- `npm run lint -- --no-fix`：通过；`git diff --check`：通过。
- 尚未声称后端全量通过；此前用户提供 HEAD 基线全量为 **3117 passed, 5 failed**，本轮未以退出码 0 重跑全量。

## Task 13：缓存隔离测试 seam 修复（2026-08-31）

- 根因确认：`LegacyProcessMixin` 位于 `smart_assistant/agent/orchestrator/persistence.py`，通过 `persistence._root()` 动态读取编排器包根；测试原先使用字符串 patch 目标虽指向包根，但该测试路径实际还被确认钩子拦截，未进入真实工具缓存写入，导致 `captured_context_sigs` 为空。
- 测试修复：在 `test_e2e_cache_isolated_by_user_and_scope` 中显式导入已加载的 `smart_assistant.agent.orchestrator` 包根，并以 `patch.object(orchestrator_root, "cache_tool_result", ...)` 绑定兼容 seam；同时将固定测试工具明确设为 `require_confirmation = False`，确保测试验证真实工具执行后的 plain/admin scope-aware 缓存写入，而非确认预演路径。
- 未修改任何生产代码、缓存安全逻辑或安全边界。

### 验证结果

- 修复前 RED：目标测试 `1 failed`，失败为 `captured_context_sigs` 为空。
- 修复后目标测试：`1 passed, 1 warning`（随机 `SECRET_KEY` warning 为既有测试 settings 行为）。
- 相关缓存与 legacy 测试：`63 passed, 1 warning`，覆盖 `test_cache.py`、`test_cache_stream_shortcut.py`、`test_cache_stampede.py`、`test_cache_confirmation_draft.py`、`test_legacy_process_helpers.py` 及目标 E2E 测试。
- `git diff --check`：通过。
- 未运行后端全量测试；报告中此前记录的全量基线/遗留失败不因本次测试 seam 修复而改变。

## Task 13：Notify 审计身份与来源 URL 凭据边界（2026-08-31）

### 根因与修复
- `NotifyTool._confirmed` 原先将进程内 `sent/failed` 条目的 `user_id` 复制到 `AgentEvent` 审计 payload；`SAFE_EVENT_PAYLOAD_KEYS` 又允许 `sent/failed` 进入公开事件，导致 AgentEventSerializer、SSE 和 timeline 可见稳定用户标识。
- 发送结果仍保留进程内 `user_id` 供返回/去重逻辑使用；写入 AgentEvent 的审计 payload 改为仅保存计数、channels 及逐项 channel/reason 摘要。
- `_safe_event_payload` 对历史或伪造事件中的 `sent/failed` 做二次字段白名单，仅保留 `channel`、非身份 `reason/status`，不放宽全局 sanitizer。
- `_is_public_url` 现在拒绝 authority 中的 username/password，以及 fragment 中的 token、signature、credential、access_token 标识；普通 HTTPS 外链和无凭据 query 保留。

### TDD 与验证
- RED：先加入真实 `NotifyTool -> PersistentEventBus -> AgentEvent -> _safe_event_payload/AgentEventSerializer/timeline/SSE` 回归测试及 URL authority/fragment 测试；首次运行分别复现 `user_id` 落库、`safe_public_value` 保留 `user_id`、以及凭据 URL 被保留。
- GREEN：最小生产修复后 targeted 测试 `3 passed`（使用 `--no-cov`；覆盖新增审计集成、身份 sanitizer、URL sanitizer）。
- 测试环境随机 `SECRET_KEY` warning 为既有行为。

### 变更边界与遗留项
- 未修改 `VERSION`、`CHANGELOG`、用户 spec；未恢复 found/schedules/personnel 等原始明细，也未放宽全局 sanitizer。
- 本报告追加内容与本轮代码/测试均属于 Task 13；工作区原有 task-11 报告改动保持不动。
- 全量测试在最终提交前运行并记录实际结果；若环境/基线失败，将明确列出。

## Task 13：确认重放与流式安全契约收口（2026-08-31）

### 根因与处理
- 三个指定失败均先在 HEAD 复现：确认 E2E 首次响应的 `tool_result` 被同步 payload 的通用 `public_tool_result` 收口为空，导致确认 UI 丢失摘要；其余两个失败是测试仍断言旧结果结构。
- 生产修复：`_build_sync_payload` 对 `awaiting_confirmation` 使用 `public_confirmation_draft` 输出 `draft.summary` 与安全 `fields`，不恢复 server-side 原始 draft；普通/重放结果继续使用 `public_tool_result` allowlist。
- 测试修复：确认 E2E 和 replay 测试明确断言 `found`、`summary` 及字段集合；流式测试明确断言固定 `FORMAT_VERSION` 与未知 nested 结果被删除。

### TDD 与验证
- RED：三个原始测试全部失败；生产回归的确认摘要丢失由 `test_full_replay_chain` 直接复现。
- GREEN：相关确认重放、流式及 Task 13 boundary 测试：`29 passed, 1 warning`（`--no-cov`）。
- 后端全量测试：`cd /home/fz/project/OmniDesk/omni_desk_backend && /home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest --ds=omni_desk_backend.settings.test -q`：`3124 passed, 2 xfailed, 11 xpassed, 42 warnings`，退出码 `0`，总覆盖率 `93.40%`。

### 变更边界
- 保留既有 AgentLog、scope/CAS、Notify audit、URL、SSE content/type/format 修复。

## Task 13：统计权限与 URL 凭据文本脱敏（2026-08-31）

### 根因与处理
- `StatsViewSet` 原先仅要求 `IsAuthenticated`，且 `overview`/`daily` 查询全体 `AgentLog`；统计页属于管理端，因此改为 `IsAdminUser`，普通已认证用户返回 403。
- `days` 限制为 1 至 365 的整数；非法或越界参数返回 400，不再抛出 500。
- `top_questions` 改为按 `intent` 安全聚合，不返回 `user_query` 原文；前端表格同步显示“热门意图”。
- `sanitize_public_text` 增加有限 URL query 凭据替换，覆盖 `X-Amz-Signature`、`X-Amz-Credential`、`X-Amz-Security-Token`、`sig`、`signature`、`access_token` 及连字符变体；普通 HTTPS 外链和普通 query 保持不变，来源 DTO 原有 URL 校验未放宽。

### TDD 与验证
- RED：新增测试先复现普通用户 200、非法 `days` 500、原始 `user_query` 返回及签名 URL 值泄露；修正测试收集错误后重新确认均为预期 RED。
- GREEN targeted：统计与缓存后端测试 `23 passed, 1 warning`，退出码 0；拆分统计 `14 passed`、缓存 `26 passed`，退出码均 0。
- 前端智能助手测试：19 suites / 168 tests passed，退出码 0；仅有既有 React `act`/Ant Design deprecation warnings。
- 后端全量：仓库根目录误执行一次退出码 1（Django import path 缺失）；在 `/home/fz/project/OmniDesk/omni_desk_backend` 正确执行后 `3134 passed, 2 xfailed, 11 xpassed, 42 warnings`，覆盖率 93.41%，退出码 0。

### 变更边界复核
- 保留 confirmation summary 固定文案、fields 白名单、scope/CAS、AgentLog 脱敏字段、Notify audit 无身份、来源 DTO URL 校验、SSE content/type/format、`public_tool_result` 聚合边界；未修改 `VERSION`、`CHANGELOG`、user spec。

## Task 13：确认首次响应公开字段白名单补强（2026-08-31）

### 处理内容
- 在 `/home/fz/project/OmniDesk/omni_desk_backend/smart_assistant/tests/test_confirm_replay_e2e.py` 的首次确认响应断言中，补充 `public_draft["fields"]` 的正向白名单断言。
- 允许字段集合严格限制为 `operation_id`、`operation`、`phase`、`scope`、`status`、`count`、`total`；并明确断言 `content`、`recipient_ids`、`recipient_names`、`credentials`、`query` 均不存在。
- 仅增强测试契约，未修改生产代码、`public_confirmation_draft` 实现或任何安全边界。

### 验证
- 基线目标测试（修改前）：3 passed；默认覆盖率阈值导致进程退出码 1（单文件运行总覆盖率 17%，与本次测试变更无关）。
- 本轮未执行 RED：这是针对现有安全 DTO 的补充断言，非生产行为变更；基线已证明原有 3 个场景通过，直接进入 GREEN 验证。
- GREEN 目标测试：3 passed（`--no-cov`），1 个既有随机 `SECRET_KEY` warning。
- 相关确认/replay/boundary 测试：54 passed（`--no-cov`），1 个既有随机 `SECRET_KEY` warning。
  - `test_confirm_replay_e2e.py` + `test_view_confirm_replay.py`：12 passed。
  - `test_cache_confirmation_draft.py` + `test_task13_public_boundaries.py`：42 passed。
- `git diff --check`：通过。

### 最终阻塞修复：通用确认摘要任意 query 泄露（2026-08-31）

#### 根因与处理
- 阻塞问题：`public_confirmation_draft` 对非 `agent_notify` 工具将 server-side `draft.summary` 经 `sanitize_public_text` 直接公开；任意用户 query/业务文本不是该 sanitizer 可识别的固定敏感模式，因此会进入首次确认 HTTP 响应。
- TDD RED：先在真实 `test_confirm_replay_e2e.py` 首次确认链注入 `QUERY_SECRET_123`、正文、收件人 ID/姓名、credentials 等哨兵，并断言完整公开 draft JSON 不含哨兵；旧实现因 summary 包含 `QUERY_SECRET_123` 按预期失败。
- GREEN：`public_confirmation_draft` 的通用分支改为固定摘要 `请确认工具操作`，不透传 `draft.summary`、tool_name 或未知自由文本；保留安全字段 allowlist 及前端所需 `summary`/`fields` 结构。`agent_notify` 仍只公开 operation、recipient_count、脱敏 title、operation_id。
- 通知确认测试补充正向字段集合与正文、IDs、names、credentials/query 哨兵不泄露断言。

#### 验证
- RED：目标 E2E 先因 `QUERY_SECRET_123` 出现在公开 summary 失败。
- GREEN targeted：`35 passed`（`test_confirm_replay_e2e.py` + `test_tasks.py`，`--no-cov`）；单链路复跑 `1 passed`。
- 后端全量首次从仓库根目录执行因 Django import path 环境错误退出码 1；按正确后端目录重跑后首轮发现 2 个旧摘要断言，更新为固定安全模板后回归 `2 passed`。
- 后端全量最终（完成测试断言更新后重新执行）：`3124 passed, 2 xfailed, 11 xpassed, 42 warnings`，退出码 `0`，耗时约 2 分 48 秒。

#### 变更边界
- 未修改 AgentLog、sync answer/sources/RAG DTO、public_tool_result allowlist、Notify audit、URL 凭据拒绝、replay scope/CAS 或 SSE 契约。
- 未修改 `VERSION`、`CHANGELOG`、user spec。
