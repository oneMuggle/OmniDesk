# Fix round 4 补充报告

- 后端 sanitizer 对 content/result 递归字符串执行邮箱、手机号、身份证号脱敏，并规范化过滤 api_key、access_token、private_key、session 等敏感 key，同时保留深度、容器和长度限制。
- `mapAgentEvent` 保留顶层/payload 的 task_id、subtask_id、status；ToolCallCard 保持安全结构化渲染。
- retry 明确为“重新查看/重新订阅”，保留历史与 lastSeq，不再清空事件伪装重跑。
- agentTaskApi 在 `getReader` 前检查 TextDecoder、ReadableStream、body.getReader 和 AbortController；无 sequence 事件不推进 sequence；坏 JSON 触发 onError。

验证：前端 focused Jest 5 suites / 45 tests 通过；`py_compile`、`git diff --check` 通过。显式 ESLint 修改文件无 error，仅既有 prop-types warnings。

Concerns：后端专项 pytest 仍受仓库全局 coverage fail-under 80% 阻断；跨用户和真实嵌套 payload 测试需协调分支补齐。
