# 智能助手功能增强计划

> 日期：2026-07-28 ｜ 分支：`feat/smart-assistant-enhancement` ｜ 基线版本：v0.7.0-rc.1

## 背景与目标

2026-07-28 对智能助手做了可用性实测与代码调研，结论：

- **主链路完整**（对话 + SSE + 意图分类 + 13 业务工具 + RAG + 会话 + 配置 + 统计审计，721 个后端测试），
- **当前部署不可用**：离线 RC 栈无 RAGFlow 容器、`LlmEndpoint` 表为空、兜底 Ollama 不存在，对话返回"所有 LLM 端点均不可用"；
- **若干半成品/死链路**：聚合卡片前端渲染断链（功能实际失效）、反馈/成本/滚动摘要"有字段无链路"、多 Agent 框架无前端；
- 参考 `/home/fz/project/claw-code`（Claude Code 的 Rust 重写）的设计模式（doctor 自检、输出契约、Hooks 审计、分层权限、会话压缩、主动式循环）制定增强方案。

**目标**：恢复可用性 → 补齐半成品闭环 → 架构增强 → 主动式助手演进，四个阶段全部落地并通过测试。

## 涉及的文件与模块

| 模块 | 涉及文件 |
|---|---|
| 后端对话核心 | `smart_assistant/views/chat.py`、`agent/conversation_context.py`、`agent/orchestrator.py` |
| 后端配置/日志/知识库 | `smart_assistant/views/logs.py`、`views/knowledge_base.py`、`views/stats.py`、`urls.py` |
| 多 Agent | `smart_assistant/agents/`、`views/tasks.py`、`hooks/builtin/` |
| LLM 接入层 | `llm_service/router.py`、`llm_service/ollama_client.py`、`office_assistant/views.py` |
| RAG | `ragflow_service/models.py`（api_key 加密迁移） |
| 前端 | `features/smart-assistant/`（SmartChatPage、ToolResult、api）、新增多 Agent 面板组件、`routes/index.jsx` |
| 部署 | `deployment/docker/docker-compose.offline.yml`、`deploy_offline.sh`、LLM 端点种子脚本 |
| 文档 | `docs/technical/16-smart-assistant.md` |

## 技术方案要点

1. **LLM 失败不落库**：`chat.py` 中 LLM 调用失败（answer 以错误前缀开头或 `tool_fallback` 失败标记）时，不写入 `session.messages`，避免污染多轮上下文。
2. **成本核算**：写 `AgentLog` 时按 `LlmEndpoint.cost_per_1k_tokens × usage tokens` 计算 `estimated_cost`（router 返回 usage 与命中的 endpoint）。
3. **滚动摘要**：会话保存路径调用 `should_summarize()`，超阈值时生成摘要写入 `Session.summary_text`；`conversation_context` 构造历史时摘要优先于早期消息。
4. **反馈闭环**：`AgentLogViewSet` 增加 `feedback` @action（PATCH `user_feedback`），前端赞踩接入。
5. **数据集 CRUD**：新增 `KnowledgeDatasetViewSet`（router 注册），替换仅 Django admin 可建的现状。
6. **office_assistant 统一路由**：改经 `LLMRouter`（app_name="office_assistant"），消除直连 Ollama 裂缝；统一三处 Ollama 默认模型为 `qwen2.5:7b`；删除死代码 `openai_client.py`；`RagflowConfig.api_key` 改 `EncryptedCharField` + 数据迁移。
7. **doctor 自检**：`GET /api/smart-assistant/doctor/` 逐项探测 LLM 端点（连通+模型列表）、RAGFlow（连通+数据集）、缓存/限流配置，返回 `{checks: [{name, status, kind, message, hint}]}` 结构化报告。
8. **输出契约**：SSE 事件增加 `format_version: 1`；错误响应统一 `{kind, message, hint}`，`kind` 枚举：`no_llm_endpoint` / `llm_unavailable` / `ragflow_unavailable` / `rate_limited` / `internal_error`。
9. **Hooks 补全**：`hooks/builtin/` 新增 `PiiMaskingHook`（pre-tool 输出脱敏手机号/身份证）、`TimeoutGuardHook`（工具执行超时熔断）。
10. **工具权限分级**：`tools/base.py` 工具元数据增加 `risk_level`（read/write/destructive），orchestrator 对 write+ 记录显式审计，destructive 预留二次确认协议字段。
11. **Mock LLM 等价测试**：`smart_assistant/tests/mock_llm_server.py`（线程内 HTTP server，确定性 `/v1/chat/completions`）+ SSE 全链路 e2e 测试，CI 不依赖真实 LLM。
12. **多 Agent 前端面板**：新增 `/smart-assistant/tasks` 路由 + `AgentTaskPanel`（SSE timeline 订阅 `/api/smart-assistant/tasks/{id}/stream/`、介入表单）。
13. **每日晨报**：Celery beat 任务 `generate_daily_digest`（每工作日 8:30）→ 复用聚合工具链生成简报 → 写 `notifications` 通知中心。
14. **会话 fork/导出**：`SessionViewSet` 增加 `fork` / `export`（Markdown）@action，前端会话菜单接入。
15. **Dify 决策**：维持 iframe 浅集成（YAGNI + 内网离线部署成本），在技术文档记录决策理由，不做服务端 API 集成。

## 实施步骤

### P0 — 恢复可用

- [x] 步骤 1：LLM 失败响应不落库 session.messages（`views/chat.py`，同步 + 流式两条路径）
- [x] 步骤 2：修复聚合卡片渲染断链（前端 `ToolResult.jsx` 对齐后端扁平 `tool_result` 结构）
- [x] 步骤 3：离线 compose 补入 RAGFlow 服务；`deploy_offline.sh` 增加默认 LLM 端点种子（management command `seed_llm_endpoint`）

### P1 — 补齐半成品

- [x] 步骤 4：成本核算写入 `AgentLog.estimated_cost`
- [x] 步骤 5：启用滚动摘要（`conversation_context.py` + 会话保存路径）
- [x] 步骤 6：反馈 API（`agent-logs/{id}/feedback/`）+ 前端赞踩接入
- [x] 步骤 7：知识库数据集 CRUD API（`KnowledgeDatasetViewSet`）
- [x] 步骤 8：office_assistant 统一 LLMRouter + Ollama 默认模型统一 + 删 `openai_client.py` + `RagflowConfig.api_key` 加密迁移

### P2 — 架构增强（借鉴 claw-code）

- [x] 步骤 9：`/api/smart-assistant/doctor/` 自检端点
- [x] 步骤 10：输出契约（SSE `format_version` + 错误 `kind` 结构化）+ 前端按 kind 提示
- [x] 步骤 11：PII 脱敏 hook + 超时熔断 hook
- [x] 步骤 12：工具权限分级（`risk_level` 元数据 + 审计）
- [x] 步骤 13：Mock LLM 等价测试（确定性 e2e，不依赖真实 LLM）

### P3 — 主动式演进

- [x] 步骤 14：多 Agent 前端面板（`/smart-assistant/tasks` + SSE timeline + 介入 UI）
- [x] 步骤 15：每日晨报 Celery beat + notifications 推送
- [x] 步骤 16：会话 fork / Markdown 导出

### 收尾

- [x] 步骤 17：全量 pytest 1912 passed（+279）+ 前端 jest 489 passed（+53）/ lint 通过，覆盖率 90.16%
- [x] 步骤 18：code-reviewer 评审，修复 CRITICAL 1 + HIGH 5 + MEDIUM 2（M3-M10 留后续 fix 分支）
- [x] 步骤 19：更新 `docs/technical/16-smart-assistant.md`（全面重写 §1-10）+ README 同步

## 风险评估与依赖

| 风险 | 缓解 |
|---|---|
| 多 agent 并行改同一文件冲突 | 按文件域切分 agent；轮次间串行 + 全量测试把关 |
| 覆盖率门槛 80% 被新代码拉低 | 每个 agent 必须为新代码写测试 |
| 加密字段迁移影响已有 Ragflow 配置 | 数据迁移双向可逆（RunPython + reverse） |
| Celery beat 在离线部署的时区 | beat schedule 显式 `crontab(hour=8, minute=30)` + `CELERY_TIMEZONE` 已为 Asia/Shanghai |
| Dify 深集成诉求 | 明确 YAGNI，文档记录决策，后续按需启动 |

## 不在范围内

- ❌ 真实 LLM/RAGFlow 的端到端线上验证（本机无 GPU/镜像，以 mock 测试 + 接口实测为准）
- ❌ 自动推送镜像 / 打 tag（交由发布流程）
- ❌ Dify 服务端 API 集成（见决策 15）
