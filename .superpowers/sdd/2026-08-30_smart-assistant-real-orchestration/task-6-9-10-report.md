# 阶段 6、9、10 Fix Round 5 完整报告

## 改动文件与理由
- `omni_desk_frontend/src/features/smart-assistant/hooks/useAgentTaskStream.js`：SSE/fallback `onDone` 显式处理 `paused`，设置手动暂停语义并阻止误落 `completed`。
- `omni_desk_frontend/src/features/smart-assistant/api/agentTaskApi.js`：done 帧 sequence 使用 `Math.max` 推进本地序号，保证服务端倒退时本地 `lastSeq` 单调。
- `omni_desk_frontend/src/features/smart-assistant/scenario/components/ToolCallCard.jsx`：对字符串值中的邮箱、手机号、15/18 位身份证号脱敏；扩充 API/access/private/session 等敏感 key 过滤；导出纯 helper 供测试验证。
- `omni_desk_frontend/src/features/smart-assistant/api/__tests__/agentTaskApi.test.js`：新增 done sequence 倒退测试。
- `omni_desk_frontend/src/features/smart-assistant/hooks/useAgentTaskStream.test.js`：新增 paused done 不误判 completed 测试。
- `omni_desk_frontend/src/features/smart-assistant/scenario/utils/__tests__/ToolCallCard.test.jsx`：新增 PII 与敏感 key 渲染安全测试。
- `omni_desk_frontend/src/features/smart-assistant/scenario/utils/__tests__/mapAgentEvent.test.js`：新增顶层字段优先及 payload fallback 测试。
- `omni_desk_backend/smart_assistant/tests/test_agent_task_stream.py`：新增 stream/timeline 跨用户 404、负数/超大 `last_seq` 边界，以及嵌套 PII/sensitive key sanitizer 真实测试。

## 验证
- `pytest omni_desk_backend/smart_assistant/tests/test_agent_task_stream.py omni_desk_backend/smart_assistant/tests/test_tasks.py --ds=omni_desk_backend.settings.test -q --no-cov -p no:randomly`：17 passed。
- `cd omni_desk_frontend && npm test -- --runTestsByPath ... --coverage=false`：4 suites passed，40 tests passed。
- 显式 ESLint（全部本轮修改前端文件）：0 errors，6 个既有 `react/prop-types` warnings。
- `git diff --check`：通过。
- 未运行 `npm run build`，避免 prebuild 无关改写 `public/routes.json`；本轮不涉及路由。

## Concerns
- ESLint warnings 仅来自既有 JSX props validation 规则，未引入 error。
- 未修改后端生产代码；后端现有 sanitizer/用户隔离/last_seq 实现由新增真实测试覆盖。

## Breaker 兼容性修复（后续独立任务）
- `ToolCallCard.jsx` 移除全部 JavaScript lookbehind/lookahead，改用 IE11 可解析的数字 token 扫描与长度/字符边界判断；仅脱敏独立的 11 位手机号、15/18 位身份证号，不误伤更长数字串。
- `agentTaskApi.test.js` 移除模块级 `ReadableStream` shim；每个测试保存并恢复原值，新增真实将 `globalThis.ReadableStream` 设为 `undefined` 且响应 body 仍提供 `getReader` 的 timeline fallback 测试。
- 验证：聚焦 Jest 2 suites / 24 tests 通过；显式 ESLint 0 errors（6 个既有 `react/prop-types` warnings）；`git diff --check` 通过；目标文件 grep 未发现 lookbehind/lookahead。
