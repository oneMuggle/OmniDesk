from rest_framework import serializers
from .models import Sensor, SensorMovement, CalibrationReminder, SensorCategory, StorageLocation, SensorCalibration
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

class SensorSerializer(serializers.ModelSerializer):
    next_calibration_date = serializers.DateField(read_only=True)
    sensor_category_name = serializers.CharField(source='sensor_category.name', read_only=True)
    location_name = serializers.CharField(source='location.name', read_only=True)
    room_temperature = serializers.SerializerMethodField()
    relative_humidity = serializers.SerializerMethodField()

    class Meta:
        model = Sensor
        fields = [
            'id', 'serial_number', 'sensor_name', 'sensor_number', 'manufacturer',
            'calibration_accuracy', 'production_date', 'purchase_date',
            'last_calibration_date', 'calibration_interval_days', 'current_quantity',
            'status', 'sensor_category', 'location', 'created_at', 'updated_at',
            'next_calibration_date', 'sensor_category_name', 'location_name',
            'room_temperature', 'relative_humidity'
        ]
        read_only_fields = ('created_at', 'updated_at')

    def get_room_temperature(self, obj):
        latest_calibration = obj.calibrations.order_by('-calibration_date').first()
        return latest_calibration.room_temperature if latest_calibration else None

    def get_relative_humidity(self, obj):
        latest_calibration = obj.calibrations.order_by('-calibration_date').first()
        return latest_calibration.relative_humidity if latest_calibration else None

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

class SensorCalibrationSerializer(serializers.ModelSerializer):
    class Meta:
        model = SensorCalibration
        fields = [
            'id', 'sensor', 'calibration_instrument', 'calibration_range',
            'calibration_date', 'room_temperature', 'relative_humidity',
            'pressure_values', 'voltage_values', 'non_linearity', 'hysteresis',
            'resonant_frequency', 'repeatability', 'accuracy', 'rise_time',
            'sensitivity', 'calibration_equation', 'calibrator', 'reviewer',
            'notes', 'created_at', 'updated_at'
        ]
        read_only_fields = ('created_at', 'updated_at')