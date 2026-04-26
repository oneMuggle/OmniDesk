from rest_framework.generics import CreateAPIView

from .models import CalendarEvent
from .serializers import CalendarEventSerializer, UserRegistrationSerializer


class CalendarEventCreateView(CreateAPIView):
    permission_classes = []
    queryset = CalendarEvent.objects.all()
    serializer_class = CalendarEventSerializer

class UserRegistrationView(CreateAPIView):
    serializer_class = UserRegistrationSerializer
