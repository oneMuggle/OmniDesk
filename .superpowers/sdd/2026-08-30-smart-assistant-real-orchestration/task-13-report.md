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

## Continuation（39403641 之后）

### 根因与修复
- 管理探针旧测试 patch 了已移除的 `views.llm_config.socket`，并假设请求调用点为 `http_requests.get`；测试已迁移到共享 SSRF resolver seam，生产代码不再保留测试特判。
- `safe_request` 新增显式 `requester` 与 `resolver` 参数；默认仍使用真实 `requests` transport、真实 DNS 预检和 `allow_redirects=False`。resolver 注入时仍校验其返回的每个地址；测试 resolver 仅解析安全 hostname，受控 requester 再将其映射至本地 mock 服务，绝不放行字面 loopback。
- `LLMRouter` 接受可选 requester/resolver，并将其用于数据库 endpoint 的 `generate`/`generate_with_tools`；固定 Ollama fallback 继续使用原有本地请求路径。旧成本测试改 patch 共享 `safe_request`，Ollama 专属测试仍 patch `requests.post`。

### TDD / 验证记录
- RED（复现）：39403641 后定向运行得到管理探针 collection error、4 个 router tool-call SSRF 拒绝及 mock LLM E2E/native E2E 失败；另确认旧成本测试 patch `requests.post` 已无法观察 DB endpoint 请求。
- GREEN：共享 transport/resolver 契约与测试 seam 完成后，定向 SSRF/配置/router/E2E 测试 **41 passed**，退出码 0；`core/tests/test_backup_db.py` **9 passed**，退出码 0。
- 后端全量第一次复测：**3157 passed、4 failed、2 xfailed、11 xpassed、42 warnings**，4 项均为旧成本测试 seam，退出码 1；迁移成本测试后定向成本测试 **7 passed**。
- 后端全量最终复测：**3161 passed、2 xfailed、11 xpassed、42 warnings**，退出码 **0**。
