from django.db import models
from users.models import CustomUser


class Notification(models.Model):
    TYPE_CHOICES = [
        ("schedule_change", "排班变更"),
        ("announcement", "公告发布"),
        ("memo_due", "备忘录到期"),
        ("calibration_reminder", "校准提醒"),
        ("project_update", "项目更新"),
        ("compliance_issue", "合规问题"),
        ("system", "系统通知"),
        # ---- P1-1 新增类型(2026-06-05 人员-用户关联方案) ----
        ("position_changed", "岗位/部门变动"),
        ("account_linked", "账号已关联"),
        ("emergency_contact", "紧急联系人变更"),
        ("training_assigned", "培训任务分配"),
        ("reward_punishment", "奖惩记录"),
        # ---- SP1-2 新增类型(2026-06-06 排班换班方案,决策 1C:两人互认即生效) ----
        ("schedule_swap_requested", "换班申请已发起"),
        ("schedule_swap_approved", "换班已生效(双方互认)"),
        ("schedule_swap_rejected", "换班被接收方拒绝"),
        ("schedule_swap_cancelled", "换班已撤销"),
        ("schedule_swap_expired", "换班申请已超时"),
    ]

    PRIORITY_CHOICES = [
        (1, "低"),
        (2, "普通"),
        (3, "高"),
        (4, "紧急"),
    ]
    PRIORITY_LOW = 1
    PRIORITY_NORMAL = 2
    PRIORITY_HIGH = 3
    PRIORITY_URGENT = 4

    user = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name="notifications", verbose_name="接收用户"
    )
    type = models.CharField(max_length=30, choices=TYPE_CHOICES, verbose_name="通知类型")
    priority = models.PositiveSmallIntegerField(
        choices=PRIORITY_CHOICES, default=PRIORITY_NORMAL, verbose_name="优先级"
    )
    title = models.CharField(max_length=200, verbose_name="标题")
    content = models.TextField(verbose_name="内容")
    link = models.CharField(max_length=500, blank=True, verbose_name="跳转链接")
    is_read = models.BooleanField(default=False, verbose_name="是否已读", db_index=True)
    read_at = models.DateTimeField(null=True, blank=True, verbose_name="已读时间")
    dedupe_key = models.CharField(max_length=128, blank=True, db_index=True, verbose_name="去重键")
    is_system = models.BooleanField(default=False, verbose_name="系统通知")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "通知"
        verbose_name_plural = "通知管理"
        indexes = [
            models.Index(fields=["user", "is_read", "-created_at"], name="notif_user_read_idx"),
            models.Index(fields=["dedupe_key", "created_at"], name="notif_dedupe_idx"),
        ]

    def __str__(self):
        return f"[{self.get_type_display()}] {self.title}"


class NotificationPreference(models.Model):
    """用户通知偏好:免打扰时段 + 渠道开关。

    渠道开关(channel_settings)为 JSONField,示例:
        {
            "email": {"schedule_change": true, "announcement": false, ...},
            "sms":   {"schedule_change": true}
        }
    未在 JSON 中列出的 type,默认走"全开"策略(即全渠道均发送)。
    """

    user = models.OneToOneField(
        CustomUser, on_delete=models.CASCADE, related_name="notification_pref", verbose_name="用户"
    )
    quiet_hours_start = models.TimeField(null=True, blank=True, verbose_name="免打扰开始")
    quiet_hours_end = models.TimeField(null=True, blank=True, verbose_name="免打扰结束")
    channel_settings = models.JSONField(default=dict, blank=True, verbose_name="渠道设置")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        verbose_name = "通知偏好"
        verbose_name_plural = "通知偏好管理"

    def __str__(self):
        return f"通知偏好:{self.user.username}"
