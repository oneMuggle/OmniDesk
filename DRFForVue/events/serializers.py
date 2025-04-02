from rest_framework import serializers
from django.db import transaction
from .models import Trial, TimeSlot
from users.models import CustomUser
from .models import Trial, Equipment, Personnel, DocumentTemplate
from users.serializers import UserSerializer

class TimeSlotSerializer(serializers.ModelSerializer):
    trial_id = serializers.IntegerField(source='trial.id', read_only=True)
    
    class Meta:
        model = TimeSlot
        fields = ['id', 'trial_id', 'start_time', 'end_time', 'description']
        extra_kwargs = {
            'description': {'required': False, 'allow_blank': True}
        }

    def validate(self, data):
        """验证时间槽逻辑"""
        if data['start_time'] >= data['end_time']:
            raise serializers.ValidationError("时间槽结束时间必须晚于开始时间")
        return data

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
    time_slots = TimeSlotSerializer(
        many=True,
        required=False,
        allow_empty=True,
        help_text="时间段列表（可为空或多个），格式：[{'start_time': '2023-01-01T09:00', 'end_time': '2023-01-01T12:00', 'description': ''}, ...]"
    )
    
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
        source='equipments'
    )

    class Meta:
        model = Trial
        fields = [
            'id', 'title', 'client', 'status',
            'start_date', 'end_date', 'description',
            'equipments', 'responsible_persons', 'time_slots',
            'responsible_person_ids', 'equipment_ids'
        ]
        extra_kwargs = {
            'title': {'required': True, 'help_text': '试验名称'},
            'client': {'required': True, 'help_text': '客户单位'},
            'status': {'default': 'planned', 'help_text': '试验状态'},
            'start_date': {
                'required': False,
                'help_text': '主开始时间（自动从时间段计算）'
            },
            'end_date': {
                'required': False,
                'help_text': '主结束时间（自动从时间段计算）'
            },
            'description': {'required': True, 'help_text': '试验描述'},
            'time_slots': {'required': False, 'help_text': '时间段明细'}
        }

    def validate(self, data):
        """时间验证"""
        time_slots = data.get('time_slots', [])
        
        # 自动计算主时间范围
        if time_slots:
            start_dates = [slot['start_time'] for slot in time_slots]
            end_dates = [slot['end_time'] for slot in time_slots]
            data['start_date'] = min(start_dates)
            data['end_date'] = max(end_dates)

        # 时间段数量限制
        if len(time_slots) > 50:
            raise serializers.ValidationError("单个试验最多允许50个时间段")

        return data

    def create(self, validated_data):
        time_slots = validated_data.pop('time_slots', [])
        with transaction.atomic():
            trial = super().create(validated_data)
            for slot in time_slots:
                # 创建TimeSlot并自动关联到当前试验
                TimeSlot.objects.create(
                    trial=trial,
                    start_time=slot['start_time'],
                    end_time=slot['end_time'],
                    description=slot.get('description', '')
                )
        return trial

    def update(self, instance, validated_data):
        time_slots = validated_data.pop('time_slots', [])
        with transaction.atomic():
            instance = super().update(instance, validated_data)
            # 删除原有时间段
            instance.time_slots.all().delete()
            # 创建新时间段
            for slot in time_slots:
                TimeSlot.objects.create(
                    trial=instance,
                    start_time=slot['start_time'],
                    end_time=slot['end_time'],
                    description=slot.get('description', '')
                )
        return instance
