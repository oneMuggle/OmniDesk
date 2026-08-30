# 43. 智能助手多智能体协作卡片

> **状态**：🔄 真实编排接入设计（2026-08-30）
> **代码位置**：`omni_desk_frontend/src/features/smart-assistant/scenario/` 与 `omni_desk_backend/smart_assistant/`
> **入口**：`/smart-assistant` 智能助手聊天页
> **核心定位**：协作卡片是 `AgentTask` 真实执行过程的可视化消费端。卡片消费后端持久化的 `AgentEvent` SSE 流，展示真实 Agent、工具调用、结果、失败和审计信息；历史剧本只提供示例提问入口，不是执行引擎。

## 1. 设计动机与边界

多智能体协作不再由前端模拟。用户发起复杂任务后，后端创建 `AgentTask` 与 `AgentSubTask`，由 Celery 执行真实的 LLM 规划和子任务编排；每个重要阶段写入 `AgentEvent`，协作卡片通过任务 SSE 流订阅这些事件。因此，卡片显示的进度、工具调用和最终结果均来自实际任务，而不是本地 `setTimeout` 或 mock 数据。

本章覆盖以下链路：

- **真实任务**：`AgentTask` / `AgentSubTask` 是任务与子任务的持久化状态，`AgentEvent` 是协作事件的单一事实来源。
- **真实执行**：Celery `execute_agent_task` 调用通用编排器；Supervisor 进行真实 LLM 规划，SubTaskRunner 可通过 tool-calling 循环执行已注册工具并回灌结果。
- **可恢复订阅**：前端使用带 JWT 的 `fetch` + `getReader()` 订阅 `/tasks/{id}/stream/`，以 `last_seq` 断点续传并按 `sequence` 去重；不依赖浏览器 `EventSource`。
- **可控状态**：任务支持暂停、恢复、取消和重试；失败任务显示原因，部分子任务成功时以 `partial` 状态保留已有产出。
- **审计与回滚**：事件时间线支持审计 JSON 导出；涉及可回滚业务写入的工具记录 `AgentWriteLog`，从写操作列表进入回滚接口。

`scenarios.js` 中保留的剧本（如历史示例问题、标题和图标）只用于示例入口或快捷提问。它们不包含执行步骤，不决定后端是否升级为多智能体任务，也不绕过真实 API。普通问题仍走单轮 chat；多智能体任务由显式复杂任务入口或后端升级逻辑决定，前端不再按关键词拦截并回放。

## 2. 目录与职责

```
src/features/smart-assistant/scenario/
├── components/
│   ├── AgentCollabStream.jsx          # 将后端事件映射为协作流并配对工具调用/结果
│   ├── AgentCard.jsx                  # 单个 Agent 的思考与完成态
│   ├── ToolCallCard.jsx               # 真实工具调用、参数和返回结果
│   ├── FinalAnswerCard.jsx            # 任务最终答案及 partial/failed 展示
│   ├── AuditTimeline.jsx              # 按 sequence 展示原始审计事件
│   └── ScenarioCollabCard.jsx         # 卡片容器、状态操作、导出和错误提示
├── data/
│   ├── agents.js                      # Agent 展示元数据
│   ├── tools.js                       # 工具展示元数据（不执行 mock 工具）
│   └── scenarios.js                   # 示例入口：id/title/userInput/icon
└── hooks/
    └── useAgentTaskStream.js           # 真实 AgentTask SSE 订阅、续传和操作
```

后端相关职责：

- `smart_assistant` 的任务 API 创建任务、执行任务并处理 pause/resume/cancel/intervene。
- Celery 执行 `execute_agent_task`，向编排器注入 `PersistentEventBus` 和 `agent_task_id`。
- `PersistentEventBus` 先保留内存事件，再将事件持久化为 `AgentEvent`；事件写库失败不能中断业务执行，但最终事件应报告 `dropped_events`。
- `AgentWriteLog` 记录可回滚写操作；`/api/smart-assistant/write-logs/` 提供查询，`POST /api/smart-assistant/write-logs/{id}/revert/` 提供归属校验后的回滚入口。

## 3. 真实触发与执行流程

```
用户在 /smart-assistant 发起问题或点击复杂任务示例
   ↓
useSmartChat 创建 AgentTask，并请求执行
   ↓
Celery execute_agent_task
   ↓
Supervisor 真实 LLM 规划 → PipelineRunner / SubTaskRunner
   ↓
真实工具调用（tool_call）→ 工具结果（tool_result）→ 后续 LLM/子任务
   ↓
PersistentEventBus 持久化 AgentEvent(sequence)
   ↓
useAgentTaskStream 以 SSE 订阅 /tasks/{id}/stream/?last_seq=N
   ↓
mapAgentEvent 保留 eventType 并映射为卡片渲染类型
   ↓
AgentCollabStream / AuditTimeline / FinalAnswerCard 展示实时结果
```

SSE 信封统一使用 `sse_event()` 序列化，包含 `format_version`、`id` 和 `sequence`。多智能体事件仍保留自身的 `event_type` 语义（例如 `subtask.progress`、`subtask.tool_call`、`subtask.tool_result`、`task.completed`），不与单轮 chat 的 `chunk` / `meta` / `confirmation` 强行合并。

### 3.1 前端事件映射

后端事件映射在独立的 `mapAgentEvent(backendEvent)` 纯函数中完成，既方便测试，也保证审计导出保留原始事件类型：

| 后端 `event_type` | 前端 `type` | 卡片展示 |
|---|---|---|
| `subtask.started` / `subtask.progress` | `thinking` | Agent 开始与进度 |
| `subtask.tool_call` | `tool_call` | 工具名称、参数、轮次 |
| `subtask.tool_result` | `tool_result` | 工具返回值与执行结果 |
| `subtask.completed` | `thinking` 收尾 | Agent 完成态 |
| `task.completed` | `final_answer` | 最终答案 |
| `subtask.skipped` / `subtask.failed` / `task.failed` / `task.aborted` | `error` | 失败原因、重试和后续影响 |

前端事件对象至少保留以下字段：

```js
{
  id: `evt-${sequence}`,
  sequence,
  type,                 // thinking | tool_call | tool_result | final_answer | error
  eventType,            // 原始 AgentEvent.event_type，审计使用
  agent, tool, input, output, content, ts,
}
```

未知事件类型应保留原始载荷并以安全的 `thinking` 兜底，同时记录诊断信息，避免后端新增事件导致整张卡片无法显示。

## 4. SSE 续传、心跳与兼容性

客户端维护 `lastSequenceRef`。每次收到事件后推进该值，重连时请求 `?last_seq=N`，服务端只返回 sequence 大于 `N` 的事件。这样断线期间产生的事件可补齐，重连时已有事件不会重复渲染；事件 ID 也使用 sequence，调用方可按 sequence 去重。

- 不使用 `Last-Event-ID`：当前客户端不是原生 `EventSource`，需要自定义 JWT 请求头，且 IE11 不支持 `EventSource`。
- 服务端轮询 `AgentEvent`，无新事件时发送 `: ping` 心跳，避免长任务的静默连接被 nginx 或客户端误判为断开。
- `done` / `timeout` 帧也通过统一 SSE 出口，并携带终止时的 `sequence`；`paused`、`partial` 均属于可识别的终止或稳定状态。
- 服务端断点参数缺省为 `last_seq=0`。前端收到服务端 timeout 但任务仍未终止时立即续订；网络错误按 1s / 2s / 4s 退避，超过次数才显示连接错误。
- 不支持 `ReadableStream` 的 IE11 / Win7 环境降级轮询 `/timeline/`，按 sequence 去重，仍可查看任务进度。

## 5. 状态机与用户操作

任务状态与服务端保持一致：

```
idle → running → { pausing → paused → resuming → running }
                 ↘ completed | failed | partial | cancelled
```

`pausing` / `resuming` 是前端乐观中间态；只有收到后端对应事件才转为正式状态，超时则恢复原状态并提示操作失败。任务在服务端运行，因此暂停、恢复和取消都可能失败，不能仅修改本地 state 假装成功。

- **暂停 / 恢复**：调用任务干预接口；worker 在子任务边界响应暂停，恢复后从 checkpoint 继续。
- **取消**：调用 cancel 干预接口；已完成、失败、部分完成或已取消的任务拒绝重复取消。
- **重试**：以同一 objective 创建新的 `AgentTask`，获得新的 task ID 和新卡片；不再提供含义不清的本地 `reset`。
- **失败**：错误事件指出失败的 subtask、原因、重试次数及后续跳过或终止情况。
- **部分完成**：`partial` 是合法终态；成功子任务的结果仍展示，失败子任务单独呈现，不把整个卡片清空。

后端不支持的 FANOUT / HIERARCHICAL 模式按配置错误处理并落为 `failed`，不把 `rejected` 写入任务状态。

## 6. 真实工具执行与写入安全

SubTaskRunner 使用真实 tool-calling 循环：LLM 请求工具时发出 `subtask.tool_call`，通过 `ToolRegistry` 做用户权限范围内的解析与执行，工具返回后发出 `subtask.tool_result`，再将结果回灌给 LLM，直到不再请求工具或达到轮次/预算上限。工具 schema 缺省时由基类根据 `get_schema()` 生成通用 schema，已提供精确 schema 的工具继续使用精确版本。

写工具必须经过 `dry_run` / `confirmed` 两阶段和既有确认钩子。`Memo` 等可回滚写入与业务写操作在同一 `transaction.atomic` 中写入 `AgentWriteLog`，记录：

- `task`、`session_id`、触发用户和 `tool_name`；
- `target_model`、`target_pk`、`operation`；
- update / delete 的 `before`，create / update 的 `after`；
- `reverted_at`、`reverted_by` 以及创建时间。

回滚入口为 `POST /api/smart-assistant/write-logs/{id}/revert/`。它锁定日志、校验归属和当前值是否仍与 `after` 一致，已回滚或被人工改动时返回 `409`，不会静默覆盖人工修改。`delete` 操作明确不可逆，仅供审计；回滚动作本身再写一条 `AgentWriteLog`。任务页可通过 `GET /api/smart-assistant/write-logs/?task_id=` 列出本次任务的写入并提供撤销入口。`notify` 属于不可撤回的通知，其调用参数进入 `AgentEvent` 审计，不伪造写入回滚按钮。

## 7. 审计 JSON 导出格式

审计导出保留既有 JSON 契约的顶层字段和事件字段，兼容已有消费方；真实任务中 `scenarioId` / `scenarioTitle` 可表示所选示例入口，不能被解释为执行剧本。事件增加或保留 `sequence` 与 `eventType`，以便断点复核和审计时还原后端原始语义。

```json
{
  "scenarioId": "trip-approval",
  "scenarioTitle": "出差审批示例入口",
  "userInput": "帮我处理一下报销",
  "status": "completed",
  "generatedAt": "2026-08-27T10:23:45.678Z",
  "events": [
    {
      "id": "evt-1",
      "sequence": 1,
      "type": "thinking",
      "eventType": "subtask.progress",
      "agent": "planner",
      "content": "…",
      "ts": 1724759000000
    },
    {
      "id": "evt-2",
      "sequence": 2,
      "type": "tool_call",
      "eventType": "subtask.tool_call",
      "agent": "dispatcher",
      "tool": "query_trip_policy",
      "input": { "query": "…" },
      "ts": 1724759001000
    },
    {
      "id": "evt-3",
      "sequence": 3,
      "type": "tool_result",
      "eventType": "subtask.tool_result",
      "tool": "query_trip_policy",
      "output": { "…": "…" },
      "ts": 1724759001100
    }
  ]
}
```

`ts` 保留前端现有导出语义；服务端持久化事件的权威排序以 `sequence` 为准，时间线同时可用于查看 `created_at`。导出内容应包含失败、partial、暂停相关事件，不能只导出成功路径。

## 8. 与后端模块的关系

| 维度 | 后端任务编排 | 协作卡片 |
|---|---|---|
| 执行来源 | Celery + Supervisor + Pipeline/SubTaskRunner | 消费 `AgentEvent` SSE，不自行执行 |
| 事实来源 | `AgentTask` / `AgentSubTask` / `AgentEvent` | `useAgentTaskStream` 的事件状态 |
| 工具行为 | 真实 `ToolRegistry` 调用与结果回灌 | 展示 `tool_call` / `tool_result` |
| 连接恢复 | `/stream/` 支持 `last_seq` 断点查询 | 保存 `lastSequence`、重连和去重 |
| 失败与控制 | failed / partial / paused / cancelled 等服务端状态 | 错误渲染、暂停/恢复/取消/重试操作 |
| 审计与回滚 | `AgentEvent` + `AgentWriteLog` 与 revert API | 时间线导出、写入列表和回滚入口 |
| 剧本作用 | 不参与决策或执行 | 仅提供示例提问和展示元数据 |

## 9. 维护要点

- 新增事件类型时，同时更新后端 `EVENT_TYPE_CHOICES`、前端 `mapAgentEvent`、失败/未知类型兜底和审计导出测试。
- 新增工具时，确认 `ToolRegistry` 注册、schema、用户权限范围、真实执行结果和 `tool_call` / `tool_result` 事件；写工具必须补确认、审计与回滚语义。
- 修改状态机时同步更新后端 choices、SSE 终止集合、前端状态按钮和 `FinalAnswerCard` 的 partial/failed 展示。
- 修改 SSE 时保持 `format_version`、`id`、`sequence` 和 `last_seq` 契约；不要改回本地 timer 或原生 `EventSource`。
- `scenarios.js` 只维护示例入口元数据（`id` / `title` / `userInput` / `icon`），不得重新加入硬编码 steps、mockFn 或关键词拦截。
- 审计 JSON 必须保留原始 `eventType`、`sequence` 和完整失败事件，不能只导出前端映射后的粗粒度 `type`。

## 10. 已知限制与后续范围

- 当前多智能体任务流使用数据库轮询事件，不在本范围内引入 Redis pub/sub。
- FANOUT / HIERARCHICAL 执行模式暂不启用；不以伪造的 `rejected` 终态替代明确失败。
- 单轮 chat 的 token 预算与多智能体任务预算仍分别治理。
- `SwapRequest` 写工具的业务状态回滚、管理员撤销他人写入，以及 Email/SMS 等外部通知通道需单独设计。
- IE11 使用 timeline 轮询降级，不支持 `ReadableStream` 的实时 SSE 连接。
