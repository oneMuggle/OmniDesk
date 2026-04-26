import logging

from rest_framework import viewsets

from .models import CalibrationRecord, Sensor
from .serializers import CalibrationRecordSerializer, SensorSerializer

logger = logging.getLogger(__name__)

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

