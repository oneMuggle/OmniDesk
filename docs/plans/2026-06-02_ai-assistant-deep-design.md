# AI 应用助手深化设计方案

> 日期：2026-06-02
> 状态：Phase 1 + 2 + 3 + 4 已完成
>
> **本文档是 `docs/plans/2026-05-17_smart-assistant-enhancement.md` 的深化补充**，
> 在原有 5 个 Phase 的基础上，增加问题根因分析、详细组件设计和架构演进方案。

---

## 一、现状概述

OmniDesk 的 AI 助手系统由以下模块组成：

| 模块 | 职责 |
|------|------|
| `smart_assistant` | 核心 AI Agent：意图分类 → 工具路由 → LLM 回答，SSE 流式对话，会话管理，审计日志 |
| `llm_service` | LLM 客户端库：OpenAIClient + OllamaClient |
| `dify_apps` | 第三方 Dify 应用嵌入 |
| `ragflow_service` | Ragflow 知识库集成 |
| `office_assistant` | 文档文本处理（校对/翻译/润色） |

**核心架构**：单轮、单工具、意图分类后执行。支持 4 种意图（`schedule_query`、`personnel_query`、`knowledge_qa`、`general_chat`）和 3 个工具（ScheduleTool、PersonnelTool、RAGTool）。

---

## 二、深化设计目标

### 2.1 P0 级（必须修复）

1. **多轮对话真正生效** — 当前会话历史被存储但从未传入 LLM，后续追问完全丢失上下文
2. **工具链 / 多步推理** — 当前只能选一个工具，复杂查询需要组合多个数据源
3. **模型故障自动降级** — 单一 LLM 端点，无 fallback，一旦不可用全系统瘫痪

### 2.2 P1 级（核心增强）

4. **工具生态扩展** — 仅 3 个工具，大部分业务查询落到通用聊天
5. **前端 Markdown 渲染** — 回答以纯文本展示，无表格/代码块/列表渲染
6. **多数据集 RAG 路由** — 单一知识库，无 fallback
7. **上下文窗口管理** — 长对话超出 token 限制无处理策略

### 2.3 P2 级（运营优化）

8. **成本监控与用量分析** — 无 token 计数、无费用追踪
9. **管理分析仪表盘** — 无聚合指标展示
10. **自我反思 / 错误恢复** — 意图分类错误无纠正路径
11. **用户反馈收集** — 无点赞/点踩机制

---

## 三、深化设计方案

### 3.1 多轮对话系统

#### 3.1.1 问题根因分析

`SmartAssistantSession.messages`（`smart_assistant/models.py:43`）存储了完整对话历史，但：

- `generate_answer()`（`intent_classifier.py:25-40`）不传入 history
- `generate_general_answer()`（`intent_classifier.py:62-68`）不传入 history
- `OpenAIClient.generate()`（`openai_client.py:75-109`）虽然内部支持 `messages` 数组（line 87-90），但调用方只传了单个 prompt 字符串

**结论**：系统存储了对话历史但从未将其用于 LLM 上下文。每一轮对话对 LLM 来说都是无状态的。后续追问如"第二天呢？"完全丢失。

#### 3.1.2 设计方案

**历史注入层**：在 `AgentOrchestrator` 中增加 `ConversationContext` 类：

```python
class ConversationContext:
    def load_history(self, session_id)        # 从 Session.messages 加载
    def append(self, role, content, meta={})  # 追加消息（支持 tool_call 元数据）
    def build_messages(self)                  # 构建 LLM messages 数组
        # ├── system prompt
        # ├── [summarized_old_turns]           # 早期轮次摘要（见 3.1.3）
        # └── [recent_turns]                  # 最近 N 轮原始消息
    def estimate_tokens(self)                 # 预估 token 数
```

**调用链路改造**：

```
用户输入 → AgentOrchestrator.process()
  ├── load ConversationContext from session
  ├── classify_intent(query, schemas, conversation_history)  # 分类器也接收历史
  ├── tool.execute(query, context={history: ..., session: ...})
  ├── generate_answer(query, intent, tool_name, tool_result, conversation_history)  # 注入历史
  └── save updated context back to session.messages
```

**关键改动文件**：
- `smart_assistant/agent/conversation_context.py` — 新建
- `smart_assistant/agent/intent_classifier.py` — `classify_intent()` 和 `generate_answer()` 接收 history
- `smart_assistant/views/chat.py` — 传递 conversation_history
- `llm_service/openai_client.py` — 暴露 `generate_with_messages(messages, ...)` 方法

#### 3.1.3 上下文窗口管理

策略：**滚动摘要 + 最近窗口**

| 对话阶段 | 处理方式 |
|----------|----------|
| ≤ 6 轮 | 全部保留原始消息 |
| 7–15 轮 | 前 N-6 轮压缩为摘要，最近 6 轮保留原文 |
| > 15 轮 | 触发后台 Celery 任务生成长期摘要，只保留摘要 + 最近 3 轮 |

摘要生成：在对话达到阈值时，异步调用 LLM 用低成本模型（Haiku 或本地 Ollama）对旧消息做摘要，存储到 `Session.summary_text`。

**模型字段新增**：
```python
class SmartAssistantSession(models.Model):
    # 新增字段
    summary_text = models.TextField(blank=True, default='')
    summary_token_count = models.IntegerField(null=True)
    turn_count = models.IntegerField(default=0)
```

---

### 3.2 工具链（Multi-Tool Chaining）

#### 3.2.1 问题根因

`AgentOrchestrator`（`orchestrator.py:15`）只选择一个工具执行，无法处理"查询张三的值班安排并检查他是否有未审批的流程"这类复合查询。

#### 3.2.2 设计方案

**两层工具路由**：

```
Level 1: Intent Classifier → 识别主意图 + 检测是否需要多工具
  ├── single_tool: 直接执行（保持现有路径）
  └── multi_tool: 进入 Plan-and-Execute 路径

Level 2: Tool Chain Planner
  ├── 解析用户意图，生成工具执行计划
  ├── 计划格式: List[{tool_name, parameters, depends_on}]
  └── 顺序执行，后一个工具可依赖前一个的输出
```

**执行计划示例**：

```json
{
  "plan": [
    {"tool": "schedule_tool", "params": {"date": "明天", "person": "张三"}, "depends_on": null},
    {"tool": "approval_tool", "params": {"person": "$schedule_tool.person"}, "depends_on": "schedule_tool"}
  ],
  "final_synthesis": "结合两个工具的结果，生成综合回答"
}
```

**新增组件**：

| 组件 | 文件 | 职责 |
|------|------|------|
| `ToolChainPlanner` | `smart_assistant/agent/tool_chain_planner.py` | LLM 生成工具执行计划 |
| `ToolChainExecutor` | `smart_assistant/agent/tool_chain_executor.py` | 按依赖顺序执行工具，注入变量替换 |
| `ResultSynthesizer` | `smart_assistant/agent/result_synthesizer.py` | 综合多工具结果生成最终回答 |

**BaseTool 接口扩展**：

```python
class BaseTool:
    # 现有
    def execute(self, query, context=None) -> dict
    def get_schema(self) -> dict

    # 新增
    def get_examples(self) -> list[str]       # few-shot 示例
    def validate_params(self, params) -> bool # 参数校验
    async def aexecute(self, query, context=None) -> dict  # 异步支持
```

**新增工具（P1 优先级）**：

| 工具 | 意图 | 数据源 | 功能 |
|------|------|--------|------|
| `ApprovalTool` | `approval_query` | `projects` / `compliance` app | 查询审批状态、待办列表 |
| `MeetingRoomTool` | `meeting_room_query` | `meeting_rooms` app | 查询会议室可用性和预订 |
| `SensorTool` | `sensor_query` | `sensor_management` app | 查询传感器数据和告警 |
| `ProjectTool` | `project_query` | `projects` app | 查询项目进度、里程碑 |
| `DocumentTool` | `document_query` | `documents` app | 文档检索、摘要生成 |
| `ReportTool` | `report_query` | 多模型聚合 | 生成周期性报告 |

**意图分类扩展**：新增 `approval_query`、`meeting_room_query`、`sensor_query`、`project_query`、`document_query`、`report_query`。

---

### 3.3 模型故障自动降级（Model Fallback）

#### 3.3.1 问题根因

`OpenAIClient` 只配置一个端点，该端点不可用时没有任何降级手段。

#### 3.3.2 设计方案

**三层降级策略**：

```
Tier 1: 主模型（配置的 OpenAI-compatible 端点）
  ↓ 连接超时 / 5xx / 429
Tier 2: 备用模型（配置第二个 LlmEndpoint，标记为 fallback）
  ↓ 连接超时 / 5xx / 429
Tier 3: 本地 Ollama（预设轻量模型）
  ↓ 不可用
Fallback: 缓存回答 / 返回"服务暂时不可用"
```

**LlmEndpoint 模型扩展**：

```python
class LlmEndpoint(models.Model):
    # 新增字段
    priority = models.IntegerField(default=1)        # 优先级，1=主
    is_fallback = models.BooleanField(default=False)   # 是否为备用
    model_capabilities = models.JSONField(default=list) # ["chat", "embedding", "vision"]
    rate_limit_per_minute = models.IntegerField(null=True)
    cost_per_1k_tokens = models.DecimalField(null=True)
```

**LLMRouter 组件**：

```python
class LLMRouter:
    def get_client(self, app_config: LlmAppConfig) -> BaseLLMClient:
        """按优先级获取可用的 LLM 客户端"""

    def execute_with_fallback(self, request, clients) -> LLMResponse:
        """带降级的 LLM 调用，自动切换备用端点"""

    def record_failure(self, endpoint_id, error_type)
    def record_success(self, endpoint_id, latency, tokens)
```

**关键改动文件**：
- `smart_assistant/models.py` — LlmEndpoint 新增字段
- `llm_service/router.py` — 新建 LLMRouter
- `llm_service/base_client.py` — 新建抽象基类
- `smart_assistant/agent/intent_classifier.py` — 使用 LLMRouter 替代直接实例化

---

### 3.4 前端 Markdown 渲染

#### 3.4.1 设计方案

**消息渲染升级**：

```
SmartChatPage.jsx
├── MessageBubble
│   ├── 用户消息: 保持现有样式
│   └── AI 消息:
│       ├── <thinking> 标签: 折叠展示（现有）
│       ├── ToolResult 组件: 结构化卡片（现有，增强样式）
│       └── 文本内容:
│           ├── react-markdown 渲染
│           ├── remark-gfm (GFM 表格/任务列表)
│           ├── react-syntax-highlighter 代码高亮
│           └── 自定义组件: 表格、列表、公式
├── 新增: 消息操作栏
│   ├── 复制按钮
│   ├── 点赞/点踩按钮
│   └── 重试按钮
└── 新增: 建议追问区
    └── AI 回答结束后显示 3 个建议追问
```

**依赖新增**：
- `react-markdown` — Markdown 渲染
- `remark-gfm` — GFM 表格/任务列表支持
- `react-syntax-highlighter` — 代码高亮
- `react-copy-to-clipboard` — 复制功能

**ToolResult 增强**：

```
ToolResult.jsx
├── ScheduleResult — 可点击的排班卡片
├── PersonnelResult — 人员详情卡片（带头像/部门）
├── KnowledgeResult — 知识来源引用（带跳转链接）
├── ApprovalResult — 审批状态时间线
├── MeetingRoomResult — 会议室可用时间段可视化
├── SensorResult — 传感器数据迷你图表
└── ErrorResult — 工具执行失败的友好提示
```

---

### 3.5 多数据集 RAG 路由

#### 3.5.1 设计方案

**知识库注册表**：

```python
class KnowledgeDataset(models.Model):
    """替代单一 SMART_ASSISTANT_DATASET_ID 配置"""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField()
    ragflow_dataset_id = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    tags = models.JSONField(default=list)  # ["HR", "技术", "政策"]
    document_count = models.IntegerField(default=0)
```

**RAG 路由器**：

```python
class RAGRouter:
    def route_query(self, query: str) -> list[KnowledgeDataset]:
        """根据查询关键词匹配最相关的知识库"""
        # 1. 基于 tags 的关键词匹配
        # 2. 如果配置了本地向量库，做语义相似度排序
        # 3. 返回前 2 个最相关数据集

    def search_multi(self, query: str, datasets: list[KnowledgeDataset]) -> list[Result]:
        """并行搜索多个知识库，合并结果"""
```

**RAGTool 改造**：

```python
class RAGTool(BaseTool):
    def execute(self, query, context=None):
        # 1. RAGRouter.route_query() → 相关数据集列表
        # 2. 并行搜索各数据集
        # 3. 合并、去重、排序结果
        # 4. 返回 Top-K 片段
```

**KnowledgeBasePage 前端改造**：支持多数据集切换和管理。

---

### 3.6 上下文窗口管理（详细设计）

#### 3.6.1 Token 估算

```python
def estimate_tokens(text: str) -> int:
    """粗略估算 token 数（中文 ~1.5 字符/token，英文 ~4 字符/token）"""
    chinese_chars = sum(1 for c in text if '一' <= c <= '鿿')
    other_chars = len(text) - chinese_chars
    return int(chinese_chars / 1.5 + other_chars / 4)
```

#### 3.6.2 摘要策略

| 触发条件 | 操作 |
|----------|------|
| 总 token > 3000 | 将最早的 2 轮压缩为摘要 |
| 总 token > 6000 | 压缩至只剩摘要 + 最近 3 轮 |
| 会话结束 | 异步生成完整会话摘要，存储到 `summary_text` |

摘要通过后台 Celery 任务生成，使用低成本模型：
```python
@shared_task
def summarize_session(session_id):
    """异步生成会话摘要"""
    session = SmartAssistantSession.objects.get(id=session_id)
    messages = session.messages
    # 调用低成本 LLM 生成摘要
    summary = cheap_llm.generate(f"Summarize this conversation: {messages}")
    session.summary_text = summary
    session.save()
```

---

### 3.7 成本监控与用量分析

#### 3.7.1 AgentLog 扩展

```python
class AgentLog(models.Model):
    # 新增字段
    model_name = models.CharField(max_length=100, blank=True)
    input_tokens = models.IntegerField(null=True)
    output_tokens = models.IntegerField(null=True)
    total_tokens = models.IntegerField(null=True)
    estimated_cost = models.DecimalField(max_digits=10, decimal_places=6, null=True)
    response_time_ms = models.IntegerField(null=True)
    tool_success = models.BooleanField(null=True)  # 工具执行是否成功
    user_feedback = models.CharField(max_length=20, blank=True, null=True)  # 'up' / 'down'
```

#### 3.7.2 Token 计数

在 `OpenAIClient` 中捕获响应 header 或解析响应体的 `usage` 字段：

```python
# OpenAI-compatible 响应格式
{
  "usage": {
    "prompt_tokens": 120,
    "completion_tokens": 80,
    "total_tokens": 200
  }
}
```

#### 3.7.3 用量分析 API

```
GET /api/smart-assistant/usage/stats/
  → {
      total_queries: 1234,
      total_tokens: 567890,
      total_cost: 12.34,
      avg_response_time_ms: 850,
      intent_distribution: {"schedule_query": 40%, "general_chat": 30%, ...},
      tool_success_rate: 85%,
      model_distribution: {"gcli-v2": 70%, "ollama-fallback": 30%}
    }

GET /api/smart-assistant/usage/daily/?start=2026-06-01&end=2026-06-07
  → [{date, queries, tokens, cost, avg_latency}, ...]

GET /api/smart-assistant/usage/user/{user_id}/
  → 用户级别用量统计
```

---

### 3.8 管理分析仪表盘

#### 3.8.1 前端设计

在 `AgentAuditPanel.jsx` 基础上升级为 **AI 运营仪表盘**：

```
AI运营仪表盘
├── 概览卡片
│   ├── 今日对话数
│   ├── 今日 Token 消耗
│   ├── 今日费用估算
│   └── 平均响应时间
├── 意图分布图（饼图）
├── 工具成功率（柱状图）
├── 每日用量趋势（折线图，近 7 天）
├── 模型费用占比（饼图）
├── Top 用户排行榜
└── 异常告警列表
    ├── 高频失败工具
    ├── 超时查询
    └── 异常高费用
```

**图表库**：使用已有的 `@ant-design/charts` 或 `echarts`（项目已引入则复用）。

---

### 3.9 自我反思 / 错误恢复

#### 3.9.1 意图分类置信度

```python
def classify_intent_with_confidence(query, schemas, history=None):
    """
    返回 (intent, confidence, reasoning)
    confidence: 0.0-1.0
    reasoning: LLM 解释为什么选择这个意图
    """
```

**置信度策略**：

| 置信度 | 操作 |
|--------|------|
| ≥ 0.8 | 直接执行 |
| 0.5–0.8 | 执行，但在回答中标注不确定性 |
| < 0.5 | 向用户确认意图："您是想查询排班信息，还是人员信息？" |

#### 3.9.2 工具执行结果验证

```python
class ValidationResult:
    is_valid: bool
    reason: str

class BaseTool:
    def validate_result(self, result: dict) -> ValidationResult:
        """工具自我验证结果有效性"""
        return ValidationResult(is_valid=True, reason="")
```

当工具返回 `found: False` 或验证失败时：
1. 尝试其他可能相关的工具（降级到第二意图）
2. 如果所有工具都不匹配，生成一般回答并提示用户换一种方式提问

---

### 3.10 用户反馈收集

#### 3.10.1 前端

在每条 AI 消息底部添加反馈按钮：

```jsx
<MessageActions messageId={msg.id}>
  <ThumbsUp onClick={() => submitFeedback(msg.id, 'up')} />
  <ThumbsDown onClick={() => submitFeedback(msg.id, 'down')} />
  <CopyButton text={msg.content} />
  <RetryButton onClick={() => retryLastMessage()} />
</MessageActions>
```

#### 3.10.2 后端

```
POST /api/smart-assistant/feedback/
  { message_id, feedback_type: 'up' | 'down', comment?: string }
  → 更新 AgentLog.user_feedback
```

反馈数据用于：
- 分析低质量回答的根因（意图分类错误？工具缺失？）
- 训练数据积累（高评分问答对可用于 prompt 优化）

---

## 四、实施路线图

### Phase 1：基础修复（2-3 周）

| 任务 | 工作量 | 优先级 |
|------|--------|--------|
| 多轮对话历史注入 | 3-4 天 | P0 |
| 上下文窗口管理（滚动摘要） | 2-3 天 | P0 |
| 模型故障降级（LLMRouter） | 3-4 天 | P0 |
| AgentLog 字段扩展 | 1 天 | P2 |

### Phase 2：工具生态扩展（3-4 周）

| 任务 | 工作量 | 优先级 |
|------|--------|--------|
| BaseTool 接口扩展 | 2 天 | P1 |
| 工具链执行器（ToolChainPlanner + Executor） | 5-7 天 | P0 |
| ApprovalTool | 3-4 天 | P1 |
| MeetingRoomTool | 2-3 天 | P1 |
| SensorTool | 2-3 天 | P1 |
| ProjectTool | 2-3 天 | P1 |
| 意图分类扩展（6 种新意图） | 2 天 | P1 |

### Phase 3：前端体验升级（2-3 周）

| 任务 | 工作量 | 优先级 |
|------|--------|--------|
| Markdown 渲染集成 | 2-3 天 | P1 |
| ToolResult 组件增强 | 3-4 天 | P1 |
| 消息操作栏（复制/反馈/重试） | 2 天 | P2 |
| 建议追问功能 | 2 天 | P2 |
| 文件上传对话 | 3-4 天 | P2 |

### Phase 4：知识库与运营（2-3 周）

| 任务 | 工作量 | 优先级 |
|------|--------|--------|
| 多数据集 RAG 路由 | 4-5 天 | P1 |
| 成本监控 API | 2-3 天 | P2 |
| 运营仪表盘前端 | 3-4 天 | P2 |
| 意图分类置信度 + 错误恢复 | 3 天 | P2 |
| 用户反馈系统 | 2 天 | P2 |

---

## 五、技术风险与应对

| 风险 | 影响 | 应对 |
|------|------|------|
| 多工具链执行超时 | 用户体验差 | 设置总超时 30s，单工具超时 10s，超时后返回部分结果 |
| LLM Router 故障转移延迟 | 响应变慢 | 缓存端点健康状态，避免每次请求都尝试失败端点 |
| 上下文摘要质量 | 丢失关键信息 | 摘要 prompt 经过人工审核，保留工具调用结果原文 |
| Token 成本增长 | 费用失控 | 设置每日预算上限，超出后自动切换低成本模型 |
| 新工具与现有模型的兼容性 | 工具不被识别 | 每个新工具提供 3-5 个 few-shot 示例 |

---

## 六、架构总览（深化后）

```
┌─────────────────────────────────────────────────────────────┐
│                        前端层                                 │
│  SmartChatPage  KnowledgeBasePage  AuditDashboard             │
│  ├── Markdown 渲染                                              │
│  ├── ToolResult 富组件                                           │
│  ├── 反馈/复制/重试                                              │
│  └── 建议追问                                                   │
└──────────────────────────┬──────────────────────────────────┘
                           │ SSE / REST
┌──────────────────────────▼──────────────────────────────────┐
│                      API 层                                   │
│  SmartChatViewSet  SessionViewSet  KnowledgeBaseViewSet        │
│  AgentLogViewSet   LlmConfigViewSet  UsageStatsViewSet         │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                    Agent 核心层                               │
│  AgentOrchestrator                                            │
│  ├── ConversationContext（多轮历史管理）                         │
│  ├── IntentClassifier（意图分类 + 置信度）                        │
│  ├── ToolChainPlanner（多工具计划生成）                          │
│  ├── ToolChainExecutor（工具链执行）                             │
│  ├── ResultSynthesizer（结果综合）                               │
│  └── LLMRouter（模型路由 + 降级）                                │
│                                                                │
│  ToolRegistry → [ScheduleTool, PersonnelTool, RAGTool,          │
│                  ApprovalTool, MeetingRoomTool, SensorTool,     │
│                  ProjectTool, DocumentTool, ReportTool]         │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                    服务层                                     │
│  OpenAIClient → 主 LLM 端点                                    │
│  OllamaClient → 降级 LLM                                      │
│  RagflowClient → RAG 检索                                      │
│  Django ORM → 各业务模型                                        │
└─────────────────────────────────────────────────────────────┘
```

---

## 七、与 2026-05-17 方案的关系

| 5月17日方案 Phase | 本文档对应深化内容 |
|-------------------|-------------------|
| Phase 1: 工具扩展 | §3.2 工具链设计（BaseTool 接口扩展、执行计划格式、新增 6 个工具详细设计） |
| Phase 2: 多轮对话 | §3.1 多轮对话系统（根因分析、ConversationContext 类设计、token 估算、滚动摘要策略） |
| Phase 3: 运营统计 | §3.7 成本监控（AgentLog 字段扩展、用量分析 API）+ §3.8 运营仪表盘 |
| Phase 4: 知识库优化 | §3.5 多数据集 RAG 路由（KnowledgeDataset 模型、RAGRouter） |
| Phase 5: 可靠性 | §3.3 模型故障降级（三层降级策略、LLMRouter、数据库 schema 变更） |
| （未覆盖） | §3.4 前端 Markdown 渲染 |
| （未覆盖） | §3.6 上下文窗口管理（详细算法） |
| （未覆盖） | §3.9 自我反思 / 错误恢复 |
| （未覆盖） | §3.10 用户反馈收集 |

---

## 八、后续演进方向（超出本期范围）

1. **多 Agent 协作** — 研究型 Agent、操作型 Agent、分析型 Agent 分工协作
2. **本地向量数据库** — pgvector / FAISS 集成，降低 Ragflow 依赖
3. **Prompt 版本管理** — 数据库存储 Prompt 模板，支持 A/B 测试
4. **语音输入/输出** — Web Speech API + TTS
5. **对话导出与分享** — PDF 导出、分享链接
6. **用户画像记忆** — 跨会话记住用户偏好和常用查询模式
7. **Agent 自主规划** — Plan-and-Execute + ReAct 模式
