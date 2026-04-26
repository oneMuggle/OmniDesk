from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import MeetingRoomBookingViewSet, MeetingRoomMaintenanceViewSet, MeetingRoomStatsAPIView, MeetingRoomViewSet

router = DefaultRouter()
router.register(r'meeting-rooms', MeetingRoomViewSet)
router.register(r'meeting-room-bookings', MeetingRoomBookingViewSet, basename='meetingroombooking')
router.register(r'meeting-room-maintenance', MeetingRoomMaintenanceViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('meeting-room-stats/', MeetingRoomStatsAPIView.as_view(), name='meeting-room-stats'),
]
