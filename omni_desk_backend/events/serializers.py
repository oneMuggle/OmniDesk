from django.db import transaction
from rest_framework import serializers
from .models import (
    Trial, TimeSlot, Equipment, DocumentTemplate, Schedule, Announcement, UploadedImage,
    PersonnelSequence, LeaderSequence, Holiday, Position
)
from personnel.serializers import PersonnelSerializer
from personnel.models import Personnel

class TimeSlotSerializer(serializers.ModelSerializer):
    class Meta:
        model = TimeSlot
        fields = '__all__'

class EquipmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Equipment
        fields = ['id', 'name']

class TrialSerializer(serializers.ModelSerializer):
    time_slots = TimeSlotSerializer(many=True, read_only=True)
    responsible_persons = PersonnelSerializer(many=True, read_only=True)
    equipments = EquipmentSerializer(many=True, read_only=True)
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

class PersonnelSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Personnel
        fields = ('id', 'name')


class PersonnelSequenceSerializer(serializers.ModelSerializer):
    personnel_details = serializers.SerializerMethodField()
    holiday_personnel_details = serializers.SerializerMethodField()

    class Meta:
        model = PersonnelSequence
        fields = [
            'id', 'name', 'personnel', 'sequence',
            'holiday_personnel', 'holiday_sequence', 'personnel_details',
            'holiday_personnel_details'
        ]
        extra_kwargs = {
            'personnel': {'write_only': True},
            'holiday_personnel': {'write_only': True},
        }

    def get_personnel_details(self, obj):
        """
        Fetches details for each personnel in the sequence, skipping any invalid IDs.
        """
        personnel_ids = obj.sequence
        if not personnel_ids:
            return []

        # Fetch all valid personnel objects in one query, optimizing for user_account access.
        valid_personnel = Personnel.objects.filter(id__in=personnel_ids)
        
        # Create a dictionary for quick lookups
        personnel_map = {p.id: p for p in valid_personnel}
        
        # Build the result list, preserving the original order and skipping invalid IDs
        result_list = []
        for person_id in personnel_ids:
            if person_id in personnel_map:
                personnel = personnel_map[person_id]
                serializer = PersonnelSimpleSerializer(personnel)
                result_list.append(serializer.data)
        
        return result_list

    def get_holiday_personnel_details(self, obj):
        personnel_list = obj.holiday_personnel.all()
        return PersonnelSimpleSerializer(personnel_list, many=True).data

    def update(self, instance, validated_data):
        """
        自定义更新方法以处理指向旧 personnel 表的 M2M 关系。
        """
        instance.name = validated_data.get('name', instance.name)
        instance.sequence = validated_data.get('sequence', instance.sequence)
        instance.holiday_sequence = validated_data.get('holiday_sequence', instance.holiday_sequence)

        personnel_data = validated_data.get('personnel')
        holiday_personnel_data = validated_data.get('holiday_personnel')

        with transaction.atomic():
            instance.save()

            if personnel_data is not None:
                old_personnel_list = []
                for new_personnel in personnel_data:
                    try:
                        # 创可贴修复：通过 CustomUser 桥接，将新的 personnel.Personnel 对象
                        # 转换为旧的 events.Personnel 对象。
                        # 假设从 CustomUser 到旧 Personnel 的反向关系为 'events_personnel'。
                        if hasattr(new_personnel, 'user_account') and new_personnel.user_account and hasattr(new_personnel.user_account, 'events_personnel'):
                            old_personnel_list.append(new_personnel.user_account.events_personnel)
                    except AttributeError:
                        # 如果找不到关联的旧对象，则跳过，避免崩溃
                        continue
                instance.personnel.set(old_personnel_list)

            if holiday_personnel_data is not None:
                old_holiday_personnel_list = []
                for new_personnel in holiday_personnel_data:
                    try:
                        if hasattr(new_personnel, 'user_account') and new_personnel.user_account and hasattr(new_personnel.user_account, 'events_personnel'):
                            old_holiday_personnel_list.append(new_personnel.user_account.events_personnel)
                    except AttributeError:
                        continue
                instance.holiday_personnel.set(old_holiday_personnel_list)

        return instance

class LeaderSequenceSerializer(serializers.ModelSerializer):
    personnel_details = serializers.SerializerMethodField()

    class Meta:
        model = LeaderSequence
        fields = ['id', 'name', 'personnel', 'sequence', 'personnel_details']
        extra_kwargs = {
            'personnel': {'write_only': True},
        }

    def get_personnel_details(self, obj):
        """
        Fetches details for each personnel in the sequence, skipping any invalid IDs.
        """
        personnel_ids = obj.sequence
        if not personnel_ids:
            return []

        valid_personnel = Personnel.objects.filter(id__in=personnel_ids)
        personnel_map = {p.id: p for p in valid_personnel}
        
        result_list = []
        for person_id in personnel_ids:
            if person_id in personnel_map:
                personnel = personnel_map[person_id]
                serializer = PersonnelSimpleSerializer(personnel)
                result_list.append(serializer.data)
        
        return result_list

class HolidaySerializer(serializers.ModelSerializer):
    class Meta:
        model = Holiday
        fields = '__all__'

class PositionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Position
        fields = ['id', 'name']


class GenerateScheduleSerializer(serializers.Serializer):
    """
    Serializer for validating schedule generation parameters.
    """
    workday_personnel_sequence_id = serializers.IntegerField()
    holiday_personnel_sequence_id = serializers.IntegerField(required=False, allow_null=True)
    leader_sequence_id = serializers.IntegerField()
    start_personnel_id = serializers.IntegerField(required=False, allow_null=True)
    start_leader_id = serializers.IntegerField(required=False, allow_null=True)
    target_month = serializers.CharField(required=False, allow_null=True, max_length=7)
    duration_days = serializers.IntegerField(required=False, allow_null=True)
    start_date = serializers.DateField(required=False, allow_null=True)

    def validate(self, data):
        if not data.get('target_month') and not (data.get('start_date') and data.get('duration_days')):
            raise serializers.ValidationError(
                "Either 'target_month' or both 'start_date' and 'duration_days' are required."
            )
        return data
