# 智能助手系统

> 类似贾维斯的智能助手,通过聊天快速获取信息、知识库问答、文献搜索。
>
> 📅 **最近更新:2026-06-06** — 模块结构、覆盖率和开发状态已与代码同步;覆盖率补齐计划见 [28-smart-assistant-coverage-roadmap.md](./28-smart-assistant-coverage-roadmap.md)

## 1. 架构概览

```
用户提问 → 意图分类(Ollama) → 工具路由 → 结果生成 → 返回答案
                                │
                    ┌───────────┼───────────────┐
                    ▼           ▼               ▼
               ScheduleTool  PersonnelTool    RAGTool
               (排班查询)     (人员查询)      (知识库/Ragflow)
```

### 1.1 当前真实模块结构(2026-06-06 实测)

| 类别 | 模块 | 文件 | 说明 |
|------|------|------|------|
| **Agent(7)** | 意图分类 | `agent/intent_classifier.py` | Ollama 本地 LLM 识别用户意图 |
| | 编排器 | `agent/orchestrator.py` | 分类→路由→生成(支持单/多工具链) |
| | Prompt 构建 | `agent/prompt_builder.py` | 系统 prompt + 工具链 prompt |
| | 对话上下文 | `agent/conversation_context.py` | 多轮历史 + 滚动摘要 |
| | RAG 路由 | `agent/rag_router.py` | 多数据集关键词匹配 + 并行搜索 |
| | 工具链规划 | `agent/tool_chain_planner.py` | LLM 生成多工具执行计划 |
| | 工具链执行 | `agent/tool_chain_executor.py` | 按依赖顺序执行,支持 `$variable` 替换 |
| **工具(12)** | 见 §2.1 | `tools/*.py` | 单例注册中心 `tools/registry.py` |
| **视图(6)** | 聊天 | `views/chat.py` | 非流式 + SSE 流式两路 |
| | 知识库 | `views/knowledge_base.py` | 文档上传/列表/删除/状态 |
| | LLM 配置 | `views/llm_config.py` | 端点/激活/健康检查 |
| | 会话 | `views/sessions.py` | 会话 CRUD |
| | 日志 | `views/logs.py` | 审计日志 API |
| | 统计 | `views/stats.py` | 用量/意图分布聚合 |
| **中间件(1)** | 限流 | `middleware/rate_limit.py` | 30 req/min/user,SSE 接口限流 |
| **缓存** | 3 级 | `cache.py` | 意图(1h)/工具(30min)/回答(2h) |
| **Celery** | 文档向量化 | `tasks.py` | 上传→Ragflow 解析→状态流转 |

### 1.2 核心数据流

1. **非流式路径**:`POST /api/smart-assistant/chat/` → 解析 → 查缓存 → 意图分类 → 工具链规划 → 工具执行 → LLM 生成回答 → 写入 AgentLog
2. **流式路径**:`POST /api/smart-assistant/chat/stream/` → 同上但 LLM 调用改为 `generate_answer_stream` → 逐 chunk 通过 SSE 推送(meta → chunks → done)

## 2. 后端实现

### 2.1 数据模型

| 模型 | 关键字段 | 说明 |
|------|----------|------|
| `AgentLog` | user, query, response, tool_used, tool_output, intent | 助手调用日志(扩展字段见 [17-ai-assistant-deep-design §6](./17-ai-assistant-deep-design.md)) |
| `SmartAssistantSession` | user, conversation_id, messages(JSON), summary_text, turn_count | 对话会话(已支持多轮压缩) |
| `KnowledgeBaseDocument` | title, file, status, vectorized_at | 知识库文档 |
| `KnowledgeDataset` | name, ragflow_dataset_id, tags, is_active | 多数据集 RAG 路由 |
| `LlmEndpoint` / `LlmAppConfig` | name, priority, is_fallback, model_capabilities | 多 LLM 端点配置 |

### 2.2 工具系统(12 个)

| 工具 | 功能 | 数据源 |
|------|------|--------|
| `ScheduleTool` | 排班/值班查询 | `events.Schedule` |
| `PersonnelTool` | 人员信息查询 | `personnel.Personnel` |
| `RAGTool` | 知识库问答 | Ragflow 向量数据库 |
| `DocumentTool` | 公文/文档搜索 | `documents` 模块 |
| `EventTool` | 事件/日程/节假日查询 | `events` 模块 |
| `MemoTool` | 备忘录查询 | `memos.Memo` |
| `ProjectTool` | 项目进度查询 | `projects.Project` |
| `NewsTool` | 新闻/通知搜索 | `news.NewsArticle` |
| `MeetingRoomTool` | 会议室可用性 | `meeting_rooms` |
| `SensorTool` | 传感器数据/告警 | `sensor_management` |
| `AnnouncementTool` | 公告查询(规划中) | `communication.Announcement` |
| `ComplianceTool` | 合规检查(规划中) | `compliance.InspectionRecord` |
| `ExternalLinkTool` | 外部链接/书签(规划中) | `external-links.Bookmark` |

> ⚠️ 最后 3 个工具(Announcement/Compliance/ExternalLink)为本次优化方案 P1 阶段计划新增,详见 [优化方案 §维度 2](../plans/2026-06-06_smart-assistant-optimization.md)。

### 2.3 API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/smart-assistant/chat/` | POST | 发送聊天消息(非流式) |
| `/api/smart-assistant/chat/stream/` | POST | 流式响应(SSE) |
| `/api/smart-assistant/sessions/` | GET/POST | 会话列表/创建 |
| `/api/smart-assistant/sessions/<id>/` | GET/DELETE | 会话详情/删除 |
| `/api/smart-assistant/knowledge-base/` | GET/POST | 知识库文档管理 |
| `/api/smart-assistant/logs/` | GET | 审计日志列表 |
| `/api/smart-assistant/logs/<id>/` | GET | 审计日志详情 |
| `/api/smart-assistant/llm-config/` | GET/POST | LLM 端点配置 |
| `/api/smart-assistant/stats/` | GET | 用量/意图分布聚合 |
| `/api/smart-assistant/usage/{stats,daily,user}/` | GET | 用量分析(详见 [17-ai-assistant-deep-design §6.2](./17-ai-assistant-deep-design.md)) |

## 3. 前端实现

| 组件 | 路径 | 说明 |
|------|------|------|
| `SmartChatPage` | `/smart-assistant` | 聊天主界面(400 行,流式打字) |
| `KnowledgeBasePage` | `/knowledge-base` | 知识库管理 |
| `AgentAuditPanel` | `/smart-assistant/audit` | 管理员审计面板(图表+过滤) |
| `StatsPage` | `/smart-assistant/stats` | 用量统计页 |
| `ToolResult` | 共享组件 | 工具结果渲染(排班/人员/知识来源等) |
| `MessageMarkdown` | 共享组件 | Markdown 渲染(`react-markdown` + remark-gfm) |
| `MessageActions` | 共享组件 | 点赞/点踩/复制/重试 |
| `QuickCommands` | 共享组件 | 快捷指令面板 |
| `DocumentPreview` | 共享组件 | 文档预览(上传/下载) |

### 3.1 流式响应

- 后端:`StreamingHttpResponse` 按 chunk 推送,首帧先发 `meta`(工具意图/工具结果)
- 前端:`fetch` + `ReadableStream` 逐段渲染,打字效果;加载状态在 `meta` 到达后即切换为工具意图预览

## 4. 配置

| 环境变量 | 说明 | 默认 |
|----------|------|------|
| `SMART_ASSISTANT_DATASET_ID` | Ragflow 默认数据集 ID | 无(待配置) |
| `SMART_ASSISTANT_CHAT_RATE_LIMIT` | 每用户每分钟最大请求数 | `30` |
| `SMART_ASSISTANT_MAX_HISTORY_TOKENS` | 长会话压缩阈值 | `2000`(规划中) |
| `SMART_ASSISTANT_AGENT_VERSION` | Agent 框架版本(v1/v2) | `v1`(规划中) |
| `OLLAMA_ENDPOINT` | Ollama 本地服务地址 | 项目默认 |
| `OLLAMA_MODEL` | Ollama 模型名称 | `deepseek-r1:1.5b` |
| `OLLAMA_KEEP_ALIVE` | 模型常驻时间(规划中) | `24h` |

## 5. 模块覆盖率与质量(2026-06-06 实测)

**模块总覆盖率 63.25%**(55 passed,远低于项目基线 80.89%)。

覆盖率断点(详细补齐路径见 [28-smart-assistant-coverage-roadmap.md](./28-smart-assistant-coverage-roadmap.md)):

| 文件 | 覆盖率 | 缺口 |
|------|--------|------|
| `views/llm_config.py` | 37% | 51 行 |
| `views/chat.py` | 48% | 50 行 |
| `views/stats.py` | 42% | 22 行 |
| `tools/event_tool.py` | 32% | 19 行 |
| `tools/sensor_tool.py` | 35% | 13 行 |
| `tools/document_tool.py` | 39% | 11 行 |
| `tools/meeting_room_tool.py` | 33% | 18 行 |
| `tools/base.py` | 48% | 16 行 |
| `middleware/rate_limit.py` | 48% | 17 行 |
| `migrations/0004` | 52% | 11 行 |

## 6. 开发状态(2026-06-06 更新)

| 阶段 | 状态 | 备注 |
|------|------|------|
| Phase 1:核心聊天 + 基础工具(3) | ✅ 已完成 | 实际已扩到 12 工具 |
| Phase 2:知识库文档上传与向量化 | ✅ 已完成 | 仅需配置 `SMART_ASSISTANT_DATASET_ID` |
| Phase 3:流式响应 + 对话历史 | ✅ 已完成 | 含多轮压缩(≤6/7-15/>15 三档) |
| Phase 4:审计面板 + 错误处理 | ✅ 已完成 | 含 3 级缓存、限流、token 用量统计 |
| Phase 5:深化设计(模型降级/多数据集 RAG/成本监控) | ✅ 已完成 | 见 [17-ai-assistant-deep-design.md](./17-ai-assistant-deep-design.md) |
| **Phase 6:覆盖率补齐与质量守卫(P0)** | 🔄 进行中 | 本次优化方案 阶段 2 |
| Phase 7:新工具(公告/合规/外部链接)(P1) | 📝 计划 | 本次优化方案 阶段 3 |
| Phase 8:性能与体验(P1) | 📝 计划 | 本次优化方案 阶段 4 |
| Phase 9:架构升级(ReAct + Reflexion)(P2) | 📝 计划 | 本次优化方案 阶段 5 |

## 7. 相关文档

- [17-ai-assistant-deep-design.md](./17-ai-assistant-deep-design.md) — 多轮对话、工具链、模型降级、成本监控
- [28-smart-assistant-coverage-roadmap.md](./28-smart-assistant-coverage-roadmap.md) — 覆盖率补齐与守卫策略
- [优化实施计划](../plans/2026-06-06_smart-assistant-optimization.md) — 6 阶段路线图(2026-06-06)
- [用户操作手册](../user-manual/08-smart-assistant-usage.md) — 终端用户使用指南
