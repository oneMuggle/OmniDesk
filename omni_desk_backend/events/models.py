from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from users.models import CustomUser

# 导入新的 personnel 模型


class Equipment(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()

    class Meta:
        ordering = ["id"]  # 设置默认排序字段
        verbose_name = "试验"
        verbose_name_plural = "试验管理"
        permissions = [
            ("manage_equipment", "Can manage equipment"),
        ]

    def __str__(self):
        return self.name


class TimeSlot(models.Model):
    trial = models.ForeignKey("Trial", on_delete=models.CASCADE, related_name="time_slots", verbose_name="关联试验")
    start_time = models.DateTimeField(verbose_name="开始时间")
    end_time = models.DateTimeField(verbose_name="结束时间")
    description = models.TextField(verbose_name="时间段描述", blank=True)

    class Meta:
        ordering = ["start_time"]
        verbose_name = "试验时间段"
        constraints = [
            models.CheckConstraint(
                name="prevent_time_slot_overlap", check=models.Q(start_time__lt=models.F("end_time"))
            )
        ]

    def __str__(self):
        return f"{self.start_time.strftime('%Y-%m-%d %H:%M')} - {self.end_time.strftime('%Y-%m-%d %H:%M')}"

    def save(self, *args, **kwargs):
        """保存时触发关联试验的时间范围更新"""
        super().save(*args, **kwargs)
        if self.trial:
            self.trial.update_time_range()

    def delete(self, *args, **kwargs):
        """删除时触发关联试验的时间范围更新"""
        trial = self.trial
        super().delete(*args, **kwargs)
        if trial:
            trial.update_time_range()


class Trial(models.Model):
    STATUS_CHOICES = [
        ("planned", "计划中"),
        ("in_progress", "进行中"),
        ("completed", "已完成"),
        ("cancelled", "已取消"),
    ]

    title = models.CharField(max_length=200, verbose_name="试验名称")
    version = models.IntegerField(default=0, verbose_name="版本号")
    client = models.CharField(max_length=200, verbose_name="客户单位")
    description = models.TextField(verbose_name="试验描述")
    start_date = models.DateTimeField(verbose_name="主开始时间", null=True, blank=True, db_index=True)
    end_date = models.DateTimeField(verbose_name="主结束时间", null=True, blank=True, db_index=True)
    equipments = models.ManyToManyField(Equipment, blank=True, related_name="trials", verbose_name="相关设备")
    responsible_persons = models.ManyToManyField("personnel.Personnel", related_name="trials", verbose_name="责任人")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="planned", verbose_name="试验状态")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    def save(self, *args, **kwargs):
        """自动从时间段计算主时间范围"""
        super().save(*args, **kwargs)
        # The related TimeSlot's save/delete will call update_time_range.
        # We call it here to handle cases where a Trial is saved directly.
        if not kwargs.get("skip_time_range_update", False):
            self.update_time_range()

    def update_time_range(self):
        """
        Calculates and updates the Trial's start_date and end_date based on its associated TimeSlots.
        """
        from django.db.models import Max, Min

        time_slots = self.time_slots.all()
        if time_slots.exists():
            time_range = time_slots.aggregate(min_start=Min("start_time"), max_end=Max("end_time"))
            new_start_date = time_range["min_start"]
            new_end_date = time_range["max_end"]
        else:
            new_start_date = None
            new_end_date = None

        # Update only if the dates have changed to prevent recursion
        if self.start_date != new_start_date or self.end_date != new_end_date:
            # Use update to bypass this save method and avoid recursion
            Trial.objects.filter(pk=self.pk).update(start_date=new_start_date, end_date=new_end_date)
            # Refresh the current instance's fields for immediate use
            self.start_date = new_start_date
            self.end_date = new_end_date

    def get_time_slots(self):
        """获取关联的时间段"""
        return TimeSlot.objects.filter(trial=self).order_by("start_time")

    class Meta:
        ordering = ["id"]  # 设置默认排序字段

    def __str__(self):
        return self.title


class DocumentTemplate(models.Model):
    EXPERIMENT_TYPES = [
        ("chemical", "化学实验"),
        ("biological", "生物实验"),
        ("physical", "物理实验"),
    ]

    name = models.CharField(max_length=100)
    experiment_type = models.CharField(max_length=20, choices=EXPERIMENT_TYPES)
    template_file = models.FileField(upload_to="templates/")
    created_at = models.DateTimeField(auto_now_add=True)
    owner = models.ForeignKey("users.CustomUser", on_delete=models.CASCADE, related_name="event_templates")

    def __str__(self):
        return f"{self.name} ({self.get_experiment_type_display()})"


class Schedule(models.Model):
    duty_date = models.DateField(unique=True, verbose_name="值班日期")
    duty_person = models.ForeignKey(
        "personnel.Personnel",
        on_delete=models.SET_NULL,
        null=True,
        related_name="duty_schedules",
        verbose_name="值班人员",
    )
    duty_leader = models.ForeignKey(
        "personnel.Personnel",
        on_delete=models.SET_NULL,
        null=True,
        related_name="leader_schedules",
        verbose_name="值班领导",
    )

    class Meta:
        ordering = ["duty_date"]
        verbose_name = "排班表"
        verbose_name_plural = "排班管理"
        permissions = [
            ("manage_schedule", "Can manage schedule"),
            ("manage_announcements", "Can manage announcements"),
        ]
        constraints = [models.UniqueConstraint(fields=["duty_date"], name="unique_duty_date")]

    def __str__(self):
        return f"{self.duty_date}: {self.duty_person.name} (值班), {self.duty_leader.name} (领导)"


class Announcement(models.Model):
    title = models.CharField(max_length=200, verbose_name="公告标题")
    content = models.TextField(verbose_name="公告内容")
    author = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True, related_name="announcements", verbose_name="发布者"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "公告"
        verbose_name_plural = "公告管理"
        permissions = [
            ("manage_announcements", "Can manage announcements"),
        ]

    def __str__(self):
        return self.title


class UploadedImage(models.Model):
    image = models.ImageField(upload_to="announcement_images/")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.image.name


class PersonnelSequence(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="人员顺序名称")
    personnel = models.ManyToManyField(
        "personnel.Personnel", related_name="personnel_sequences", verbose_name="工作日人员"
    )
    sequence = models.JSONField(default=list, verbose_name="工作日人员ID顺序列表")

    holiday_personnel = models.ManyToManyField(
        "personnel.Personnel", related_name="holiday_personnel_sequences", verbose_name="节假日人员", blank=True
    )
    holiday_sequence = models.JSONField(default=list, verbose_name="节假日人员ID顺序列表", blank=True)

    class Meta:
        ordering = ["id"]
        verbose_name = "人员顺序"
        verbose_name_plural = "人员顺序管理"

    def __str__(self):
        return self.name


class LeaderSequence(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="领导顺序名称")
    personnel = models.ManyToManyField("personnel.Personnel", related_name="leader_sequences")
    sequence = models.JSONField(default=list, verbose_name="领导ID顺序列表")

    class Meta:
        ordering = ["id"]
        verbose_name = "领导顺序"
        verbose_name_plural = "领导顺序管理"

    def __str__(self):
        return self.name


from django.utils import timezone


class Holiday(models.Model):
    name = models.CharField(max_length=100)
    start_date = models.DateField(default=timezone.now)
    end_date = models.DateField(default=timezone.now)

    def __str__(self):
        return self.name


# ---- SP1-1: ScheduleSwapRequest(决策 1C: 两人互认即生效) ----


class ScheduleSwapRequest(models.Model):
    """值班换班申请(状态机见 plan 文档 §4)。

    状态流转:
        pending → approved(接收方 accept,ViewSet 内部调 apply_swap)
        pending → rejected_by_target(接收方 reject)
        pending → cancelled(申请方 cancel)
        pending → expired(系统 48h 超时)
    """

    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected_by_target"
    STATUS_CANCELLED = "cancelled"
    STATUS_EXPIRED = "expired"
    STATUS_CHOICES = [
        (STATUS_PENDING, "待接收方确认"),
        (STATUS_APPROVED, "已生效(双方互认)"),
        (STATUS_REJECTED, "接收方已拒绝"),
        (STATUS_CANCELLED, "申请方已撤销"),
        (STATUS_EXPIRED, "已超时失效"),
    ]

    SCOPE_DUTY_PERSON = "duty_person"
    SCOPE_DUTY_LEADER = "duty_leader"
    SCOPE_CHOICES = [
        (SCOPE_DUTY_PERSON, "值班人员"),
        (SCOPE_DUTY_LEADER, "值班领导"),  # 决策 5A:首版仅用 duty_person,字段预留
    ]

    requester = models.ForeignKey(
        "personnel.Personnel",
        on_delete=models.PROTECT,
        related_name="initiated_swap_requests",
        verbose_name="申请发起人",
    )
    original_schedule = models.ForeignKey(
        Schedule,
        on_delete=models.CASCADE,
        related_name="outgoing_swap_requests",
        verbose_name="原排班",
    )
    scope = models.CharField(
        max_length=20,
        choices=SCOPE_CHOICES,
        default=SCOPE_DUTY_PERSON,
        verbose_name="换岗范围",
    )
    target_personnel = models.ForeignKey(
        "personnel.Personnel",
        on_delete=models.PROTECT,
        related_name="incoming_swap_requests",
        verbose_name="接收换班者",
    )
    target_schedule = models.ForeignKey(
        Schedule,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="incoming_swap_requests",
        verbose_name="对调排班(可选)",
        help_text="若为空=单方面替班;若有值=双向对调(决策 2C)",
    )
    reason = models.CharField(max_length=500, verbose_name="申请理由")
    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,
        verbose_name="状态",
    )

    target_decided_at = models.DateTimeField(null=True, blank=True, verbose_name="接收方决策时间")
    target_decision_note = models.CharField(max_length=500, blank=True, verbose_name="接收方备注")

    approver = models.ForeignKey(
        "users.CustomUser",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_swap_requests",
        verbose_name="审批人(本设计中=接收方 user_account)",
    )
    approved_at = models.DateTimeField(null=True, blank=True, verbose_name="生效时间")
    approval_note = models.CharField(max_length=500, blank=True, verbose_name="生效备注")

    expires_at = models.DateTimeField(db_index=True, verbose_name="失效时间(默认 48h)")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        verbose_name = "排班换班申请"
        verbose_name_plural = "排班换班申请"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "expires_at"], name="swap_status_expires_idx"),
            models.Index(fields=["requester", "status"], name="swap_requester_status_idx"),
            models.Index(fields=["target_personnel", "status"], name="swap_target_status_idx"),
        ]
        constraints = [
            # 同一原排班同时只能有一个 active 申请(pending 状态)
            models.UniqueConstraint(
                fields=["original_schedule"],
                condition=models.Q(status="pending"),
                name="uniq_active_swap_per_schedule",
            ),
        ]

    def clean(self):
        """L3 数据完整性防护。不依赖用户上下文,仅校验数据本身。"""
        super().clean()
        errors = {}
        if self.requester_id and self.target_personnel_id and self.requester_id == self.target_personnel_id:
            errors["target_personnel"] = "不能把班换给自己"
        if self.scope == self.SCOPE_DUTY_PERSON:
            if (
                self.original_schedule_id
                and self.requester_id
                and self.original_schedule.duty_person_id != self.requester_id
            ):
                errors["requester"] = "您不是该日的值班人员,无权发起换班"
        elif self.scope == self.SCOPE_DUTY_LEADER:
            if (
                self.original_schedule_id
                and self.requester_id
                and self.original_schedule.duty_leader_id != self.requester_id
            ):
                errors["requester"] = "您不是该日的值班领导,无权发起换班"
        if self.original_schedule_id and self.original_schedule.duty_date:
            if self.original_schedule.duty_date < timezone.now().date():
                errors["original_schedule"] = "无法对已过去的排班发起换班申请"
        if self.expires_at and self.expires_at <= timezone.now():
            errors["expires_at"] = "失效时间必须晚于当前时间"
        if errors:
            raise ValidationError(errors)

    def apply_swap(self, approver=None):
        """执行 Schedule 字段交换。决策 1C:接收方 accept 后自动调用。

        必须在 transaction.atomic() 块中调用;同时用 select_for_update 锁原/目标排班。
        """
        field_name = "duty_person" if self.scope == self.SCOPE_DUTY_PERSON else "duty_leader"

        original = Schedule.objects.select_for_update().get(pk=self.original_schedule_id)
        if self.target_schedule_id:
            target = Schedule.objects.select_for_update().get(pk=self.target_schedule_id)
            original_val = getattr(original, field_name)
            target_val = getattr(target, field_name)
            setattr(original, field_name, target_val)
            setattr(target, field_name, original_val)
            original.save(update_fields=[field_name])
            target.save(update_fields=[field_name])
        else:
            setattr(original, field_name, self.target_personnel)
            original.save(update_fields=[field_name])

        self.status = self.STATUS_APPROVED
        self.approver = approver
        self.approved_at = timezone.now()
        self.save(update_fields=["status", "approver", "approved_at", "updated_at"])

    @property
    def status_display(self):
        """对外暴露状态中文(供前端直接使用,免去 i18n 配置)。"""
        return self.get_status_display()

    def __str__(self):
        return f"#{self.pk} {self.requester.name} → {self.target_personnel.name} [{self.status}]"


class ScheduleSwapAuditLog(models.Model):
    """换班申请状态流转审计日志。每次状态变更追加一行。

    独立于 users.AuditLogEntry(后者专为 link_user_personnel 批处理设计)。
    """

    swap_request = models.ForeignKey(
        ScheduleSwapRequest,
        on_delete=models.CASCADE,
        related_name="audit_logs",
        verbose_name="关联换班申请",
    )
    actor = models.ForeignKey(
        "users.CustomUser",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="swap_audit_actions",
        verbose_name="操作者",
    )
    from_status = models.CharField(max_length=30, verbose_name="原状态")
    to_status = models.CharField(max_length=30, verbose_name="新状态")
    note = models.CharField(max_length=500, blank=True, verbose_name="备注")
    metadata = models.JSONField(default=dict, blank=True, verbose_name="元数据")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        verbose_name = "换班审计日志"
        verbose_name_plural = "换班审计日志"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["swap_request", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.from_status} → {self.to_status} by {self.actor_id or 'system'}"
