"""R5-B2: MeetingRoomBooking 嵌套序列化 N+1 测试。

MeetingRoomBookingSerializer.user 嵌套 UserDetailSerializer,其访问:
- phone_numbers(反向 FK)
- assigned_by + assigned_by_username(FK 及其 username)
- personnel(StringRelatedField → __str__)

修复前每条 booking 额外产生 3 条查询;修复后 queryset 应一次取齐。
"""

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from meeting_rooms.models import MeetingRoom, MeetingRoomBooking
from personnel.models import Personnel
from users.models import CustomUser, PhoneNumber

pytestmark = pytest.mark.django_db


@pytest.fixture
def booking_owner(db):
    owner = CustomUser.objects.create_user(username="booking_owner", password="pass123")
    assigner = CustomUser.objects.create_user(username="booking_assigner", password="pass123")
    owner.assigned_by = assigner
    owner.save()
    person = Personnel.objects.create(name="张三")
    owner.personnel = person
    owner.save()
    PhoneNumber.objects.create(user=owner, number="13800000000")
    return owner


@pytest.fixture
def bookings(db, booking_owner):
    room = MeetingRoom.objects.create(name="会议室A", capacity=10)
    return [
        MeetingRoomBooking.objects.create(
            user=booking_owner,
            meeting_room=room,
            start_time=f"2026-09-0{day}T09:00:00Z",
            end_time=f"2026-09-0{day}T10:00:00Z",
            title=f"预约{i}",
        )
        for i, day in enumerate(range(1, 6), start=1)
    ]


class TestBookingListQueryCount:
    def test_list_bookings_query_count_is_bounded(self, api_client, booking_owner, bookings):
        """5 条 booking 的 list 不应随行数线性增长查询数。

        基线:1(session/user) + 1(count) + 1(bookings+select_related) +
        1(phone_numbers prefetch) = 4;给足余量上限 8。
        """
        client = APIClient()
        client.force_authenticate(user=booking_owner)
        with CaptureQueriesContext(connection) as ctx:
            response = client.get("/api/meeting-rooms/meeting-room-bookings/")
        assert response.status_code == 200
        assert len(response.data["results"]) == 5
        assert len(ctx.captured_queries) <= 8, (
            f"list bookings 执行了 {len(ctx.captured_queries)} 条查询(>8),存在 N+1: "
            f"{[q['sql'][:120] for q in ctx.captured_queries]}"
        )

    def test_nested_user_fields_present(self, api_client, booking_owner, bookings):
        """修复不得破坏嵌套字段输出。"""
        client = APIClient()
        client.force_authenticate(user=booking_owner)
        response = client.get("/api/meeting-rooms/meeting-room-bookings/")
        user_data = response.data["results"][0]["user"]
        assert user_data["username"] == "booking_owner"
        assert user_data["assigned_by_username"] == "booking_assigner"
        assert user_data["personnel"] == "张三"
        assert user_data["phone_numbers"][0]["number"] == "13800000000"
