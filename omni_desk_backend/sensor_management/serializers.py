from rest_framework import serializers
from .models import Sensor, SensorMovement, CalibrationReminder
from users.models import CustomUser

class SensorSerializer(serializers.ModelSerializer):
    next_calibration_date = serializers.DateField(read_only=True) # 自定义next_calibration_date字段

    class Meta:
        model = Sensor
        fields = '__all__'
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