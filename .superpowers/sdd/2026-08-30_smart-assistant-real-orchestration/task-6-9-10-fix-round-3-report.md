# Fix round 3 补充报告

- `mapAgentEvent` 按存在性保留 `status`、`subtask_id`、`task_id`，支持顶层及 payload 回退。
- 后端事件 payload 使用递归 sanitizer，限制深度、字段数、数组数、字符串长度，并过滤 token/password/secret/api_key/access_token/authorization/prompt/args/private_key/session 等敏感字段；保留安全 result/content。
- `ToolCallCard` 扩展 api key/access key/private key/session 等敏感 key 过滤。
- `agentTaskApi` 保持能力检查、2 秒 fallback、sequence 去重和坏 JSON 错误回调。

验证：前端 focused Jest 5 suites / 45 tests 全部通过；后端 `py_compile` 通过；`git diff --check` 通过。显式 ESLint 修改文件无 error，仅 prop-types warnings。

Concerns：后端专项 pytest 的整体 coverage 仍受仓库 fail-under 80%（约 49%）阻断；跨用户/嵌套 payload 专项断言需协调分支继续补充。
