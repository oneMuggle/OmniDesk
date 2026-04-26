from django.db import models


class Sensor(models.Model):
    """
    传感器模型
    """
    name = models.CharField(max_length=255, verbose_name="传感器名称")
    serial_number = models.CharField(max_length=255, unique=True, verbose_name="传感器编号")
    calibration_range = models.CharField(max_length=255, verbose_name="校准范围")

    def __str__(self):
        return f"{self.name} ({self.serial_number})"

class CalibrationRecord(models.Model):
    """
    压力传感器校准记录卡模型
    """
    sensor = models.ForeignKey(Sensor, on_delete=models.CASCADE, related_name='calibration_records', verbose_name="传感器")
    room_temperature = models.FloatField(verbose_name="室温 (℃)")
    relative_humidity = models.FloatField(verbose_name="相对湿度 (%RH)")
    calibration_instrument = models.CharField(max_length=255, verbose_name="校准用仪器")
    calibration_date = models.DateField(verbose_name="校准日期")

    # Main table data for calibration points
    main_table_data = models.JSONField(default=dict, verbose_name="主要表格数据")

    # Performance indicators
    performance_indicators = models.JSONField(default=dict, verbose_name="性能指标")

    def __str__(self):
        return f"Calibration for {self.sensor.name} on {self.calibration_date}"
