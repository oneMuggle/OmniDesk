import logging

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from .models import CalibrationRecord, Sensor
from .serializers import CalibrationRecordSerializer, SensorSerializer

logger = logging.getLogger(__name__)

class SensorViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows sensors to be viewed or edited.
    """
    queryset = Sensor.objects.all()
    serializer_class = SensorSerializer
    permission_classes = [IsAuthenticated]

class CalibrationRecordViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows calibration records to be viewed or edited.
    """
    queryset = CalibrationRecord.objects.all()
    serializer_class = CalibrationRecordSerializer
    permission_classes = [IsAuthenticated]

