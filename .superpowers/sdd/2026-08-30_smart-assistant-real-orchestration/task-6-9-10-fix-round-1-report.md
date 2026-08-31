# Fix round 1 补充报告

- 恢复 `scenarios.js` 的 `listScenarios` 与 `matchScenarioByInput` 兼容导出，修复 QuickCommands/useSmartChat 运行时回归。
- `tasks.py` 的 stream/timeline 输出改为安全字段白名单，保留 task/subtask 状态与事件序列字段，避免原始内部 payload 外发；对象查询继续按当前用户隔离。
- `agentTaskApi.js` 保留 IE11 timeline fallback 与 abort/sequence 语义；无 AbortController 时直接进入轮询。
- `useAgentTaskStream.js` retry 明确为重跑：清空事件并重置 lastSeq；pause/resume 立即进入 pausing/resuming，失败恢复状态并保留 error。
- `ToolCallCard.jsx` 增加敏感 key、字段数量和长度限制，避免原样展示工具参数/结果。

测试与 concerns：fix round 修改后需执行 focused Jest、后端 smart_assistant pytest 与显式 ESLint；后端既有测试若依赖完整 serializer 字段，需按新安全契约更新断言。
