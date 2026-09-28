from django.db import models
from django.conf import settings

from personnel.models import EncryptedCharField


class KnowledgeDataset(models.Model):
    """知识库数据集（支持多个 Ragflow 数据集）"""

    name = models.CharField(max_length=100, unique=True, verbose_name="数据集名称")
    description = models.TextField(blank=True, default="", verbose_name="描述")
    ragflow_dataset_id = models.CharField(max_length=100, verbose_name="Ragflow 数据集 ID")
    is_active = models.BooleanField(default=True, verbose_name="是否激活")
    tags = models.JSONField(default=list, blank=True, verbose_name="标签（用于智能路由）")
    document_count = models.IntegerField(default=0, verbose_name="文档数量")
    priority = models.IntegerField(default=1, verbose_name="优先级")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "知识库数据集"
        verbose_name_plural = verbose_name
        ordering = ["priority", "name"]

    def __str__(self):
        return self.name


class KnowledgeBaseDocument(models.Model):
    """知识库文档"""

    CATEGORY_CHOICES = [
        ("general", "通用"),
        ("technical", "技术"),
        ("policy", "政策"),
        ("procedure", "流程"),
        ("faq", "常见问题"),
    ]
    title = models.CharField(max_length=255, verbose_name="文档标题")
    file = models.FileField(upload_to="knowledge_base/", verbose_name="文档文件")
    content_text = models.TextField(blank=True, verbose_name="提取的文本内容")
    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
        default="general",
        verbose_name="文档分类",
    )
    tags = models.CharField(max_length=500, blank=True, verbose_name="标签（逗号分隔）")
    dataset = models.ForeignKey(
        KnowledgeDataset,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="documents",
        verbose_name="所属数据集",
    )
    embedding_status = models.CharField(
        max_length=20,
        choices=[
            ("pending", "待处理"),
            ("processing", "处理中"),
            ("completed", "已完成"),
            ("failed", "失败"),
        ],
        default="pending",
    )
    ragflow_document_id = models.CharField(max_length=255, blank=True, null=True, verbose_name="Ragflow 文档ID")
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "知识库文档"
        verbose_name_plural = verbose_name
        ordering = ["-created_at"]


class SmartAssistantSession(models.Model):
    """助手会话记录"""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="assistant_sessions",
    )
    title = models.CharField(max_length=255, verbose_name="会话标题")
    messages = models.JSONField(default=list, verbose_name="对话消息历史")
    # 多轮对话上下文管理
    summary_text = models.TextField(blank=True, default="", verbose_name="早期对话摘要")
    summary_token_count = models.IntegerField(null=True, blank=True, verbose_name="摘要 token 数")
    turn_count = models.IntegerField(default=0, verbose_name="对话轮数")
    # P0-K:持久化最近一次聊天错误,便于前端展示与运维排查
    last_error = models.TextField(blank=True, default="", verbose_name="最近错误")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "助手会话"
        verbose_name_plural = verbose_name
        ordering = ["-created_at"]


class LlmEndpoint(models.Model):
    """LLM API 端点配置（一次配置，多处复用）"""

    name = models.CharField(max_length=100, verbose_name="配置名称")
    api_endpoint = models.URLField(verbose_name="API 端点")
    api_key = EncryptedCharField(max_length=500, verbose_name="API 密钥")
    is_active = models.BooleanField(default=True, verbose_name="是否激活")
    # 降级与路由相关字段
    priority = models.IntegerField(default=1, verbose_name="优先级（数字越小优先级越高）")
    is_fallback = models.BooleanField(default=False, verbose_name="是否为备用端点")
    model_capabilities = models.JSONField(default=list, blank=True, verbose_name="模型能力")
    cost_per_1k_tokens = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        null=True,
        blank=True,
        verbose_name="每千 token 费用（元）",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "LLM API 端点"
        verbose_name_plural = verbose_name
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.api_endpoint})"


class LlmAppConfig(models.Model):
    """LLM 应用配置（为每个应用分配端点+模型+参数）"""

    APP_CHOICES = [
        ("smart_assistant", "智能助手"),
        ("office_assistant", "办公助手"),
    ]
    app_name = models.CharField(max_length=50, choices=APP_CHOICES, verbose_name="应用名称")
    endpoint = models.ForeignKey(
        LlmEndpoint,
        on_delete=models.CASCADE,
        related_name="app_configs",
        verbose_name="API 端点",
    )
    model_name = models.CharField(max_length=100, verbose_name="模型名称")
    temperature = models.FloatField(null=True, blank=True, default=0.7)
    top_p = models.FloatField(null=True, blank=True, default=0.9)
    is_active = models.BooleanField(default=True, verbose_name="是否激活")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "LLM 应用配置"
        verbose_name_plural = verbose_name
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_app_name_display()} - {self.model_name}"


class AgentWriteLog(models.Model):
    """智能助手确认写操作的可回滚审计记录。"""

    task = models.ForeignKey("AgentTask", null=True, blank=True, on_delete=models.SET_NULL, related_name="write_logs")
    session_id = models.CharField(max_length=255, null=True, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="agent_write_logs")
    tool_name = models.CharField(max_length=100)
    target_model = models.CharField(max_length=255)
    target_pk = models.CharField(max_length=64)
    operation = models.CharField(
        max_length=20, choices=[("create", "create"), ("update", "update"), ("delete", "delete"), ("revert", "revert")]
    )
    before = models.JSONField(null=True, blank=True)
    after = models.JSONField(null=True, blank=True)
    revert_of = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="revert_logs")
    reverted_at = models.DateTimeField(null=True, blank=True)
    reverted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="performed_write_reverts",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "-created_at"]), models.Index(fields=["target_model", "target_pk"])]


class AgentLog(models.Model):
    """Agent 执行日志（用于调试和审计）"""

    session = models.ForeignKey(
        SmartAssistantSession,
        on_delete=models.CASCADE,
        null=True,
    )
    user_query = models.TextField(verbose_name="用户问题")
    intent = models.CharField(max_length=50, verbose_name="识别的意图类型")
    tool_used = models.CharField(max_length=50, verbose_name="使用的工具")
    tool_input = models.JSONField(default=dict, verbose_name="工具输入")
    tool_output = models.JSONField(default=dict, verbose_name="工具输出")
    llm_response = models.TextField(verbose_name="LLM 回答")
    # 用量与成本追踪
    model_name = models.CharField(max_length=100, blank=True, default="", verbose_name="使用的模型")
    input_tokens = models.IntegerField(null=True, blank=True, verbose_name="输入 token 数")
    output_tokens = models.IntegerField(null=True, blank=True, verbose_name="输出 token 数")
    total_tokens = models.IntegerField(null=True, blank=True, verbose_name="总 token 数")
    estimated_cost = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        null=True,
        blank=True,
        verbose_name="预估费用（元）",
    )
    response_time_ms = models.IntegerField(null=True, blank=True, verbose_name="响应时间（ms）")
    tool_success = models.BooleanField(null=True, blank=True, verbose_name="工具执行是否成功")
    user_feedback = models.CharField(
        max_length=20,
        blank=True,
        default="",
        verbose_name="用户反馈（up/down）",
    )
    # L1 原生 Function Calling(2026-08-06)决策日志
    tool_call_path = models.CharField(
        max_length=16,
        choices=[("native", "native"), ("json", "json"), ("none", "none")],
        default="none",
        blank=True,
        verbose_name="工具调用路径",
    )
    tool_calls_meta = models.JSONField(
        default=list,
        blank=True,
        verbose_name="每轮工具调用的元数据(rounds/tool/arguments/duration_ms)",
    )
    tool_calls_rounds = models.IntegerField(
        default=0,
        verbose_name="实际工具调用轮数(用于审计 / 成本分析)",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Agent 日志"
        verbose_name_plural = verbose_name
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["-created_at"]),
            models.Index(fields=["intent"]),
        ]


# ---------------------------------------------------------------------------
# 多 Agent 协作相关模型(Phase 1 新增)
# ---------------------------------------------------------------------------


class AgentTask(models.Model):
    """多 Agent 协作的主任务

    代表用户发起的一个复杂任务(如"调研 RAG 技术并整理报告"),
    由 Supervisor 分解为多个 SubTask,由 MultiAgentExecutor 执行。
    """

    STATUS_CHOICES = [
        ("pending", "待执行"),
        ("running", "执行中"),
        ("paused", "已暂停"),
        ("completed", "已完成"),
        ("failed", "已失败"),
        ("partial", "部分完成"),
        ("cancelled", "已取消"),
    ]

    EXECUTION_MODE_CHOICES = [
        ("pipeline", "顺序执行"),
        ("fanout", "并行执行"),
        ("hierarchical", "层级执行"),
    ]

    task_id = models.UUIDField(unique=True, editable=False, verbose_name="任务 ID")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="agent_tasks",
        verbose_name="发起人",
    )
    session = models.ForeignKey(
        SmartAssistantSession,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="agent_tasks",
        verbose_name="关联会话",
    )
    objective = models.TextField(verbose_name="任务目标")
    execution_mode = models.CharField(
        max_length=20,
        choices=EXECUTION_MODE_CHOICES,
        default="pipeline",
        verbose_name="执行模式",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
        verbose_name="任务状态",
    )
    task_packet = models.JSONField(default=dict, verbose_name="任务包(Supervisor 生成的 JSON)")
    global_budget = models.IntegerField(default=20000, verbose_name="全局 Token 预算")
    tokens_used = models.IntegerField(default=0, verbose_name="已使用 Token 数")
    started_at = models.DateTimeField(null=True, blank=True, verbose_name="开始时间")
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="完成时间")
    final_output = models.JSONField(null=True, blank=True, verbose_name="最终产出物")
    resume_claim_id = models.UUIDField(null=True, blank=True, editable=False, verbose_name="恢复 worker claim")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        verbose_name = "Agent 任务"
        verbose_name_plural = verbose_name
        ordering = ["-created_at"]
        indexes = [
            # "按用户查任务列表并按时间倒序" 的高频查询(与 ToolChainPlan 的 Index 先例一致)
            models.Index(fields=["user", "-created_at"]),
        ]

    def __str__(self):
        return f"Task-{str(self.task_id)[:8]} {self.objective[:30]}"


class AgentSubTask(models.Model):
    """子任务实例

    主任务分解出的单个执行步骤,绑定到特定角色(Worker)。
    """

    STATUS_CHOICES = [
        ("pending", "待执行"),
        ("running", "执行中"),
        ("completed", "已完成"),
        ("failed", "已失败"),
        ("skipped", "已跳过"),
    ]

    task = models.ForeignKey(
        AgentTask,
        on_delete=models.CASCADE,
        related_name="subtasks",
        verbose_name="所属主任务",
    )
    subtask_id = models.CharField(max_length=64, verbose_name="子任务 ID(在 TaskPacket 中唯一)")
    role = models.CharField(max_length=30, verbose_name="执行角色(AgentRole 枚举值)")
    objective = models.TextField(verbose_name="子任务目标")
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
        verbose_name="子任务状态",
    )
    depends_on = models.JSONField(default=list, blank=True, verbose_name="依赖的子任务 ID 列表")
    inputs = models.JSONField(default=dict, blank=True, verbose_name="输入参数(支持 $task_id.field 引用)")
    output = models.JSONField(null=True, blank=True, verbose_name="产出物")
    tokens_used = models.IntegerField(default=0, verbose_name="已使用 Token 数")
    started_at = models.DateTimeField(null=True, blank=True, verbose_name="开始时间")
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="完成时间")
    retry_count = models.IntegerField(default=0, verbose_name="重试次数")
    error_message = models.TextField(null=True, blank=True, verbose_name="错误信息")

    class Meta:
        verbose_name = "Agent 子任务"
        verbose_name_plural = verbose_name
        ordering = ["task", "subtask_id"]
        unique_together = [("task", "subtask_id")]

    def __str__(self):
        return f"SubTask-{self.subtask_id} ({self.role})"


class AgentEvent(models.Model):
    """细粒度事件流

    记录多 Agent 协作过程中的每一步事件,用于:
    - SSE 实时推送给前端(进度条 / 时间线)
    - 故障排查(完整事件回放)
    - 运营分析(成功率 / 平均耗时 / 工具使用情况)
    """

    EVENT_TYPE_CHOICES = [
        ("task.started", "任务开始"),
        ("task.paused", "任务暂停(等待用户介入)"),
        ("task.resumed", "任务恢复"),
        ("task.completed", "任务完成"),
        ("task.failed", "任务失败"),
        ("task.cancelled", "任务取消"),
        ("subtask.started", "子任务开始"),
        ("subtask.progress", "子任务进度(LLM 流式输出)"),
        ("subtask.tool_call", "子任务工具调用"),
        ("subtask.quality_gate", "子任务质量门禁检查"),
        ("subtask.completed", "子任务完成"),
        ("subtask.failed", "子任务失败"),
        ("subtask.skipped", "子任务跳过"),
        ("subtask.tool_result", "子任务工具结果"),
        ("task.aborted", "任务中止"),
        ("supervisor.decision", "Supervisor 决策"),
        ("supervisor.intervention", "Supervisor 介入"),
        ("user.intervention", "用户介入"),
        ("hook.triggered", "Hook 触发"),
    ]

    task = models.ForeignKey(
        AgentTask,
        on_delete=models.CASCADE,
        related_name="events",
        verbose_name="所属任务",
    )
    subtask = models.ForeignKey(
        AgentSubTask,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="events",
        verbose_name="关联子任务",
    )
    sequence = models.PositiveIntegerField(verbose_name="事件序号(任务内递增)")
    event_type = models.CharField(
        max_length=40,
        choices=EVENT_TYPE_CHOICES,
        verbose_name="事件类型",
    )
    payload = models.JSONField(default=dict, blank=True, verbose_name="事件详细数据")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="事件时间")

    class Meta:
        verbose_name = "Agent 事件"
        verbose_name_plural = verbose_name
        ordering = ["task", "sequence"]
        unique_together = [("task", "sequence")]
        indexes = [
            models.Index(fields=["task", "-sequence"]),
        ]

    def __str__(self):
        return f"Event#{self.sequence} {self.event_type}"


class ToolChainPlan(models.Model):
    """多工具链执行计划的持久化记录。

    用于断点恢复(分支 3)、审计追踪、plan 可视化。
    """

    STATUS_CHOICES = [
        ("pending", "待执行"),
        ("running", "执行中"),
        ("completed", "已完成"),
        ("failed", "失败"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tool_chain_plans",
    )
    plan_data = models.JSONField(default=dict)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    current_step = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "smart_assistant_tool_chain_plan"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"ToolChainPlan(id={self.pk}, user={self.user_id}, status={self.status})"


# ---------------------------------------------------------------------------
# S4-1 数字员工
# ---------------------------------------------------------------------------


class AgentProfile(models.Model):
    """数字员工角色配置（S4-1）：每个角色可单独启停、单独设配额。"""

    TRIGGER_PASSIVE = "passive"
    TRIGGER_BEAT = "beat"
    TRIGGER_EVENT = "event"
    TRIGGER_CHOICES = [(TRIGGER_PASSIVE, "被动"), (TRIGGER_BEAT, "定时"), (TRIGGER_EVENT, "业务事件")]

    key = models.SlugField(max_length=50, unique=True, verbose_name="角色标识")
    name = models.CharField(max_length=100, verbose_name="名称")
    description = models.TextField(blank=True, verbose_name="职责说明")
    system_prompt = models.TextField(blank=True, verbose_name="系统提示词")
    toolsets = models.JSONField(default=list, blank=True, verbose_name="工具集白名单")
    data_scope = models.CharField(max_length=200, blank=True, verbose_name="数据范围说明")
    trigger = models.CharField(max_length=20, choices=TRIGGER_CHOICES, default=TRIGGER_BEAT, verbose_name="触发方式")
    schedule_label = models.CharField(max_length=100, blank=True, verbose_name="定时说明")
    enabled = models.BooleanField(default=False, verbose_name="是否启用")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="owned_agent_profiles",
        verbose_name="负责人",
    )
    daily_llm_quota = models.PositiveIntegerField(default=0, verbose_name="每日 LLM 调用配额")
    daily_action_quota = models.PositiveIntegerField(default=100, verbose_name="每日动作配额")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "数字员工"
        verbose_name_plural = verbose_name
        ordering = ["id"]

    def __str__(self):
        return f"{self.name}({self.key})"


class AgentRun(models.Model):
    """数字员工的一次运行。"""

    STATUS_RUNNING = "running"
    STATUS_SUCCEEDED = "succeeded"
    STATUS_DEGRADED = "degraded"
    STATUS_FAILED = "failed"
    STATUS_SKIPPED = "skipped"
    STATUS_CHOICES = [
        (STATUS_RUNNING, "运行中"),
        (STATUS_SUCCEEDED, "成功"),
        (STATUS_DEGRADED, "已降级"),
        (STATUS_FAILED, "失败"),
        (STATUS_SKIPPED, "已跳过"),
    ]
    TRIGGER_CHOICES = [("beat", "定时"), ("manual", "手动")]

    profile = models.ForeignKey(AgentProfile, on_delete=models.CASCADE, related_name="runs")
    trigger = models.CharField(max_length=20, choices=TRIGGER_CHOICES, default="beat")
    triggered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_RUNNING)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    stats = models.JSONField(default=dict, blank=True)
    error = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ["-started_at", "-id"]
        indexes = [models.Index(fields=["profile", "-started_at"])]


class AgentRunEvent(models.Model):
    """数字员工审计事件：每个动作一条，也用于统计当日配额用量。"""

    EVENT_CHOICES = [
        ("run.started", "运行开始"),
        ("run.completed", "运行完成"),
        ("run.failed", "运行失败"),
        ("run.skipped", "运行跳过"),
        ("llm.call", "调用 LLM"),
        ("llm.fallback", "LLM 降级"),
        ("notify.sent", "发送通知"),
        ("proposal.created", "创建待确认事项"),
        ("proposal.approved", "待确认事项已确认"),
        ("proposal.rejected", "待确认事项已取消"),
        ("proposal.expired", "待确认事项已过期"),
        ("proposal.failed", "待确认事项执行失败"),
        ("quota.exceeded", "超出配额"),
        ("config.changed", "配置变更"),
    ]
    #: 计入每日动作配额的事件
    ACTION_EVENTS = ("notify.sent", "proposal.created")

    profile = models.ForeignKey(AgentProfile, on_delete=models.CASCADE, related_name="events")
    run = models.ForeignKey(AgentRun, null=True, blank=True, on_delete=models.CASCADE, related_name="events")
    event_type = models.CharField(max_length=40, choices=EVENT_CHOICES)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["profile", "event_type", "created_at"])]


class AgentProposal(models.Model):
    """数字员工发给某个用户的待确认事项（持久化，替代 10 分钟的确认缓存）。"""

    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_EXPIRED = "expired"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_PENDING, "待确认"),
        (STATUS_APPROVED, "已确认"),
        (STATUS_REJECTED, "已取消"),
        (STATUS_EXPIRED, "已过期"),
        (STATUS_FAILED, "执行失败"),
    ]

    profile = models.ForeignKey(AgentProfile, on_delete=models.CASCADE, related_name="proposals")
    run = models.ForeignKey(AgentRun, null=True, blank=True, on_delete=models.SET_NULL, related_name="proposals")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="agent_proposals")
    kind = models.CharField(max_length=50)
    title = models.CharField(max_length=200)
    fields = models.JSONField(default=dict, blank=True)
    preview = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    dedupe_key = models.CharField(max_length=200)
    expires_at = models.DateTimeField()
    decided_at = models.DateTimeField(null=True, blank=True)
    result = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["user", "status", "-created_at"])]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "dedupe_key"],
                condition=models.Q(status="pending"),
                name="uniq_pending_agent_proposal",
            )
        ]


class KnowledgeSource(models.Model):
    """业务对象自动入库 RAGFlow 的记录（S4-2）。

    一个业务对象（公告 / 文档库文档）对应一条记录。检索结果按 ``ragflow_document_id``
    反查这里，再按用户能否看到原对象过滤（见 ``smart_assistant.knowledge.acl``）。
    """

    TYPE_ANNOUNCEMENT = "announcement"
    TYPE_PAPERLESS = "paperless_document"
    TYPE_CHOICES = [
        (TYPE_ANNOUNCEMENT, "公告"),
        (TYPE_PAPERLESS, "文档库"),
    ]

    STATUS_PENDING = "pending"
    STATUS_INGESTED = "ingested"
    STATUS_FAILED = "failed"
    STATUS_REMOVED = "removed"
    STATUS_CHOICES = [
        (STATUS_PENDING, "待入库"),
        (STATUS_INGESTED, "已入库"),
        (STATUS_FAILED, "失败"),
        (STATUS_REMOVED, "已移除"),
    ]

    source_type = models.CharField(max_length=32, choices=TYPE_CHOICES, verbose_name="来源类型")
    source_id = models.PositiveIntegerField(verbose_name="来源对象 ID")
    title = models.CharField(max_length=255, blank=True, default="", verbose_name="标题")
    ragflow_dataset_id = models.CharField(max_length=100, blank=True, default="", verbose_name="RAGFlow 数据集 ID")
    ragflow_document_id = models.CharField(
        max_length=100, blank=True, default="", db_index=True, verbose_name="RAGFlow 文档 ID"
    )
    content_hash = models.CharField(max_length=64, blank=True, default="", verbose_name="入库内容 sha256")
    status = models.CharField(
        max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True, verbose_name="状态"
    )
    attempts = models.PositiveIntegerField(default=0, verbose_name="连续失败次数")
    last_error = models.CharField(max_length=500, blank=True, default="", verbose_name="最近错误")
    ingested_at = models.DateTimeField(null=True, blank=True, verbose_name="入库时间")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "知识入库记录"
        verbose_name_plural = "知识入库记录"
        constraints = [
            models.UniqueConstraint(fields=["source_type", "source_id"], name="uniq_knowledge_source"),
        ]
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.get_source_type_display()} #{self.source_id} ({self.get_status_display()})"


class LlmUsageDaily(models.Model):
    """LLM 调用每日汇总（预算与配额）。

    由 ``llm_service.metering`` 在每次调用后累加；不记单次明细。
    ``user`` 为空表示数字员工或无法归属的调用；``staff_key`` 非空表示数字员工。
    """

    date = models.DateField(verbose_name="日期")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="llm_usage_days",
        verbose_name="用户",
    )
    # 唯一键用：user_id，无用户为 0（Django 4.2 的唯一约束无法把 NULL 视为相同值）
    user_key = models.PositiveIntegerField(default=0, editable=False)
    app_name = models.CharField(max_length=50, verbose_name="应用")
    staff_key = models.CharField(max_length=32, blank=True, default="", verbose_name="数字员工")
    calls = models.PositiveIntegerField(default=0, verbose_name="成功调用次数")
    failed_calls = models.PositiveIntegerField(default=0, verbose_name="失败调用次数")
    estimated_calls = models.PositiveIntegerField(default=0, verbose_name="估算 token 的调用次数")
    prompt_tokens = models.PositiveBigIntegerField(default=0)
    completion_tokens = models.PositiveBigIntegerField(default=0)
    total_tokens = models.PositiveBigIntegerField(default=0)
    estimated_cost = models.DecimalField(max_digits=14, decimal_places=6, default=0, verbose_name="预估费用")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "LLM 每日用量"
        verbose_name_plural = "LLM 每日用量"
        constraints = [
            models.UniqueConstraint(fields=["date", "user_key", "app_name", "staff_key"], name="uniq_llm_usage_daily"),
        ]
        indexes = [
            models.Index(fields=["date", "app_name"], name="llm_usage_date_app"),
            models.Index(fields=["user", "date"], name="llm_usage_user_date"),
        ]

    def __str__(self):
        return f"{self.date} {self.app_name} u={self.user_id} {self.total_tokens}t/{self.calls}c"


class LlmBudgetPolicy(models.Model):
    """LLM 每日上限配置：全员默认 / 用户组 / 个人 / 应用。上限 0 表示不限。

    用户上限：个人覆盖 > 所在用户组（多个组逐项取最宽松）> 全员默认。
    ``soft_limit_percent`` 只取全员默认那条，达到该比例降为只读。
    """

    SCOPE_DEFAULT = "default"
    SCOPE_GROUP = "group"
    SCOPE_USER = "user"
    SCOPE_APP = "app"
    SCOPE_CHOICES = [
        (SCOPE_DEFAULT, "全员默认"),
        (SCOPE_GROUP, "用户组"),
        (SCOPE_USER, "个人"),
        (SCOPE_APP, "应用"),
    ]

    scope = models.CharField(max_length=16, choices=SCOPE_CHOICES, verbose_name="作用范围")
    group = models.ForeignKey(
        "auth.Group", null=True, blank=True, on_delete=models.CASCADE, related_name="+", verbose_name="用户组"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="llm_budget_policies",
        verbose_name="用户",
    )
    app_name = models.CharField(max_length=50, blank=True, default="", verbose_name="应用")
    daily_token_limit = models.PositiveBigIntegerField(default=0, verbose_name="每日 token 上限（0 不限）")
    daily_call_limit = models.PositiveIntegerField(default=0, verbose_name="每日调用次数上限（0 不限）")
    soft_limit_percent = models.PositiveSmallIntegerField(default=80, verbose_name="只读阈值（%）")
    note = models.CharField(max_length=200, blank=True, default="", verbose_name="备注")
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "LLM 预算上限"
        verbose_name_plural = "LLM 预算上限"
        constraints = [
            models.UniqueConstraint(
                fields=["scope"], condition=models.Q(scope="default"), name="uniq_llm_budget_default"
            ),
            models.UniqueConstraint(fields=["group"], condition=models.Q(scope="group"), name="uniq_llm_budget_group"),
            models.UniqueConstraint(fields=["user"], condition=models.Q(scope="user"), name="uniq_llm_budget_user"),
            models.UniqueConstraint(fields=["app_name"], condition=models.Q(scope="app"), name="uniq_llm_budget_app"),
        ]
        ordering = ["scope", "id"]

    def __str__(self):
        return f"{self.get_scope_display()} {self.group or self.user or self.app_name or ''}".strip()
