from django.db import models
from users.models import CustomUser


class Personnel(models.Model):
    name = models.CharField(max_length=100)
    department = models.CharField(max_length=50)
    phone = models.CharField(max_length=15, blank=True, null=True)

    class Meta:
        ordering = ['id']  # 设置默认排序字段

    def __str__(self):
        return f"{self.name} ({self.department})"

class Equipment(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    
    class Meta:
            ordering = ['id']  # 设置默认排序字段

    def __str__(self):
        return self.name


class TimeSlot(models.Model):
    trial = models.ForeignKey('Trial', on_delete=models.CASCADE, related_name='time_slots')
    start_time = models.DateTimeField(verbose_name="实际开始时间")
    end_time = models.DateTimeField(verbose_name="实际结束时间")
    
    class Meta:
        ordering = ['start_time']
        verbose_name = '试验时间段'

    def __str__(self):
        return f"{self.start_time.strftime('%Y-%m-%d %H:%M')} - {self.end_time.strftime('%Y-%m-%d %H:%M')}"

class Trial(models.Model):
    title = models.CharField(max_length=200)
    client = models.CharField(max_length=200)
    description = models.TextField()
    start_date = models.DateTimeField(verbose_name="预期开始时间")
    end_date = models.DateTimeField(verbose_name="预期结束时间")
    equipments = models.ManyToManyField('Equipment', blank=True)
    responsible_persons = models.ManyToManyField(Personnel)
    status = models.CharField(max_length=20, choices=[
        ('planned', '计划中'),
        ('in_progress', '进行中'),
        ('completed', '已完成'),
        ('cancelled', '已取消')
    ], default='planned')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

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
    owner = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE)
    
    def __str__(self):
        return f"{self.name} ({self.get_experiment_type_display()})"
