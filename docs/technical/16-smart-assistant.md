# 智能助手系统

> 类似贾维斯的智能助手,通过聊天快速获取信息、知识库问答、文献搜索。
>
> 📅 **最近更新:2026-08-09** — L1.1 原生 Function Calling 加固:§13 新增流式原生 tool_calls(F2)、结构化参数透传(I-2);§2.10 Hook 表新增 ConfirmationHook 并修正接线现状(写工具确认 fail-open → fail-closed,I-1)。此前 2026-08-06 同步 2026-08 阶段 1 完工:智能助手 Office 文件附件能力(`chat/` 与 `chat/stream/` 支持 multipart 上传 .docx/.pdf/.xlsx/.pptx/.txt/.md/.csv,`OfficeExtractor` 统一抽取,新增 `OfficeReadTool` / `OfficeGenerateTool` / `SpreadsheetTool` 三个工具,生成 .docx 通过签名 token 下载卡片交付)。详见 §12。

## 1. 架构概览

```
用户提问 → 意图分类(Ollama) → 工具路由/链规划 → 工具执行 → LLM 生成 → 返回答案
                                │                  │
                    ┌───────────┼───────────────┐  ├─ Hooks(PII 脱敏/超时熔断/审计,按需注册)
                    ▼           ▼               ▼  └─ risk_level 分级(read/write/destructive)
               ScheduleTool  PersonnelTool    RAGTool
               (排班查询)     (人员查询)      (知识库/Ragflow)

失败路径:classify_error_kind → kind + hint(失败响应不写 session,仅写 AgentLog 审计)
长会话:滚动摘要(>3000 token 触发,截断保留最近 6 轮,摘要优先构造历史)
```

### 1.1 当前真实模块结构(2026-07-29 实测)

| 类别 | 模块 | 文件 | 说明 |
|------|------|------|------|
| **Agent(7)** | 意图分类 | `agent/intent_classifier.py` | Ollama 本地 LLM 识别用户意图 |
| | 编排器 | `agent/orchestrator.py` | 分类→路由→生成(支持单/多工具链);含输出契约(`FORMAT_VERSION`、`classify_error_kind`、`annotate_error_kind`) |
| | Prompt 构建 | `agent/prompt_builder.py` | 系统 prompt + 工具链 prompt |
| | 对话上下文 | `agent/conversation_context.py` | 多轮历史 + 滚动摘要 + 失败回答判定(`is_failed_answer`) |
| | RAG 路由 | `agent/rag_router.py` | 多数据集关键词匹配 + 并行搜索 |
| | 工具链规划 | `agent/tool_chain_planner.py` | LLM 生成多工具执行计划 |
| | 工具链执行 | `agent/tool_chain_executor.py` | 按依赖顺序执行,支持 `$variable` 替换 |
| **多 Agent** | 执行器 | `agents/` | MultiAgentExecutor / Pipeline / Fanout / Hierarchical,详见 [32-smart-assistant-multi-agent.md](./32-smart-assistant-multi-agent.md) |
| **工具(13)** | 见 §2.1 | `tools/*.py` | 单例注册中心 `tools/registry.py`;全部声明 `risk_level="read"` |
| **视图(8)** | 聊天 | `views/chat.py` | 非流式 + SSE 流式两路(失败不落库 + 错误 kind 标注) |
| | 知识库 | `views/knowledge_base.py` | 文档上传/列表/删除/状态 + 数据集 CRUD |
| | LLM 配置 | `views/llm_config.py` | 端点/激活/健康检查 |
| | 会话 | `views/sessions.py` | 会话 CRUD + fork + Markdown 导出 |
| | 日志 | `views/logs.py` | 审计日志 API + 反馈 action |
| | 统计 | `views/stats.py` | 用量/意图分布聚合 |
| | 自检 | `views/doctor.py` | 2026-07 新增:6 项系统自检(staff) |
| | 多 Agent 任务 | `views/tasks.py` | 多 Agent 任务/时间线/介入/流订阅(见第 32 章) |
| **Hook 系统** | 内置 3 个 | `hooks/builtin/` | AuditLogHook / PiiMaskingHook / TimeoutGuardHook(注册表默认为空,调用方显式注册) |
| **中间件(1)** | 限流 | `middleware/rate_limit.py` | 30 req/min/user,SSE 接口限流 |
| **缓存** | 3 级 | `cache.py` | 意图(1h)/工具(30min)/回答(2h) |
| **晨报** | 每日摘要 | `digest.py` | 复用聚合链路生成每日晨报 Markdown |
| **Celery** | 文档向量化 | `tasks.py` | 上传→Ragflow 解析→状态流转 |
| | 每日晨报 | `tasks.py::send_daily_digests` | beat 工作日 8:30 触发,推送通知中心 |

### 1.2 核心数据流

1. **非流式路径**:`POST /api/smart-assistant/chat/` → 解析 → 查缓存 → 意图分类 → 工具链规划 → 工具执行 → LLM 生成回答 → 失败判定(`_resolve_error`)→ 成功:写入 `session.messages` + AgentLog(携带 `estimated_cost`);失败:仅写 AgentLog(`tool_success=False`),响应追加 `kind`/`hint`
2. **流式路径**:`POST /api/smart-assistant/chat/stream/` → 同上但 LLM 调用改为 `generate_answer_stream` → 逐 chunk 通过 SSE 推送(meta → chunks → done → session);**所有 SSE 帧携带 `format_version=1`**;done 帧携带显式 `error` 标记 + `kind`/`hint`;失败时不写 `session.messages`(无 `conversation_id` 时显式置空 `persist_session`)
3. **会话压缩**:会话保存路径调用 `apply_rolling_summary()`,token 超 `SOFT_TOKEN_LIMIT`(3000)且尚无摘要时,对早期消息生成 `summary_text` 并把 `messages` 截断为最近 6 轮(12 条)
4. **历史构造**:下一次请求由 `build_effective_history()` 组装,**摘要优先**——有摘要时返回 `[摘要 system 消息] + 最近 6 轮`,无摘要返回全量

> 失败时**仍写 AgentLog**(审计需要,`session` 可为空),审计与"不污染多轮上下文"是两条独立链路。

## 2. 后端实现

### 2.1 数据模型

| 模型 | 关键字段 | 说明 |
|------|----------|------|
| `AgentLog` | user, query, response, tool_used, tool_output, intent, **estimated_cost, model_name, input_tokens/output_tokens/total_tokens, user_feedback** | 助手调用日志;`estimated_cost` 为 `DecimalField(10, 6)` 可空(预估费用,元);`user_feedback` 取值 `""`/`up`/`down`(扩展字段见 [17-ai-assistant-deep-design §6](./17-ai-assistant-deep-design.md)) |
| `SmartAssistantSession` | user, conversation_id, messages(JSON), summary_text, **summary_token_count**, turn_count | 对话会话(滚动摘要已启用) |
| `KnowledgeBaseDocument` | title, file, status, vectorized_at | 知识库文档 |
| `KnowledgeDataset` | name, ragflow_dataset_id, tags, is_active | 多数据集 RAG 路由(全局共享资源,无属主字段) |
| `LlmEndpoint` / `LlmAppConfig` | name, priority, is_fallback, model_capabilities, **api_key(加密存储)** | 多 LLM 端点配置 |

### 2.2 工具系统(16 个)

| 工具 | 功能 | 数据源 |
|------|------|--------|
| `ScheduleTool` | 排班/值班查询 | `events.Schedule` |
| `PersonnelTool` | 人员信息查询 | `personnel.Personnel` |
| `RAGTool` | 知识库问答 | Ragflow 向量数据库 |
| `DocumentTool` | 公文/文档搜索 | `documents` 模块 |
| `EventTool` | 事件/日程/节假日查询 | `events` 模块 |
| `MemoTool` | 备忘录查询 | `memos.Memo` |
| `MemoCreateTool` | 创建备忘录(写, 需确认) | `memos.Memo` |
| `MemoUpdateTool` | 修改备忘录(写, 需确认) | `memos.Memo` |
| `MemoDeleteTool` | 删除备忘录(破坏性, 需确认) | `memos.Memo` |
| `ProjectTool` | 项目进度查询 | `projects.Project` |
| `NewsTool` | 新闻/通知搜索 | `news.NewsArticle` |
| `MeetingRoomTool` | 会议室可用性 | `meeting_rooms` |
| `SensorTool` | 传感器数据/告警 | `sensor_management` |
| `AnnouncementTool` | 公告查询 | `communication.Post` |
| `ComplianceTool` | 合规问题/待整改查询 | `compliance.ComplianceIssue` |
| `ExternalLinkTool` | 内网外链导航(VPN/Jira) | `external_integration.ExternalLink` |

最后 3 个工具(Announcement/Compliance/ExternalLink)为 2026-06 阶段 3 计划新增(详见
[2026-06-07_smart-assistant-stage3-new-tools.md](../plans/2026-06-07_smart-assistant-stage3-new-tools.md))。

#### 2.2.1 新工具 API(阶段 3 增量)

**AnnouncementTool**(`intent_type="announcement_query"`)

- 数据源: `communication.Post`,过滤 `is_archived=False` AND (`expires_at IS NULL` OR `expires_at > now()`)
- 关键词: 字符级 strip 停用词,`len >= 2` 时按 `title__icontains OR content__icontains` 过滤
- 排序: `order_by("-created_at")`,限 10 条
- 返回结构:
  ```python
  {"found": True, "count": int, "posts": [{"title", "content" (≤200+...), "author", "created_at", "expires_at"}]}
  ```
  或 `{"found": False, "count": 0, "posts": [], "message": "..."}`
- 性能: `select_related("author")` 防 N+1

**ComplianceTool**(`intent_type="compliance_query"`)

- 数据源: `compliance.ComplianceIssue`,过滤 `status IN ("待处理", "处理中")`
- 关键词: 同上策略(去除 `合/规/待/已/什么/查/看/几/条`,**不** strip `改/整` 因为是核心业务词)
- 业务词触发:
  - `"紧急" in query` → `severity="紧急"`
  - `"即将到期" / "快到期" in query` → `due_date <= today + 7`
- 排序: `Case/When` 业务优先级(紧急=0/高=1/中=2/低=3),然后 `due_date` 升序;**不用** `order_by("-severity")` 因为 CharField 字典序与业务优先级不一致
- 性能: `select_related("project", "document_book", "document_template")` 防 N+1
- 返回结构:
  ```python
  {"found": True, "count": int, "issues": [{"issue_type", "description" (≤200+...), "status", "severity", "project", "due_date", "location"}]}
  ```

**ExternalLinkTool**(`intent_type="external_link_query"`)

- 数据源: `external_integration.ExternalLink`,过滤 `is_active=True`
- 关键词: 三字段 OR(`name` / `description` / `category`),`"所有"/"全部"` 或无关键词时返回全部
- 排序: 模型 Meta `ordering = ["category", "sort_order", "name"]`,限 20 条
- 返回结构:
  ```python
  {"found": True, "count": int, "links": [{"name", "url", "category", "description" (≤150), "sso_enabled", "sso_token_endpoint" (仅 SSO 启用时)]}
  ```

#### 2.2.2 工具上下文抽象(`ToolContext`)

新工具统一通过 `ToolContext` 接收上下文(替代裸 dict),由 Registry 在分发时构造:

```python
@dataclass(frozen=True)
class ToolContext:
    user: Any                                # CustomUser 实例(必填)
    request_id: str = field(default_factory=lambda: str(uuid4()))
    history: Optional[List[dict]] = field(default_factory=list)
```

`BaseTool.required_auth: bool = True` 默认值实现 fail-closed(新工具默认需登录);`ToolRegistry.get_tool_for_user(intent_type, user)` 在分发时校验,未授权返回 `None`(不抛异常)。

#### 2.2.3 E2E 覆盖(阶段 3 增量)

`smart_assistant/tests/test_e2e_smart_chat.py` 新增 4 个 E2E 场景:

- `TestSmartChatE2EAnnouncementQuery` / `TestSmartChatE2EComplianceQuery` / `TestSmartChatE2EExternalLinkQuery`: 3 个新工具的 happy path(含 fixture 数据 + mock orchestrator + AgentLog 写入验证)
- `TestSmartChatE2EUnauthToolRejection`: 未认证用户调用 chat 端点 → 401

共 9 个 E2E 测试覆盖完整链路。

#### 2.2.4 工具风险分级(`risk_level`,2026-07 新增)

`tools/base.py` 引入工具风险元数据,为写操作/破坏性操作预留分级与二次确认协议:

| 常量 | 取值 | 约定 |
|------|------|------|
| `RISK_LEVEL_READ` | `read` | 只读查询,`BaseTool` 默认值 |
| `RISK_LEVEL_WRITE` | `write` | 有副作用的写操作,orchestrator 记录显式审计 |
| `RISK_LEVEL_DESTRUCTIVE` | `destructive` | 破坏性操作,约定必须同时置 `require_confirmation=True`(预留二次确认) |

- `VALID_RISK_LEVELS` frozenset 由 `tests/test_tool_risk_level.py` 全量校验,非法取值在测试中 fail
- `get_schema()` 输出包含 `risk_level`,供前端/审计消费
- **现状:13 个工具全部显式声明 `risk_level="read"`**(均为只读查询,无副作用),write/destructive 为框架预留,尚无实例
- 审计:`AuditLogHook._audit_input()` 将 `risk_level` 并入 `AgentLog.tool_input`(JSONField);`destructive` 调用额外 `logger.warning` 提升日志级别

### 2.3 API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/smart-assistant/chat/` | POST | 发送聊天消息(非流式);失败响应追加 `kind`/`hint` |
| `/api/smart-assistant/chat/stream/` | POST | 流式响应(SSE,全帧 `format_version=1`,实现于 2026-07 重写) |
| `/api/smart-assistant/sessions/` | GET/POST | 会话列表/创建 |
| `/api/smart-assistant/sessions/{id}/` | GET/DELETE | 会话详情/删除 |
| `/api/smart-assistant/sessions/{id}/fork/` | POST | **新增**:会话 fork(可选 `at_message` 截断前 N 条、`title`) |
| `/api/smart-assistant/sessions/{id}/export/` | GET | **新增**:Markdown 导出(RFC 5987 文件名) |
| `/api/smart-assistant/knowledge-base/` | GET/POST | 知识库文档管理 |
| `/api/smart-assistant/knowledge-base/datasets/` | GET/POST/PUT/PATCH/DELETE | **新增**:数据集 CRUD(`KnowledgeDatasetViewSet`,仅 `IsAuthenticated`,数据集为全局共享资源) |
| `/api/smart-assistant/agent-logs/{id}/feedback/` | PATCH | **新增**:回答反馈(`up`/`down`/`null` 清除,仅本人可反馈) |
| `/api/smart-assistant/logs/` | GET | 审计日志列表 |
| `/api/smart-assistant/logs/{id}/` | GET | 审计日志详情 |
| `/api/smart-assistant/llm-config/` | GET/POST | LLM 端点配置 |
| `/api/smart-assistant/stats/` | GET | 用量/意图分布聚合 |
| `/api/smart-assistant/usage/{stats,daily,user}/` | GET | 用量分析(详见 [17-ai-assistant-deep-design §6.2](./17-ai-assistant-deep-design.md)) |
| `/api/smart-assistant/doctor/` | GET | **新增**:系统自检(staff only),见 §2.7 |
| `/api/smart-assistant/tasks/...` | GET/POST | 多 Agent 任务/执行/介入/时间线/流订阅,详见 [32-smart-assistant-multi-agent.md](./32-smart-assistant-multi-agent.md) |

### 2.4 输出契约与错误分类(2026-07 新增)

**SSE 契约**:所有 SSE 事件(meta/chunk/done/session)经 `orchestrator.sse_event()` 统一注入 `format_version: 1`(`FORMAT_VERSION` 常量)。同步(非 SSE)响应的 JSON **不带** `format_version`,仅在失败时追加 `kind`/`hint`。

**错误分类单一事实源**:`classify_error_kind(result)` 位于 `agent/orchestrator.py` 顶部,纯函数 + 单次 DB 查询,同步路径与流式 done/session 帧经 `annotate_error_kind()` 复用同一分类,保证各出口一致。

| kind | 触发条件 | hint(中文指引) |
|------|----------|-----------------|
| `no_llm_endpoint` | 无激活的 LlmAppConfig/端点 | 请前往管理后台 → AI 应用配置 LLM 端点 |
| `llm_unavailable` | 有配置但回答带失败前缀 | LLM 服务暂时不可用,请稍后重试或检查端点连通性 |
| `ragflow_unavailable` | `tool_used="knowledge_qa"` 且错误涉及 ragflow | 知识库服务暂时不可用 |
| `internal_error` | 其余失败(兜底) | 服务异常,请稍后重试 |

hint 文案来自模块级 `ERROR_KIND_HINTS` 字典;查不到 kind 时 fallback 到 `internal_error` 的 hint。

### 2.5 失败响应不落库与滚动摘要(2026-07 新增)

**失败不落库(双保险)**:

- 统一判定 `_resolve_error(result)` = 显式 `error` 标记 **OR** `is_failed_answer(answer)` 前缀判断
- 显式标记:orchestrator 每个返回分支都带 `"error": is_failed_answer(answer)`
- 前缀兜底:`is_failed_answer()` 匹配 `FAILED_ANSWER_PREFIX="回答生成失败"` 与 `FAILED_ANSWER_STREAM_PREFIX="[错误] 回答生成失败"`(`agent/conversation_context.py`)
- 同步与流式两条路径在失败时均跳过 `session.messages` 写入,避免错误回答污染多轮上下文

**滚动摘要**:

| 常量(`agent/conversation_context.py`) | 值 | 含义 |
|------|------|------|
| `SOFT_TOKEN_LIMIT` | 3000 | 摘要触发阈值(且尚无摘要) |
| `HARD_TOKEN_LIMIT` | 6000 | 硬上限 |
| `RECENT_TURNS_SOFT` | 6 | soft 触发时截断保留最近轮数(12 条消息) |
| `RECENT_TURNS_HARD` | 3 | hard 触发时保留轮数 |

- `generate_rolling_summary(messages)` 经 `llm_service.router` 生成(`ROLLING_SUMMARY_PROMPT`:保留人物/时间/事项/结论,≤300 字);异常或失败响应 → 返回 `None`,静默降级保留全量历史
- `apply_rolling_summary(session)` 写入 `summary_text` + `summary_token_count`,截断 `messages` 并重算 `turn_count`
- `build_effective_history(messages, summary_text)` **摘要优先**:有摘要 → `[摘要 system 消息] + 最近 6 轮`;无摘要 → 全量

### 2.6 成本核算(2026-07 新增)

- `llm_service/router.py::_enrich_usage()` 在非流式 `generate()` 返回的 usage 中补充:
  - `estimated_cost`:按命中端点 `cost_per_1k_tokens × total_tokens / 1000` 计算(六位小数 `ROUND_HALF_UP`;无配置/无用量 → `0.0`)
  - `endpoint_id`:命中的 `LlmEndpoint` 主键(Ollama 兜底为 `None`)
  - `model_name`:实际模型名
- 同步路径经 `_usage_fields()` 提取后落库 `AgentLog.estimated_cost`;**流式路径显式 `estimated_cost=None`**(流式暂无 usage 统计,见 §9 遗留项)

### 2.7 doctor 自检端点(2026-07 新增)

`GET /api/smart-assistant/doctor/`,权限 `IsAuthenticated + IsAdminUser`(staff only)。

**6 个检查项**(`CHECKERS` 元组,顺序即输出顺序):

| # | 检查项 | 内容 |
|---|--------|------|
| 1 | `llm_config` | smart_assistant 的 LlmAppConfig 是否存在且激活(模型 + 端点名) |
| 2 | `llm_endpoints` | 逐个探测激活 LlmEndpoint(优先 `/v1/models`,失败回退基址;任意 HTTP 响应含 4xx 视为可达) |
| 3 | `ollama_fallback` | `settings.OLLAMA_BASE_URL` 兜底可达性(不可达仅 warn) |
| 4 | `ragflow` | 激活 RagflowConfig 存在性 + `api_endpoint` 可达性 |
| 5 | `datasets` | 激活 KnowledgeDataset 数量(0 个 → warn) |
| 6 | `cache_rate_limit` | 缓存后端类型 + RateLimitMiddleware 启用情况(LocMemCache 提示换 Redis) |

**报告结构**(与 chat 契约同源,`format_version: 1`):

```json
{
  "format_version": 1,
  "checked_at": "...",
  "summary": {"ok": 4, "warn": 1, "error": 1},
  "checks": [{"name": "...", "status": "ok|warn|error", "kind": "...", "message": "...", "hint": "..."}]
}
```

探测超时 `PROBE_TIMEOUT_SECONDS=3`;单项异常兜底为 `kind="internal_error"` 的检查项,端点本身不返回 500。doctor 的 `kind` 取值是 chat 契约的超集(另含 `ok`/`info`/`ollama_unavailable`/`no_active_dataset`)。

### 2.8 反馈 API 与数据集 CRUD(2026-07 新增)

**反馈 API**:`PATCH /api/smart-assistant/agent-logs/{id}/feedback/`(`AgentLogViewSet.feedback` action)

- 取值:`up` / `down` / `null`(`null` 清除,落库为 `""`),允许 up↔down 改选
- 归属校验:`AgentLog.objects.get(pk=pk, session__user=request.user)`——仅本人可反馈自己的日志;日志不存在、session 无主或 pk 非法一律 404,刻意不泄露他人日志存在性

**数据集 CRUD**:`KnowledgeDatasetViewSet`(ModelViewSet),前缀 `knowledge-base/datasets/`

- 完整 CRUD,权限仅 `IsAuthenticated`(无 staff 门槛;数据集为全局共享资源,被 RAGRouter 消费,模型无属主字段)
- 必填校验(name / ragflow_dataset_id)由 `KnowledgeDatasetSerializer` 完成,`document_count` 为只读统计
- ⚠️ 前端管理页面尚未落地(仅后端 API,见 §9 遗留项)

### 2.9 会话 fork 与导出(2026-07 新增)

**fork**:`POST /api/smart-assistant/sessions/{id}/fork/`

- 请求体均可选:`at_message`(非负整数,仅复制前 N 条消息,默认全量)、`title`(默认 `原标题（副本）`,对齐 `TITLE_MAX_LENGTH=255`)
- 新会话归属 `request.user`,`turn_count` 按截断结果重算,`summary_text` 置空待重建,返回 201
- `get_queryset` 限定本人会话,访问他人自动 404

**export**:`GET /api/smart-assistant/sessions/{id}/export/`

- `render_session_markdown` 输出 `# 标题` + 创建时间/轮数 + 逐条消息段落(role 映射:用户/助手/系统)
- `Content-Disposition` 双文件名:ASCII 兜底 `filename="session-{pk}.md"` + **RFC 5987** `filename*=UTF-8''{quote(filename)}`
- `build_export_filename` 正则清洗标题非法字符,最终格式 `{safe_title}-{YYYYMMDD}.md`

### 2.10 Hook 系统(2026-07 新增)

`hooks/builtin/` 内置 5 个 hook(借鉴 claw-code 设计):

| Hook | 开关 | 默认 | 作用 |
|------|------|------|------|
| `AuditLogHook` | 无 | — | 工具输入/输出并入 `AgentLog.tool_input`(含 `risk_level`);destructive 额外 warning |
| `PiiMaskingHook` | `SMART_ASSISTANT_PII_MASKING` | `True` | post_execute 递归脱敏工具输出(生成新容器,不可变);邮箱 → 身份证 → 手机号顺序匹配:手机号 `138****1234`(前 3 后 4)、身份证前 6 后 4、邮箱 local 保留前 3 位 |
| `TimeoutGuardHook` | `SMART_ASSISTANT_TOOL_TIMEOUT`(秒)/ `SMART_ASSISTANT_TOOL_TIMEOUT_ENABLED` | `10.0` / `True` | 钩子本身为配置入口 + 恢复策略;实际计时由 `run_guarded_sync`(daemon 线程 + `join(timeout)`)/ `run_guarded`(`asyncio.wait_for`)与 `BaseTool.execute_with_guard` 完成;超时返回 `{"found": False, "timed_out": True, "error": "tool_timeout", ...}`,`on_failure` 对 `TimeoutError` 返回 `RecoveryAction(action="fallback")` |
| `ConfirmationHook` | 无 | — | **pre_execute**:对 `require_confirmation=True` 的写工具(office_generate / swap×2)返回 `Reject(error_code="confirmation_required")`,激活 orchestrator confirm-replay(dry_run → draft → awaiting_confirmation → 前端确认 → replay 视图执行)。2026-08-09 I-1 新增,写工具确认 fail-open → fail-closed |
| `RateLimitHook` | `SMART_ASSISTANT_WRITE_RATE_LIMIT`(每窗口允许次数)/ 窗口固定 60s | `10` / `60s` | **pre_execute**、priority=25:对所有 `require_confirmation=True` 工具按用户 fixed window 限频;超限返回 `Reject(error_code="rate_limit_exceeded", retry_after=Ns)`,前端 toast 显示 Ns 后重试。Cache key `smart_assistant:write_rate_limit:{user_id}`,与 chat 限流(中间件层)共享同一缓存后端但 namespace 隔离。2026-08-10 P1A-2 新增,详情见 [`docs/superpowers/specs/2026-08-10-p1a2-write-tool-rate-limit-design.md`](../superpowers/specs/2026-08-10-p1a2-write-tool-rate-limit-design.md)(实施 plan [`docs/plans/2026-08-10_p1a2-write-tool-rate-limit.md`](../plans/2026-08-10_p1a2-write-tool-rate-limit.md)) |

**接线现状(重要)**:`apps.ready()` 调用 `register_builtin_hooks()` 把 **PiiMaskingHook(POST_EXECUTE)+ TimeoutGuardHook(ON_FAILURE)+ ConfirmationHook(PRE_EXECUTE)** 注册进全局注册表(`get_registry()`),幂等(按 hook name 去重,`ready()` 多次调用不重复挂载)。生产执行器(orchestrator 单工具执行 / ToolChainExecutor 逐步执行)经 `execute_guarded` / `apply_pre_execute_hooks` 消费全局注册表。三个开关项均未在 settings 中定义,完全依赖 `getattr` 兜底默认值。

### 2.11 每日晨报(2026-07 新增)

- **调度**:`CELERY_BEAT_SCHEDULE["smart-assistant-daily-digest"]` → `smart_assistant.tasks.send_daily_digests`,`crontab(hour=8, minute=30, day_of_week="1-5")`(工作日 8:30,`CELERY_TIMEZONE=Asia/Shanghai`)
- **生成**:`digest.py::generate_daily_digest(user)` 以固定晨检 query(`DIGEST_QUERY="今天我有哪些安排？请汇总今日的排班、会议室、备忘录和待办事项。"`)构造 `ToolContext(user, scope=resolve_scope(user))` 调 `AgentOrchestrator().process()`,**复用聚合链路**(`intent="aggregated_day"` → ToolChainExecutor + ResultSynthesizer);渲染 Markdown(日期标题 + summary + moduleCounts + 重点条目,`MAX_HIGHLIGHT_ITEMS=10`、`MAX_ITEM_DESC_LENGTH=80`);失败一律返回 None 不抛异常
- **推送**:经 `NotificationService.create(type="system", content=markdown, dedupe_key=...)` 写通知中心;`dedupe_key=f"smart_assistant_daily_digest:{date.isoformat()}"`(按日期去重,beat 重投不会发第二条)
- **面向用户**:`is_active=True, is_staff=True`(MVP 范围,TODO 改按 NotificationPreference 订阅);单用户失败不中断,任务返回 `{"success", "failed", "total", "date"}`

### 2.12 LLM 接入层统一(2026-07 新增)

| 变更 | 说明 |
|------|------|
| office_assistant 统一路由 | `office_assistant/views.py` 改经 `llm_service.router.get_router(app_name="office_assistant")`(流式 `stream=True`,非流式返回 `(content, usage)`),消除直连 Ollama 裂缝 |
| Ollama 默认模型统一 | `llm_service/ollama_client.py` 与 `settings/base.py` 的 `OLLAMA_MODEL_NAME` 默认值统一为 `qwen2.5:7b`(原 `llama2`),base_url 默认 `http://localhost:11434` |
| 删除死代码 | `llm_service/openai_client.py` 已删除;目录仅剩 `ollama_client.py` / `router.py` + 测试 |
| RagflowConfig.api_key 加密 | 改为 `EncryptedCharField(max_length=500)`(复用 `personnel.models` 实现:`sha256(SECRET_KEY)` 派生密钥逐字节 XOR + base64,透明加解密,解密失败降级返回原值);迁移 `ragflow_service/migrations/0003_encrypt_api_key.py` 前向用原生 SQL 读明文加密(避免 ORM 对合法 base64 明文二次加密),reverse 可解密回滚 |

### 2.13 Mock LLM 等价测试(2026-07 新增)

CI 不依赖真实 LLM 的确定性 e2e 体系:

- **`tests/mock_llm_server.py`**:纯标准库 `ThreadingHTTPServer`,仅模拟 OpenAI 兼容 `POST /v1/chat/completions`(Ollama 在测试中被故意指向死端口作确定性失败兜底);`stream=true` 时按 SSE 输出 `chat.completion.chunk` + `data: [DONE]`;关键词路由确定性返回固定回答 / 500 / 121s 超时;入口 `running_server()` 上下文管理器(端口 0 自动分配、daemon 线程)
- **`tests/test_mock_llm_e2e.py`**:5 个模块级用例——固定回答 + Decimal 精确成本(`0.003000`)/ 端点 500 失败不建 session / 流式事件序列(meta→chunk→done→session,拼接 == 非流式回答,验证流式/非流式等价)/ 单端点无重试只降级 / 超时 fallthrough
- **隔离机制**:fixture 用 ORM 真实创建 `LlmEndpoint`/`LlmAppConfig` 指向进程内 mock(走真实 TCP 全链路)+ autouse fixture monkeypatch `LLMRouter.OLLAMA_BASE` 到 discard 端口 + 清单例缓存

## 3. 前端实现

| 组件 | 路径 | 说明 |
|------|------|------|
| `SmartChatPage` | `/smart-assistant` | 聊天主界面(流式打字、错误 hint 展示、会话 ⋯ 菜单:创建副本/导出 Markdown) |
| `KnowledgeBasePage` | `/knowledge-base` | 知识库管理 |
| `AgentAuditPanel` | `/smart-assistant/audit` | 管理员审计面板(图表+过滤) |
| `StatsPage` | `/smart-assistant/stats` | 用量统计页 |
| `AgentTaskPanel` | `/smart-assistant/tasks` | **新增**:多 Agent 任务面板(SSE timeline、介入、子任务/产出展示) |
| `ToolResult` | 共享组件 | 工具结果渲染(排班/人员/知识来源等;聚合结果已对齐扁平结构) |
| `AggregatedDayCard` | 共享组件 | 跨模块汇总卡片(扁平 props:items/moduleCounts/summary) |
| `MessageMarkdown` | 共享组件 | Markdown 渲染(`react-markdown` + remark-gfm) |
| `MessageActions` | 共享组件 | 点赞/点踩/复制/重试(赞踩经 `submitFeedback` 接反馈 API) |
| `QuickCommands` | 共享组件 | 快捷指令面板 |
| `QuickAssistant` | 共享组件 | 悬浮快捷助手(同样消费错误 hint) |
| `DocumentPreview` | 共享组件 | 文档预览(上传/下载) |
| `sessionForkExportApi` | `pages/sessionForkExportApi.js` | **新增**:fork / Markdown 导出客户端(`forkSession`、`exportSessionMarkdown`、`parseDownloadFilename`;置于 pages/ 目录是为规避并行开发冲突) |

### 3.1 流式响应与错误提示

- 后端:`StreamingHttpResponse` 按 chunk 推送,首帧先发 `meta`(工具意图/工具结果);**所有 SSE 帧携带 `format_version: 1`**,失败时 done 帧携带 `error` + `kind` + `hint`
- 前端:`fetch` + `ReadableStream` 逐段渲染,打字效果;加载状态在 `meta` 到达后即切换为工具意图预览
- 错误 hint 消费:从 SSE `done`/`session` 事件经 `smartAssistantApi.resolveErrorHint(event)` 解析(`ERROR_KIND_MESSAGES` kind→文案映射表),`SmartChatPage` 挂到消息 `errorHint` 字段渲染 secondary 文本(`data-testid="message-error-hint"`),`QuickAssistant` 同模式;流无正文时兜底「回答生成失败」

### 3.2 聚合卡片渲染修复(2026-07)

- **修复前**:`ToolResult.jsx` 按嵌套结构消费(`result.data.items/moduleCounts/summary`),与后端返回的扁平 `tool_result` 不匹配,跨模块汇总卡片渲染断链(功能实际失效)
- **修复后**:新增 `normalizeAggregatedResult(result)`,主路径扁平读取 `result.items / result.moduleCounts / result.summary` 并显式传三个 prop(保留 `result.data` 包层的防御性回退)
- 同轮修复 `AggregatedDayCard.jsx` 的 Rules of Hooks 违规(`useMemo` 移到所有 early return 之前)+ 补全 propTypes

### 3.3 多 Agent 任务面板(2026-07 新增)

- 路由 `/smart-assistant/tasks`(`routes/index.jsx`,lazy 加载,`ProtectedRoute pageName="多Agent任务"` 仅要求登录);Sidebar「AI 助手」子菜单新增「多Agent任务」入口(`ClusterOutlined` 图标)
- **SSE timeline**:`subscribeTaskStream`(fetch + ReadableStream + AbortController)订阅 `/api/smart-assistant/tasks/{id}/stream/`,按 `sequence` 去重、60s 超时重连
- **介入**:`interveneAgentTask(taskId, action)` 支持 `pause` / `resume` / `cancel` 三个动作(cancel 带 Popconfirm);⚠️ 暂不支持「补充指令」动作(见 §9 遗留项)
- `agentTaskApi.js` 另导出 `getAgentTasks`、`getAgentTaskTimeline`、`createAgentTask`、`executeAgentTask` 及状态映射常量(`TASK_STATUS_MAP` / `SUBTASK_STATUS_MAP` / `EVENT_TYPE_LABELS`)
- 后端 API(Pipeline/Fanout/Hierarchical 执行器)详见 [32-smart-assistant-multi-agent.md](./32-smart-assistant-multi-agent.md)

## 4. 配置

| 环境变量 | 说明 | 默认 |
|----------|------|------|
| `SMART_ASSISTANT_DATASET_ID` | Ragflow 默认数据集 ID | 无(待配置) |
| `SMART_ASSISTANT_CHAT_RATE_LIMIT` | 每用户每分钟最大请求数 | `30` |
| `SMART_ASSISTANT_PII_MASKING` | PiiMaskingHook 开关(代码级 `getattr` 兜底,未在 settings 定义) | `True` |
| `SMART_ASSISTANT_TOOL_TIMEOUT` | 工具执行超时秒数(同上) | `10.0` |
| `SMART_ASSISTANT_TOOL_TIMEOUT_ENABLED` | 超时熔断开关(同上) | `True` |
| `SMART_ASSISTANT_AGENT_VERSION` | Agent 框架版本(v1/v2) | `v1`(规划中) |
| `OLLAMA_BASE_URL` | Ollama 本地服务地址 | 项目默认 |
| `OLLAMA_MODEL_NAME` | Ollama 模型名称(2026-07 起全站统一) | `qwen2.5:7b`(原 `llama2`) |
| `OLLAMA_KEEP_ALIVE` | 模型常驻时间(规划中) | `24h` |
| `SEED_LLM_API_ENDPOINT` | `seed_llm_endpoint` 播种的端点地址 | `http://localhost:11434/v1` |
| `SEED_LLM_MODEL` | 播种端点的模型名 | `qwen2.5:7b` |
| `SEED_LLM_API_KEY` | 播种端点的 API key | 空 |
| `RAGFLOW_PORT` | 离线 compose RAGFlow 宿主机端口 | `9380` |
| `RAGFLOW_MYSQL_PASSWORD` | 离线 compose RAGFlow MySQL 密码(`:?` 必填) | 无 |
| `RAGFLOW_API_ENDPOINT` | backend 访问 RAGFlow 的地址 | `http://ragflow:80` |

> 滚动摘要阈值为**代码常量**(`agent/conversation_context.py`:`SOFT_TOKEN_LIMIT=3000` / `HARD_TOKEN_LIMIT=6000` / `RECENT_TURNS_SOFT=6`),不经环境变量配置。

## 5. 离线部署注意事项(2026-07 新增)

- **compose 内置 RAGFlow**(可选能力):`docker-compose.offline.yml` 新增 `ragflow` 服务(`infiniflow/ragflow:v0.16.0`,`pull_policy: never` → 需 `docker load` 离线加载)+ 配套 `ragflow-mysql`(`mysql:8.0`,`RAGFLOW_MYSQL_PASSWORD` 必填)。**未使用 compose profile**,随栈启动;可选性由「backend 故意不 `depends_on` ragflow」保证——RAG 故障不阻塞主站,仅知识库检索运行时优雅降级
- **默认 LLM 端点种子**:`deploy_offline.sh` 的 `migrate` 分支在 `manage.py migrate` 后自动执行 `manage.py seed_llm_endpoint`(**幂等:`LlmEndpoint` 表非空即跳过**,管理员已手动配置则不受影响),创建 `default-llm-endpoint`(`is_active`/`is_fallback`/`priority=1`)+ 配套 `LlmAppConfig(app_name="smart_assistant")`;支持 `--dry-run`
- **env 示例**:`.env.example` / `.env.production.example` 新增 `SEED_LLM_*` 三个注释示例变量;production 版补充告警——容器内 `localhost` 指向容器自身,Ollama 部署在宿主机时须改用宿主机内网 IP
- 离线三层一致性约束(镜像/compose/env)详见 [23-offline-deployment.md](./23-offline-deployment.md)

## 6. 模块覆盖率与质量

**2026-06-06 快照:模块总覆盖率 63.25%**(55 passed,远低于项目基线 80.89%)。

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

> 2026-07-29 注:增强轮次为全部新代码补齐测试(新增 `test_doctor` / `test_digest` / `test_session_fork_export` / `test_feedback_api` / `test_dataset_crud` / `test_hooks_builtin` / `test_tool_risk_level` / `test_mock_llm_e2e` 等),全量 pytest 1876 passed、前端 jest 488 passed(见增强计划步骤 17);模块级覆盖率重新度量待执行。

## 7. 开发状态(2026-07-29 更新)

| 阶段 | 状态 | 备注 |
|------|------|------|
| Phase 1:核心聊天 + 基础工具(3) | ✅ 已完成 | 实际已扩到 13 工具 |
| Phase 2:知识库文档上传与向量化 | ✅ 已完成 | 仅需配置 `SMART_ASSISTANT_DATASET_ID` |
| Phase 3:流式响应 + 对话历史 | ✅ 已完成 | 含多轮压缩(≤6/7-15/>15 三档) |
| Phase 4:审计面板 + 错误处理 | ✅ 已完成 | 含 3 级缓存、限流、token 用量统计 |
| Phase 5:深化设计(模型降级/多数据集 RAG/成本监控) | ✅ 已完成 | 见 [17-ai-assistant-deep-design.md](./17-ai-assistant-deep-design.md) |
| Phase 6:覆盖率补齐与质量守卫 | 🔄 进行中 | 见 [28-smart-assistant-coverage-roadmap.md](./28-smart-assistant-coverage-roadmap.md) |
| Phase 7:新工具(公告/合规/外部链接) | ✅ 已完成 | 2026-06 阶段 3 落地,13 工具齐备 |
| **2026-07-28 增强轮次(P0-P3,16 项)** | ✅ 已完成 | P0 恢复可用(失败不落库/聚合卡片修复/RAGFlow+种子)/ P1 闭环(成本/摘要/反馈/数据集 CRUD/LLM 统一)/ P2 架构(doctor/输出契约/Hooks/risk_level/Mock 测试)/ P3 主动式(多 Agent 面板/晨报/fork 导出);细节并入 §1~§11 各对应小节 |
| Phase 8:性能与体验(P1) | 📝 计划 | 性能基准实测见 [34-smart-assistant-perf-benchmark.md](./34-smart-assistant-perf-benchmark.md) |
| Phase 9:架构升级(ReAct + Reflexion)(P2) | 📝 计划 | — |

## 8. 分层权限与跨模块汇总(2026-07-07 新增)

智能助手已支持跨模块汇总查询和分层权限,详见 docs/superpowers/specs/2026-07-07-smart-assistant-cross-module-aggregation-design.md。

### 8.1 三层权限 scope

| Scope | 适用用户 | 数据范围 |
|---|---|---|
| SELF | 普通员工 | 仅本人相关 |
| DEPARTMENT | 部门主管 | 同部门 |
| GLOBAL | 管理员/superuser | 全公司 |

权限自动从 `request.user.has_perm()` 派生,无需前端传参。

### 8.2 跨模块汇总

用户问"这周我有哪些事"时,智能助手自动:
1. IntentClassifier 检测 `needs_multi_tool=True`
2. ToolChainPlanner 规划多工具(Schedule + MeetingRoom + Announcement)
3. ToolChainExecutor 按 scope 过滤每个工具的 QuerySet
4. ResultSynthesizer 聚合结果(时间排序 + 同主题合并 + 模块统计)
5. LLM 合成自然语言回答 + 前端 <AggregatedDayCard> 渲染卡片

### 8.3 启动时校验

`python manage.py check_tool_scopes` 在 CI 跑,确保所有 13 个工具实现 scope 抽象方法。

### 8.4 已知 gap(已修复 — Task 17, 2026-07-07)

| Gap | 状态 | 修复方式 |
|---|---|---|
| C1: `views/chat.py` 不传 user/scope,scope filter 在生产路径不生效 | ✅ 已修复 | view 层从 `request.user` 构造 `ToolContext(user, scope=resolve_scope(user))` 并传给 `orchestrator.process()/process_stream()` |
| C2: `module_counts`(snake_case) vs `AggregatedDayCard` 期望的 `moduleCounts`(camelCase)不匹配 | ✅ 已修复 | `result_synthesizer.py` 改返回 `moduleCounts`,所有调用方 / 测试同步更新 |
| C3: orchestrator 返回 `multi_tool_chain` 但 `ToolResult.jsx` 检查 `aggregated_day` | ✅ 已修复 | orchestrator `_process_chain()` 返回 `intent="aggregated_day"`,触发 `AggregatedDayCard` |
| C4: QuickCommands 派发的 `personal_summary` intent 后端未注册 | ✅ 已修复 | 前端 `QuickCommands.jsx` 把 `{intent, scope}` 翻译回自然语言 query(方案 B),走原 `query` 路径 |
| P0 漏洞: `cache_tool_result` 用 `context_sig=""` 不区分用户 → 缓存投毒 | ✅ 已修复 | cache.py + orchestrator 派生 `u<user_pk>_s<scope_value>` 并加入 cache key;E2E 测试 `test_e2e_cache_isolated_by_user_and_scope` 验证 |

修复详情见 Task 17 plan:`docs/superpowers/plans/2026-07-07-task17-fix-integration-gaps.md`

## 9. 决策与遗留项

### 9.1 架构决策

| 决策 | 理由 |
|------|------|
| Dify 维持 iframe 浅集成,不做服务端 API 集成 | YAGNI:当前无深度编排诉求;内网离线部署下 Dify 服务端栈成本高;iframe 已满足嵌入访问需求 |
| 晨报 MVP 面向 `is_active + is_staff` 用户 | 先小范围验证;后续按 `NotificationPreference` 订阅偏好放开(代码 TODO 已标注) |
| `seed_llm_endpoint` 幂等按「表非空」而非按 name 字段 | 语义是「管理员未配置过才播种默认端点」,避免与手动配置并存产生歧义 |
| `RagflowConfig.api_key` 复用 personnel 自研加密字段(XOR + base64) | 与 `LlmEndpoint.api_key` 同方案,零新依赖;安全强度满足内网场景 |

### 9.2 已知遗留项

| 遗留 | 说明 |
|------|------|
| 流式路径 `estimated_cost` 恒为 `None` | 流式调用暂无 usage 统计,成本核算仅覆盖同步路径 |
| 数据集 CRUD 无前端页面 | 后端 `KnowledgeDatasetViewSet` 就绪,前端仍依赖 Django admin 或 API 直调 |
| 多 Agent intervene 不支持「补充指令」 | 当前介入动作仅 `pause` / `resume` / `cancel`;如需向运行中任务注入指令,需后端扩展 intervene 端点 |
| Mock LLM 覆盖范围 | 仅模拟 OpenAI 兼容端点,未覆盖 tool-calls 路径与 Ollama 正向输出对比 |

---

## 11. chat 失败持久化 + Office 助手能力收敛（2026-07 P0 批次）

> 完整审计轨迹见 [41-p0-security-data-safety-batch-2026-07.md §1.8](41-p0-security-data-safety-batch-2026-07.md)。本节覆盖 P0-J(`last_error` 落库) 和 P0-K(office_assistant 能力收敛)。

### 11.1 `SmartAssistantSession.last_error` 字段（P0-J）

[`smart_assistant/models.py`](omni_desk_backend/smart_assistant/models.py) 历史 `SmartAssistantSession` 没有"上次失败原因"字段 —— 一旦 chat API 5xx,用户重试时看不到"上次为什么失败",debug 困难。**2026-07 批次**新增:

```python
class SmartAssistantSession(models.Model):
    # ... 原有字段 ...
    last_error = models.TextField(blank=True, default='')
```

[`views/chat.py`](omni_desk_backend/smart_assistant/views/chat.py) 在编排层(`AgentOrchestrator`)异常逃逸时持久化:

```python
except LLMError as e:
    session.refresh_from_db()
    session.last_error = f"{type(e).__name__}: {e}"
    session.save(update_fields=['last_error'])
    return Response({'detail': str(e)}, status=500)

except SmartAssistantSession.DoesNotExist:
    logger.warning("invalid conversation_id=%s from user=%s",
                   conversation_id, request.user.id)
    return Response({'detail': 'session not found'}, status=404)
```

**两层防护:**

1. **流式/非流式路径统一捕获:** 同步 chat 与 SSE chat 都在 `orchestrator.process*` 入口 `try/except`,异常都写 `last_error` 后再上报
2. **`SmartAssistantSession.DoesNotExist` → 404:** 历史实现静默放过"无效 conversation_id",不报错,前端无感知;现显式返 404,前端可正确处理

**API 行为:** `GET /api/smart-assistant/sessions/{id}/` 响应新增 `last_error` 字段,前端可在 session 历史面板显示上次失败原因。

### 11.2 Office 助手能力收敛（ALLOWED_ACTIONS,P0-K）

[`office_assistant/views.py`](omni_desk_backend/office_assistant/views.py) 历史实现对前端传来的 `action` 字段**不显式校验**,LLM router 会尝试执行任意 action —— 包括文档实际不支持的(`extract_entities`、`summarize_long_doc` 等),最终 500 或返回空字符串。

**2026-07 批次**强制白名单:

```python
ALLOWED_ACTIONS = ('proofread', 'translate', 'polish')

def post(self, request):
    action = request.data.get('action')
    if action not in ALLOWED_ACTIONS:
        return Response(
            {'detail': f'unsupported action: {action}, supported: {list(ALLOWED_ACTIONS)}'},
            status=400,
        )
    # ... 原有处理 ...
```

**收敛范围:** 仅支持"文本级"操作,与前端文档/UI 实际支持的 3 项一致。**注意:** `summarize` / `extract_keywords` 暂未列入,因为：

- 当前文档解析通道(MinerU)未对这些长操作做过鲁棒性测试
- 留作 P1 加入,届时同步更新前端的"操作面板"

### 11.3 测试覆盖

| 测试文件 | 覆盖范围 |
|---|---|
| `smart_assistant/tests/test_chat_last_error.py` | mock LLM 抛 `RuntimeError('boom')`, 跑 POST chat → 断言 `r.status_code==500` + `SmartAssistantSession.objects.latest().last_error=='boom'` |
| `smart_assistant/tests/test_chat_invalid_conversation_404.py` | 传不存在的 conversation_id → 404 + `detail='session not found'` |
| `office_assistant/tests/test_capability_scope.py` | `action='extract_entities'` → 400;合法 action 仍正常处理 |
| `office_assistant/tests/test_three_allowed_actions.py` | 三种合法 action 都成功执行 |

### 11.4 用户侧效果

- 智能助手面板"历史会话"显示 "⚠️ 上次失败:LLMError: timeout"
- Office 助手面板误点击"实体抽取"等不存在功能时,精确提示"暂不支持,当前仅 proofread / translate / polish"
- 运维查 `session.last_error` 能区分真实 bug 与 LLM 端点暂时不可用

> ⚠️ **架构注记:** chat 失败落库的关键是它走**编排层**(LangGraph / 自研 orchestrator)异常逃逸,因此可以在最外层 try/except 中捕获写库。如果未来改为把 chat 拆成 Celery 异步任务,`last_error` 写入逻辑要相应迁移到任务回调。


## 12. Office 文件附件能力（2026-08 阶段 1）

> 📅 **归档于 2026-08-06** — 原实施计划与设计 spec 已归档后删除(`docs/superpowers/plans/2026-08-05-sa-office-files.md` + `docs/superpowers/specs/2026-08-05-sa-office-files-design.md`),本节即为该计划的完整归档。共 18 个 commit 已合入 `feat/sa-office-files` 分支。

### 12.1 目标

让用户**直接在智能助手聊天流中**完成"看文件 / 问表格 / 生成文档"三类操作:

1. **Chat 附件上传**: `chat/` 与 `chat/stream/` 支持 multipart 附件上传
2. **OfficeExtractor 统一抽取**: docx / pdf / xlsx / pptx / txt / md / csv → 文本 / 表格 / Markdown
3. **3 个新工具注册**: `OfficeReadTool` / `OfficeGenerateTool` / `SpreadsheetTool`
4. **聊天内下载卡片**: 生成的 .docx 通过下载卡片交付
5. **附件临时读取**: 不入库、不落盘(生成产物除外),用完即弃

### 12.2 架构

```
┌─ 前端 ─────────────────────────────────────┐
│ SmartChatPage / QuickAssistant             │
│  ├─ 输入框旁: Upload 按钮(附件选择)        │
│  └─ 消息流: ToolResult 渲染下载卡片         │
└──────────────┬─────────────────────────────┘
               │ POST chat/stream/ (multipart: query + attachment)
               ▼
┌─ 后端 ─────────────────────────────────────┐
│ chat.py (MultiPartParser)                   │
│  → 附件 → magic MIME 校验 → 大小校验(10MB) │
│  → OfficeExtractor 抽取 (docx/pdf/xlsx/     │
│     pptx/txt/md/csv)                        │
│  → 切片策略: <50k 字符全量注入, >50k 注入   │
│    前 2 片 + 提示 LLM 可用 ReadTool 按需读  │
│  → 附件上下文拼入 prompt                    │
│  → LLM: 直接回答 / 调工具                   │
│                                            │
│ ToolRegistry 新增:                          │
│  ├─ OfficeReadTool  (read)                  │
│  ├─ OfficeGenerateTool (write+确认)         │
│  └─ SpreadsheetTool (read)                  │
│                                            │
│ 生成结果 → 临时 .docx 文件 + 短期签名 token  │
│  → GET /office-download/<token>/ 返回 blob  │
└────────────────────────────────────────────┘
```

**关键约束**:

- **附件上下文与历史消息隔离**:抽取内容只存在于本次请求内存,不写 `ChatMessage`
- **工具层薄**:复用 `BaseTool` / `ToolRegistry` / confirm-replay 基础设施
- **Extractor 独立**:可单测、可替换格式处理器
- **零模型改动**:不新增持久化字段,无数据库迁移

### 12.3 后端组件

| 文件 | 操作 | 说明 |
|------|------|------|
| `extractors/office_extractor.py` | 新 | 统一抽取器,`ExtractedDocument` dataclass(text / markdown / tables / sheets / metadata) + `chunk_text()` 切片 |
| `tools/office_read_tool.py` | 新 | `office_read` 工具,`risk_level="read"`,按 `file_index + chunk_range` 从附件上下文缓存读取切片 |
| `tools/office_generate_tool.py` | 新 | `office_generate` 工具,`risk_level="write"` + `require_confirmation=True`,python-docx 构建标题/段落/表格 + 变量替换,支持 confirm-replay |
| `tools/spreadsheet_tool.py` | 新 | `spreadsheet_qa` 工具,`risk_level="read"`,openpyxl → pandas DataFrame,简单聚合/groupby + 复杂问答复用 `NaturalLanguageQuery` |
| `views/office_download.py` | 新 | `office_download` action,签名 token 验证(JWT 鉴权仍要),10 分钟过期,下载后删除 |

### 12.4 格式路由表

| 格式 | 处理器 | 关键库 |
|------|--------|--------|
| `.docx` | python-docx 抽段落+表格 + mammoth 转 Markdown | `python-docx`, `mammoth` |
| `.pdf` | pdfplumber 抽文本 + 表格 | `pdfplumber` |
| `.xlsx` | openpyxl 遍历 sheet → markdown / json | `openpyxl` |
| `.pptx` | python-pptx 抽文本 + 备注 + 表格 | `python-pptx`(本批新依赖,`>=0.6.21`) |
| `.txt` / `.md` | 直接 decode utf-8 | — |
| `.csv` | 读取 + pandas 转 markdown + 编码回退 | `pandas` |

**显式拒绝**: `.doc` / `.xls` / `.ppt`(老格式,需 LibreOffice;阶段 2+ 再考虑)。

### 12.5 修改文件清单

| 文件 | 改动 |
|------|------|
| `serializers.py` | `SmartChatRequestSerializer` 增加 `attachment = FileField(required=False, allow_null=True)` |
| `views/chat.py` | `create` / `stream` 加 `parser_classes = [MultiPartParser, FormParser]`;附件接收 → 校验 → 抽取 → 注入 prompt |
| `apps.py` | `ready()` 注册 3 个新工具 |
| `urls.py` | 增加 `office-download/<str:token>/` 路由 |
| `cache.py` / 新 `office_attachment.py` | 附件内容按 `conversation_id + file_hash` 短时缓存(TTL 10 分钟);生成临时文件注册清理 |
| `requirements.in` / `.txt` / `-prod.txt` | 新增 `python-pptx>=0.6.21`(由 pip-compile 重生成锁) |

### 12.6 SSE 契约扩展(向后兼容)

`chat/stream/` 的 SSE 事件中,`tool_result` 新增可选字段:

```json
{
  "intent": "office_generate",
  "tool_result": {
    "file_download": {
      "filename": "请假单.docx",
      "download_url": "/api/smart-assistant/office-download/<token>/",
      "content_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    }
  }
}
```

旧前端忽略该字段即可,兼容。

### 12.7 性能与缓存

- **附件抽取**: `conversation_id + file_hash` 作 key,TTL 10 分钟;重复提问同一附件不重复抽取
- **附件内容注入**: <50k 字符全量,>50k 只注入前 2 片约 16k 字符 + 提示 LLM 可调 `office_read`
- **确认流**: 复用现有 confirm-replay 缓存(`set_confirmation_draft`),`_confirmed` 优先用 `ctx.draft_fields` 避免二次 LLM 规划

### 12.8 错误处理

| 场景 | 行为 |
|------|------|
| 不支持的格式(.doc/.xls/.ppt) | 前端拦截 + 后端 magic 校验 → 400「暂不支持该格式,支持 .docx/.pdf/.xlsx/.pptx/.txt/.md/.csv」 |
| 文件过大(>10MB,`MAX_OFFICE_UPLOAD_SIZE`) | 前端 + 后端双重校验 → 400 |
| MIME 伪装 | python-magic 检测真实类型不符 → 400 |
| 损坏文件 / 抽取失败 | `OfficeExtractError` → 400「文件无法解析,请确认文件未损坏」 |
| 空文件 / 无可抽取内容 | 提示「未从文件中提取到文本内容,可能为纯图片扫描件」 |
| 生成确认超时 | confirm_token 过期 → 400「确认已过期,请重新发起」 |
| 下载 token 过期 / 已使用 | 403「链接已失效,请重新生成」 |

### 12.9 安全

- **鉴权**: `office-download` 端点仍要求 JWT 鉴权(token 仅防 URL 猜测,不替代登录)
- **大小**: `MAX_OFFICE_UPLOAD_SIZE = 10MB` 常量,前后端一致
- **签名 token**: `secrets.token_urlsafe(32)` + 过期时间戳 + HMAC 签名(`settings.SECRET_KEY`)
- **敏感信息**: 抽取文本注入 LLM 前过现有 `PiiMaskingHook`
- **临时文件**: 下载后即删;未被下载的由 Celery 定时清理(TTL 10 分钟)
- **零迁移**: 不新增持久化字段,无数据库迁移

### 12.10 关键设计决策

| 决策 | 原因 |
|------|------|
| 附件上下文以 `role="system"` 消息 prepend | `_select_recent_messages` 必须保留 system 消息,否则 token 截断可能丢掉附件内容 |
| 生成产物仅写临时文件 + 签名 token | 阶段 1 无个人文档库,生成文档用完即弃;`MEDIA_ROOT/tmp_office/` |
| `OfficeGenerateTool` 走 confirm-replay | 与现有 swap 工具一致的 UX;前端 ConfirmModal 复用 |
| SSE 流式补充 confirm-replay 拦截(spec 未明写) | 探索发现 `process_stream`(SSE 路径)没有 confirm-replay 拦截,只有非流式 `process()` 有;不补则 `OfficeGenerateTool`(`require_confirmation=True`)在聊天主界面(SSE)下确认流不可用。此改动同时修复现有 swap 工具在 SSE 下的同类 gap |
| python-pptx 只用于"读" | 写 PPT 复杂版式差;阶段 1 仅读不写,延后到阶段 2 再决定 |
| 切片阈值 50k / 8000 字符 | 实测一般长文档 50k 字符 ≈ 25k token,LLM 上下文一般可承载;>50k 让 LLM 自助用 `office_read` 按需读取 |

### 12.11 与现行架构的关系

- **不入库**: 附件内容只读,不写 `ChatMessage`,不创建 `DocumentTemplate` / `GeneratedDocument`
- **依赖现有工具链**: 复用 `BaseTool` / `ToolRegistry` / `confirm-replay` / `SSE` 全套基础设施
- **不影响现有 14 个工具**: 3 个新工具独立注册,无冲突
- **Win7 兼容**: 下载卡片用 `URL.createObjectURL` + `<a download>`,AntD 5 现有能力


## 13. 原生 Function Calling(L1,2026-08-06 实施;L1.1 加固,2026-08-09)

智能助手的 LLM router 现已支持 OpenAI 兼容协议的原生 tool_calls / tool_choice。
实现细节见 `docs/superpowers/specs/2026-08-06-native-function-calling-design.md`;
L1.1 加固(流式原生 tool_calls / 结构化参数透传 / 写工具确认)见
`docs/superpowers/specs/2026-08-09-native-function-calling-hardening-design.md`。

### 13.1 协议支持

- LLM 端点必须支持 OpenAI `/v1/chat/completions` 的 `tools=[...]` + `tool_choice` 参数
- doctor 自检的 `native_tool_calls` 项自动探测并缓存到 `LlmEndpoint.model_capabilities`
- 旧端点自动降级到 JSON 路径(`AgentLog.tool_call_path="json"`)

### 13.2 主循环

- 最多 3 轮,3 轮后强制 `tool_choice="none"` 让 LLM 给出最终回答
- 工具调用错误分 4 类:invalid_arguments / tool_unavailable_for_user / tool_timeout / execution_failed
- LLM 通常会自动重选工具
- **L1.1(I-2)**:工具参数由 LLM 给出完整 validated dict,经 `_execute_native_tool()`
  **整体透传**给 `execute_guarded(tool, params=validated, ...)`;`query` 仍由
  `_dict_to_query()` 提取供确认/审计/日志/回退用,但结构化字段(date_from /
  chunk_index / department / status / is_completed / limit / target_date …)不再丢失,
  Tier 1 工具显式消费(排班日期范围 / office_read 切片 / personnel 部门与在职状态 /
  memo 完成态 / 条数上限 / event 与 meeting_room 目标日期)。缺失时回退现有 query
  解析,零回归(行为与 JSON 路径一致)

### 13.3 决策日志

`AgentLog.tool_calls_meta` 字段记录每轮:
- `round`(0-indexed)
- `tool`(intentional_type)
- `arguments`(LLM 给的参数,用于 A/B 评估)
- `duration_ms`(工具执行耗时)
- `error`(失败原因)

缓存 key 额外纳入 `tool_call_path` 维度,避免 A/B 切换时 native/json 两路径
的缓存互相污染。

### 13.4 灰度策略

- 默认:仅 `is_staff=True` 用户启用新路径(无用户上下文的内部调用同样走 JSON)
- 验证 1 周后,通过 settings `USE_NATIVE_TOOL_CALLS_FOR_ALL=True` 全员开放
- 单次调用可用 `process(use_native_tool_calls=True/False)` / `process_stream(...)`
  kwarg 强制覆盖路由

### 13.5 相关配置

| settings | 默认 | 说明 |
|---|---|---|
| `USE_NATIVE_TOOL_CALLS` | `true` | 原生 tool_calls 总开关 |
| `MAX_TOOL_CALLS_ROUNDS` | `3` | 单次 agent 调用最大工具轮数 |
| `TOOL_CALLS_TIMEOUT_SECONDS` | `30` | 单次工具调用超时(秒) |
| `USE_NATIVE_TOOL_CALLS_FOR_ALL` | `false` | L1 灰度:置 `true` 全员开放原生路径 |

### 13.6 流式原生 tool_calls(L1.1 F2,2026-08-09)

`process_stream()` 现支持原生 tool_calls 流式分支,与 `process()` 对称:

- **门控一致**:`USE_NATIVE_TOOL_CALLS` + endpoint 能力 + staff(或 FOR_ALL 开关);
  原生分支外层异常 → 输出失败回答 + kind/hint(不抛给视图层、不回退 intent);
  工具轮内 `generate_with_tools` 异常 → 降级到 JSON 路径(回答质量对等)
- **缓冲工具轮**:`_run_tool_calls_rounds()` 复用非流式工具轮(最多 3 轮,scope-aware +
  完整 hook 链 + confirm-replay + I-2 透传),首轮无 tool_calls 时直接单 chunk 输出
- **流式最终轮**:工具轮实际执行过后,用 `router.generate(messages=final_messages,
  stream=True)` 重生成,逐 chunk yield —— 真打字动画(仅当工具轮执行过才重生成,
  无工具轮零额外成本)
- **确认透传**:写工具命中 `Reject(confirmation_required)` → dry_run → draft → yield
  `awaiting_confirmation + confirmation_token` 事件 → 前端确认后 replay 视图执行
- **SSE 契约**:非确认场景先发 meta(前端依赖 `types[0]=="meta"`),再 chunk,最后
  done(`error=is_failed_answer`),与现有流式契约一致
- **跳过 intent 单工具路由 + tool_chain 检测**:原生开启时跳过 `classify_intent`
  结果驱动的单工具路由与 `generate_tool_chain_plan` 检测(aggregated_day 仍走非原生
  路径);无历史时 `classify_intent` 仍作为回答缓存键执行
- **确认边界(仅单工具路径)**:写工具二次确认(ConfirmationHook)只保证**单工具路径**
  (native/JSON/intent 单工具);多工具链路径(`tool_chain_executor` 只走 `execute_guarded`
  超时守卫,不接 `apply_pre_execute_hooks`)暂不拦截 —— 链式计划不应包含写工具
  (aggregated_day 等均为只读聚合),LLM 生成的多工具 plan 默认无写工具场景


## 10. 相关文档

- [17-ai-assistant-deep-design.md](./17-ai-assistant-deep-design.md) — 多轮对话、工具链、模型降级、成本监控
- [28-smart-assistant-coverage-roadmap.md](./28-smart-assistant-coverage-roadmap.md) — 覆盖率补齐与守卫策略
- [32-smart-assistant-multi-agent.md](./32-smart-assistant-multi-agent.md) — 多 Agent 执行器 / Hook 系统 / 任务 API
- [33-ragflow-integration.md](./33-ragflow-integration.md) — RAGFlow API 客户端与部署
- [34-smart-assistant-perf-benchmark.md](./34-smart-assistant-perf-benchmark.md) — 性能基准实测
- [23-offline-deployment.md](./23-offline-deployment.md) — 离线部署三层一致性约束
- [用户操作手册](../user-manual/08-smart-assistant-usage.md) — 终端用户使用指南
