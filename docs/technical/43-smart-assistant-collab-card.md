# 43. 智能助手多智能体协作卡片

> **状态**：✅ 已实现（2026-08-27，`feat/offline-smoke-reliability` 工作期间提交）
> **代码位置**：`omni_desk_frontend/src/features/smart-assistant/scenario/`
> **入口**：`/smart-assistant` 智能助手聊天页（全员可用）
> **核心定位**：在智能助手真实聊天流中嵌入"多智能体协作卡片"消息，模拟智能助手真在调起多 Agent 完成差旅 / 文档 / 设备 / 合规 4 类业务场景，作为产品体验的一部分。

## 1. 设计动机

OmniDesk 后端的 `smart_assistant` 多 Agent 协作能力（见 [32-smart-assistant-multi-agent.md](32-smart-assistant-multi-agent.md)）已经成熟，但前端用户**只看到 chat 流**——智能体怎么思考、tool 怎么被调用、结果怎么生成、审计怎么追溯，全部"黑盒"在 LLM 输出里。

协作卡片用**纯前端 + 剧本回放**的方式把这条链路"白盒化"：

- 4 个业务场景覆盖核心链路（差旅 / 文档 / 设备 / 合规）
- 全部数据本地 mock，零网络依赖
- 用户在 chat 框发一句自然语言 → 智能助手回以"协作卡片"消息
- 卡片里能看到多智能体思考 / 工具调用 / 工具结果 / 最终答案 + 审计时间线

它是智能助手的**真实使用路径**而不是独立页面：

- 无独立路由、无独立菜单（`/control-panel/ai-assistant-demo` 已废弃）
- 入口在 `/smart-assistant` 智能助手聊天页，所有登录用户都能用
- 与 chat 流并存：未命中关键词时走真实 LLM 流式，命中时走协作卡片

## 2. 目录与文件

```
src/features/smart-assistant/scenario/
├── components/
│   ├── AgentCollabStream.jsx          # 协作流容器，配对 tool_call→tool_result
│   ├── AgentCard.jsx                  # 单个智能体气泡（thinking / final 两种变体）
│   ├── ToolCallCard.jsx               # 工具调用 + 结果（input/output JSON 块）
│   ├── FinalAnswerCard.jsx            # 最终答案（按 payloadKind 切换：email_draft / card_preview / workorder / announcement）
│   ├── AuditTimeline.jsx              # 审计时间线
│   └── ScenarioCollabCard.jsx         # 消息卡片容器（Header 状态/暂停/继续/重置/审计导出 + 流 + 审计）
├── data/
│   ├── agents.js                      # 13 个 Agent 元数据
│   ├── tools.js                       # ~25 个工具定义 + mockFn(input)
│   └── scenarios.js                   # 4 业务场景：trip-approval / doc-summary / device-incident / compliance-audit
└── hooks/
    └── useScenarioPlayer.js           # 剧本播放器 useReducer + setTimeout 推进
```

入口文件改动：

- `src/features/smart-assistant/components/MessageList.jsx` — messages 渲染循环加 `type === 'collab_card'` 早返分支，渲染 `ScenarioCollabCard`
- `src/features/smart-assistant/hooks/useSmartChat.js` — `sendMessage` 在 `matchScenarioByInput(query)` 命中时注入协作卡片消息 + 跳过 runStream

## 3. 触发流程

```
用户在 chat 输入框发 query
   ↓
useSmartChat.sendMessage(query)
   ↓
matchScenarioByInput(query) 命中场景关键词?
   │
   ├─ 否 → 走原 SSE 流(runStream)→ typing → assistant 文本消息
   │
   └─ 是 → setMessages([...prev, userMessage, collabCardMessage])
         collabCardMessage = {
           id, role: 'assistant', type: 'collab_card',
           scenarioId, userInput,
         }
         → 跳过 runStream / 不连后端
         → MessageList 渲染 ScenarioCollabCard
         → 卡片内 useScenarioPlayer 启动,setTimeout 按 step.delayAfter 推进
         → 用户看到完整多智能体协作过程 + 审计
```

**关键词**定义在 `data/scenarios.js`:

| 场景 | 关键词 |
|------|--------|
| `trip-approval` | 出差 / 审批 / 报销 / 差旅 |
| `doc-summary` | 文档 / 总结 / 搜索 / 总结文档 |
| `device-incident` | 设备 / 故障 / 传感器 / 告警 |
| `compliance-audit` | 合规 / 审计 / 通报 / 合规公告 |

无命中 → 走原 chat 链路。**前后端互斥**，不会出现"协作卡片 + LLM 流式回答"双发。

## 4. 状态机（useScenarioPlayer）

`ScenarioCollabCard` 内部 `useScenarioPlayer()`,由 ScenarioCollabCard mount 时 `start(scenarioId, userInput)` 触发。每条协作卡片消息独立持有一份 state,互不影响。

```
            ┌────────────┐
   start()  │   idle     │
   ───────► │            │
            └────┬───────┘
                 ▼
            ┌────────────┐ ◄── resume() ┐
            │  running   │ ──── pause() ─┤
            └────┬───────┘              │
                 │ 末步完成            │
                 ▼                      │
            ┌────────────┐              │
            │  completed  │              │
            └────┬───────┘              │
                 │ reset()              │
                 └──────────► idle ◄────┘
```

```js
// state 形状
{
  activeScenarioId: string|null,
  events: PlayerEvent[],          // thinking / tool_call / tool_result / final_answer
  status: 'idle' | 'running' | 'paused' | 'completed',
  cursor: number,
  userInput: string|null
}
```

实现要点：

- **`useReducer`** 管理状态机；`dispatch` 永远是稳定引用
- **`setTimeout` 推进**：每个 step 的 `delayAfter`（600~1200ms 区间）决定下一步延迟
- **`tickRef` + `useEffect` 同步 ref**：避免 `tick` 在 `useCallback` 内部自引用触发 lint 错误
- **`timerRef`** 持有最新 setTimeout id；`pause()` / `reset()` 通过 `clearTimeout` 立即取消
- **`startedRef` 哨兵**：ScenarioCollabCard 多次 mount 同 scenarioId 不重复 start

## 5. 卡片布局

| 区域 | 内容 |
|------|------|
| Card title | 场景名 + 状态 Tag(协作进行中/已暂停/已完成/准备中)+ 用户输入回显 |
| Card extra | 暂停 / 继续 / 重置 / 审计 4 个 type=text 小按钮(按状态条件渲染) |
| 主体上半 | `AgentCollabStream`:配对 `tool_call` → `tool_result` 渲染为单卡片；thinking / final_answer 各自分发到对应组件 |
| 主体下半 | `AuditTimeline`:按 `stepIndex` 升序展示所有事件，类型着色 |

操作：

- **暂停 / 继续**：仅在 running / paused 时显示对应按钮
- **审计**：构建 Blob 触发下载，文件名 `audit-<scenarioId>-<YYYYMMDD-HHmmss>.json`
- **重置**：清空 state 并回到 idle

## 6. 4 个业务场景

| ID | 标题 | 智能体 | 步骤数 |
|----|------|--------|--------|
| `trip-approval`       | 出差审批全流程     | dispatcher + approver + notifier | 12~16 |
| `doc-summary`         | 文档检索与摘要     | doc_retriever + summarizer + writer | 12~16 |
| `device-incident`     | 设备告警与派单     | monitor + diagnosis + dispatcher(notify) | 12~16 |
| `compliance-audit`    | 合规审计与公告     | auditor + legal + publisher | 12~16 |

按业务真实链路编排：

```
trip-approval:
  planner.thinking → dispatcher.query_trip_policy → approver.check_compliance
  → notifier.send_email → final_answer(email_draft)

compliance-audit:
  auditor.fetch_audit_logs → legal.compare_versions → publisher.draft_announcement
  → publisher.send_announcement → final_answer(announcement)
```

## 7. 审计 JSON 导出格式

```json
{
  "scenarioId": "trip-approval",
  "scenarioTitle": "出差审批全流程",
  "userInput": "帮我处理一下报销",
  "status": "completed",
  "generatedAt": "2026-08-27T10:23:45.678Z",
  "events": [
    { "id": "evt-…", "type": "thinking", "agent": "planner", "content": "…", "ts": 1724759000000 },
    { "id": "evt-…", "type": "tool_call", "agent": "dispatcher", "tool": "query_trip_policy", "input": {…}, "ts": 1724759001000 },
    { "id": "evt-…", "type": "tool_result", "tool": "query_trip_policy", "output": {…}, "ts": 1724759001100 }
  ]
}
```

可作为合规追溯展示物；每条事件含 `ts`（`Date.now()`），可对接 ELK / Loki 等日志系统再加工。

## 8. 与后端多 Agent 模块的关系

| 维度 | 后端 [32-smart-assistant-multi-agent.md](32-smart-assistant-multi-agent.md) | 本模块 |
|------|----------------------------------|--------|
| 是否真实执行 | ✅ 真实调用 LLM + 工具 | ❌ 纯前端剧本回放 |
| 输入 | 用户自然语言（HTTP API） | 场景关键词触发的 query |
| 输出 | SSE 流 + Hook 副作用 | 协作卡片消息 + 审计 JSON |
| 触发时机 | 用户在 chat 框发任意 query | query 命中场景关键词时互斥触发 |
| 适用场景 | 生产链路 | 产品体验 / 客户演示 / 培训 / 内部 review |

**互斥规则**：`useSmartChat.sendMessage` 中 `matchScenarioByInput` 命中时**不调** `runStream`，协作卡片与 LLM 流式回答不会双发。同一 query 只可能走一条路径。

## 9. 维护要点

- **新增场景**：编辑 `src/features/smart-assistant/scenario/data/scenarios.js`，每个 step 必须有 `type` 与对应字段；`keywords` 是匹配输入的关键，必须显式列出
- **新增 Agent**：编辑 `agents.js` 的 `AGENTS` 与 `ICON_MAP`（同步）；icon 名必须是 `@ant-design/icons` 实际导出
- **新增工具**：编辑 `tools.js` 的 `TOOLS` + `MOCK_FNS`（同步）；`mockFn(input)` 必须同步返回（无 Promise）
- **修改状态机**：在 `useScenarioPlayer.js`；注意 `tickRef` / `timerRef` 的清空；新增 dispatch action 必须更新 reducer 的 `case`
- **接入新消息类型**：参考 `MessageList.jsx` 的 `collab_card` 早返分支；在 `useSmartChat` 的 `messages` state 注入对应形状

## 10. 已知限制

- 全部数据 mock；如需对接真实后端 multi-agent 流，把 `useScenarioPlayer` 替换为 SSE 订阅，UI 渲染层无需改动
- 协作卡片不支持重试（retry 按钮只对普通 assistant 消息生效）
- 协作卡片无赞踩反馈（feedback 只对真实 LLM 响应生效）
- 协作卡片不持久化进度；切到其他会话再切回，已完成的卡片保留最终态，running 状态的卡片停在切换前一刻