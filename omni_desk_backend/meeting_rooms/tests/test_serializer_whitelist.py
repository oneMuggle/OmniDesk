"""meeting_rooms serializer 白名单化测试 (R3-B1 PR-3)。

契约(plan §3.2 PR-3):
- 3 个 serializer(MeetingRoom/Booking/Maintenance)显式白名单字段,
  不随 `__all__` 暴露模型全部字段
- BookingSerializer 保留前端深度消费的 user 嵌套(UserDetailSerializer)与 meeting_room_name
- MaintenanceSerializer 保留 meeting_room_name
"""

from datetime import timedelta

import pytest
from django.utils import timezone

from meeting_rooms.models import MeetingRoom, MeetingRoomBooking, MeetingRoomMaintenance
from meeting_rooms.serializers import (
    MeetingRoomBookingSerializer,
    MeetingRoomMaintenanceSerializer,
    MeetingRoomSerializer,
)


def _future(hours=1):
    return timezone.now() + timedelta(hours=hours)


@pytest.fixture
def meeting_room(db):
    return MeetingRoom.objects.create(name="第一会议室", capacity=10, location="A栋")


@pytest.mark.django_db
class TestMeetingRoomSerializerWhitelist:
    def test_fields_whitelisted(self):
        room = MeetingRoom.objects.create(name="第一会议室", capacity=10)

        data = MeetingRoomSerializer(room).data

        assert set(data.keys()) == {"id", "name", "description", "capacity", "location"}


@pytest.mark.django_db
class TestMeetingRoomBookingSerializerWhitelist:
    def test_fields_whitelisted(self, meeting_room, regular_user_obj):
        booking = MeetingRoomBooking.objects.create(
            meeting_room=meeting_room,
            user=regular_user_obj,
            start_time=_future(1),
            end_time=_future(2),
            title="项目评审",
            participants="张三、李四",
            description="季度项目评审会",
        )

        data = MeetingRoomBookingSerializer(booking).data

        assert set(data.keys()) == {
            "id",
            "meeting_room",
            "user",
            "start_time",
            "end_time",
            "title",
            "participants",
            "description",
            "created_at",
            "updated_at",
            "meeting_room_name",
        }

    def test_nested_user_and_room_name_kept(self, meeting_room, regular_user_obj):
        booking = MeetingRoomBooking.objects.create(
            meeting_room=meeting_room,
            user=regular_user_obj,
            start_time=_future(1),
            end_time=_future(2),
            title="项目评审",
        )

        data = MeetingRoomBookingSerializer(booking).data

        assert data["meeting_room_name"] == "第一会议室"
        assert data["user"]["username"] == regular_user_obj.username


@pytest.mark.django_db
class TestMeetingRoomMaintenanceSerializerWhitelist:
    def test_fields_whitelisted(self, meeting_room):
        maint = MeetingRoomMaintenance.objects.create(
            meeting_room=meeting_room,
            start_time=_future(1),
            end_time=_future(2),
            reason="空调检修",
        )

        data = MeetingRoomMaintenanceSerializer(maint).data

        assert set(data.keys()) == {
            "id",
            "meeting_room",
            "start_time",
            "end_time",
            "reason",
            "created_at",
            "updated_at",
            "meeting_room_name",
        }

    def test_room_name_kept(self, meeting_room):
        maint = MeetingRoomMaintenance.objects.create(
            meeting_room=meeting_room,
            start_time=_future(1),
            end_time=_future(2),
            reason="空调检修",
        )

        data = MeetingRoomMaintenanceSerializer(maint).data

        assert data["meeting_room_name"] == "第一会议室"
