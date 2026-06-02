# AI 助手深化设计

> 智能助手的深化架构设计，覆盖多轮对话、工具链、模型降级等核心能力。

## 1. 架构概览

```
用户输入 → AgentOrchestrator
  ├── ConversationContext（多轮历史管理 + 滚动摘要）
  ├── IntentClassifier（意图分类 + 置信度）
  ├── ToolChainPlanner（多工具计划生成）
  ├── ToolChainExecutor（工具链执行）
  ├── ResultSynthesizer（结果综合）
  └── LLMRouter（模型路由 + 降级）
       ├── Tier 1: 主模型（LlmAppConfig 按 priority）
       ├── Tier 2: 备用模型（is_fallback=True）
       └── Tier 3: 本地 Ollama（qwen2.5:7b）
```

## 2. 多轮对话系统

### 2.1 ConversationContext

文件：`smart_assistant/agent/conversation_context.py`

| 功能 | 说明 |
|------|------|
| 历史加载 | 从 `SmartAssistantSession.messages` 加载 |
| 消息追加 | 支持 tool_call 元数据 |
| 构建 messages | system prompt + 早期摘要 + 最近轮次 |
| Token 估算 | 中文 ~1.5 字符/token，英文 ~4 字符/token |

### 2.2 上下文窗口管理

| 对话阶段 | 处理方式 |
|----------|----------|
| ≤ 6 轮 | 全部保留原始消息 |
| 7–15 轮 | 前 N-6 轮压缩为摘要，最近 6 轮保留原文 |
| > 15 轮 | 触发 Celery 异步任务生成长期摘要，保留摘要 + 最近 3 轮 |

### 2.3 模型字段

`SmartAssistantSession` 新增：`summary_text`、`summary_token_count`、`turn_count`

迁移文件：`0006_add_conversation_context_fields.py`

## 3. 工具链（Multi-Tool Chaining）

### 3.1 执行流程

```
Level 1: IntentClassifier → 识别主意图 + 检测是否需要多工具
Level 2: ToolChainPlanner → LLM 生成工具执行计划
Level 3: ToolChainExecutor → 按依赖顺序执行，变量替换
Level 4: ResultSynthesizer → 综合多工具结果生成最终回答
```

### 3.2 工具清单（12个）

| 工具 | 数据源 | 功能 |
|------|--------|------|
| `ScheduleTool` | events.Schedule | 排班/值班查询 |
| `PersonnelTool` | personnel.Personnel | 人员信息查询 |
| `RAGTool` | Ragflow | 知识库问答 |
| `DocumentTool` | documents | 公文/文档搜索 |
| `EventTool` | events | 事件/日程/节假日 |
| `MemoTool` | memos | 备忘录查询 |
| `ProjectTool` | projects | 项目进度查询 |
| `NewsTool` | news | 新闻/通知搜索 |
| `MeetingRoomTool` | meeting_rooms | 会议室可用性 |
| `SensorTool` | sensor_management | 传感器数据/告警 |

### 3.3 BaseTool 接口扩展

新增方法：`get_examples()`、`validate_params()`、`aexecute()`（异步）

文件：`smart_assistant/agent/tool_chain_planner.py`、`tool_chain_executor.py`

## 4. 模型故障自动降级

### 4.1 LLMRouter

文件：`llm_service/router.py`

降级链路：
1. **Tier 1**: 主模型（`LlmAppConfig` 按 `priority` 升序）
2. **Tier 2**: 备用模型（`is_fallback=True`）
3. **Tier 3**: 本地 Ollama（qwen2.5:7b）

### 4.2 LlmEndpoint 扩展字段

| 字段 | 说明 |
|------|------|
| `priority` | 优先级，1=主 |
| `is_fallback` | 是否为备用 |
| `model_capabilities` | `["chat", "embedding", "vision"]` |
| `rate_limit_per_minute` | 速率限制 |
| `cost_per_1k_tokens` | 成本估算 |

## 5. 多数据集 RAG 路由

### 5.1 KnowledgeDataset 模型

| 字段 | 说明 |
|------|------|
| `name` | 数据集名称（唯一） |
| `ragflow_dataset_id` | Ragflow 数据集 ID |
| `is_active` | 是否启用 |
| `tags` | 标签（用于匹配查询） |
| `document_count` | 文档数量 |

### 5.2 RAGRouter

文件：`smart_assistant/agent/rag_router.py`

1. 基于 tags 关键词匹配最相关知识库
2. 并行搜索多个知识库
3. 合并、去重、排序返回 Top-K 片段

## 6. 成本监控与用量分析

### 6.1 AgentLog 扩展字段

| 字段 | 说明 |
|------|------|
| `model_name` | 使用的模型名称 |
| `input_tokens` / `output_tokens` / `total_tokens` | Token 用量 |
| `estimated_cost` | 费用估算 |
| `response_time_ms` | 响应时间 |
| `tool_success` | 工具执行是否成功 |
| `user_feedback` | `'up'` / `'down'` |

### 6.2 用量分析 API

| 端点 | 说明 |
|------|------|
| `GET /api/smart-assistant/usage/stats/` | 聚合统计（总查询、总token、费用、意图分布、工具成功率） |
| `GET /api/smart-assistant/usage/daily/` | 每日用量趋势 |
| `GET /api/smart-assistant/usage/user/{user_id}/` | 用户级别用量 |

## 7. 前端体验

### 7.1 Markdown 渲染

- `react-markdown` + `remark-gfm`（表格/任务列表）
- 流式打字效果
- `<thinking>` 标签折叠展示

### 7.2 ToolResult 组件

支持多种工具结果的结构化渲染：排班卡片、人员卡片、知识来源引用、审批状态、会议室可视化等。

### 7.3 用户反馈

每条 AI 消息底部提供点赞/点踩、复制、重试按钮。反馈数据回写 `AgentLog.user_feedback`。

## 8. 置信度与错误恢复

| 置信度 | 操作 |
|--------|------|
| ≥ 0.8 | 直接执行 |
| 0.5–0.8 | 执行，标注不确定性 |
| < 0.5 | 向用户确认意图 |

工具执行失败时降级到第二意图，或提示用户换一种方式提问。

## 9. 运营仪表盘

`/smart-assistant/audit` — 管理面板：

- 概览卡片：今日对话数、Token 消耗、费用估算、平均响应时间
- 意图分布图（饼图）
- 工具成功率（柱状图）
- 每日用量趋势（折线图）
- 异常告警列表

## 10. 待实现项

| 项目 | 说明 |
|------|------|
| ApprovalTool | 审批状态查询工具 |
| ReportTool | 周期性报告生成工具 |
| 前端反馈按钮 UI | 后端字段已就绪，前端按钮待添加 |
| 建议追问区 | AI 回答后显示 3 个建议追问 |
