"""联培生模块的 Celery 任务。"""

import logging

from celery import shared_task
from django.utils import timezone

from joint_students.models import AssessmentCycle
from joint_students.services.cycle import create_cycle

logger = logging.getLogger(__name__)


@shared_task(name="joint_students.check_and_create_assessment_cycle")
def check_and_create_assessment_cycle(
    year: int = None,
    month: int = None,
    trigger_source: str = AssessmentCycle.TRIGGER_AUTO,
    creator=None,
) -> dict:
    """检查并创建本月考核批次 (幂等)。

    Celery Beat 每月 1 号 02:00 自动调用 (在 celery.py 配置)。
    联培生管理员也可手动调用 (通过 API 端点)。
    """
    now = timezone.now()
    year = year or now.year
    month = month or now.month

    cycle = create_cycle(year, month, trigger_source=trigger_source, creator=creator)
    return {
        "cycle_id": cycle.id,
        "year": cycle.year,
        "month": cycle.month,
        "status": cycle.status,
        "trigger_source": cycle.trigger_source,
    }
