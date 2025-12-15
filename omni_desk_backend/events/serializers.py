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
    time_slots_data = serializers.ListField(
        child=serializers.DictField(), write_only=True, required=False
    )

    class Meta:
        model = Trial
        fields = '__all__'

    def create(self, validated_data):
        time_slots_data = validated_data.pop('time_slots_data', [])
        trial = Trial.objects.create(**validated_data)
        for slot_data in time_slots_data:
            TimeSlot.objects.create(trial=trial, **slot_data)
        return trial

    def update(self, instance, validated_data):
        time_slots_data = validated_data.pop('time_slots_data', None)
        instance = super().update(instance, validated_data)
        if time_slots_data is not None:
            for slot_data in time_slots_data:
                slot_id = slot_data.pop('id', None)
                if slot_id:
                    TimeSlot.objects.filter(id=slot_id, trial=instance).update(**slot_data)
                else:
                    TimeSlot.objects.create(trial=instance, **slot_data)
        return instance

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
