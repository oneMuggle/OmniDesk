from datetime import timedelta
import logging

from celery import shared_task
from django.db.models import F, Q
from django.utils import timezone

from users.models import CustomUser  # 假设需要关联到用户

from .models import CalibrationReminder, Sensor

logger = logging.getLogger(__name__)

# 导入Django的User模型，如果需要发送邮件给特定用户
# from django.contrib.auth import get_user_model
# User = get_user_model()


def send_notification(user, subject, message):
    """
    模拟发送通知的函数。
    在实际项目中，这里会集成邮件发送、站内信、短信等服务。
    """
    logger.info("发送通知给 %s: 主题=%s", user.username, subject)
    # 实际项目中，这里会调用对应的通知服务
    # send_mail(subject, message, 'from@example.com', [user.email])
    # 或者创建站内信记录等
    pass


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

    for days_before in remind_days:
        remind_date = today + timedelta(days=days_before)

        # 查找符合条件的传感器(select_related 获取 sensor_category,避免 N+1)
        sensors_due = (
            Sensor.objects.filter(
                Q(last_calibration_date__isnull=False)
                & Q(last_calibration_date__date__lte=remind_date - timedelta(days=F("calibration_interval_days")))
            )
            .exclude(status__in=["under_calibration", "retired"])
            .select_related("sensor_category")
            .distinct()
        )

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

            # 发送通知给相关用户
            subject = f"校准提醒：传感器 {sensor.serial_number} 即将到期"
            message = f"传感器 {sensor.serial_number}（类别：{sensor.sensor_category.name}）的校准日期为 {sensor.next_calibration_date}，请及时处理。"
            for user in admin_users:
                send_notification(user, subject, message)

    logger.info("校准提醒任务执行完毕")
