from rest_framework import serializers

from users.serializers import UserDetailSerializer  # 使用UserDetailSerializer来显示用户信息

from .models import MeetingRoom, MeetingRoomBooking, MeetingRoomMaintenance


class MeetingRoomSerializer(serializers.ModelSerializer):
    class Meta:
        model = MeetingRoom
        fields = "__all__"


class MeetingRoomBookingSerializer(serializers.ModelSerializer):
    user = UserDetailSerializer(read_only=True)  # 嵌套显示用户信息
    meeting_room_name = serializers.CharField(source="meeting_room.name", read_only=True)  # 显示会议室名称

    class Meta:
        model = MeetingRoomBooking
        fields = "__all__"
        read_only_fields = ("user",)  # 用户信息由后端自动填充


class MeetingRoomMaintenanceSerializer(serializers.ModelSerializer):
    meeting_room_name = serializers.CharField(source="meeting_room.name", read_only=True)  # 显示会议室名称

    class Meta:
        model = MeetingRoomMaintenance
        fields = "__all__"
