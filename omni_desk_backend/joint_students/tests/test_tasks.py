"""Celery 任务测试。"""
from datetime import datetime
from unittest.mock import patch

import pytest

from joint_students.models import AssessmentCycle
from joint_students.tasks import check_and_create_assessment_cycle
from joint_students.tests.factories import create_cycle


@pytest.mark.django_db
class TestCheckAndCreateAssessmentCycle:
    def test_create_cycle_for_current_month(self):
        """默认情况下为本月创建批次。"""
        with patch("joint_students.tasks.timezone") as mock_tz:
            mock_tz.now.return_value = datetime(2026, 7, 15, 10, 0, 0)
            result = check_and_create_assessment_cycle(trigger_source="auto")
        assert result["year"] == 2026
        assert result["month"] == 7
        assert result["status"] == "collecting"
        assert AssessmentCycle.objects.filter(year=2026, month=7).exists()

    def test_create_cycle_idempotent(self):
        """二次创建同月任务不会重复。"""
        create_cycle(year=2026, month=7)
        result = check_and_create_assessment_cycle(
            year=2026, month=7, trigger_source="manual",
        )
        # 第二次调用应该返回已存在, 不创建新行
        assert AssessmentCycle.objects.filter(year=2026, month=7).count() == 1
        assert result["cycle_id"] is not None

    def test_create_cycle_records_trigger_source(self):
        """trigger_source 正确记录。"""
        result = check_and_create_assessment_cycle(
            year=2026, month=8, trigger_source="manual",
        )
        cycle = AssessmentCycle.objects.get(id=result["cycle_id"])
        assert cycle.trigger_source == "manual"
