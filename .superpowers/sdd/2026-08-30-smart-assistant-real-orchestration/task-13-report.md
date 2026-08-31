# Task 13 报告：LLM 端点 SSRF 安全收紧

## 完成内容
- 新增 `smart_assistant/ssrf.py`，统一协议、userinfo、端口、DNS 全地址及受限地址校验，并强制关闭重定向。
- `fetch_models` / `test_endpoint` 统一返回固定安全中文错误，不回显上游正文、异常文本、URL 或密钥。
- `LlmEndpointCreateSerializer` 复用运行时 URL 校验规则。
- `LLMRouter.generate` 与 `generate_with_tools` 的数据库端点改用安全 transport；本地 Ollama 兜底保持原有路径。

## 测试记录
- RED：新增 SSRF 测试首次收集失败，因共享模块尚不存在（退出码 2）。
- GREEN：`pytest -q smart_assistant/tests/test_ssrf_safe_transport_new.py --no-cov`，3 passed，退出码 0。
- targeted：相关配置、router、transport 测试 31 passed，退出码 0。
- 后端全量：3142 passed、2 skipped、2 xfailed、11 xpassed、17 failed，退出码 1；失败主要来自既有测试对 loopback mock 端点及旧 requests.post mock 的假设，另有 1 个 core 原子写测试失败。

## 遗留项
- 真实 loopback 配置端点按 SSRF 策略拒绝；现有 mock TCP E2E 仍需改为受控测试 transport/allowlist 后才能通过。
