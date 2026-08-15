# R3-D3: AgentTaskPanel.jsx 拆分实施计划

> 日期:2026-08-15 | 状态:已完成 | 关联:round3 计划 `docs/plans/2026-08-14_project-optimization-round3.md` R3-D3
> 模式:与 R3-D1/R3-D2 同款 SDD 拆分流程 —— 拆文件 + 逐字搬运 + repoint + 差分验证(前端已有先例:`utils/chatUtils.js` + `hooks/useSmartChat.js` + 子组件)

## 1. 背景与目标

### 背景

`omni_desk_frontend/src/features/smart-assistant/pages/AgentTaskPanel.jsx` 当前 **522 行**,单文件同时承担 4 类职责:

| 职责 | 位置 | 行数 |
|---|---|---|
| 模块级纯函数 + 常量(`TERMINAL_STATUSES` / `eventColor` / `formatTime` / `formatPayload` / `normalizeHistoryEvent` / `normalizeStreamEvent` / `statusInfoOf`) | L47-89 | ~43 |
| 页面状态 + refs(15 个 useState + 2 个 useRef)与全部业务 handler(`stopStream` / `loadTasks` / `startStream` / `loadTaskDetail` / `handleSelectTask` / `handleCreateAndExecute` / `handleIntervene` + 3 个 useEffect) | L91-283 | ~193 |
| 渲染 JSX:创建表单 + 任务列表 | L285-364 | ~80 |
| 渲染 JSX:任务详情(概要 + 介入按钮 + 子任务 + 时间线 + 产出) | L367-519 | ~153 |

与 R3-D1(713 行 SmartChatPage)/ R3-D2(588 行 ToolResult)同类,是 round3 计划 R3-D 前端大组件系列的一部分,明确列为 R3-D3(拆为 `AgentTaskPanel` + `AgentTaskItem` + `AgentLogStream`)。

### 目标

1. 将 `AgentTaskPanel.jsx` 拆为**薄壳(~70 行)** + HookLayer(`useAgentTaskPanel`) + 1 个 utils 模块 + 6 个子组件,各新文件 <800 行、函数 <50 行
2. **对外契约零变化**:`routes/index.jsx` lazy import 路径不变,默认导出不变 → 路由不受影响
3. 拆分行为逐字一致,经既有测试套件(12 用例)全量回归 + 差分验证,并新增 utils 单测补纯函数覆盖
4. 延续 R3-D1/D2 既定模式(utils/ + hooks/ + components/ 子组件目录),保持 smart-assistant 前端结构一致

## 2. 涉及的文件与模块

### 新增(8 个)

| 文件 | 职责 | 预估行数 |
|---|---|---|
| `smart-assistant/utils/agentTaskUtils.js` | 纯函数:`eventColor` + `formatTime` + `formatPayload` + `normalizeHistoryEvent` + `normalizeStreamEvent` + `statusInfoOf` + `TERMINAL_STATUSES` 常量 | ~60 |
| `smart-assistant/hooks/useAgentTaskPanel.js` | HookLayer:全部 state + refs + stopStream/loadTasks/startStream/loadTaskDetail + handleSelectTask/handleCreateAndExecute/handleIntervene + 3 个 useEffect | ~200 |
| `smart-assistant/components/agentTask/TaskCreateForm.jsx` | 创建表单(Input + 创建并执行 Button + 错误 Alert) | ~45 |
| `smart-assistant/components/agentTask/TaskListPanel.jsx` | 任务列表容器(Card + List + Empty 空态 + 错误态 + 刷新按钮),内部渲染 `<AgentTaskItem>` | ~50 |
| `smart-assistant/components/agentTask/AgentTaskItem.jsx` | 任务列表单项(objective + 状态 Tag + 选中高亮 + onClick) | ~35 |
| `smart-assistant/components/agentTask/TaskDetailPanel.jsx` | 详情容器(概要 + 子任务 + 最终产出 + 空/载/错态),组合介入按钮组与时间线 | ~75 |
| `smart-assistant/components/agentTask/TaskInterveneActions.jsx` | 暂停/恢复/终止按钮组(含 Popconfirm 确认终止) | ~50 |
| `smart-assistant/components/agentTask/AgentLogStream.jsx` | 执行时间线(Timeline + 事件节点渲染 + payload 截断 + 空态) | ~70 |

### 修改(1 个)

| 文件 | 改动 |
|---|---|
| `pages/AgentTaskPanel.jsx` | 522 → ~70 行薄壳,组合 useAgentTaskPanel + 子组件,保留标题与描述区块 |

### 新增测试(1 个)

| 文件 | 覆盖 |
|---|---|
| `smart-assistant/utils/__tests__/agentTaskUtils.test.js` | 纯函数:`eventColor` 各分支(后缀 .failed/.completed、前缀 task./supervisor./user.、hook.triggered、默认 gray)、`normalizeHistoryEvent`/`normalizeStreamEvent` 键映射、`formatPayload` 截断与空对象、`formatTime` 空值、`statusInfoOf` 回退 |

### 不变(4 个)

| 文件 | 说明 |
|---|---|
| `src/routes/index.jsx` | `lazy(() => import('../features/smart-assistant/pages/AgentTaskPanel'))`,不变 |
| `api/agentTaskApi.js` | 已被 useAgentTaskPanel 复用,不变 |
| `pages/__tests__/AgentTaskPanel.test.jsx` | 全部 `render(<AgentTaskPanel />)` 整页渲染 + mock `agentTaskApi` 模块,不引用内部函数 → **零 repoint** |
| `api/__tests__/agentTaskApi.test.js` | 与本轮无关,不动 |

## 3. 技术方案(架构/接口设计)

### 3.1 模块职责划分

```
pages/AgentTaskPanel.jsx(薄壳 ~70 行)
  ├── useAgentTaskPanel()                    # HookLayer:全部业务逻辑
  │     ├── state: 15 个 useState(原封不动)
  │     ├── refs:  subscriptionRef / loadTaskDetailRef
  │     ├── sse:   stopStream / startStream(含 onEvent 去重 / onDone / onTimeout / onError)
  │     ├── data:  loadTasks / loadTaskDetail(含终态停流 + resubscribe 自动订阅)
  │     ├── actions: handleSelectTask / handleCreateAndExecute / handleIntervene
  │     ├── effects: loadTaskDetailRef 同步 / 初始 loadTasks / 卸载 stopStream
  │     └── 返回扁平对象 { tasks, tasksLoading, tasksError, goal, setGoal,
  │                        createLoading, createError, selectedTaskId, taskDetail,
  │                        subtasks, events, detailLoading, detailError,
  │                        streaming, streamError, interveneLoading,
  │                        loadTasks, handleSelectTask, handleCreateAndExecute,
  │                        handleIntervene }
  │
  ├── 标题 + 描述(薄壳内联,原封不动)
  ├── <TaskCreateForm goal createLoading createError
  │        onGoalChange onCreate />
  ├── <TaskListPanel tasks tasksLoading tasksError selectedTaskId
  │        onSelect onRefresh />
  │     └── 内部渲染 <AgentTaskItem task selected onClick />
  └── <TaskDetailPanel selectedTaskId taskDetail subtasks events
        detailLoading detailError streaming streamError interveneLoading
        onIntervene />
        ├── 概要 + streamError Alert + 子任务 List + 最终产出 pre(内联)
        ├── <TaskInterveneActions status interveneLoading onIntervene />
        └── <AgentLogStream events detailLoading />
```

### 3.2 Hook 返回契约(扁平对象)

```js
const {
  tasks, tasksLoading, tasksError,
  goal, setGoal, createLoading, createError,
  selectedTaskId, taskDetail, subtasks, events,
  detailLoading, detailError, streaming, streamError,
  interveneLoading,
  loadTasks, handleSelectTask, handleCreateAndExecute, handleIntervene,
} = useAgentTaskPanel();
```

### 3.3 子组件 props 契约

```js
<TaskCreateForm goal createLoading createError onGoalChange onCreate />
<TaskListPanel tasks tasksLoading tasksError selectedTaskId onSelect onRefresh />
  <AgentTaskItem task selected onClick />
<TaskDetailPanel selectedTaskId taskDetail subtasks events
  detailLoading detailError streaming streamError interveneLoading onIntervene />
  <TaskInterveneActions status interveneLoading onIntervene />
  <AgentLogStream events detailLoading />
```

### 3.4 逐字搬运原则

- 纯函数逐字搬入 `utils/agentTaskUtils.js`,`TERMINAL_STATUSES` 常量一并迁移
- state 声明与全部 handler 逐字搬入 hook,仅新增 return 暴露;**不改语义**:
  - SSE `onEvent` 内按 sequence 去重的 `prev.some` 逻辑原样保留
  - `onDone` 里 fire-and-forget `loadTasks()`(不被 await)原样保留
  - `onTimeout` 里 `{ resubscribe: true }` 重订阅原样保留
  - `loadTaskDetail` 的 `resubscribe` 参数语义与终态停流判断原样保留
  - `loadTaskDetailRef` 通过 `useEffect` 无依赖数组同步(防闭包过期)原样保留
  - 卸载时 `stopStream()` 清理 effect 原样保留
  - `handleCreateAndExecute` 中 execute 失败降级 warning + 乐观插入新任务原样保留
  - `handleIntervene` 用 `statusInfoOf(response.data.status, TASK_STATUS_MAP)` 取标签原样保留
- 渲染 JSX 按区块逐字搬入子组件,props 对齐 hook 返回契约;`canPause`/`canResume`/`canCancel` 派生值移入 `TaskInterveneActions` 内部由 `status` 推导
- 不做任何逻辑改动(本轮是纯拆分,非行为优化)

## 4. 实施步骤

### Task 1: 新增 `utils/agentTaskUtils.js`

- [x] 逐字搬运 `TERMINAL_STATUSES` + `eventColor` + `formatTime` + `formatPayload` + `normalizeHistoryEvent` + `normalizeStreamEvent` + `statusInfoOf`
- [x] 模块级导出,无 React 依赖(纯 ES 模块)

### Task 2: 新增 `hooks/useAgentTaskPanel.js`

- [x] 逐字搬运全部 useState/useRef/useCallback/useEffect(L91-283)
- [x] `TERMINAL_STATUSES` 从 utils import(不再本地定义)
- [x] import 调整:`agentTaskApi` / `agentTaskUtils`
- [x] 返回扁平对象暴露 state + setter + handlers + loadTasks

### Task 3: 新增 6 个子组件(`components/agentTask/`)

- [x] `TaskCreateForm.jsx` — 创建表单
- [x] `TaskListPanel.jsx` — 任务列表容器 + 空/错态
- [x] `AgentTaskItem.jsx` — 任务列表项
- [x] `TaskDetailPanel.jsx` — 详情容器(概要 + 子任务 + 产出)
- [x] `TaskInterveneActions.jsx` — 介入按钮组(暂停/恢复/终止)
- [x] `AgentLogStream.jsx` — 执行时间线
- [x] 无独立 CSS(沿用页面内联 style,与拆分前一致)

### Task 4: 重构 `pages/AgentTaskPanel.jsx` 为薄壳

- [x] 组合 useAgentTaskPanel + 子组件容器,保留标题 + 描述 + `Row/Col` 布局
- [x] 删除全部内联逻辑与纯函数,仅保留组合
- [x] 确认 `routes/index.jsx` lazy import 路径零改动

### Task 5: 新增 utils 单测

- [x] 新增 `utils/__tests__/agentTaskUtils.test.js` 覆盖纯函数各分支

### Task 6: 验证

- [x] 既有 `AgentTaskPanel.test.jsx`(12 用例)**零改动**通过
- [x] 新增 utils 单测通过
- [x] `npm test` 全量回归绿(与 baseline 对比)
- [x] `npm run lint` 通过
- [x] 代码检阅后补齐 6 个子组件 propTypes 契约(修复 code-reviewer 发现的 MEDIUM:40 个 react/prop-types warning)
- [x] `npm run build` 通过(generate-routes + vite build)

### Task 7: 文档更新 + PR + merge

- [x] round3 plan 标注 R3-D3 完成
- [x] feature 分支 push → PR → CI 监控 → merge → 清理(按 R3-D1/D2 先例)

## 5. 验收标准

| 标准 | 验证方式 |
|---|---|
| `AgentTaskPanel.jsx` ≤80 行薄壳 | `wc -l` |
| 各新文件 <800 行 / 函数 <50 行 | `wc -l` + 目检 |
| 既有 12 用例零改动通过 + 新增 utils 单测通过 | `npx jest pages/__tests__/AgentTaskPanel.test.jsx` + `npx jest utils/__tests__/agentTaskUtils.test.js` |
| 全量 jest / lint / build 三绿 | `npm test` + `npm run lint` + `npm run build` |
| `routes/index.jsx` lazy import 不变 | `git diff` |
| 行为逐字一致(SSE 去重 / 重连 / 终态停流 / 介入标签) | 差分验证 + 既有测试兜底 |

## 6. 风险评估与依赖

| 风险 | 缓解 |
|---|---|
| **高**:Hook 抽离引入闭包 / 依赖数组回归(SSE 编排 + loadTaskDetailRef 反模式是核心) | 逐字搬运 + 既有 12 用例覆盖 SSE 订阅/去重/卸载中断/介入全流程;`loadTaskDetailRef` 无依赖同步 effect 原样保留;依赖数组不精简 |
| **中**:子组件 props 传错(无 TypeScript) | 逐字搬运 + props 契约表 + jest 全量回归兜底 |
| **中**:`canPause/canResume/canCancel` 派生值从父级移入 `TaskInterveneActions` 内部导致时序差异 | 由 `status` prop 单向推导,纯函数无副作用;既有"终态按钮禁用"用例兜底 |
| **低**:子组件无独立 CSS,依赖页面内联 style | 逐字保留内联 style(拆分前即内联,不引 CSS 文件) |

## 7. 关联

- 上游:`docs/plans/2026-08-14_project-optimization-round3.md`(R3-D3)
- 同源:R3-D1(`docs/plans/2026-08-15_smart-chat-page-split.md`)、R3-D2(`docs/plans/2026-08-15_tool-result-split.md`),同款 utils/ + hooks/ + 子组件拆分 + 测试零 repoint 流程
- 技术文档:`docs/technical/32-smart-assistant-multi-agent.md`(前端模块表,可选更新)
