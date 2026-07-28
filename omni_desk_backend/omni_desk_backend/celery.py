# omni_desk_backend/omni_desk_backend/celery.py

import os

from celery import Celery
from django.conf import settings

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "omni_desk_backend.settings")

app = Celery("omni_desk_backend")

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()

# 联培生考核批次自动创建: 每月 N 号 02:00 触发 (N 来自 settings.JOINT_STUDENT_CYCLE_DAY)
# 仅在已有 beat_schedule (来自 settings.CELERY_BEAT_SCHEDULE) 之上追加, 不覆盖。
app.conf.beat_schedule.update({
    "create-monthly-assessment-cycle": {
        "task": "joint_students.check_and_create_assessment_cycle",
        "cron": f"0 2 {settings.JOINT_STUDENT_CYCLE_DAY} * *",
        "kwargs": {"trigger_source": "auto"},
    },
})


@app.task(bind=True)
def debug_task(self):
    print(f"Request: {self.request!r}")
