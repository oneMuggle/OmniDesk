"""传感器 Seeder：类别、位置、传感器、校准、出入库、校准提醒"""
import random
from datetime import date, timedelta
from sensor_management.models import (
    SensorCategory, StorageLocation, Sensor,
    SensorMovement, CalibrationReminder, SensorCalibration, CalibrationDataPoint,
)
from events.management.seeders.base import BaseSeeder


class SensorSeeder(BaseSeeder):
    name = "传感器管理"
    order = 40
    models = [SensorCategory, StorageLocation, Sensor, SensorMovement, CalibrationReminder, SensorCalibration, CalibrationDataPoint]

    def seed(self):
        user = self.context.get("user")

        categories = ["温度传感器", "压力传感器", "湿度传感器", "加速度传感器", "位移传感器"]
        category_objs = []
        for name in categories:
            obj, _ = self.safe_get_or_create(SensorCategory, name=name, defaults={"description": f"{name}的类别定义"})
            category_objs.append(obj)

        locations = ["仓库A区", "仓库B区", "实验室1号柜", "实验室2号柜", "备件库"]
        location_objs = []
        for name in locations:
            obj, _ = self.safe_get_or_create(StorageLocation, name=name, defaults={"description": f"{name}的描述"})
            location_objs.append(obj)

        sensor_defs = [
            ("温度传感器-A型", "TEMP-001", "上海仪器仪表厂"),
            ("压力传感器-B型", "PRES-002", "北京传感器科技"),
            ("湿度传感器-C型", "HUMI-003", "广州电子科技"),
            ("加速度传感器-D型", "ACCL-004", "深圳精密仪器"),
            ("位移传感器-E型", "DISP-005", "杭州测量技术"),
            ("温度传感器-F型", "TEMP-006", "上海仪器仪表厂"),
            ("压力传感器-G型", "PRES-007", "北京传感器科技"),
        ]

        sensors = []
        for name, number, mfr in sensor_defs:
            prod_date = date(2023, random.randint(1, 12), random.randint(1, 28))
            purch_date = prod_date + timedelta(days=random.randint(30, 90))
            last_cal = date(2025, random.randint(1, 12), random.randint(1, 28))

            obj, _ = self.safe_get_or_create(
                Sensor,
                sensor_number=number,
                defaults={
                    "name": name,
                    "serial_number": f"SN-2024-{number.split('-')[-1]}",
                    "sensor_category": random.choice(category_objs),
                    "manufacturer": mfr,
                    "calibration_accuracy": f"±{random.uniform(0.1, 2.0):.1f}%",
                    "production_date": prod_date,
                    "purchase_date": purch_date,
                    "last_calibration_date": last_cal,
                    "calibration_interval_days": random.choice([180, 365, 730]),
                    "current_quantity": random.randint(1, 10),
                    "status": random.choice(["in_stock", "in_use", "in_use", "in_use"]),
                    "location": random.choice(location_objs),
                    "room_temperature": round(random.uniform(20, 26), 1),
                    "relative_humidity": round(random.uniform(40, 60), 1),
                }
            )
            sensors.append(obj)

        # 校准记录
        cal_count = 0
        dp_count = 0
        for sensor in sensors[:4]:
            cal_date = sensor.last_calibration_date or date(2025, 6, 1)
            cal, _ = self.safe_get_or_create(
                SensorCalibration,
                sensor=sensor,
                calibration_date=cal_date,
                defaults={
                    "calibration_instrument": "FLUKE 5520A 多功能校准器",
                    "calibration_range": f"0-{random.randint(100, 1000)} Pa",
                    "non_linearity": round(random.uniform(0.01, 0.5), 3),
                    "hysteresis": round(random.uniform(0.01, 0.3), 3),
                    "repeatability": round(random.uniform(0.01, 0.2), 3),
                    "accuracy": round(random.uniform(0.1, 1.0), 2),
                    "sensitivity": round(random.uniform(10, 100), 2),
                    "calibrated_by": user,
                    "reviewed_by": user,
                    "remarks": "校准合格",
                }
            )
            if cal:
                cal_count += 1
                if not cal.data_points.exists():
                    for pressure in [0, 100, 200, 300, 400, 500]:
                        CalibrationDataPoint.objects.get_or_create(
                            sensor_calibration=cal,
                            pressure_value=pressure,
                            defaults={
                                "positive_trip_voltage_1": round(pressure * 0.01 + random.uniform(-0.1, 0.1), 3),
                                "positive_trip_voltage_2": round(pressure * 0.01 + random.uniform(-0.1, 0.1), 3),
                                "positive_trip_voltage_3": round(pressure * 0.01 + random.uniform(-0.1, 0.1), 3),
                                "negative_trip_voltage_1": round(pressure * 0.01 + random.uniform(-0.1, 0.1), 3),
                                "negative_trip_voltage_2": round(pressure * 0.01 + random.uniform(-0.1, 0.1), 3),
                                "negative_trip_voltage_3": round(pressure * 0.01 + random.uniform(-0.1, 0.1), 3),
                            }
                        )
                        dp_count += 1

        # 出入库记录
        for sensor in sensors[:3]:
            SensorMovement.objects.get_or_create(
                sensor=sensor,
                movement_type="in",
                defaults={"quantity": random.randint(1, 5), "reason": "采购入库",
                          "destination_source": "供应商发货", "operator": user},
            )

        # 校准提醒
        for sensor in sensors[:2]:
            remind = (sensor.last_calibration_date + timedelta(days=sensor.calibration_interval_days - 30)
                      if sensor.last_calibration_date else date(2026, 6, 1))
            CalibrationReminder.objects.get_or_create(
                sensor=sensor,
                defaults={"remind_date": remind, "is_sent": False,
                          "notes": f"传感器 {sensor.sensor_number} 即将到期校准"},
            )

        return [
            ("传感器类别", len(categories)),
            ("存储位置", len(locations)),
            ("传感器", len(sensors)),
            ("校准记录", cal_count),
            ("校准数据点", dp_count),
        ]
