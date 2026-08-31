# Task 13 修复报告

## 状态
已完成问题 A、问题 B 的 scoped review 修复，尚未提交前的工作区仅包含本轮目标代码/测试与本报告（另有既有 task-11 报告改动未纳入本次提交）。

## 根因调查
- `AgentLogSerializer` 的 `user_query` 使用 ModelSerializer 默认字段，直接返回模型中的原文；同一 serializer 已有 `sanitize_public_text` canonical helper 可复用。
- `chat_stream._consume_stream_events` 对完整 SSE data 调用 `safe_public_value(data)`；全局 sanitizer 将 `content` 定义为敏感键，因此正常 chunk 与固定失败 chunk 的 `content` 被删除。全局 sanitizer 不能放宽，否则会扩大其他公开出口的暴露面。
- SSE 事件由 `sse_event` 统一添加 `format_version`，因此新边界处理必须保留既有 envelope 字段契约，同时拒绝未知异常字段。

## TDD 过程
1. 先新增 `test_user_query_is_publicly_redacted`，以及三个 SSE sanitizer 回归测试。
2. 首次运行 targeted pytest 得到预期 RED：日志测试返回完整 `user_query` 原文；SSE 测试因 `_sanitize_stream_event` 尚不存在而 ImportError。
3. 以最小生产改动进入 GREEN，并重新运行 targeted 测试通过。

## 本轮修复
### 问题 A
- `omni_desk_backend/smart_assistant/serializers.py`
  - 将 `AgentLogSerializer.user_query` 改为 `SerializerMethodField`。
  - `get_user_query` 复用 `sanitize_public_text`，覆盖邮箱、手机号、token/authorization、JSON 与普通敏感文本脱敏。
  - 未改变字段白名单或其他安全元数据字段契约。
- `omni_desk_backend/smart_assistant/tests/test_agent_log_serializer.py`
  - 直接构造包含邮箱、手机号、token、authorization JSON 的 `AgentLog`，断言输出不含原文/敏感值且保留普通文本。

### 问题 B
- `omni_desk_backend/smart_assistant/views/chat_stream.py`
  - 新增 `_sanitize_stream_event`：按 `chunk`、`meta`、`done`、`confirmation` 建立明确字段 allowlist。
  - `chunk.content` 与 confirmation answer 作为用户可见文本字段，单独调用 `sanitize_public_text`，不经过会删除 `content` 的全局 envelope sanitizer。
  - 结构化字段继续使用 `safe_public_value`；`format_version` 保留；异常、`exception`、原始 `message` 等未知字段不进入客户端结果。
  - 未放宽全局 sanitizer，未透传原始异常，也未修改 `stream_runner` 的固定安全错误文案/重复拼接逻辑。
- `omni_desk_backend/smart_assistant/tests/test_stream_runner.py`
  - 覆盖普通 chunk content 保留并脱敏、固定失败前缀保留、含 token/URL 的异常字段不出现在客户端 envelope。

## 验证
- TDD RED：新增测试首次运行失败，失败原因与两个根因一致。
- targeted：`52 passed`（`--no-cov`，覆盖 serializer、stream runner、chat stream、stream failure、orchestrator、mock LLM 相关测试）。
- `git diff --check`：通过。
- 智能助手测试全集：基线中仍有既有失败（涉及确认草稿/工具结果等其他近期安全契约），未发现属于本轮 serializer 或 SSE envelope 改动的 targeted 回归；本轮不排除或修改这些无关失败。
- 测试运行产生的 SECRET_KEY 随机值 warning 为测试 settings 的既有行为。

## 提交
待提交：使用中文 conventional commit，说明 AgentLog 查询脱敏与 SSE 公开 envelope 修复。

## 遗留项
- 全量智能助手测试中仍有与本轮无关的既有契约失败，主要集中在其他确认重放/工具结果公开摘要测试；需由对应后续 scoped review 单独处理。
- 无已知与本轮改动相关的遗留疑问。

## 变更边界
未修改 `VERSION`、任何 `CHANGELOG`、用户 spec；未修改全局 sanitizer。
