from rest_framework import serializers

from .models import (
    CalibrationDataPoint,
    CalibrationReminder,
    Sensor,
    SensorCalibration,
    SensorCategory,
    SensorMovement,
    StorageLocation,
)


class SensorCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = SensorCategory
        # R3-B1: 白名单化
        fields = ["id", "name", "description", "created_at", "updated_at"]
        read_only_fields = ("created_at", "updated_at")


class StorageLocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = StorageLocation
        # R3-B1: 白名单化
        fields = ["id", "name", "description", "created_at", "updated_at"]
        read_only_fields = ("created_at", "updated_at")


class CalibrationDataPointSerializer(serializers.ModelSerializer):
    class Meta:
        model = CalibrationDataPoint
        # R3-B1: 白名单化,嵌套于 SensorCalibrationSerializer
        fields = [
            "id",
            "sensor_calibration",
            "pressure_value",
            "positive_trip_voltage_1",
            "positive_trip_voltage_2",
            "positive_trip_voltage_3",
            "negative_trip_voltage_1",
            "negative_trip_voltage_2",
            "negative_trip_voltage_3",
        ]


class SensorCalibrationSerializer(serializers.ModelSerializer):
    data_points = CalibrationDataPointSerializer(many=True)
    calibrated_by_username = serializers.CharField(source="calibrated_by.username", read_only=True)
    reviewed_by_username = serializers.CharField(source="reviewed_by.username", read_only=True)

    class Meta:
        model = SensorCalibration
        fields = [
            "id",
            "sensor",
            "calibration_instrument",
            "calibration_range",
            "calibration_date",
            "non_linearity",
            "hysteresis",
            "resonant_frequency",
            "repeatability",
            "accuracy",
            "rise_time",
            "sensitivity",
            "calibration_equation",
            "calibrated_by",
            "calibrated_by_username",
            "reviewed_by",
            "reviewed_by_username",
            "remarks",
            "created_at",
            "updated_at",
            "data_points",
        ]
        read_only_fields = ("created_at", "updated_at")

    def create(self, validated_data):
        data_points_data = validated_data.pop("data_points")
        calibration = SensorCalibration.objects.create(**validated_data)
        for data_point_data in data_points_data:
            CalibrationDataPoint.objects.create(sensor_calibration=calibration, **data_point_data)
        return calibration


class SensorSerializer(serializers.ModelSerializer):
    next_calibration_date = serializers.DateField(read_only=True)
    sensor_category_name = serializers.CharField(source="sensor_category.name", read_only=True)
    location_name = serializers.CharField(source="location.name", read_only=True)
    calibrations = SensorCalibrationSerializer(many=True, read_only=True)
    category = serializers.PrimaryKeyRelatedField(
        queryset=SensorCategory.objects.all(),
        source="sensor_category",  # 确保 source 指向模型的 'sensor_category' 字段
        write_only=True,  # 仅用于写入
    )
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    storage_location = serializers.PrimaryKeyRelatedField(
        queryset=StorageLocation.objects.all(),
        source="location",  # 确保 source 指向模型的 'location' 字段
        write_only=True,  # 仅用于写入
    )

    class Meta:
        model = Sensor
        fields = [
            "id",
            "serial_number",
            "name",
            "sensor_number",
            "manufacturer",
            "calibration_accuracy",
            "production_date",
            "purchase_date",
            "last_calibration_date",
            "calibration_interval_days",
            "current_quantity",
            "status",
            "status_display",
            "created_at",
            "updated_at",
            "next_calibration_date",
            "sensor_category_name",
            "location_name",
            "room_temperature",
            "relative_humidity",
            "calibrations",
            "category",
            "storage_location",
        ]
        read_only_fields = ("created_at", "updated_at")


class SensorMovementSerializer(serializers.ModelSerializer):
    class Meta:
        model = SensorMovement
        # R3-B1: 白名单化。operator_username/sensor_serial_number 声明字段前端零消费,收敛剔除
        fields = [
            "id",
            "sensor",
            "movement_type",
            "movement_date",
            "operator",
            "quantity",
            "reason",
            "destination_source",
        ]
        read_only_fields = ("movement_date",)


class CalibrationReminderSerializer(serializers.ModelSerializer):
    class Meta:
        model = CalibrationReminder
        # R3-B1: 白名单化。sensor_serial_number 声明字段前端零消费,收敛剔除
        fields = [
            "id",
            "sensor",
            "remind_date",
            "is_sent",
            "sent_date",
            "notes",
            "reminded_users",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ("created_at", "updated_at")
