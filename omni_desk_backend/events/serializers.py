from django.db import transaction
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
        return [{'id': p.user_account.id, 'real_name': p.user_account.real_name} for p in obj.personnel.all() if hasattr(p, 'user_account') and p.user_account]

    def get_holiday_personnel_details(self, obj):
        return [{'id': p.user_account.id, 'real_name': p.user_account.real_name} for p in obj.holiday_personnel.all() if hasattr(p, 'user_account') and p.user_account]

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
