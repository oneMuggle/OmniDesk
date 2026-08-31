# 阶段 13：RAGFlow 正式调用链安全收口报告

**日期**：2026-08-31
**分支**：`feat/smart-assistant-real-orchestration`

## 完成内容

- `RagflowClient` 的每次请求统一经过 `smart_assistant.ssrf.safe_request`，保留 Session 复用、现有 API 路径和返回契约；请求禁止重定向，并支持测试显式注入 requester/resolver。
- RAGFlow 客户端统一将端点、HTTP、网络、响应解析异常转换为稳定 code 与固定中文安全消息；日志只记录异常类型及 HTTP status，不记录 body、URL 或密钥。
- `health_check`、Ragflow 配置 views、RAG router 的错误路径均改为固定安全文案；文档 embedding 失败仅持久化固定文案，不持久化原始异常。
- 补充/扩展客户端安全测试，覆盖合法调用、受限 literal、多 DNS 地址任一受限、禁止重定向、HTTP body/密钥脱敏、连接异常、JSON 异常及 health HTTP 调用链。

## 验证结果

- RED：初始新增 health 调用链测试与现有未注入 resolver 的 Session 测试暴露 DNS 校验失败；随后按生产 SSRF 规则修正测试注入，未放宽生产规则。
- targeted：`ragflow_service/tests/test_client_session.py`、`ragflow_service/tests/test_ragflow_views.py`、`smart_assistant/tests/test_rag_router_coverage.py`、`smart_assistant/tests/test_e2e_rag_tool.py`，**50 passed**（`--no-cov`）。
- 后端全量：**失败**，`3169 passed, 2 xfailed, 11 xpassed, 1 failed`；唯一失败为既有 `smart_assistant/tests/test_parallel_tool_execution.py::TestParallelToolExecution::test_mixed_deps_only_independent_parallel`，非 Ragflow 变更路径。
- `git diff --check`：通过。

## 遗留限制

- 全量测试存在并行工具执行计时/调度相关失败，不能宣称后端全量通过；需另行调查。
- 未执行真实外部 RAGFlow、Celery worker 或生产数据库现场验收；测试使用显式 requester/resolver。
