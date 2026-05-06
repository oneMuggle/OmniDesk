from rest_framework import serializers

from .models import CalibrationRecord, Sensor


class SensorSerializer(serializers.ModelSerializer):
    status_display = serializers.SerializerMethodField()

    class Meta:
        model = Sensor
        fields = '__all__'

    def get_status_display(self, obj):
        return obj.get_status_display()

class CalibrationRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = CalibrationRecord
        fields = '__all__'
