from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import MeetingRoomViewSet, MeetingRoomBookingViewSet, MeetingRoomMaintenanceViewSet, MeetingRoomStatsAPIView

router = DefaultRouter()
router.register(r'meeting-rooms', MeetingRoomViewSet)
router.register(r'meeting-room-bookings', MeetingRoomBookingViewSet, basename='meetingroombooking')
router.register(r'meeting-room-maintenance', MeetingRoomMaintenanceViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('meeting-room-stats/', MeetingRoomStatsAPIView.as_view(), name='meeting-room-stats'),
]