from rest_framework import serializers

from users.serializers import UserDetailSerializer  # 使用UserDetailSerializer来显示用户信息

from .models import MeetingRoom, MeetingRoomBooking, MeetingRoomMaintenance


class MeetingRoomSerializer(serializers.ModelSerializer):
    class Meta:
        model = MeetingRoom
        # R3-B1: 白名单化,前端消费字段
        fields = ["id", "name", "description", "capacity", "location"]


class MeetingRoomBookingSerializer(serializers.ModelSerializer):
    user = UserDetailSerializer(read_only=True)  # 嵌套显示用户信息
    meeting_room_name = serializers.CharField(source="meeting_room.name", read_only=True)  # 显示会议室名称

    class Meta:
        model = MeetingRoomBooking
        # R3-B1: 白名单化,保留 user 嵌套 + meeting_room_name(前端深度消费)
        fields = [
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
        ]
        read_only_fields = ("user",)  # 用户信息由后端自动填充


class MeetingRoomMaintenanceSerializer(serializers.ModelSerializer):
    meeting_room_name = serializers.CharField(source="meeting_room.name", read_only=True)  # 显示会议室名称

    class Meta:
        model = MeetingRoomMaintenance
        # R3-B1: 白名单化,保留 meeting_room_name
        fields = [
            "id",
            "meeting_room",
            "start_time",
            "end_time",
            "reason",
            "created_at",
            "updated_at",
            "meeting_room_name",
        ]
