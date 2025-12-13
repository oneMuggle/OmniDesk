from rest_framework import serializers
from .models import (
    Trial, TimeSlot, Equipment, DocumentTemplate, Schedule, Announcement, UploadedImage,
    PersonnelSequence, LeaderSequence, Holiday, Position
)
from personnel.serializers import PersonnelSerializer

class TimeSlotSerializer(serializers.ModelSerializer):
    class Meta:
        model = TimeSlot
        fields = '__all__'

class TrialSerializer(serializers.ModelSerializer):
    time_slots = TimeSlotSerializer(many=True, read_only=True)
    responsible_persons = PersonnelSerializer(many=True, read_only=True)

    class Meta:
        model = Trial
        fields = '__all__'

class EquipmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Equipment
        fields = '__all__'

class DocumentTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentTemplate
        fields = '__all__'

class ScheduleSerializer(serializers.ModelSerializer):
    duty_person = PersonnelSerializer(read_only=True)
    duty_leader = PersonnelSerializer(read_only=True)

    class Meta:
        model = Schedule
        fields = '__all__'

class AnnouncementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Announcement
        fields = '__all__'

class UploadedImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = UploadedImage
        fields = '__all__'

class PersonnelSequenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = PersonnelSequence
        fields = '__all__'

class LeaderSequenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaderSequence
        fields = '__all__'

class HolidaySerializer(serializers.ModelSerializer):
    class Meta:
        model = Holiday
        fields = '__all__'

class PositionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Position
        fields = ['id', 'name']
