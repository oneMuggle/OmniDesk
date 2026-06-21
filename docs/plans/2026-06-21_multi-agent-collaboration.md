# Plan: Smart Assistant 多 Agent 协作增强

**状态**: Draft · 待评审
**作者**: Claude Code
**日期**: 2026-06-21
**参考项目**: `claw-code`(ultraworkers/claw-code,Rust 实现的 agent-managed CLI)
**关联计划**: `2026-06-07_smart-assistant-stage3-new-tools.md`

---

## 1. 背景与目标

### 1.1 背景

`smart_assistant` 目前具备完整的单 Agent 管道:意图分类 → 工具链规划 → 工具执行 → 回答生成,支持 13 个业务工具、多 LLM 端点降级、三级缓存、SSE 流式、完整审计。

但现有架构的"任务复杂度上限"受限于**单 Agent 单轮对话**:
- 无法处理"调研 + 分析 + 写报告"这类需要**多专业角色协作**的长任务
- 工具链执行器(`tool_chain_planner.py`)虽有依赖解析,但缺乏**质量门禁、失败自愈、角色隔离**
- 无法承载后续业务扩展:**文献调研、数据分析、报告整理、简单代码开发**

参考 `claw-code` 项目的 agent 设计(Worker Boot 状态机、Task Packet、Recovery Recipes、Lane Event Sourcing、Policy Engine、多 Agent 顺序执行器),可在**不替换现有框架**的前提下扩展出多 Agent 协作层。

### 1.2 目标

1. **支持长任务、多步骤、多角色协作**:覆盖文献调研 / 数据分析 / 报告整理 / 代码开发四大业务场景
2. **保持向后兼容**:现有单 Agent 聊天链路(`AgentOrchestrator`)继续工作,复杂任务走新管道
3. **质量可量化、可观测**:引入质量门禁、事件流、任务回放
4. **可扩展、可自愈**:插件化工具、Recovery Recipes、策略引擎

### 1.3 非目标(v1 不做)

- ❌ 完全替换 `AgentOrchestrator`(保留为"简单任务"快速通道)
- ❌ 引入 LangGraph / CrewAI 等外部重型框架(自研 + 借鉴思想)
- ❌ 多 Agent 并行协作中的"辩论/对抗"模式(场景不匹配)
- ❌ 跨系统的 Agent Federation(只考虑单进程内)

---

## 2. 涉及的文件与模块

### 2.1 现有模块(扩展)

| 模块 | 改动 |
|---|---|
| `agent/intent_classifier.py` | 增加 `complex_task` 意图,分流到 MultiAgentExecutor |
| `agent/orchestrator.py` | 抽出 `_call_llm()` / `_invoke_tool()` 等可复用方法到 `llm_service` 下的共享 helper |
| `agent/prompt_builder.py` | 抽出 Prompt 模板注册机制,支持角色级 prompt 加载 |
| `agent/tool_chain_executor.py` | 抽出"依赖解析 + 变量替换"逻辑到共享 util,被新旧两条管道复用 |
| `models.py` | 新增 `AgentTask` / `AgentSubTask` / `AgentEvent` 三个模型 |
| `views/chat.py` | 新增 `/chat/task/` 端点,创建并执行多 agent 任务 |
| `views/tasks.py`(新) | `AgentTaskViewSet`:查询 / 执行 / 介入 / 时间线 |
| `urls.py` | 注册新路由 |
| `middleware/rate_limit.py` | 多 agent 任务的速率限制策略(按 task 而非 request) |
| `tasks.py`(Celery) | 新增 `execute_agent_task` 异步任务 |
| `apps.py` | 注册新角色、新钩子 |

### 2.2 新增模块

```
smart_assistant/
├── agents/                              # 新:多 Agent 协作层
│   ├── __init__.py
│   ├── roles.py                         # AgentRole 枚举 + RoleProfile 注册表
│   ├── task_packet.py                   # TaskPacket / SubTask 数据类
│   ├── shared_context.py                # 跨 agent 共享上下文
│   ├── executor.py                      # MultiAgentExecutor(主执行器)
│   ├── pipeline.py                      # Pipeline 模式实现
│   ├── fanout.py                        # Fan-out 模式实现(并行)
│   ├── hierarchical.py                  # Hierarchical 模式实现(Supervisor 调度)
│   ├── quality_gate.py                  # 质量门禁(基于 role 的 output_contract)
│   ├── recovery.py                      # Recovery Recipes(故障自愈)
│   └── supervisor.py                    # Supervisor LLM(任务分解 + 动态调整)
│
├── hooks/                               # 新:Hook 系统
│   ├── __init__.py
│   ├── base.py                          # ToolHook 协议 + HookRegistry
│   ├── builtin/
│   │   ├── audit_log.py                 # 审计日志钩子
│   │   ├── pii_sanitizer.py             # PII 脱敏钩子
│   │   ├── sensitive_data_gate.py       # 敏感数据门控
│   │   └── tool_timeout.py              # 工具超时重试
│   └── registry.py                      # Hook 全局注册表
│
├── policy/                              # 新:策略引擎
│   ├── __init__.py
│   ├── engine.py                        # PolicyEngine(声明式条件树)
│   └── models.py                        # ToolPolicy 模型
│
└── tests/
    ├── test_agents/                     # 多 agent 协作测试
    │   ├── test_roles.py
    │   ├── test_task_packet.py
    │   ├── test_executor_pipeline.py
    │   ├── test_executor_fanout.py
    │   ├── test_quality_gate.py
    │   ├── test_recovery.py
    │   └── test_supervisor.py
    ├── test_hooks/
    │   └── test_hook_registry.py
    └── test_policy/
        └── test_policy_engine.py
```

---

## 3. 技术方案

### 3.1 总体架构

```
                    ┌──────────────────────┐
 用户查询 ─────────►│ IntentClassifier     │
                    └──────────┬───────────┘
                               │
                 ┌─────────────┴─────────────┐
                 │                           │
                 ▼                           ▼
         [简单查询]                    [复杂任务]
         (60% 场景)                    (40% 场景)
                 │                           │
                 ▼                           ▼
    ┌────────────────────┐      ┌─────────────────────────┐
    │ AgentOrchestrator  │      │ MultiAgentExecutor      │
    │ (现有,单 Agent)    │      │ (新,多 Agent 协作)      │
    │ < 5s 响应          │      │ 10s - 10min 长任务      │
    └────────────────────┘      └─────────────────────────┘
                                          │
                              ┌───────────┼───────────┐
                              ▼           ▼           ▼
                          Pipeline    Fan-out    Hierarchical
                          (顺序)      (并行)     (Supervisor)
```

### 3.2 角色体系(`AgentRole`)

```python
class AgentRole(Enum):
    # Supervisor 层
    SUPERVISOR = "supervisor"              # 任务分解 + 调度
    SYNTHESIZER = "synthesizer"            # 综合产出物

    # Worker 层
    RESEARCHER = "researcher"              # 文献检索 + 初筛
    ANALYST = "analyst"                    # 数据分析
    VISUALIZER = "visualizer"              # 可视化(图表/表格)
    WRITER = "writer"                      # 长文本撰写
    EDITOR = "editor"                      # 校对润色
    CODER = "coder"                        # 代码开发
    TESTER = "tester"                      # 测试编写与执行
    REVIEWER = "reviewer"                  # 质量把关

    # 通用
    GENERAL = "general"                    # 兜底,兼容现有 AgentOrchestrator
```

每个角色绑定:`system_prompt` / `allowed_tools` / `input_contract`(JSON Schema)/ `output_contract` / `max_tokens` / `temperature` / `quality_criteria`。

### 3.3 TaskPacket(任务包)

借鉴 claw-code 的 `TaskPacket`,定义结构化任务:

```python
@dataclass(frozen=True)
class SubTask:
    id: str                                # 唯一 ID,供其他 subtask 引用
    role: AgentRole
    objective: str
    inputs: dict[str, str]                 # 支持 `$task_id.field` 变量引用
    failure_mode: FailureMode = FailureMode.RETRY   # SKIP / RETRY / FALLBACK / ABORT
    depends_on: list[str] = field(default_factory=list)
    quality_gate: list[str] = field(default_factory=list)

@dataclass(frozen=True)
class TaskPacket:
    task_id: str
    objective: str
    execution_mode: ExecutionMode          # PIPELINE / FANOUT / HIERARCHICAL
    subtasks: list[SubTask]
    final_synthesis: SubTask | None
    user_context: dict
    global_budget: int = 20000            # 全局 Token 预算
    timeout_seconds: int = 600
```

**Supervisor LLM 自动生成**:用户输入一段查询 → Supervisor 用专门的 prompt 生成 TaskPacket JSON → 校验 JSON Schema → 实例化 TaskPacket。

### 3.4 SharedContext(跨 Agent 上下文)

解决"信息孤岛"问题:每个 Worker 能看到它**需要**的前置产物,而非全部上下文。

```python
@dataclass
class SharedContext:
    original_query: str
    user_context: dict
    artifacts: dict[str, dict]             # subtask_id → 产物
    decisions: list[Decision]              # 已做出的决策(避免重复)
    error_log: list[ErrorRecord]
    token_budget_used: int = 0

    def resolve_references(self, template: str) -> str:
        """解析 `$task_id.field` 引用"""

    def to_context_for(self, subtask: SubTask) -> list[Message]:
        """为指定 subtask 构造精简上下文"""
```

### 3.5 三种执行模式

#### 3.5.1 Pipeline(顺序)

前一个 subtask 的输出通过 `SharedContext` 注入到下一个 subtask 的输入。最常用,覆盖"文献调研 → 分析 → 撰写 → 校对"这类串行工作流。

```python
async def _execute_pipeline(task: TaskPacket, ctx: SharedContext):
    results = []
    for subtask in task.subtasks:
        await _wait_for_dependencies(subtask.depends_on)
        result = await _run_subtask_with_retry(subtask, ctx)
        ctx.artifacts[subtask.id] = result.output
        results.append(result)
    return results
```

#### 3.5.2 Fan-out(并行)

多个独立 subtask 同时执行,最后合并。适合"同时查询多个数据源""同时分析多个维度"。

```python
async def _execute_fanout(task: TaskPacket, ctx: SharedContext):
    tasks = [_run_subtask_with_retry(st, ctx) for st in task.subtasks]
    return await asyncio.gather(*tasks)
```

#### 3.5.3 Hierarchical(层级)

Supervisor Agent 在运行时动态调整 Worker 策略:基于中间结果决定下一步。适合复杂研究课题、跨部门协调。

```python
async def _execute_hierarchical(task: TaskPacket, ctx: SharedContext):
    supervisor = SupervisorAgent(ctx)
    while not supervisor.is_done():
        next_action = await supervisor.decide()    # LLM 决策
        if next_action.type == "dispatch":
            result = await _run_subtask(next_action.subtask, ctx)
            supervisor.observe(result)
        elif next_action.type == "synthesize":
            return await _run_subtask(task.final_synthesis, ctx)
```

### 3.6 Hook 系统

借鉴 claw-code 的 `PreToolUse / PostToolUse / PostToolUseFailure` 钩子,实现工具执行的插件化扩展:

```python
class ToolHook(Protocol):
    def pre_execute(self, tool, ctx, params) -> dict | Reject: ...
    def post_execute(self, tool, result, ctx) -> Any: ...
    def on_failure(self, tool, error, ctx) -> RecoveryAction: ...

class HookRegistry:
    def register(self, event: str, hook: ToolHook, priority: int = 0): ...
    async def run_pre_hooks(self, tool, ctx, params) -> dict: ...
    async def run_post_hooks(self, tool, result, ctx) -> Any: ...
```

**内置钩子**:
- `AuditLogHook`:统一写 `AgentLog`
- `PIISanitizerHook`:脱敏用户输入中的手机号 / 身份证 / 银行卡
- `SensitiveDataGateHook`:权限门控(替代硬编码 `required_auth=True`)
- `ToolTimeoutHook`:超时重试

### 3.7 Recovery Recipes(故障自愈)

借鉴 claw-code 的 `recovery_recipes.rs`,为常见故障场景定义恢复策略:

```python
class FailureScenario(Enum):
    LLM_TIMEOUT = "llm_timeout"
    LLM_RATE_LIMIT = "llm_rate_limit"
    LLM_CONTENT_FILTER = "llm_content_filter"
    TOOL_TIMEOUT = "tool_timeout"
    TOOL_PERMISSION_DENIED = "tool_permission_denied"
    RAG_EMPTY_RESULT = "rag_empty_result"
    JSON_PARSE_ERROR = "json_parse_error"

RECOVERY_RECIPES = {
    FailureScenario.LLM_CONTENT_FILTER: [
        RetryWithSanitizedPrompt(),
        RetryWithDifferentModel(),
        FallbackToTemplateResponse(),
    ],
    FailureScenario.RAG_EMPTY_RESULT: [
        RelaxQueryKeywords(),
        FallBackToDocumentSearch(),
        AdmitNoKnowledge(),
    ],
    FailureScenario.JSON_PARSE_ERROR: [
        RetryWithStrictPrompt(),
        RegexFallbackExtraction(),
    ],
}
```

每个 Worker 失败时按 recipe 顺序尝试,全失败才上报。

### 3.8 Policy Engine(策略引擎)

声明式策略控制工具使用,替代硬编码 `required_auth=True`:

```python
class ToolPolicy(models.Model):
    name = models.CharField(max_length=100, unique=True)
    condition = models.JSONField()         # 声明式条件树(AND / OR / IN / BETWEEN)
    effect = models.CharField(choices=[("ALLOW",), ("DENY",), ("REQUIRE_APPROVAL",)])
    priority = models.IntegerField()

# 例:财务部门用户只能在工作时间查员工敏感数据
{
    "AND": [
        {"user.department": "finance"},
        {"tool.name": {"IN": ["personnel_tool", "memo_tool"]}},
        {"time.hour": {"BETWEEN": [9, 18]}}
    ]
}
```

### 3.9 质量门禁(Quality Gate)

每个角色定义 `quality_criteria`(自然语言列表),执行后由 Reviewer 或专门的质量 LLM 调用检查:

```python
def check_quality_gate(role: AgentRole, output: dict) -> QualityResult:
    profile = ROLE_PROFILES[role]
    checks = [_evaluate_criterion(criterion, output) for criterion in profile.quality_criteria]
    return QualityResult(
        passed=all(c.passed for c in checks),
        failed_criteria=[c.name for c in checks if not c.passed],
        suggestions=[c.suggestion for c in checks if not c.passed],
    )
```

未通过时根据 `failure_mode` 决定:重试 / 跳过 / 终止 / 用兜底。

### 3.10 数据模型

```python
class AgentTask(models.Model):
    task_id = models.UUIDField(default=uuid4, unique=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    session = models.ForeignKey(SmartAssistantSession, on_delete=models.CASCADE, null=True)
    objective = models.TextField()
    execution_mode = models.CharField(max_length=20)
    status = models.CharField(max_length=20, default="pending")
    task_packet = models.JSONField()
    global_budget = models.IntegerField(default=20000)
    tokens_used = models.IntegerField(default=0)
    started_at = models.DateTimeField(null=True)
    completed_at = models.DateTimeField(null=True)
    final_output = models.JSONField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)

class AgentSubTask(models.Model):
    task = models.ForeignKey(AgentTask, on_delete=models.CASCADE, related_name="subtasks")
    subtask_id = models.CharField(max_length=64)
    role = models.CharField(max_length=30)
    objective = models.TextField()
    status = models.CharField(max_length=20, default="pending")
    depends_on = models.JSONField(default=list)
    output = models.JSONField(null=True)
    tokens_used = models.IntegerField(default=0)
    started_at = models.DateTimeField(null=True)
    completed_at = models.DateTimeField(null=True)
    retry_count = models.IntegerField(default=0)
    error_message = models.TextField(null=True)

class AgentEvent(models.Model):
    task = models.ForeignKey(AgentTask, on_delete=models.CASCADE, related_name="events")
    subtask = models.ForeignKey(AgentSubTask, on_delete=models.CASCADE, null=True)
    sequence = models.PositiveIntegerField()
    event_type = models.CharField(max_length=40)
    payload = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sequence"]
        unique_together = [("task", "sequence")]
```

### 3.11 API 设计

```
POST   /api/smart-assistant/chat/task/            # 创建任务(用户查询 → Supervisor 分解)
GET    /api/smart-assistant/tasks/                # 任务列表
GET    /api/smart-assistant/tasks/{task_id}/      # 任务详情(含 subtasks)
POST   /api/smart-assistant/tasks/{task_id}/execute/   # 开始执行
POST   /api/smart-assistant/tasks/{task_id}/intervene/ # 用户介入(暂停/调整/取消)
GET    /api/smart-assistant/tasks/{task_id}/stream/      # SSE 实时进度
GET    /api/smart-assistant/tasks/{task_id}/timeline/    # 完整时间线(甘特图数据)
DELETE /api/smart-assistant/tasks/{task_id}/      # 取消并清理
```

### 3.12 前端集成

在现有 `SmartChatPage` 基础上新增 `SmartTaskPage`(独立路由 `/smart-assistant/task/:id`):

- **任务分解卡片**:展示 Supervisor 生成的 TaskPacket,用户可修改后确认执行
- **进度条 + 子任务列表**:实时 SSE 推送,每完成一个 subtask 自动展开产物预览
- **时间线视图**:甘特图展示每个 subtask 的执行时间、状态、Token 消耗
- **产物查看器**:每个 subtask 的输出(文本 / 图表 / 代码)可独立查看和下载
- **用户介入**:任意 subtask 完成后可暂停、调整后续 subtask、或人工接管某个 Worker

判定逻辑在 intent classifier 后:**复杂任务自动跳转到 `/smart-assistant/task/new?query=...`**,简单任务留在 chat 界面。

### 3.13 关键技术决策

#### 决策 1:并发模型 → **Celery + asyncio 混合**(推荐)

- Supervisor 和 SSE Stream 用 asyncio(低延迟、流式友好)
- Worker 执行用 Celery 任务(可持久化、可重试、与现有 Celery 集成一致)
- 中间结果通过 Django cache(Redis)传递

**理由**:现有 `smart_assistant/tasks.py` 已用 Celery 处理文档向量化,复用基础设施;纯 asyncio 方案在 Worker 长时间运行时难以持久化。

#### 决策 2:模型选择策略

| 角色 | 推荐模型 | 理由 |
|---|---|---|
| Supervisor | 高能力模型(当前 Gemini 2.5 Pro 主端点) | 任务分解质量决定全局 |
| Researcher | 中等模型 + 大上下文窗口 | 需处理大量文献 |
| Writer / Reviewer | 高能力模型 | 产出物质量要求高 |
| Coder | 高能力模型 + 代码特化(可选 DeepSeek-Coder) | 代码质量要求高 |
| Analyst / Visualizer | 中等模型 | 主要是调用工具 + 解释 |

通过 `LlmAppConfig` 的 `app_name` 字段绑定到角色,数据库配置、热切换。

#### 决策 3:是否引入外部框架 → **自研,借鉴 LangGraph 思想**(推荐)

- **不引入** LangGraph / CrewAI 等重型框架
- 借鉴 LangGraph 的 StateGraph 思想:`State` 在节点间传递,每个节点是一个 Worker
- 与现有 `AgentOrchestrator` / `ToolRegistry` / `LLMRouter` 保持一致风格

**理由**:OmniDesk 已有完整 Agent 框架,新框架会引入学习成本、版本风险、黑盒问题。自研 + 借鉴思想更可控。

---

## 4. 实施步骤

### Phase 1:Pipeline 模式 + 报告场景(2-3 个月)

> 目标:跑通顺序执行,覆盖"文献调研 → 报告整理"场景

**里程碑 1.1:基础设施(1 周)**
- [ ] 新建 `smart_assistant/agents/` 包,定义 `AgentRole` / `RoleProfile` / `ROLE_PROFILES`
- [ ] 新建 `smart_assistant/hooks/` 包,定义 `ToolHook` 协议 + `HookRegistry`
- [ ] 数据模型:`AgentTask` / `AgentSubTask` / `AgentEvent`,写 migration
- [ ] 单元测试:角色注册、Hook 注册

**里程碑 1.2:TaskPacket + SharedContext(1 周)**
- [ ] `TaskPacket` / `SubTask` 数据类 + JSON Schema 校验
- [ ] `SharedContext`:artifact 存储、`$task_id.field` 变量解析
- [ ] 单元测试:变量解析、上下文构造

**里程碑 1.3:Pipeline 执行器(2 周)**
- [ ] `MultiAgentExecutor` 主类 + `_execute_pipeline()` 方法
- [ ] Celery 任务 `execute_agent_task`,支持异步执行
- [ ] `AgentEvent` SSE 推送(Supervisor 决策、subtask 进度、产物)
- [ ] 集成测试:3 步 Pipeline(Researcher → Analyst → Writer)端到端

**里程碑 1.4:6 个核心角色实现(2 周)**
- [ ] Supervisor(system prompt 调优,生成 TaskPacket JSON)
- [ ] Researcher:绑定 `rag_tool` / `document_tool`,输出结构化文献列表
- [ ] Analyst:绑定 `document_tool` / `sensor_tool`,输出趋势分析
- [ ] Writer:绑定 `document_tool`(模板),输出长文本
- [ ] Editor:校对 + 润色
- [ ] Reviewer:质量门禁检查

**里程碑 1.5:Intent Classifier 分流(1 周)**
- [ ] `intent_classifier.py` 增加 `complex_task` 意图
- [ ] 分流 prompt:识别"调研 + 报告 + 分析 + 开发"等关键词
- [ ] 单元测试:分流准确率 ≥ 90%

**里程碑 1.6:前端 MVP(2 周)**
- [ ] 新路由 `/smart-assistant/task/:id`
- [ ] `TaskView`:进度条 + 子任务列表(实时 SSE)
- [ ] `ArtifactViewer`:每个 subtask 产物预览
- [ ] 与现有 `SmartChatPage` 的入口打通(复杂查询自动跳转)

**里程碑 1.7:文档 + 测试(1 周)**
- [ ] 单元测试覆盖率 ≥ 80%(agents / hooks)
- [ ] 集成测试:3 个端到端场景(文献调研 / 报告整理 / 简单数据分析)
- [ ] 用户手册:`docs/user-manual/07-smart-task.md`
- [ ] 技术文档:`docs/technical/08-multi-agent-collaboration.md`

**Phase 1 验收标准**:用户输入"帮我调研 X 并整理成报告",系统自动分解 4-5 步、顺序执行、输出 2000+ 字报告 + 引用列表,耗时 < 3 分钟。

---

### Phase 2:Fan-out + 质量门禁(2-3 个月)

- [ ] Fan-out 执行器:`asyncio.gather` 并行运行无依赖 subtasks
- [ ] 每个角色的 `quality_gate` 自动检查
- [ ] 质量门禁失败处理:重试 / 调整 prompt / 人工介入
- [ ] 前端:Timeline 甘特图 + 产物对比视图
- [ ] 新角色:Visualizer(图表生成)、Tester(代码测试)
- [ ] 任务模板:预设"文献调研""数据分析""代码开发"的 TaskPacket 模板

---

### Phase 3:Hierarchical + Supervisor 智能调度(3-4 个月)

- [ ] Hierarchical 执行器:Supervisor 运行时动态调整 Worker 策略
- [ ] 用户介入:暂停、调整 subtask、人工接管 Worker
- [ ] 任务历史学习:从过往任务优化 Supervisor prompt
- [ ] 跨 session 任务:支持"明天继续"
- [ ] 协作可视化:Supervisor 决策过程可视化

---

## 5. 风险评估与依赖

### 5.1 风险

| 风险 | 影响 | 缓解措施 |
|---|---|---|
| **Token 成本爆炸** | 长任务消耗大量 Token,成本失控 | 全局 budget + 每角色 budget;小模型兜底;中间结果缓存 |
| **任务失败率高** | 用户体验差,失去信任 | Recovery Recipes + 用户介入点;渐进式放开复杂度 |
| **响应时间过长** | 用户等待焦虑 | 流式进度反馈;并行化;预计算常见任务模板 |
| **Supervisor 分解质量差** | 整个任务方向错误 | 预设 TaskPacket 模板(覆盖 80% 常见场景);用户可编辑后再执行 |
| **前端复杂度高** | 开发周期长 | Phase 1 只做 MVP;验证后再加高级功能 |
| **LLM 输出不稳定** | JSON 解析失败、格式漂移 | `quality_gate` + `RetryWithStrictPrompt`;结构化输出优先 |
| **跨 Worker 上下文污染** | 后续 Worker 被前置错误误导 | `SharedContext` 严格 schema 校验;`decisions` 审计链 |

### 5.2 依赖

| 依赖 | 说明 | 状态 |
|---|---|---|
| Django 4.2 | 数据模型、Admin、ORM | ✅ 已就绪 |
| Celery + Redis | 异步任务执行、中间结果缓存 | ✅ 已就绪(`smart_assistant/tasks.py` 已用) |
| Redis | 缓存(三级缓存、SharedContext) | ✅ 已就绪 |
| `LLMRouter` | 多端点降级 | ✅ 已就绪 |
| `ToolRegistry` + 13 个工具 | Worker 调用 | ✅ 已就绪 |
| SSE 流式能力 | 进度推送 | ✅ 已就绪(`chat/stream/`) |
| PostgreSQL | 持久化 `AgentTask` / `AgentEvent` | ✅ 生产环境已用 |
| Ragflow | RAG 后端 | ✅ 已集成 |
| 前端 React 18 + Vite | 新页面开发 | ✅ 已就绪 |

### 5.3 与现有架构的兼容性

- ✅ 现有 `AgentOrchestrator` 不改动,继续服务简单查询
- ✅ 现有 13 个工具原样复用,无需重写
- ✅ 现有 `AgentLog` 继续写(Hook 系统额外增强)
- ✅ 新数据模型独立,不破坏现有表结构
- ⚠️ `intent_classifier.py` 需扩展(增加 `complex_task` 意图)
- ⚠️ `prompt_builder.py` 需抽出 Prompt 模板注册机制

---

## 6. 验收标准(总体)

1. **功能**:用户输入"调研 X + 整理报告",系统自动分解、执行、输出完整报告
2. **性能**:单任务 < 5 分钟完成;Token 消耗 < 30k;并发任务 ≥ 5
3. **质量**:Review 通过率 ≥ 80%;用户满意度 ≥ 4/5
4. **可观测**:所有任务有完整事件流,可回放;运营大盘可查看任务分布、成功率、平均耗时
5. **可维护**:代码覆盖率 ≥ 80%;文档齐全(技术手册 + 用户手册)

---

## 7. 待评审问题(请用户确认)

1. **Phase 1 范围**是否合适?是否要先做"文献调研"场景,还是"报告整理"更优先?
2. **并发模型**倾向 Celery 混合 还是 纯 asyncio?
3. **模型选择策略**是否需要更精细(例如为每个角色单独配置 endpoint)?
4. **前端 MVP** 是否要先做"只读任务监控",把"用户介入"放到 Phase 2?
5. **Hook 系统** 第一期要做几个?建议先做 `AuditLogHook` + `PIISanitizerHook`,其他放 Phase 2。

---

**下一步**:评审通过后,建 feature 分支 `feat/multi-agent-collaboration`,按 Phase 1 的 7 个里程碑逐步实施。每个里程碑独立可验证、独立 commit、独立 PR。
