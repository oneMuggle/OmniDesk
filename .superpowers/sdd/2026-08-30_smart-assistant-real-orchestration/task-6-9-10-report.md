# 阶段 6、9、10 完成报告

## 改动文件与理由
- `omni_desk_frontend/src/features/smart-assistant/api/agentTaskApi.js`：完善 SSE `last_seq`、sequence 去重与 done sequence；在 AbortController/ReadableStream 缺失时使用 2 秒 timeline 轮询，支持终态、超时及 abort 清理。
- `omni_desk_frontend/src/features/smart-assistant/hooks/useAgentTaskStream.js`：沿用真实任务 hook 的状态、重连、暂停/恢复/取消/重试接缝。
- `omni_desk_frontend/src/features/smart-assistant/scenario/utils/mapAgentEvent.js`：未知事件安全映射为 thinking，保留 eventType 和 sequence；错误事件继续映射为 error。
- `omni_desk_frontend/src/features/smart-assistant/scenario/components/ScenarioCollabCard.jsx`：消费真实 stream，覆盖状态标签，动作改为取消/重试，保留 partial 事件产出。
- `omni_desk_frontend/src/features/smart-assistant/scenario/components/AgentCollabStream.jsx`、`ErrorCard.jsx`：独立展示任务/子任务错误，避免渲染原始 payload。
- `omni_desk_frontend/src/features/smart-assistant/scenario/components/FinalAnswerCard.jsx`：支持 failed/partial，未知 payload 不再原样 JSON 输出。
- `omni_desk_frontend/src/features/smart-assistant/scenario/data/scenarios.js`：精简为入口元数据。
- 删除 `scenario/hooks/useScenarioPlayer.js`：移除旧 timer 播放器。
- `scenario/utils/__tests__/mapAgentEvent.test.js`、`api/__tests__/agentTaskApi.test.js`：同步未知事件及异步 fallback 契约测试。

## 测试
- `npm test -- --runInBand=false src/features/smart-assistant/api/__tests__/agentTaskApi.test.js src/features/smart-assistant/hooks/useAgentTaskStream.test.js src/features/smart-assistant/scenario/utils/__tests__/mapAgentEvent.test.js`
  - 3 suites passed，34 tests passed。
- `npx eslint src/features/smart-assistant --ext .js,.jsx`
  - 仓库既有 ESLint errors（测试 DOM 查询、AgentAuditPanel effect、动态 icon 组件等）；修改文件单独检查无 error，仅既有 prop-types warnings。

## Concerns
- 后端 SSE view 未在本阶段修改，需等待前序后端变更合并后运行对应后端测试确认 payload 白名单、用户隔离和 last_seq 契约。
- 未运行 frontend build，以避免 prebuild 改写 `public/routes.json`；建议集成分支单独执行并审查生成文件。
