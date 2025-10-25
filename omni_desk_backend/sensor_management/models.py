from django.db import models
from django.db.models import JSONField
from users.models import CustomUser
from datetime import date, timedelta

class Sensor(models.Model):
    STATUS_CHOICES = [
        ('in_stock', '库存中'),
        ('in_use', '使用中'),
        ('under_calibration', '校准中'),
        ('retired', '已报废'),
    ]

    serial_number = models.CharField(max_length=100, unique=True, verbose_name="序列号")
    sensor_name = models.CharField(max_length=255, verbose_name="传感器名称", default='未知传感器')
    sensor_number = models.CharField(max_length=100, verbose_name="传感器编号", default='未知编号')
    sensor_category = models.ForeignKey('SensorCategory', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="传感器类别")
    manufacturer = models.CharField(max_length=100, verbose_name="制造商")
    calibration_accuracy = models.FloatField(verbose_name="校准精度")
    production_date = models.DateField(verbose_name="生产日期", null=True, blank=True)
    purchase_date = models.DateField(verbose_name="购买日期", null=True, blank=True)
    last_calibration_date = models.DateField(verbose_name="上次校准日期", null=True, blank=True)
    calibration_interval_days = models.IntegerField(default=365, verbose_name="校准周期（天）")
    current_quantity = models.IntegerField(default=0, verbose_name="当前数量")
    
    @property
    def next_calibration_date(self):
        if self.last_calibration_date and self.calibration_interval_days:
            return self.last_calibration_date + timedelta(days=self.calibration_interval_days)
        return None

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='in_stock',
        verbose_name="状态"
    )
    location = models.ForeignKey('StorageLocation', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="存放位置")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        verbose_name = "传感器"
        verbose_name_plural = "传感器管理"
        ordering = ['serial_number']

    def __str__(self):
        return f"{self.model_name} ({self.serial_number})"

class SensorCategory(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="类别名称")
    description = models.TextField(blank=True, verbose_name="描述")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        verbose_name = "传感器类别"
        verbose_name_plural = "传感器类别管理"
        ordering = ['name']

    def __str__(self):
        return self.name

class SensorMovement(models.Model):
    MOVEMENT_TYPES = [
        ('in', '入库'),
        ('out', '出库'),
    ]

    sensor = models.ForeignKey(Sensor, on_delete=models.CASCADE, related_name='movements', verbose_name="传感器")
    movement_type = models.CharField(max_length=10, choices=MOVEMENT_TYPES, verbose_name="出入库类型")
    movement_date = models.DateTimeField(auto_now_add=True, verbose_name="出入库日期")
    operator = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="操作人员")
    quantity = models.IntegerField(default=1, verbose_name="数量")
    reason = models.TextField(blank=True, verbose_name="原因")
    destination_source = models.CharField(max_length=200, blank=True, verbose_name="去向/来源")

    class Meta:
        verbose_name = "传感器出入库记录"
        verbose_name_plural = "传感器出入库记录"
        ordering = ['-movement_date']

    def __str__(self):
        return f"{self.sensor.serial_number} - {self.get_movement_type_display()} on {self.movement_date.strftime('%Y-%m-%d %H:%M')}"

class CalibrationReminder(models.Model):
    sensor = models.OneToOneField(Sensor, on_delete=models.CASCADE, related_name='calibration_reminder', verbose_name="传感器")
    remind_date = models.DateField(verbose_name="提醒日期")
    is_sent = models.BooleanField(default=False, verbose_name="是否已发送")
    sent_date = models.DateTimeField(null=True, blank=True, verbose_name="发送日期")
    notes = models.TextField(blank=True, verbose_name="备注")
    reminded_users = models.ManyToManyField(CustomUser, blank=True, verbose_name="被提醒用户")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        verbose_name = "校准提醒"
        verbose_name_plural = "校准提醒"
        ordering = ['remind_date']

    def __str__(self):
        return f"传感器 {self.sensor.serial_number} 校准提醒 ({self.remind_date})"

class SensorCalibration(models.Model):
    sensor = models.ForeignKey(Sensor, on_delete=models.CASCADE, related_name='calibrations', verbose_name="传感器")
    calibration_instrument = models.CharField(max_length=255, verbose_name="校准仪器")
    calibration_range = models.CharField(max_length=100, verbose_name="校准范围")
    calibration_date = models.DateField(verbose_name="校准日期")
    room_temperature = models.FloatField(verbose_name="室温", null=True, blank=True)
    relative_humidity = models.FloatField(verbose_name="相对湿度", null=True, blank=True)
    pressure_values = JSONField(verbose_name="压力值", null=True, blank=True)
    voltage_values = JSONField(verbose_name="电压值", null=True, blank=True)
    non_linearity = models.FloatField(verbose_name="非线性度", null=True, blank=True)
    hysteresis = models.FloatField(verbose_name="迟滞", null=True, blank=True)
    resonant_frequency = models.FloatField(verbose_name="谐振频率", null=True, blank=True)
    repeatability = models.FloatField(verbose_name="重复性", null=True, blank=True)
    accuracy = models.FloatField(verbose_name="准确度", null=True, blank=True)
    rise_time = models.FloatField(verbose_name="上升时间", null=True, blank=True)
    sensitivity = models.FloatField(verbose_name="灵敏度", null=True, blank=True)
    calibration_equation = models.CharField(max_length=255, verbose_name="校准方程", null=True, blank=True)
    calibrator = models.CharField(max_length=100, verbose_name="校准人", null=True, blank=True)
    reviewer = models.CharField(max_length=100, verbose_name="审核人", null=True, blank=True)
    notes = models.TextField(blank=True, verbose_name="备注")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        verbose_name = "传感器校准记录"
        verbose_name_plural = "传感器校准记录"
        ordering = ['-calibration_date']

    def __str__(self):
        return f"{self.sensor.serial_number} - 校准日期: {self.calibration_date}"

class StorageLocation(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="位置名称")
    description = models.TextField(blank=True, verbose_name="描述")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        verbose_name = "存放位置"
        verbose_name_plural = "存放位置管理"
        ordering = ['name']

    def __str__(self):
        return self.name
