"""联培生管理 - 数据模型 (5 张表)。"""

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from personnel.models import Personnel


class JointStudent(models.Model):
    """联培生扩展表 (1:1 关联 Personnel)。"""

    STUDENT_TYPE_MASTER = "master"
    STUDENT_TYPE_PHD = "phd"
    STUDENT_TYPE_CHOICES = [
        (STUDENT_TYPE_MASTER, "硕士"),
        (STUDENT_TYPE_PHD, "博士"),
    ]

    personnel = models.OneToOneField(
        Personnel,
        on_delete=models.PROTECT,
        related_name="joint_student",
        verbose_name="关联人员",
    )
    student_type = models.CharField(
        max_length=10,
        choices=STUDENT_TYPE_CHOICES,
        verbose_name="培养类型",
    )
    student_id = models.CharField(max_length=50, unique=True, verbose_name="学号")
    enrollment_date = models.DateField(verbose_name="入学日期")
    graduation_date = models.DateField(null=True, blank=True, verbose_name="毕业日期")
    mentor = models.ForeignKey(
        Personnel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="mentored_joint_students",
        verbose_name="导师",
    )
    is_active = models.BooleanField(default=True, verbose_name="在读")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        verbose_name = "联培生"
        verbose_name_plural = "联培生管理"
        indexes = [models.Index(fields=["student_type", "is_active"], name="js_type_active_idx")]

    def __str__(self):
        return f"{self.student_id} - {self.personnel.name}"


class MonthlyReport(models.Model):
    """月度报告。一人一月一份。"""

    STATUS_DRAFT = "draft"
    STATUS_SUBMITTED = "submitted"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "草稿"),
        (STATUS_SUBMITTED, "已提交"),
        (STATUS_APPROVED, "已通过"),
        (STATUS_REJECTED, "已驳回"),
    ]

    joint_student = models.ForeignKey(
        JointStudent,
        on_delete=models.CASCADE,
        related_name="monthly_reports",
        verbose_name="联培生",
    )
    year = models.PositiveSmallIntegerField(verbose_name="年")
    month = models.PositiveSmallIntegerField(verbose_name="月")
    work_progress = models.TextField(verbose_name="工作进展")
    work_highlights = models.TextField(verbose_name="工作亮点")
    attendance_days_actual = models.DecimalField(
        max_digits=5,
        decimal_places=1,
        verbose_name="实际出勤天数",
    )
    attendance_days_expected = models.DecimalField(
        max_digits=5,
        decimal_places=1,
        default=22,
        verbose_name="应出勤天数",
    )
    attendance_notes = models.TextField(blank=True, verbose_name="出勤说明")
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default=STATUS_DRAFT,
        verbose_name="状态",
    )
    submitted_at = models.DateTimeField(null=True, blank=True, verbose_name="提交时间")
    reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name="审核时间")
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_reports",
        verbose_name="审核人",
    )
    reviewer_comment = models.TextField(blank=True, verbose_name="审核意见")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        verbose_name = "月度报告"
        verbose_name_plural = "月度报告"
        ordering = ["-year", "-month"]
        constraints = [
            models.UniqueConstraint(
                fields=["joint_student", "year", "month"],
                name="report_unique_per_student_month",
            ),
        ]

    def __str__(self):
        return f"{self.joint_student} {self.year}-{self.month:02d}"


class AssessmentCycle(models.Model):
    """考核批次。一月一批。"""

    STATUS_COLLECTING = "collecting"
    STATUS_CLOSED = "closed"
    STATUS_FINALIZED = "finalized"
    STATUS_CHOICES = [
        (STATUS_COLLECTING, "收集评分中"),
        (STATUS_CLOSED, "已截止"),
        (STATUS_FINALIZED, "已归档"),
    ]

    TRIGGER_AUTO = "auto"
    TRIGGER_MANUAL = "manual"
    TRIGGER_CHOICES = [(TRIGGER_AUTO, "Celery自动"), (TRIGGER_MANUAL, "管理员手动")]

    year = models.PositiveSmallIntegerField(verbose_name="年")
    month = models.PositiveSmallIntegerField(verbose_name="月")
    cycle_start_date = models.DateField(verbose_name="报告提交窗口开始")
    cycle_end_date = models.DateField(verbose_name="报告审核截止")
    scoring_deadline = models.DateField(verbose_name="专家打分截止")
    status = models.CharField(
        max_length=15,
        choices=STATUS_CHOICES,
        default=STATUS_COLLECTING,
        verbose_name="状态",
    )
    trigger_source = models.CharField(
        max_length=10,
        choices=TRIGGER_CHOICES,
        default=TRIGGER_MANUAL,
        verbose_name="触发来源",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_cycles",
        verbose_name="创建人",
    )

    class Meta:
        verbose_name = "考核批次"
        verbose_name_plural = "考核批次"
        ordering = ["-year", "-month"]
        constraints = [
            models.UniqueConstraint(fields=["year", "month"], name="cycle_unique_per_month"),
        ]

    def __str__(self):
        return f"{self.year}-{self.month:02d}"


class ExpertScore(models.Model):
    """专家打分。"""

    cycle = models.ForeignKey(
        AssessmentCycle,
        on_delete=models.CASCADE,
        related_name="scores",
        verbose_name="考核批次",
    )
    expert = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="expert_scores",
        verbose_name="专家",
    )
    joint_student = models.ForeignKey(
        JointStudent,
        on_delete=models.PROTECT,
        related_name="expert_scores",
        verbose_name="联培生",
    )
    score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="分数",
    )
    comment = models.TextField(blank=True, verbose_name="评语")
    submitted_at = models.DateTimeField(verbose_name="提交时间")
    is_locked = models.BooleanField(default=True, verbose_name="是否锁定")

    class Meta:
        verbose_name = "专家打分"
        verbose_name_plural = "专家打分"
        constraints = [
            models.UniqueConstraint(
                fields=["cycle", "expert", "joint_student"],
                name="score_unique_per_expert_cycle_student",
            ),
        ]

    def __str__(self):
        return f"{self.expert} → {self.joint_student}: {self.score}"


class StipendRecord(models.Model):
    """补助记录。"""

    STATUS_PENDING = "pending"
    STATUS_LOCKED = "locked"
    STATUS_CHOICES = [(STATUS_PENDING, "待复核"), (STATUS_LOCKED, "已锁定")]

    GRADE_A = "A"
    GRADE_B = "B"
    GRADE_CHOICES = [(GRADE_A, "A档"), (GRADE_B, "B档")]

    cycle = models.ForeignKey(
        AssessmentCycle,
        on_delete=models.CASCADE,
        related_name="stipends",
        verbose_name="考核批次",
    )
    joint_student = models.ForeignKey(
        JointStudent,
        on_delete=models.PROTECT,
        related_name="stipends",
        verbose_name="联培生",
    )
    average_score = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="平均分")
    rank_in_cycle = models.PositiveSmallIntegerField(verbose_name="周期内排名")
    grade = models.CharField(max_length=1, choices=GRADE_CHOICES, verbose_name="档次")
    base_amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="基本额度")
    grade_coefficient = models.DecimalField(max_digits=4, decimal_places=2, verbose_name="档次系数")
    attendance_ratio = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="出勤比")
    final_amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="最终金额")
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        verbose_name="状态",
    )
    locked_at = models.DateTimeField(null=True, blank=True, verbose_name="锁定时间")
    locked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="locked_stipends",
        verbose_name="锁定操作人",
    )
    notes = models.TextField(blank=True, verbose_name="备注")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        verbose_name = "补助记录"
        verbose_name_plural = "补助记录"
        constraints = [
            models.UniqueConstraint(
                fields=["cycle", "joint_student"],
                name="stipend_unique_per_cycle_student",
            ),
        ]

    def __str__(self):
        return f"{self.joint_student} {self.cycle}: {self.final_amount} ({self.grade})"
