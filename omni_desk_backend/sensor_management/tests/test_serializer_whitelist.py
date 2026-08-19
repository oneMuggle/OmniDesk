"""sensor_management serializer 白名单化测试 (R3-B1 PR-4)。

契约(plan §3.2 PR-4):
- SensorCategory / StorageLocation 白名单 `("id","name","description","created_at","updated_at")`
- CalibrationDataPointSerializer 白名单 9 字段
- SensorMovementSerializer 白名单,收敛声明字段 operator_username/sensor_serial_number(前端零消费)
- CalibrationReminderSerializer 白名单,收敛声明字段 sensor_serial_number(前端零消费)
"""

from datetime import date

import pytest

from sensor_management.models import (
    CalibrationDataPoint,
    CalibrationReminder,
    Sensor,
    SensorCalibration,
    SensorCategory,
    SensorMovement,
    StorageLocation,
)
from sensor_management.serializers import (
    CalibrationDataPointSerializer,
    CalibrationReminderSerializer,
    SensorCategorySerializer,
    SensorMovementSerializer,
    StorageLocationSerializer,
)


@pytest.fixture
def sensor(db):
    return Sensor.objects.create(
        name="压力传感器",
        sensor_number="SN-001",
        serial_number="SER-001",
    )


@pytest.mark.django_db
class TestSensorCategorySerializerWhitelist:
    def test_fields_whitelisted(self):
        category = SensorCategory.objects.create(name="压力类", description="压力传感器")

        data = SensorCategorySerializer(category).data

        assert set(data.keys()) == {"id", "name", "description", "created_at", "updated_at"}


@pytest.mark.django_db
class TestStorageLocationSerializerWhitelist:
    def test_fields_whitelisted(self):
        location = StorageLocation.objects.create(name="A栋仓库", description="主仓库")

        data = StorageLocationSerializer(location).data

        assert set(data.keys()) == {"id", "name", "description", "created_at", "updated_at"}


@pytest.mark.django_db
class TestCalibrationDataPointSerializerWhitelist:
    def test_fields_whitelisted(self, sensor):
        calibration = SensorCalibration.objects.create(
            sensor=sensor,
            calibration_instrument="标准压力计",
            calibration_range="0-100kPa",
            calibration_date=date(2026, 8, 1),
        )
        point = CalibrationDataPoint.objects.create(
            sensor_calibration=calibration,
            pressure_value=10.0,
            positive_trip_voltage_1=1.0,
            positive_trip_voltage_2=1.1,
            positive_trip_voltage_3=1.2,
            negative_trip_voltage_1=0.9,
            negative_trip_voltage_2=0.8,
            negative_trip_voltage_3=0.7,
        )

        data = CalibrationDataPointSerializer(point).data

        assert set(data.keys()) == {
            "id",
            "sensor_calibration",
            "pressure_value",
            "positive_trip_voltage_1",
            "positive_trip_voltage_2",
            "positive_trip_voltage_3",
            "negative_trip_voltage_1",
            "negative_trip_voltage_2",
            "negative_trip_voltage_3",
        }


@pytest.mark.django_db
class TestSensorMovementSerializerWhitelist:
    def test_fields_whitelisted(self, sensor, regular_user_obj):
        movement = SensorMovement.objects.create(
            sensor=sensor,
            movement_type="in",
            operator=regular_user_obj,
            quantity=2,
            reason="采购入库",
            destination_source="供应商A",
        )

        data = SensorMovementSerializer(movement).data

        assert set(data.keys()) == {
            "id",
            "sensor",
            "movement_type",
            "movement_date",
            "operator",
            "quantity",
            "reason",
            "destination_source",
        }
        # 声明字段 operator_username/sensor_serial_number 前端零消费,收敛剔除
        assert "operator_username" not in data
        assert "sensor_serial_number" not in data

    def test_write_accepts_fields(self, sensor, regular_user_obj):
        serializer = SensorMovementSerializer(
            data={
                "sensor": sensor.id,
                "movement_type": "out",
                "operator": regular_user_obj.id,
                "quantity": 1,
                "reason": "领用出库",
            }
        )

        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data["sensor"] == sensor
        assert serializer.validated_data["quantity"] == 1


@pytest.mark.django_db
class TestCalibrationReminderSerializerWhitelist:
    def test_fields_whitelisted(self, sensor, regular_user_obj):
        reminder = CalibrationReminder.objects.create(
            sensor=sensor,
            remind_date=date(2026, 9, 1),
            is_sent=False,
            notes="到期提醒",
        )
        reminder.reminded_users.add(regular_user_obj)

        data = CalibrationReminderSerializer(reminder).data

        assert set(data.keys()) == {
            "id",
            "sensor",
            "remind_date",
            "is_sent",
            "sent_date",
            "notes",
            "reminded_users",
            "created_at",
            "updated_at",
        }
        # 声明字段 sensor_serial_number 前端零消费,收敛剔除
        assert "sensor_serial_number" not in data

    def test_write_accepts_fields(self, sensor):
        serializer = CalibrationReminderSerializer(
            data={
                "sensor": sensor.id,
                "remind_date": date(2026, 9, 1),
                "notes": "备注",
            }
        )

        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data["sensor"] == sensor
        assert serializer.validated_data["remind_date"] == date(2026, 9, 1)
