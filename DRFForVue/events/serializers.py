from rest_framework import serializers
from .models import Trial, TimeSlot
from users.models import CustomUser
from .models import Trial, Equipment, Personnel, DocumentTemplate
from users.serializers import UserSerializer

class TimeSlotSerializer(serializers.ModelSerializer):
    class Meta:
        model = TimeSlot
        fields = ['id', 'start_time', 'end_time']

class PersonnelSerializer(serializers.ModelSerializer):
    department = serializers.CharField(allow_blank=True, required=False)
    
    class Meta:
        model = Personnel
        fields = '__all__'
        extra_kwargs = {
            'phone': {'required': False},
            'department': {'required': False}
        }

class EquipmentSerializer(serializers.ModelSerializer):
    name = serializers.CharField()
    description = serializers.CharField(allow_blank=True, required=False)
    
    class Meta:
        model = Equipment
        fields = '__all__'
        extra_kwargs = {
            'purchase_date': {'required': False},
            'maintenance_interval': {'default': 365}
        }

class DocumentTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentTemplate
        fields = '__all__'
        extra_kwargs = {
            'template_file': {'required': True},
            'owner': {'read_only': True}
        }

class TrialSerializer(serializers.ModelSerializer):
    responsible_persons = PersonnelSerializer(many=True, read_only=True)
    equipments = EquipmentSerializer(many=True, read_only=True)
    related_equipment = EquipmentSerializer(many=True, read_only=True, source='equipments')
    time_slots = TimeSlotSerializer(many=True, required=False)
    
    responsible_person_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Personnel.objects.all(),
        required=True,
        write_only=True,
        source='responsible_persons'
    )
    equipment_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Equipment.objects.all(),
        required=True,
        write_only=True,
        source='related_equipment'
    )

    class Meta:
        model = Trial
        fields = [
            'id', 'title', 'description', 
            'start_date', 'end_date', 'client',
            'related_equipment', 'responsible_persons','equipments', 'time_slots',
            'status', 'responsible_person_ids', 'equipment_ids'
        ]
        extra_kwargs = {
            'title': {'required': True},
            'description': {'required': True},
            'start_date': {'required': True},
            'end_date': {'required': True},
            'client': {'required': True},
            'status': {'default': 'planned'},
            'time_slots': {'required': False}
        }

    def create(self, validated_data):
        time_slots_data = validated_data.pop('time_slots', [])
        trial = super().create(validated_data)
        for slot_data in time_slots_data:
            TimeSlot.objects.create(trial=trial, **slot_data)
        return trial

    def update(self, instance, validated_data):
        time_slots_data = validated_data.pop('time_slots', [])
        instance = super().update(instance, validated_data)
        
        # 清空原有时间段并创建新的
        instance.time_slots.clear()
        for slot_data in time_slots_data:
            TimeSlot.objects.create(trial=instance, **slot_data)
        return instance

    def validate(self, data):
        """时间验证"""
        if data['start_date'] > data['end_date']:
            raise serializers.ValidationError("试验结束时间不能早于开始时间")
        return data
