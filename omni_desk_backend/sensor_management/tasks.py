from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from django.db.models import Q, F
from .models import Sensor, CalibrationReminder
from users.models import CustomUser # 假设需要关联到用户

# 导入Django的User模型，如果需要发送邮件给特定用户
# from django.contrib.auth import get_user_model
# User = get_user_model()

def send_notification(user, subject, message):
    """
    模拟发送通知的函数。
    在实际项目中，这里会集成邮件发送、站内信、短信等服务。
    """
    print(f"发送通知给 {user.username}:")
    print(f"主题: {subject}")
    print(f"内容: {message}")
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
    
    # 定义提醒的提前天数
    remind_days = [5, 1, 0] # 提前5天，提前1天，当天

    for days_before in remind_days:
        remind_date = today + timedelta(days=days_before)
        
        # 查找符合条件的传感器
        sensors_due = Sensor.objects.filter(
            Q(last_calibration_date__isnull=False) &
            Q(
                last_calibration_date__date__lte=remind_date - timedelta(days=F('calibration_interval_days'))
            )
        ).exclude(status__in=['under_calibration', 'retired']).distinct()

        for sensor in sensors_due:
            # 检查是否已经存在当天的提醒
            existing_reminder = CalibrationReminder.objects.filter(
                sensor=sensor,
                remind_date=today
            ).exists()

            if not existing_reminder:
                # 创建新的校准提醒
                reminder = CalibrationReminder.objects.create(
                    sensor=sensor,
                    remind_date=today,
                    notes=f"传感器 {sensor.serial_number} 即将或已到期校准。"
                )
                # 假设有一个默认的管理用户或者通过某种逻辑分配提醒用户
                # 这里可以根据业务逻辑，将提醒关联到特定的管理用户
                # 例如：可以遍历所有管理员或特定角色用户并添加到 reminded_users
                admin_users = CustomUser.objects.filter(Q(is_superuser=True) | Q(groups__name__in=['Admin', 'Manager'])) # 示例：获取管理员和经理角色用户
                reminder.reminded_users.set(admin_users)
                
                print(f"为传感器 {sensor.serial_number} 创建了校准提醒，提醒日期：{today}")

                # 发送通知给相关用户
                subject = f"校准提醒：传感器 {sensor.serial_number} 即将到期"
                message = f"传感器 {sensor.serial_number}（类别：{sensor.sensor_category.name}）的校准日期为 {sensor.next_calibration_date}，请及时处理。"
                for user in admin_users:
                    send_notification(user, subject, message)

            else:
                print(f"传感器 {sensor.serial_number} 今天已有校准提醒，跳过。")

    print("校准提醒任务执行完毕。")