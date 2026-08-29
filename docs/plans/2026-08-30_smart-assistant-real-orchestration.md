# 智能助手真实多智能体编排 — 实施计划

**日期**：2026-08-30
**设计文档**：`docs/superpowers/specs/2026-08-30-smart-assistant-real-orchestration-design.md`
**分支**：`feat/smart-assistant-real-orchestration`

## 背景与目标

把智能助手的多智能体协作从"前端剧本回放"转为真实能力。设计与根因分析见 spec，本文只记实施顺序、验证方式与进度。

四项交付能力：事件完整性、真实工具执行、可续传可中断、写操作可回滚。

## 涉及的文件与模块

### 后端

| 文件 | 变更类型 |
|---|---|
| `smart_assistant/agents/persistent_event_bus.py` | 新增 |
| `smart_assistant/agents/subtask_runner.py` | 大改（内嵌 tool-calling 循环） |
| `smart_assistant/tasks.py` | 改（注入 event_bus、删重复事件、超时换算、bulk_update） |
| `smart_assistant/views/tasks.py` | 改（并发闸门、SSE 续传、心跳） |
| `smart_assistant/models.py` | 改（`AgentWriteLog` 新表、两处 choices） |
| `smart_assistant/tools/base.py` | 改（`get_openai_tool_schema` 降级） |
| `smart_assistant/tools/notify_tool.py` | 新增 |
| `smart_assistant/tools/registry.py` | 改（注册 notify、lint 语义） |
| `smart_assistant/hooks/builtin/audit_log.py` | 改（移除 `_write_agent_event`） |
| `smart_assistant/views/write_logs.py` | 新增（回滚入口） |
| `smart_assistant/urls.py` | 改（write-logs 路由） |
| `smart_assistant/agent/sse_contract.py` | 可能微调（多智能体流复用） |
| `notifications/views.py` | 改（收紧为只读） |
| `notifications/channels/` | 新增（`NotifyChannel` + `InAppChannel`） |
| `notifications/models.py` | 改（两个 type choices） |
| `memos/models.py` | 改（软删字段） |
| `smart_assistant/tools/memo_write_tools*.py` | 改（写 `AgentWriteLog`、硬删改软删） |
| `llm_service/router.py` | 改（超时可配） |
| `settings/base.py` | 改（三个超时配置项） |

### 前端

| 文件 | 变更类型 |
|---|---|
| `scenario/hooks/useAgentTaskStream.js` | 新增 |
| `scenario/hooks/useScenarioPlayer.js` | 删除 |
| `scenario/utils/mapAgentEvent.js` | 新增 |
| `scenario/components/ScenarioCollabCard.jsx` | 改（换 hook、7 状态、cancel/retry） |
| `scenario/components/ErrorCard.jsx` | 新增 |
| `scenario/components/FinalAnswerCard.jsx` | 改（failed / partial 变形） |
| `scenario/data/scenarios.js` | 大幅精简（1270 → ~80 行） |
| `api/agentTaskApi.js` | 改（续传参数、forEach 修复、IE11 降级） |
| `hooks/useSmartChat.js` | 改（删互斥分支） |
| `components/QuickCommands.jsx` | 改（剧本降为示例入口） |

## 实施步骤

### 阶段 0：独立安全修复（不依赖后续任何阶段）

- [ ] 收紧 `notifications/views.py` 为 `ReadOnlyModelViewSet`，保留三个 `@action`
- [ ] 补测试：普通用户 POST / PUT / DELETE `/api/notifications/` 返回 405
- [ ] 确认前端 `notificationApi.js` 无调用被移除的方法

### 阶段 1：事件持久化桥（打通断链）

- [ ] 先写测试：`PersistentEventBus.emit` 落库、sequence 连续、DB 失败不中断编排并计数
- [ ] 实现 `agents/persistent_event_bus.py`
- [ ] `tasks.py:142-146` 补传 `event_bus` / `agent_task_id`
- [ ] 删除 `tasks.py:135` / `:196` / `:224` 三处手写 `AgentEvent`
- [ ] 移除 `audit_log.py` 的 `_write_agent_event` 与 `reset_sequence`（保留 `AgentLog` 写入）
- [ ] 验证：跑一个真实任务，`AgentEvent` 表出现完整事件链，sequence 无空洞
- [ ] 测试须 patch `subtask_runner` 而非 `executor.py` 的三个 compat-only shim

### 阶段 2：状态机闭合与并发闸门

- [ ] 先写测试：`partial` 状态可落库并被 SSE 识别为终态；`rejected` 映射为 `failed`
- [ ] `AgentTask.STATUS_CHOICES` 加 `partial`；`AgentEvent.EVENT_TYPE_CHOICES` 加 3 值
- [ ] `tasks.py` 落库前把 `rejected` 映射为 `failed`
- [ ] 生成迁移（choices 为 no-op，仍需生成）
- [ ] 先写测试：并发 execute + resume 只有一个生效
- [ ] `create_from_query` 包 `atomic`；`execute` / `intervene` 三分支加 `select_for_update`
- [ ] `.delay()` 移入 `transaction.on_commit`
- [ ] `cancel` 补终态校验

### 阶段 3：超时与预算

- [ ] `REQUEST_TIMEOUT` 改读 `settings.LLM_REQUEST_TIMEOUT_SECONDS`
- [ ] 新增 `AGENT_TASK_MAX_SECONDS` 配置；Celery 超时改派发时计算并传入
- [ ] `tasks.py:212-213` 的 `DoesNotExist` 改为不触发 autoretry（补测试）
- [ ] `TOOL_CALLS_TIMEOUT_SECONDS` 接到 `tool_rounds_runner`
- [ ] `tasks.py:170-184` 逐条 save 改 `bulk_update`

### 阶段 4：工具 schema 降级

- [ ] 先写测试：22 个工具全部能产出合法 openai schema；已手写 schema 的子类不被覆盖
- [ ] `tools/base.py` 的 `get_openai_tool_schema()` 改为从 `get_schema()` 降级生成
- [ ] 调整 `registry.assert_all_have_openai_schema()` 的 lint 语义
- [ ] 验证 `registry.get_openai_tools()` 不再抛 `NotImplementedError`

### 阶段 5：subtask 工具执行（本方案核心）

- [ ] 先写测试：subtask 能调工具、结果回灌、轮次上限生效、emit 两类事件
- [ ] `SubTaskRunner.run()` 内嵌 tool-calling 循环（`invoke_llm` → `generate_with_tools`）
- [ ] emit `subtask.tool_call`（payload 带 tool / arguments / round）与 `subtask.tool_result`
- [ ] 复用 `tool_rounds_runner` 的轮次上限与 `tool_choice="none"` 收尾
- [ ] 实测 token 消耗，据此调整 `global_budget` 默认值
- [ ] 验证：预算耗尽时 `pipeline.py:108-119` 的闸门正确跳过后续 subtask

### 阶段 6：SSE 契约统一与续传

- [ ] 先写测试：`?last_seq=N` 只返回 N 之后的事件；`done` / `timeout` 帧带 sequence
- [ ] 多智能体流改走 `sse_event()`，获得 `format_version`
- [ ] `last_seq` 读 query param；帧加 `id:` 行
- [ ] 终止集合补 `paused` / `partial`；`timeout` 帧移入正常退出分支
- [ ] `:256` 补 `select_related("subtask")`
- [ ] 加 15s 心跳注释帧

### 阶段 7：写操作 origin 标记与回滚

- [ ] 先写测试：`AgentWriteLog` 与业务写同事务；回滚恢复原值；当前值被改过则 409
- [ ] 新增 `AgentWriteLog` 模型 + 迁移
- [ ] `Memo` 加 `is_deleted` / `deleted_at` + 迁移（**迁移前 `check_migrations` + `backup_db`**）
- [ ] 全量 grep `Memo.objects`，逐处补 `is_deleted=False` 过滤（逐处补测试）
- [ ] `MemoDeleteTool` 硬删改软删
- [ ] memo 三个写工具在 `confirmed` 分支内写 `AgentWriteLog`
- [ ] 新增 `write_logs.py`：list + revert，四条闸门齐备
- [ ] 注册路由

### 阶段 8：notify 通道

- [ ] 先写测试：多候选拒绝、>10 人拒绝、scope 越权拒绝、dry_run 不落库
- [ ] 新增 `notifications/channels/`（`NotifyChannel` + `InAppChannel` + `NotifyResult`）
- [ ] `Notification.TYPE_CHOICES` 加两个 agent 类型 + 迁移
- [ ] 新增 `NotifyTool`（手写精确 schema），注册进 `ToolRegistry`
- [ ] driver 选择读 `NotificationPreference.channel_settings`，空则回落 `in_app`
- [ ] 任务终态自动投递 `agent_task_result`（`dedupe_key` 防重复）

### 阶段 9：前端替换

- [ ] 先写测试：`mapAgentEvent` 全部 event_type 映射正确、未知 type 走兜底
- [ ] 新增 `mapAgentEvent.js`
- [ ] 新增 `useAgentTaskStream.js`（含续传、退避策略、7 状态机）
- [ ] `agentTaskApi.js`：`some` → `forEach`、加 `lastSeq` 参数、`onDone` 带 sequence
- [ ] `ScenarioCollabCard` 换 hook，扩状态标签，`reset` → `cancel` + `retry`
- [ ] 新增 `ErrorCard`；`FinalAnswerCard` 支持 failed / partial
- [ ] 删 `useScenarioPlayer.js`
- [ ] 删 `useSmartChat.js:351-373` 互斥分支
- [ ] `scenarios.js` 精简至 `id` / `title` / `userInput` / `icon`
- [ ] `QuickCommands` 改为示例入口按钮
- [ ] 阶段一升级判据：加"复杂任务"显式入口

### 阶段 10：IE11 降级

- [ ] 先写测试：`ReadableStream` 不可用时走轮询分支
- [ ] `agentTaskApi.js` 在 `getReader` 缺失时降级为轮询 `/timeline/`（2s 间隔，按 sequence 去重）
- [ ] 在 Chrome 109 或等效环境验证

### 阶段 11：文档与验收

- [ ] 改写 `docs/technical/43-smart-assistant-collab-card.md`（第 1 / 2 / 3 / 8 / 10 节已滞后；第 2 节写"4 业务场景"实际是 8 个）
- [ ] 更新 `docs/technical/README.md` 第 43 章简介
- [ ] 后端全量 pytest + 覆盖率 ≥80%
- [ ] 前端 Jest + 覆盖率 + ESLint（注意 `eslint .` 只查 `.js`，`.jsx` 需显式路径）
- [ ] `npm run build` 验证 Vite 输出无不兼容语法
- [ ] 按 spec 第 11 节走完 10 条验收标准
- [ ] `deployment/docker/VERSION` + `CHANGELOG.md` 同步

## 风险与依赖

见 spec 第 9 节。实施中最需盯的三处：

1. **`Memo` 软删漏改查询点** — 阶段 7，必须全量 grep 而非凭印象
2. **tool-calling 的 token 消耗** — 阶段 5，需实测而非估算
3. **IE11 降级未测则 Win7 用户不可用** — 阶段 10，不能跳过

阶段依赖：0 独立；1 → 2 → 3 顺序；4 → 5 顺序（schema 是工具执行的前置）；6 依赖 1；7 / 8 独立于 5；9 依赖 6；10 依赖 9。

无新增 Python / npm 依赖。
