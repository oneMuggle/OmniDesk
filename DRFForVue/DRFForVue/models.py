from django.db import models
from django.contrib.auth.models import AbstractUser, Group

class CustomUser(AbstractUser):
    phone = models.CharField(max_length=20, blank=True)
    groups = models.ManyToManyField(Group, related_name='customuser_groups')

class CalendarEvent(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    description = models.TextField(blank=True)
    color = models.CharField(max_length=7, default='#3788d8')
