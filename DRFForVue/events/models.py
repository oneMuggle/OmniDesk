from django.db import models
from django.db.models import JSONField
from users.models import CustomUser

class Personnel(models.Model):
    name = models.CharField(max_length=100)
    department = models.CharField(max_length=50)
    phone = models.CharField(max_length=15, blank=True, null=True)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f"{self.name} ({self.department})"

class Equipment(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    
    class Meta:
        ordering = ['id']  # 设置默认排序字段
        verbose_name = '试验'
        verbose_name_plural = '试验管理'

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
            self.trial.update_time_range(changed_slots=[self])

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
        Personnel,
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
        # 先保存基础信息生成ID
        super().save(*args, **kwargs)  
        
        # 单独调用更新逻辑，避免关联关系问题
        self.update_time_range()

    def update_time_range(self, changed_slots=None):
        """优化后的时间范围计算方法"""
        if not hasattr(self, '_time_range_dirty'):
            self._time_range_dirty = False
            
        # 如果有传入变更的时间段，只设置脏标记
        if changed_slots:
            self._time_range_dirty = True
            return
            
        # 如果没有脏标记则跳过计算
        if not self._time_range_dirty:
            return
            
        time_slots = self.time_slots.all()
        if time_slots.exists():
            # 使用数据库聚合查询优化性能
            from django.db.models import Min, Max
            time_range = time_slots.aggregate(
                min_start=Min('start_time'),
                max_end=Max('end_time')
            )
            
            # 使用update避免递归保存
            self.__class__.objects.filter(pk=self.pk).update(
                start_date=time_range['min_start'],
                end_date=time_range['max_end']
            )
            self._time_range_dirty = False

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
        Personnel, 
        on_delete=models.PROTECT, 
        related_name='duty_schedules',
        verbose_name="值班人员"
    )
    duty_leader = models.ForeignKey(
        Personnel, 
        on_delete=models.PROTECT, 
        related_name='leader_schedules',
        verbose_name="值班领导"
    )
    
    class Meta:
        ordering = ['duty_date']
        verbose_name = '排班表'
        verbose_name_plural = '排班管理'
        constraints = [
            models.UniqueConstraint(
                fields=['duty_date'], 
                name='unique_duty_date'
            )
        ]
    
    def __str__(self):
        return f"{self.duty_date}: {self.duty_person.name} (值班), {self.duty_leader.name} (领导)"
