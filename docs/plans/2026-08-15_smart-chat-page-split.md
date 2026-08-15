# R3-D1: SmartChatPage.jsx 拆分实施计划

> 日期:2026-08-15 | 状态:待批准 | 关联:round3 计划 `docs/plans/2026-08-14_project-optimization-round3.md` R3-D1
> 模式:参照后端 R3-A1/A3/A4 同款 SDD 拆分流程 —— 拆文件 + 逐字搬运 + repoint + 差分验证;前端已有 hook 抽离先例(`hooks/useTypewriter.js`)

## 1. 背景与目标

### 背景

`omni_desk_frontend/src/features/smart-assistant/pages/SmartChatPage.jsx` 当前 **713 行**,单文件同时承担 5 类职责:

| 职责 | 位置 | 行数 |
|---|---|---|
| 模块级纯函数 / 内联组件(`toDisplayMessages` / `parseThinkContent` / `MessageActions`) | L18-90 | ~73 |
| 页面状态 + refs(11 个 useState + 4 个 useRef) | L95-113 | ~19 |
| 打字机适配 + 自动滚动 | L114-130 | ~17 |
| 会话管理(load/new/switch/delete/fork/export/menu) | L132-209 | ~78 |
| SSE 层(parseSSE + 5 个事件处理器 + runStream) | L211-430 | ~220 |
| 提交 / 重试 / 停止 / 反馈 + 流式收尾 useEffect | L432-555 | ~124 |
| 渲染 JSX(header / session-list / messages / input-form) | L557-709 | ~153 |

与后端 R3-A1(1520 行 orchestrator)/ R3-A4(537 行 chat.py)同类,是 R3-D 前端大组件中**核心 UX 链路**(所有用户对话流),round3 计划明确列为 R3-D1(拆为 `ChatView` + `MessageList` + `InputBar` + `HookLayer`)。

### 目标

1. 将 `SmartChatPage.jsx` 拆为**薄壳(~60 行)** + HookLayer + 5 个子组件 + 1 个 utils 模块,各新文件 <800 行、函数 <50 行
2. **对外契约零变化**:`src/routes/index.jsx` lazy import 路径不变,默认导出不变 → 路由与前端 API 调用均不受影响
3. 拆分行为逐字一致,经 4 个测试套件(30 用例)全量回归 + 差分验证
4. 消解与 `components/MessageActions.jsx` 的**命名冲突**(页面内联 `MessageActions` 与它重名)

> 已实证(2026-08-15):`parseThinkContent` 在 `QuickAssistant.jsx` / `RagflowChatPage.jsx` 各有**本地重复拷贝**,无跨文件 import → 拆分无外部依赖;合并共享不在本轮(YAGNI,标注为可选后续)。

## 2. 涉及的文件与模块

### 新增(7 个)

| 文件 | 职责 | 预估行数 |
|---|---|---|
| `smart-assistant/utils/chatUtils.js` | 纯函数:`toDisplayMessages` + `parseThinkContent` + `parseSSE` | ~60 |
| `smart-assistant/hooks/useSmartChat.js` | HookLayer:全部 state + refs + 会话 CRUD + SSE 事件路由 + typewriter 编排 + submit/retry/stop/feedback + 流式收尾 useEffect | ~330 |
| `smart-assistant/components/ChatHeader.jsx` | 标题 + 会话切换按钮 | ~25 |
| `smart-assistant/components/SessionListPanel.jsx` | 会话侧边栏(新会话 + 列表 + fork/export 菜单 + 删除) | ~90 |
| `smart-assistant/components/MessageList.jsx` | 消息渲染(气泡 + think 分离 + ToolResult + 反馈 + 重试 + streaming + loading) | ~150 |
| `smart-assistant/components/MessageFeedbackActions.jsx` | 页面内联 `MessageActions` 改名迁移(复制/赞/踩) | ~60 |
| `smart-assistant/components/ChatInputBar.jsx` | 输入表单(input + FileAttachmentInput + 发送/取消) | ~60 |

### 修改(1 个)

| 文件 | 改动 |
|---|---|
| `pages/SmartChatPage.jsx` | 713 → ~60 行薄壳,组合 useSmartChat + 子组件,保留 `SmartChatPage.css` import |

### 不变(5 个)

| 文件 | 说明 |
|---|---|
| `src/routes/index.jsx` | `lazy(() => import('../features/smart-assistant/pages/SmartChatPage'))`,不变 |
| `api/smartAssistantApi.js` / `pages/sessionForkExportApi.js` | 已被 useSmartChat 复用,不变 |
| `hooks/useTypewriter.js` | 状态机 hook,useSmartChat 调用方不变 |
| `components/MessageActions.jsx` / `components/MessageMarkdown.jsx` | 旧版遗留组件,与本轮无关,不动 |
| 4 个测试文件 `pages/__tests__/SmartChatPage.*.test.jsx` | 全部 `render(<SmartChatPage />)` 整页渲染 + mock API 模块,不引用内部函数 → **零 repoint** |

### CSS 策略

`pages/SmartChatPage.css`(406 行)**不拆分**——class 跨组件共享(如 `.message-actions` 被 MessageFeedbackActions 用),拆分引入重复/分散;本轮目标是降 JSX 行数与复杂度,CSS 拆分 YAGNI(同后端 A6 先例:453 行 <800 上限未拆包)。

## 3. 技术方案(架构/接口设计)

### 3.1 模块职责划分

```
SmartChatPage.jsx(薄壳)
  ├── useSmartChat()                    # HookLayer:全部业务逻辑
  │     ├── state: 11 个 useState(原封不动)
  │     ├── refs:  4 个 useRef(messagesEndRef/abortRef/pendingLogIdRef/pendingErrorHintRef)
  │     ├── session: loadSessions/new/switch/delete/fork/export/menuClick
  │     ├── sse: parseSSE(utils)→ handleMeta/Chunk/Session/Confirmation → handleSSEEvent → runStream
  │     ├── actions: submit/retry/stop/feedback + 流式收尾 useEffect
  │     └── 返回扁平对象 { ...state, setInputMessage, setAttachment, setShowSessionList,
  │                        handlers..., messagesEndRef }
  │
  ├── <ChatHeader showSessionList onToggleSessionList />
  ├── <SessionListPanel sessions currentSessionId showSessionList
  │     onNewSession onSwitch onDelete onMenuClick />
  ├── <MessageList messages streamingAnswer streamingMeta isLoading
  │     messagesEndRef onFeedback onRetry />
  │     └── 内部使用 <MessageFeedbackActions> + <ToolResult> + <ThinkContent>
  ├── <ChatInputBar inputMessage attachment isLoading
  │     onInputChange onAttachmentChange onSubmit onStop />
```

### 3.2 useSmartChat 返回契约(扁平对象)

```js
const {
  inputMessage, setInputMessage,
  attachment, setAttachment,
  messages, isLoading, streamingAnswer, streamingMeta,
  sessions, currentSessionId, showSessionList, setShowSessionList,
  messagesEndRef,
  handleNewSession, handleSwitchSession, handleDeleteSession,
  handleForkSession, handleExportSession, handleSessionMenuClick,
  handleSubmit, handleStop, handleRetry, handleFeedback,
} = useSmartChat();
```

### 3.3 命名冲突消解

页面内联 `MessageActions`(antd Button + 复制/赞/踩,`props: content/onFeedback/feedback/submitting`)与 `components/MessageActions.jsx`(原生 button + 复制/重新生成/引用/删除,`props: message/onCopy/onRegenerate/onDelete/onQuote`)**重名且职责不同**。拆分时内联者改名 **`MessageFeedbackActions`** 迁移为独立文件,消解语义混淆;旧版 `components/MessageActions.jsx` 不动。

### 3.4 逐字搬运原则

- 纯函数(`toDisplayMessages`/`parseThinkContent`/`parseSSE`)逐字搬入 `utils/chatUtils.js`
- state 声明与全部 handler 逐字搬入 hook,仅新增 return 暴露;`scrollToBottom` + 滚动 useEffect 保留
- 渲染 JSX 按区块逐字搬入子组件,props 对齐 hook 返回契约
- **不改语义**:SSE 三层 try/兜底 done、fire-and-forget `getSessions`(不被 await)、typewriter 竞态防御(`getReceived` 同步读)注释、`handleFeedback` 乐观更新/回滚、`handleConfirmation` 的 confirm_token replay 全部保留
- `streaming-complete` useEffect 原样留在 hook 内,**依赖数组不变**(防流式收尾时序回归)

## 4. 实施步骤

### Task 1: 新增 `utils/chatUtils.js`

- [ ] 逐字搬运 `toDisplayMessages` → 模块级导出
- [ ] 逐字搬运 `parseThinkContent` → 模块级导出
- [ ] 逐字搬运 `parseSSE` → 模块级导出

### Task 2: 新增 `hooks/useSmartChat.js`

- [ ] 逐字搬运全部 useState/useRef/useCallback/useEffect(L95-555)
- [ ] `onTypewriterTick` / `typewriter` / `scrollToBottom` 原样保留
- [ ] import 调整:api 模块 / `useTypewriter` / `chatUtils`;`AntdModal`/`antMessage`/`logger` 保留
- [ ] 返回扁平对象暴露 state + setter + handlers + messagesEndRef

### Task 3: 新增 5 个子组件

- [ ] `ChatHeader.jsx` — 标题 + 会话切换按钮
- [ ] `SessionListPanel.jsx` — 会话侧边栏(含 Dropdown fork/export 菜单)
- [ ] `MessageList.jsx` — 消息列表 + streaming 气泡 + loading + scroll ref
- [ ] `MessageFeedbackActions.jsx` — 内联 MessageActions 改名迁移
- [ ] `ChatInputBar.jsx` — 输入表单 + FileAttachmentInput + 发送/取消
- [ ] 全部 import `SmartChatPage.css` 由薄壳统一引入(子组件复用 class,不重复 import)

### Task 4: 重构 `pages/SmartChatPage.jsx` 为薄壳

- [ ] 组合 useSmartChat + 5 个子组件,保留 `SmartChatPage.css` import
- [ ] 删除全部内联逻辑,仅保留组合
- [ ] 确认 `routes/index.jsx` lazy import 路径零改动

### Task 5: 验证

- [ ] 4 个 SmartChatPage 测试套件**零改动**通过(baseline 30 passed)
- [ ] `npm test` 全量回归绿(与 baseline 对比)
- [ ] `npm run lint` 通过
- [ ] `npm run build` 通过(generate-routes + vite build)

### Task 6: 文档更新 + PR + merge

- [ ] round3 plan 标注 R3-D1 完成
- [ ] feature 分支 push → PR → CI 监控 → merge → 清理(按先例)

## 5. 验收标准

| 标准 | 验证方式 |
|---|---|
| `SmartChatPage.jsx` ≤80 行薄壳 | `wc -l` |
| 各新文件 <800 行 / 函数 <50 行 | `wc -l` + 目检 |
| 4 个 SmartChatPage 测试零改动通过 | `npx jest pages/__tests__/` |
| 全量 jest / lint / build 三绿 | `npm test` + `npm run lint` + `npm run build` |
| `routes/index.jsx` lazy import 不变 | `git diff` |
| 命名冲突消解(页面内联 MessageActions 不存在) | `grep MessageActions SmartChatPage.jsx` 仅剩 import |

## 6. 风险评估与依赖

| 风险 | 缓解 |
|---|---|
| **高**:Hook 抽离引入闭包 / 依赖数组回归(SSE 编排是核心链路,影响所有对话流) | 逐字搬运 + 4 个测试套件(30 用例)覆盖 stream/errorHint/feedback/forkExport 全部行为;差分验证;streaming-complete useEffect 依赖数组不变 |
| **中**:`runStream` 中 `currentSessionId`/`attachment` 闭包依赖在 hook 中语义变化 | 原样保留 `useCallback` 依赖数组,不精简 |
| **中**:子组件 props 传错(无 TypeScript) | 逐字搬运 + props 对齐表 + jest 全量回归兜底 |
| **低**:CSS 共享导致子组件样式依赖页面壳 import | 保留单一 CSS 由薄壳 import(拆 CSS YAGNI,同 A6 先例) |

## 7. 关联

- 上游:`docs/plans/2026-08-14_project-optimization-round3.md`(R3-D1)
- 同源:后端 R3-A4(`docs/plans/2026-08-14_chat-view-split.md`,同款逐字搬运 + repoint + 差分验证流程)、前端 `hooks/useTypewriter.js`(hook 抽离先例)
- 技术文档:`docs/technical/32-smart-assistant-multi-agent.md`(前端模块表,可选更新)
