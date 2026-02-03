from rest_framework import serializers
from rest_framework import serializers
from .models import Sensor, SensorMovement, CalibrationReminder, SensorCategory, StorageLocation, SensorCalibration, CalibrationDataPoint
from users.models import CustomUser

class SensorCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = SensorCategory
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at')

class StorageLocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = StorageLocation
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at')

class CalibrationDataPointSerializer(serializers.ModelSerializer):
    class Meta:
        model = CalibrationDataPoint
        fields = '__all__'

class SensorCalibrationSerializer(serializers.ModelSerializer):
    data_points = CalibrationDataPointSerializer(many=True)

    class Meta:
        model = SensorCalibration
        fields = [
            'id', 'sensor', 'calibration_instrument', 'calibration_range',
            'calibration_date', 'non_linearity', 'hysteresis',
            'resonant_frequency', 'repeatability', 'accuracy', 'rise_time',
            'sensitivity', 'calibration_equation', 'calibrated_by', 'reviewed_by',
            'remarks', 'created_at', 'updated_at', 'data_points'
        ]
        read_only_fields = ('created_at', 'updated_at')

    def create(self, validated_data):
        data_points_data = validated_data.pop('data_points')
        calibration = SensorCalibration.objects.create(**validated_data)
        for data_point_data in data_points_data:
            CalibrationDataPoint.objects.create(sensor_calibration=calibration, **data_point_data)
        return calibration

class SensorSerializer(serializers.ModelSerializer):
    next_calibration_date = serializers.DateField(read_only=True)
    sensor_category_name = serializers.CharField(source='sensor_category.name', read_only=True)
    location_name = serializers.CharField(source='location.name', read_only=True)
    calibrations = SensorCalibrationSerializer(many=True, read_only=True)
    category = serializers.PrimaryKeyRelatedField(
        queryset=SensorCategory.objects.all(),
        source='sensor_category',  # 确保 source 指向模型的 'sensor_category' 字段
        write_only=True  # 仅用于写入
    )
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    storage_location = serializers.PrimaryKeyRelatedField(
        queryset=StorageLocation.objects.all(),
        source='location',  # 确保 source 指向模型的 'location' 字段
        write_only=True  # 仅用于写入
    )

    class Meta:
        model = Sensor
        fields = [
            'id', 'serial_number', 'name', 'sensor_number', 'manufacturer',
            'calibration_accuracy', 'production_date', 'purchase_date',
            'last_calibration_date', 'calibration_interval_days', 'current_quantity',
            'status', 'status_display', 'created_at', 'updated_at',
            'next_calibration_date', 'sensor_category_name', 'location_name',
            'room_temperature', 'relative_humidity', 'calibrations', 'category', 'storage_location'
        ]
        read_only_fields = ('created_at', 'updated_at')


class SensorMovementSerializer(serializers.ModelSerializer):
    operator_username = serializers.CharField(source='operator.username', read_only=True)
    sensor_serial_number = serializers.CharField(source='sensor.serial_number', read_only=True)

    class Meta:
        model = SensorMovement
        fields = '__all__'
        read_only_fields = ('movement_date',)

class CalibrationReminderSerializer(serializers.ModelSerializer):
    sensor_serial_number = serializers.CharField(source='sensor.serial_number', read_only=True)

    class Meta:
        model = CalibrationReminder
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at')