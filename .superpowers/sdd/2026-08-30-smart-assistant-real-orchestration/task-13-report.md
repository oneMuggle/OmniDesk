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

### Continuation（本轮网络出口收口）

#### 根因与修复
- `LLMRouter.generate` 的固定 Ollama fallback 改为 `safe_internal_request`，仅接受代码固定的 `http://localhost:11434`，并显式 `allow_redirects=False`；数据库端点继续使用 SSRF-safe `safe_request`。
- doctor 的 LLM/Ollama/Ragflow 探测改走 `safe_request`，仅返回固定安全状态（HTTP 状态码或固定错误类别），不回显 URL、上游正文、密钥或异常文本；native tool-call 与 checker 兜底也移除异常正文。
- 旧 `OllamaClient` 保留原 API 与生产调用者，POST/GET 统一委托 `safe_request`，支持显式 requester/resolver 测试 seam，错误契约改为安全固定消息。
- `safe_request` 在交给 requests 前始终再次执行 DNS 校验，测试覆盖 rebinding 第二次解析命中受限地址；该设计缩小 TOCTOU 窗口但 requests 未做 socket IP pinning，仍存在理论竞态限制。

#### TDD / 验证记录
- RED：新增 rebinding 测试先失败（未发生第二次 DNS 校验，退出码 **1**）；随后旧 Ollama mock 测试暴露需要显式 resolver/requester seam，退出码 **1**。
- GREEN：`pytest -q smart_assistant/tests/test_ssrf_safe_transport_new.py llm_service/test_router.py llm_service/test_ollama_client.py smart_assistant/tests/test_doctor.py --no-cov`，**49 passed**，退出码 **0**。
- 后端全量：`pytest -q --no-cov`，**3160 passed、1 failed、2 skipped、2 xfailed、11 xpassed、42 warnings**，退出码 **1**；唯一失败为既有 `core/tests/test_backup_db.py::test_verify_metadata_is_atomic_write` 的 `os.replace` 原子写测试，与本轮 LLM 网络出口改动无关。

#### 遗留项
- `safe_request` 基于 requests 的 DNS preflight 仍不能做到内核级 IP pinning；生产环境需配合网络出口策略/egress allowlist，不能把 resolver 注入当作安全绕过。
- 全量测试仍有上述既有 core 原子写失败，因此不能声称后端全量通过。

### Continuation（审查后修复 Ollama fallback）

- RED：安全审查新增的 native tool-call Ollama fallback 测试失败，实际仍调用通用 `safe_request`，退出码 **1**；旧客户端测试也暴露测试 seam 对 GET/POST 的区分问题。
- GREEN：`generate_with_tools` 的 Ollama 候选显式传递 `is_ollama` 并使用 `safe_internal_request`；旧 `OllamaClient` 仅对代码固定默认地址使用 internal transport，配置/环境地址继续完整 SSRF 校验。定向 `llm_service/test_router.py llm_service/test_ollama_client.py`：**21 passed**，退出码 **0**。
- 安全审查结论：无 CRITICAL；此前发现的两个 HIGH（旧客户端默认 localhost 被拒、native tool-call fallback 被拒）已修复。仍保留 requests DNS/IP pinning 的理论 TOCTOU 限制。

## 最终审查项修复（2026-08-31）

- Ragflow views 与文档 embedding 日志移除异常链，仅记录异常类型及稳定错误 code；删除 `tasks.py` 中未使用的 `Notification` 导入。
- `_public_items` 对允许字段执行文本 sanitizer，仅接受字符串、数字、布尔值或 null，拒绝嵌套对象；补充 chats 的 secret URL/path/nested 字段测试。
- 定向测试：**55 passed**（`--no-cov`）。
- `git diff --check`：通过。
- task-11-report.md 保持原有未提交修改，未修改 VERSION/CHANGELOG。

## 最终复审修复（2026-08-31）

- Ragflow multipart 请求不再继承 JSON `Content-Type`；非文件请求显式设置 JSON，文件请求交由 requests 生成 multipart boundary。
- query 忽略客户端传入的 `conversation_id`，避免跨用户会话复用；仍保留上游返回的新会话 ID。
- 普通认证用户使用安全只读 Ragflow 配置 serializer，管理员保留完整配置能力；`api_key` 始终 write-only。
- `_public_items` 继续执行安全文本/标量过滤；新增 secret URL/path/nested 测试。
- 删除 RAG router 测试中未使用的 `pytest` 导入。
- Ragflow targeted：**55 passed**（`--no-cov`）。
