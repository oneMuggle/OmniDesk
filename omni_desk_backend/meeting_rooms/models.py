from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class MeetingRoom(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="会议室名称")
    description = models.TextField(blank=True, null=True, verbose_name="描述")
    capacity = models.IntegerField(blank=True, null=True, verbose_name="容量")
    location = models.CharField(max_length=255, blank=True, null=True, verbose_name="位置")

    class Meta:
        verbose_name = "会议室"
        verbose_name_plural = "会议室"

    def __str__(self):
        return self.name

class MeetingRoomBooking(models.Model):
    meeting_room = models.ForeignKey(MeetingRoom, on_delete=models.CASCADE, related_name='bookings', verbose_name="会议室")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='meeting_bookings', verbose_name="预约用户")
    start_time = models.DateTimeField(verbose_name="开始时间")
    end_time = models.DateTimeField(verbose_name="结束时间")
    title = models.CharField(max_length=255, verbose_name="预约主题")
    participants = models.TextField(blank=True, null=True, verbose_name="参与人员")
    description = models.TextField(blank=True, null=True, verbose_name="预约描述")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        verbose_name = "会议室预约"
        verbose_name_plural = "会议室预约"
        ordering = ['start_time']

    def clean(self):
        # 确保结束时间在开始时间之后
        if self.start_time and self.end_time and self.start_time >= self.end_time:
            raise ValidationError("结束时间必须在开始时间之后。")

        # 确保预约时间在当前时间之后
        if self.start_time and self.start_time < timezone.now():
            raise ValidationError("预约时间不能在当前时间之前。")

        # 检查与现有预约的冲突
        # 排除当前对象自身，以便在更新时可以保存
        conflicting_bookings = MeetingRoomBooking.objects.filter(
            meeting_room=self.meeting_room,
            start_time__lt=self.end_time,
            end_time__gt=self.start_time
        ).exclude(pk=self.pk)

        if conflicting_bookings.exists():
            raise ValidationError("该时间段内会议室已被预约。")

        # 检查与维护时间的冲突
        conflicting_maintenance = MeetingRoomMaintenance.objects.filter(
            meeting_room=self.meeting_room,
            start_time__lt=self.end_time,
            end_time__gt=self.start_time
        ).exclude(pk=self.pk) # 维护时间通常没有pk，但为了通用性保留

        if conflicting_maintenance.exists():
            raise ValidationError("该时间段内会议室正在维护。")

    def save(self, *args, **kwargs):
        self.full_clean() # 调用clean方法进行验证
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.title} ({self.meeting_room.name}): {self.start_time.strftime('%Y-%m-%d %H:%M')} - {self.end_time.strftime('%H:%M')}"

class MeetingRoomMaintenance(models.Model):
    meeting_room = models.ForeignKey(MeetingRoom, on_delete=models.CASCADE, related_name='maintenance_periods', verbose_name="会议室")
    start_time = models.DateTimeField(verbose_name="维护开始时间")
    end_time = models.DateTimeField(verbose_name="维护结束时间")
    reason = models.CharField(max_length=255, verbose_name="维护原因")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        verbose_name = "会议室维护"
        verbose_name_plural = "会议室维护"
        ordering = ['start_time']

    def clean(self):
        # 确保结束时间在开始时间之后
        if self.start_time and self.end_time and self.start_time >= self.end_time:
            raise ValidationError("维护结束时间必须在维护开始时间之后。")

        # 检查与现有维护时间的冲突
        conflicting_maintenance = MeetingRoomMaintenance.objects.filter(
            meeting_room=self.meeting_room,
            start_time__lt=self.end_time,
            end_time__gt=self.start_time
        ).exclude(pk=self.pk)

        if conflicting_maintenance.exists():
            raise ValidationError("该时间段内会议室已有维护计划。")

        # 检查与现有预约的冲突
        conflicting_bookings = MeetingRoomBooking.objects.filter(
            meeting_room=self.meeting_room,
            start_time__lt=self.end_time,
            end_time__gt=self.start_time
        )

        if conflicting_bookings.exists():
            raise ValidationError("该时间段内会议室存在已有的预约，无法设置维护。")

    def save(self, *args, **kwargs):
        self.full_clean() # 调用clean方法进行验证
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.meeting_room.name} 维护: {self.start_time.strftime('%Y-%m-%d %H:%M')} - {self.end_time.strftime('%H:%M')} ({self.reason})"
