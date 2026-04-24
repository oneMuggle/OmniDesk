from django.db import models
from django.db.models import JSONField
from users.models import CustomUser
# 导入新的 personnel 模型
from personnel.models import Personnel

class Equipment(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    
    class Meta:
        ordering = ['id']  # 设置默认排序字段
        verbose_name = '试验'
        verbose_name_plural = '试验管理'
        permissions = [
            ("manage_equipment", "Can manage equipment"),
        ]

    def __str__(self):
        return self.name


class TimeSlot(models.Model):
    trial = models.ForeignKey('Trial',
        on_delete=models.CASCADE,
        related_name='time_slots',
        verbose_name='关联试验')
    start_time = models.DateTimeField(verbose_name="开始时间")
    end_time = models.DateTimeField(verbose_name="结束时间")
    description = models.TextField(verbose_name="时间段描述", blank=True)
    
    class Meta:
        ordering = ['start_time']
        verbose_name = '试验时间段'
        constraints = [
            models.CheckConstraint(
                name='prevent_time_slot_overlap',
                check=models.Q(start_time__lt=models.F('end_time'))
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
        ('planned', '计划中'),
        ('in_progress', '进行中'),
        ('completed', '已完成'),
        ('cancelled', '已取消')
    ]

    title = models.CharField(max_length=200, verbose_name="试验名称")
    version = models.IntegerField(default=0, verbose_name="版本号")
    client = models.CharField(max_length=200, verbose_name="客户单位") 
    description = models.TextField(verbose_name="试验描述")
    start_date = models.DateTimeField(verbose_name="主开始时间", null=True, blank=True)
    end_date = models.DateTimeField(verbose_name="主结束时间", null=True, blank=True)
    equipments = models.ManyToManyField(
        Equipment, 
        blank=True, 
        related_name='trials',
        verbose_name="相关设备"
    )
    responsible_persons = models.ManyToManyField(
        'personnel.Personnel',
        related_name='trials',
        verbose_name="责任人"
    )
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='planned',
        verbose_name="试验状态"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    def save(self, *args, **kwargs):
        """自动从时间段计算主时间范围"""
        super().save(*args, **kwargs)
        # The related TimeSlot's save/delete will call update_time_range.
        # We call it here to handle cases where a Trial is saved directly.
        if not kwargs.get('skip_time_range_update', False):
            self.update_time_range()

    def update_time_range(self):
        """
        Calculates and updates the Trial's start_date and end_date based on its associated TimeSlots.
        """
        from django.db.models import Min, Max
        
        time_slots = self.time_slots.all()
        if time_slots.exists():
            time_range = time_slots.aggregate(
                min_start=Min('start_time'),
                max_end=Max('end_time')
            )
            new_start_date = time_range['min_start']
            new_end_date = time_range['max_end']
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
        return TimeSlot.objects.filter(trial=self).order_by('start_time')

    class Meta:
            ordering = ['id']  # 设置默认排序字段

    def __str__(self):
        return self.title


class DocumentTemplate(models.Model):
    EXPERIMENT_TYPES = [
        ('chemical', '化学实验'),
        ('biological', '生物实验'),
        ('physical', '物理实验'),
    ]
    
    name = models.CharField(max_length=100)
    experiment_type = models.CharField(max_length=20, choices=EXPERIMENT_TYPES)
    template_file = models.FileField(upload_to='templates/')
    created_at = models.DateTimeField(auto_now_add=True)
    owner = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE, related_name='event_templates')
    
    def __str__(self):
        return f"{self.name} ({self.get_experiment_type_display()})"

class Schedule(models.Model):
    duty_date = models.DateField(unique=True, verbose_name="值班日期")
    duty_person = models.ForeignKey(
        'personnel.Personnel',
        on_delete=models.SET_NULL,
        null=True,
        related_name='duty_schedules',
        verbose_name="值班人员"
    )
    duty_leader = models.ForeignKey(
        'personnel.Personnel',
        on_delete=models.SET_NULL,
        null=True,
        related_name='leader_schedules',
        verbose_name="值班领导"
    )
    
    class Meta:
        ordering = ['duty_date']
        verbose_name = '排班表'
        verbose_name_plural = '排班管理'
        permissions = [
            ("manage_schedule", "Can manage schedule"),
            ("manage_announcements", "Can manage announcements"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['duty_date'], 
                name='unique_duty_date'
            )
        ]
    
    def __str__(self):
        return f"{self.duty_date}: {self.duty_person.name} (值班), {self.duty_leader.name} (领导)"

class Announcement(models.Model):
    title = models.CharField(max_length=200, verbose_name="公告标题")
    content = models.TextField(verbose_name="公告内容")
    author = models.ForeignKey(
        CustomUser, 
        on_delete=models.SET_NULL, 
        null=True,
        related_name='announcements',
        verbose_name="发布者"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        ordering = ['-created_at']
        verbose_name = '公告'
        verbose_name_plural = '公告管理'
        permissions = [
            ("manage_announcements", "Can manage announcements"),
        ]

    def __str__(self):
        return self.title
class UploadedImage(models.Model):
    image = models.ImageField(upload_to='announcement_images/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.image.name

class PersonnelSequence(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="人员顺序名称")
    personnel = models.ManyToManyField(
        'personnel.Personnel',
        related_name='personnel_sequences',
        verbose_name="工作日人员"
    )
    sequence = models.JSONField(default=list, verbose_name="工作日人员ID顺序列表")
    
    holiday_personnel = models.ManyToManyField(
        'personnel.Personnel',
        related_name='holiday_personnel_sequences',
        verbose_name="节假日人员",
        blank=True
    )
    holiday_sequence = models.JSONField(default=list, verbose_name="节假日人员ID顺序列表", blank=True)

    class Meta:
        ordering = ['id']
        verbose_name = "人员顺序"
        verbose_name_plural = "人员顺序管理"

    def __str__(self):
        return self.name

class LeaderSequence(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="领导顺序名称")
    personnel = models.ManyToManyField('personnel.Personnel', related_name='leader_sequences')
    sequence = models.JSONField(default=list, verbose_name="领导ID顺序列表")

    class Meta:
        ordering = ['id']
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
