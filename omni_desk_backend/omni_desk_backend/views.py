from rest_framework.generics import CreateAPIView
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import authenticate
from .models import CalendarEvent
from .serializers import CalendarEventSerializer, UserRegistrationSerializer, UserLoginSerializer

class CalendarEventCreateView(CreateAPIView):
    permission_classes = []
    queryset = CalendarEvent.objects.all()
    serializer_class = CalendarEventSerializer

class UserRegistrationView(CreateAPIView):
    serializer_class = UserRegistrationSerializer

class UserLoginView(APIView):
    def post(self, request):
        serializer = UserLoginSerializer(data=request.data)
        if serializer.is_valid():
            user = authenticate(
                username=serializer.validated_data['username'],
                password=serializer.validated_data['password']
            )
            if user:
                return Response({'message': 'Login successful'}, status=status.HTTP_200_OK)
            return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
