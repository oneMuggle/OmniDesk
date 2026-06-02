from django.contrib import admin
from .models import MeetingRoom, MeetingRoomBooking, MeetingRoomMaintenance


@admin.register(MeetingRoom)
class MeetingRoomAdmin(admin.ModelAdmin):
    list_display = ("name", "capacity", "location")
    search_fields = ("name", "location")


@admin.register(MeetingRoomBooking)
class MeetingRoomBookingAdmin(admin.ModelAdmin):
    list_display = ("meeting_room", "user", "start_time", "end_time", "title")
    list_filter = ("meeting_room", "start_time")


@admin.register(MeetingRoomMaintenance)
class MeetingRoomMaintenanceAdmin(admin.ModelAdmin):
    list_display = ("meeting_room", "start_time", "end_time", "reason")
    list_filter = ("meeting_room", "start_time")
