from rest_framework import serializers
from django.db import transaction
from .models import Trial, TimeSlot, Schedule
from users.models import CustomUser
from .models import Trial, Equipment, Personnel, DocumentTemplate
from users.serializers import UserSerializer

class TimeSlotSerializer(serializers.ModelSerializer):
    trial_id = serializers.PrimaryKeyRelatedField(
        queryset=Trial.objects.all(),
        source='trial',
        required=True
    )
    
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
        read_only=True,
        help_text="时间段列表（只读）"
    )
    time_slots_data = serializers.ListField(
        child=serializers.DictField(),
        write_only=True,
        required=False,
        help_text="时间段数据（写入用），格式：[{'start_time': '2023-01-01T09:00', 'end_time': '2023-01-01T12:00', 'description': ''}, ...]"
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
            'responsible_person_ids', 'equipment_ids',
            'time_slots_data'
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
            'time_periods': {'required': False, 'help_text': '时间段明细'}
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
                TimeSlot.objects.create(
                    trial=trial,
                    start_time=slot['start_time'],
                    end_time=slot['end_time'],
                    description=slot.get('description', '')
                )
        return trial

    def update(self, instance, validated_data):
        time_slots_data = validated_data.pop('time_slots_data', None)
        with transaction.atomic():
            instance = super().update(instance, validated_data)
            
            if time_slots_data is not None:
                # 获取现有time_slots的ID集合
                existing_ids = set(instance.time_slots.values_list('id', flat=True))
                updated_ids = set()
                
                # 处理每个时间段
                for slot_data in time_slots_data:
                    slot_id = slot_data.get('id')
                    if slot_id and instance.time_slots.filter(id=slot_id).exists():
                        # 更新现有时间段
                        slot = instance.time_slots.get(id=slot_id)
                        slot.start_time = slot_data['start_time']
                        slot.end_time = slot_data['end_time']
                        slot.description = slot_data.get('description', '')
                        slot.save()
                        updated_ids.add(slot_id)
                    else:
                        # 创建新时间段
                        TimeSlot.objects.create(
                            trial=instance,
                            start_time=slot_data['start_time'],
                            end_time=slot_data['end_time'],
                            description=slot_data.get('description', '')
                        )
                
                # 删除未更新的时间段
                to_delete_ids = existing_ids - updated_ids
                if to_delete_ids:
                    instance.time_slots.filter(id__in=to_delete_ids).delete()
                    
        return instance

class ScheduleSerializer(serializers.ModelSerializer):
    duty_person = serializers.PrimaryKeyRelatedField(
        queryset=Personnel.objects.all(),
        required=True,
        help_text="值班人员ID"
    )
    duty_leader = serializers.PrimaryKeyRelatedField(
        queryset=Personnel.objects.all(),
        required=True,
        help_text="值班领导ID"
    )
    duty_date = serializers.DateField(
        required=True,
        help_text="值班日期，格式：YYYY-MM-DD"
    )
    override = serializers.BooleanField(
        required=False,
        default=False,
        help_text="是否覆盖已有排班"
    )

    class Meta:
        model = Schedule
        fields = ['id', 'duty_person', 'duty_leader', 'duty_date', 'override']
        extra_kwargs = {
            'duty_date': {'required': True},
            'id': {'read_only': False, 'required': False},
            'override': {'required': False, 'default': False}
        }

    def validate(self, data):
        """验证排班数据"""
        duty_date = data.get('duty_date')
        duty_person = data.get('duty_person')
        duty_leader = data.get('duty_leader')
        instance_id = self.instance.id if self.instance else None
        override = data.get('override', False)

        # 检查值班人和值班领导是否为同一人
        if duty_person and duty_leader and duty_person.id == duty_leader.id:
            raise serializers.ValidationError({
                'duty_leader': '值班人和值班领导不能为同一人'
            })

        # 检查值班日期是否已存在（除非是覆盖操作）
        if not override and Schedule.objects.filter(duty_date=duty_date).exclude(id=instance_id).exists():
            raise serializers.ValidationError({
                'duty_date': '该日期已有排班记录'
            })

        return data

    @transaction.atomic
    def create(self, validated_data):
        override = validated_data.pop('override', False)
        duty_date = validated_data['duty_date']
        
        if override:
            Schedule.objects.filter(duty_date=duty_date).delete()
        
        return super().create(validated_data)

    @transaction.atomic
    def update(self, instance, validated_data):
        override = validated_data.pop('override', False)
        duty_date = validated_data.get('duty_date', instance.duty_date)
        
        if override and duty_date != instance.duty_date:
            Schedule.objects.filter(duty_date=duty_date).delete()
        
        return super().update(instance, validated_data)
