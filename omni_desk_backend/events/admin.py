from django.contrib import admin
from .models import (
    Trial, TimeSlot, Schedule, Holiday,
    PersonnelSequence, LeaderSequence,
    Equipment, Announcement, DocumentTemplate, UploadedImage
)


@admin.register(Trial)
class TrialAdmin(admin.ModelAdmin):
    list_display = ('title', 'client', 'status', 'start_date', 'end_date', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('title', 'client')


@admin.register(TimeSlot)
class TimeSlotAdmin(admin.ModelAdmin):
    list_display = ('trial', 'start_time', 'end_time', 'description')
    list_filter = ('start_time',)


@admin.register(Schedule)
class ScheduleAdmin(admin.ModelAdmin):
    list_display = ('duty_date', 'duty_person', 'duty_leader')
    list_filter = ('duty_date',)


@admin.register(Holiday)
class HolidayAdmin(admin.ModelAdmin):
    list_display = ('name', 'start_date', 'end_date')
    list_filter = ('start_date',)


@admin.register(PersonnelSequence)
class PersonnelSequenceAdmin(admin.ModelAdmin):
    list_display = ('name', 'sequence')


@admin.register(LeaderSequence)
class LeaderSequenceAdmin(admin.ModelAdmin):
    list_display = ('name', 'sequence')


@admin.register(Equipment)
class EquipmentAdmin(admin.ModelAdmin):
    list_display = ('name',)


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'created_at')


@admin.register(DocumentTemplate)
class DocumentTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'experiment_type', 'owner', 'created_at')


@admin.register(UploadedImage)
class UploadedImageAdmin(admin.ModelAdmin):
    list_display = ('image', 'uploaded_at')
