from rest_framework import serializers
from .models import Sensor, CalibrationRecord

class SensorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sensor
        fields = '__all__'

class CalibrationRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = CalibrationRecord
        fields = '__all__'