"""meeting_rooms 模块补充测试。"""

import pytest
from datetime import datetime, timedelta
from django.utils import timezone

from meeting_rooms.models import MeetingRoom, MeetingRoomBooking, MeetingRoomMaintenance
from users.models import CustomUser


@pytest.mark.django_db
class TestMeetingRoomViewSet:
    def test_room_crud(self, admin_client):
        """会议室 CRUD"""
        resp = admin_client.post('/api/meeting-rooms/meeting-rooms/', {
            'name': '测试会议室',
            'capacity': 10,
            'location': '3楼',
        }, format='json')
        assert resp.status_code == 201, resp.data
        room_id = resp.data['id']

        resp = admin_client.get(f'/api/meeting-rooms/meeting-rooms/{room_id}/')
        assert resp.status_code == 200

        resp = admin_client.delete(f'/api/meeting-rooms/meeting-rooms/{room_id}/')
        assert resp.status_code == 204


@pytest.mark.django_db
class TestMeetingRoomBookingViewSet:
    def test_booking_crud(self, admin_client, admin_user_obj):
        """会议室预订 CRUD"""
        room = MeetingRoom.objects.create(name='预订会议室', capacity=8, location='3楼')
        # 使用相对时间,避免硬编码日期随时间过期
        # MeetingRoomBooking.clean() 会拒绝 start_time < timezone.now()
        start = timezone.now() + timedelta(days=1)
        end = start + timedelta(hours=1)
        resp = admin_client.post('/api/meeting-rooms/meeting-room-bookings/', {
            'meeting_room': room.id,
            'title': '测试预订',
            'start_time': start.isoformat(),
            'end_time': end.isoformat(),
        }, format='json')
        assert resp.status_code == 201, resp.data
        booking_id = resp.data['id']

        resp = admin_client.get(f'/api/meeting-rooms/meeting-room-bookings/{booking_id}/')
        assert resp.status_code == 200

        resp = admin_client.delete(f'/api/meeting-rooms/meeting-room-bookings/{booking_id}/')
        assert resp.status_code == 204


@pytest.mark.django_db
class TestMeetingRoomMaintenanceViewSet:
    def test_maintenance_crud(self, admin_client):
        """维护记录 CRUD"""
        room = MeetingRoom.objects.create(name='维护会议室', capacity=6, location='2楼')
        resp = admin_client.post('/api/meeting-rooms/meeting-room-maintenance/', {
            'meeting_room': room.id,
            'title': '空调维修',
            'reason': '空调不制冷',
            'start_time': '2026-06-15T00:00:00Z',
            'end_time': '2026-06-16T00:00:00Z',
        }, format='json')
        assert resp.status_code == 201, resp.data
        maint_id = resp.data['id']

        resp = admin_client.delete(f'/api/meeting-rooms/meeting-room-maintenance/{maint_id}/')
        assert resp.status_code == 204
