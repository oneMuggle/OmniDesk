from django.db import models
from users.models import CustomUser
import os
import uuid

def template_upload_path(instance, filename):
    return f"templates/{instance.user.id}/{uuid.uuid4()}{os.path.splitext(filename)[1]}"

class Event(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    experiment_info = models.TextField(verbose_name='试验信息', blank=True)
    responsible_person = models.CharField(max_length=100, verbose_name='负责人', blank=True)
    train_count = models.PositiveIntegerField(verbose_name='车次数量', default=0)
    created_by = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
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
