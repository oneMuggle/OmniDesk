from django.db import models
from django.conf import settings
from users.models import CustomUser
import os
import uuid

def template_upload_path(instance, filename):
    return f"templates/{instance.user.id}/{uuid.uuid4()}{os.path.splitext(filename)[1]}"

class Personnel(models.Model):
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='personnel_records',
        help_text='关联创建用户'
    )
    name = models.CharField(max_length=100, default='', help_text='请输入人员姓名')
    phone = models.CharField(max_length=20, default='', help_text='请输入联系电话')
    department = models.CharField(max_length=100, blank=True)
    position = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} - {self.position}"
    
    class Meta:
        ordering = ['-created_at']

class ExperimentResponsible(models.Model):
    experiment = models.ForeignKey('Experiment', on_delete=models.CASCADE)
    responsible = models.ForeignKey('ResponsiblePerson', on_delete=models.CASCADE)
    role = models.CharField(max_length=100, default='负责人')

    class Meta:
        db_table = 'experiment_responsible'

class Experiment(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    experiment_info = models.TextField(verbose_name='试验信息', blank=True)
    responsible_persons = models.ManyToManyField('ResponsiblePerson', through=ExperimentResponsible, blank=True)
    train_count = models.PositiveIntegerField(verbose_name='车次数量', default=0)
    created_by = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

    class Meta:
        ordering = ['-created_at']

class DocumentTemplate(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    template_file = models.FileField(upload_to=template_upload_path)
    created_at = models.DateTimeField(auto_now_add=True)
    variables = models.JSONField(default=list)

    def __str__(self):
        return f"{self.name} - {self.user.email}"

class ResponsiblePerson(models.Model):
    EVENT_TYPES = [
        ('train', '列车调度'),
        ('experiment', '试验项目'),
        ('maintenance', '设备维护')
    ]
    
    name = models.CharField(max_length=100, verbose_name='姓名')
    position = models.CharField(max_length=100, verbose_name='职位')
    contact = models.CharField(max_length=100, verbose_name='联系方式')
    event_type = models.CharField(max_length=20, choices=EVENT_TYPES, verbose_name='事件类型', default='train')
    event = models.ForeignKey(Experiment, on_delete=models.CASCADE, related_name='responsibles', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.get_event_type_display()}) - {self.position}"

    class Meta:
        verbose_name = '负责人'
        verbose_name_plural = '负责人管理'
        ordering = ['-updated_at']

class Equipment(models.Model):
    name = models.CharField(max_length=100, verbose_name='设备名称')
    description = models.TextField(verbose_name='设备简介')
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='equipment_records',
        verbose_name='创建用户'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = '试验设备'
        verbose_name_plural = '试验设备管理'
        ordering = ['-created_at']
