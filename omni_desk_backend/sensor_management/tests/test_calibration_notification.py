"""P0-L 校准提醒接入 NotificationService 测试

- 到期传感器触发 check_and_create_calibration_reminders 后产生
  type=calibration_reminder 的站内通知,发给管理员
- dedupe_key 按 传感器+日期 粒度,同日重复执行不产生重复通知
"""
from datetime import timedelta

import pytest
from django.utils import timezone

from notifications.models import Notification
from sensor_management.models import Sensor, SensorCategory
from sensor_management.tasks import check_and_create_calibration_reminders


@pytest.fixture
def due_sensor(db):
    category = SensorCategory.objects.create(name="温湿度计")
    return Sensor.objects.create(
        name="到期传感器",
        sensor_number="SN-DUE-001",
        serial_number="SN-DUE-001",
        sensor_category=category,
        last_calibration_date=timezone.now().date() - timedelta(days=400),
        calibration_interval_days=365,  # 已超期 35 天
    )


@pytest.mark.django_db
class TestCalibrationNotification:
    def test_reminder_creates_notification_for_admins(self, due_sensor, admin_user_obj):
        check_and_create_calibration_reminders()

        notes = Notification.objects.filter(type="calibration_reminder")
        assert notes.exists()
        note = notes.first()
        assert note.user_id == admin_user_obj.id
        assert note.dedupe_key == f"calibration:{due_sensor.id}:{timezone.now().date().isoformat()}"
        assert due_sensor.serial_number in note.title

    def test_same_day_rerun_does_not_duplicate(self, due_sensor, admin_user_obj):
        check_and_create_calibration_reminders()
        check_and_create_calibration_reminders()

        # 第二次执行:当天已有 CalibrationReminder → 跳过,不产生新通知
        assert Notification.objects.filter(type="calibration_reminder").count() == 1

    def test_no_admin_no_crash(self, due_sensor):
        """无管理员时任务安全跳过(既有行为不回归)。"""
        check_and_create_calibration_reminders()
        assert not Notification.objects.filter(type="calibration_reminder").exists()
