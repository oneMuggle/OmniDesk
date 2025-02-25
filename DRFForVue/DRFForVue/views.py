from rest_framework.generics import CreateAPIView
from .models import CalendarEvent
from .serializers import CalendarEventSerializer

from rest_framework.permissions import IsAuthenticated

class CalendarEventCreateView(CreateAPIView):
    permission_classes = [IsAuthenticated]
    queryset = CalendarEvent.objects.all()
    serializer_class = CalendarEventSerializer
