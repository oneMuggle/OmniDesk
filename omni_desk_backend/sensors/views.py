from rest_framework import viewsets
from .models import Sensor, CalibrationRecord
from .serializers import SensorSerializer, CalibrationRecordSerializer

class SensorViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows sensors to be viewed or edited.
    """
    queryset = Sensor.objects.all()
    serializer_class = SensorSerializer

class CalibrationRecordViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows calibration records to be viewed or edited.
    """
    queryset = CalibrationRecord.objects.all()
    serializer_class = CalibrationRecordSerializer
