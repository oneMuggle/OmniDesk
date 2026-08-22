from observability import get_logger
from datetime import timedelta

from celery import shared_task
from django.db.models import Q
from django.utils import timezone

from users.models import CustomUser  # 假设需要关联到用户

from .models import CalibrationReminder, Sensor

logger = get_logger(__name__, "sensor_management.tasks")

# 导入Django的User模型，如果需要发送邮件给特定用户
# from django.contrib.auth import get_user_model
# User = get_user_model()


def send_notification(sensor, user):
    """通过 NotificationService 创建站内校准提醒通知(P0-L)。

    dedupe_key 按 传感器 + 日期 粒度:同日任务多次执行(或同一传感器
    命中多个提前天数档位)时,同用户的未读通知会被合并而非重复轰炸。
    """
    from notifications.service import NotificationService

    today = timezone.now().date()
    identifier = sensor.serial_number or sensor.sensor_number
    category_name = sensor.sensor_category.name if sensor.sensor_category else "未知类别"
    NotificationService.create(
        user=user,
        type="calibration_reminder",
        title=f"校准提醒:传感器 {identifier} 即将到期",
        content=(f"传感器 {identifier}(类别:{category_name})的校准日期为 {sensor.next_calibration_date},请及时处理。"),
        dedupe_key=f"calibration:{sensor.id}:{today.isoformat()}",
    )


@shared_task
def check_and_create_calibration_reminders():
    """
    检查即将到期或已过期的传感器，并创建校准提醒。
    """
    today = timezone.now().date()

    # 预查询管理员用户(避免循环内重复查询,修复 N+1)
    admin_users = list(CustomUser.objects.filter(Q(is_superuser=True) | Q(groups__name__in=["Admin", "Manager"])))

    if not admin_users:
        logger.warning("无管理员用户，跳过校准提醒任务")
        return

    # 定义提醒的提前天数
    remind_days = [5, 1, 0]  # 提前5天，提前1天，当天

    # 修复:原实现 timedelta(days=F(...)) 在 Python 层构造即抛 TypeError(F 表达式
    # 不能做 timedelta 参数),该任务从未真正跑通过。改为一次查询拉候选集,
    # 用模型既有 next_calibration_date 属性在 Python 侧过滤(传感器为内网资产,
    # 规模有限;select_related 预取类别避免后续通知文案的 N+1)
    candidates = list(
        Sensor.objects.filter(last_calibration_date__isnull=False)
        .exclude(status__in=["under_calibration", "retired"])
        .select_related("sensor_category")
    )

    for days_before in remind_days:
        remind_date = today + timedelta(days=days_before)

        sensors_due = [
            sensor
            for sensor in candidates
            if sensor.next_calibration_date is not None and sensor.next_calibration_date <= remind_date
        ]

        # 批量查询今天已有的提醒(避免循环内逐条 exists 查询)
        existing_reminder_sensor_ids = set(
            CalibrationReminder.objects.filter(remind_date=today).values_list("sensor_id", flat=True)
        )

        for sensor in sensors_due:
            if sensor.pk in existing_reminder_sensor_ids:
                logger.info("传感器 %s 今天已有校准提醒，跳过", sensor.serial_number)
                continue

            # 创建新的校准提醒
            reminder = CalibrationReminder.objects.create(
                sensor=sensor, remind_date=today, notes=f"传感器 {sensor.serial_number} 即将或已到期校准。"
            )
            reminder.reminded_users.set(admin_users)

            logger.info("为传感器 %s 创建了校准提醒，提醒日期：%s", sensor.serial_number, today)

            # 发送站内通知给相关用户(P0-L:接入 NotificationService)
            for user in admin_users:
                send_notification(sensor, user)

    logger.info("校准提醒任务执行完毕")
