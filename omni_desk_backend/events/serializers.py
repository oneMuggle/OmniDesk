from rest_framework import serializers
from django.db import transaction
from .models import Trial, TimeSlot, Schedule, Announcement, UploadedImage, PersonnelSequence, LeaderSequence, Position, PhoneNumber, Holiday
from users.models import CustomUser
from users.shared_serializers import UserDataSerializer
from .models import Trial, Equipment, Personnel, DocumentTemplate

class PositionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Position
        fields = ['id', 'name']

class PhoneNumberSerializer(serializers.ModelSerializer):
    class Meta:
        model = PhoneNumber
        fields = ['id', 'number']

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
    position_name = serializers.SerializerMethodField()
    phone_numbers = PhoneNumberSerializer(many=True, required=False) # 新增phone_numbers字段
    position = serializers.PrimaryKeyRelatedField(
        queryset=Position.objects.all(),
        allow_null=True,
        required=False
    )

    class Meta:
        model = Personnel
        fields = ['id', 'name', 'position', 'position_name', 'phone_numbers'] # 修改fields
        # 移除extra_kwargs中对phone的设置

    def get_position_name(self, obj):
        return obj.position.name if obj.position else None

    def create(self, validated_data):
        phone_numbers_data = validated_data.pop('phone_numbers', [])
        personnel = Personnel.objects.create(**validated_data)
        for phone_data in phone_numbers_data:
            PhoneNumber.objects.create(personnel=personnel, **phone_data)
        return personnel

    def update(self, instance, validated_data):
        phone_numbers_data = validated_data.pop('phone_numbers', None)
        
        # Update Personnel instance fields
        instance.name = validated_data.get('name', instance.name)
        instance.position = validated_data.get('position', instance.position)
        instance.save()

        # If phone_numbers data is provided, update them
        if phone_numbers_data is not None:
            # Clear existing phone numbers
            instance.phone_numbers.all().delete()
            # Create new phone numbers
            for phone_data in phone_numbers_data:
                PhoneNumber.objects.create(personnel=instance, **phone_data)
        
        return instance

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
        time_slots_data = validated_data.pop('time_slots_data', [])
        with transaction.atomic():
            trial = super().create(validated_data)
            for slot_data in time_slots_data:
                TimeSlot.objects.create(trial=trial, **slot_data)
        trial.update_time_range() # Ensure time range is updated after creation
        return trial

    def update(self, instance, validated_data):
        time_slots_data = validated_data.pop('time_slots_data', None)
        with transaction.atomic():
            instance = super().update(instance, validated_data)
            
            if time_slots_data is not None:
                # 收集所有传入的时间段ID
                incoming_slot_ids = set()
                for slot in time_slots_data:
                    slot_id = slot.get('id')
                    try:
                        slot_id_int = int(slot_id)
                        incoming_slot_ids.add(slot_id_int)
                    except (ValueError, TypeError):
                        pass # 忽略无效ID
                
                # 删除不再存在于传入数据中的时间段
                instance.time_slots.exclude(id__in=incoming_slot_ids).delete()
                
                # 更新或创建时间段
                for slot_data in time_slots_data:
                    slot_id = slot_data.get('id')
                    try:
                        slot_id_int = int(slot_id)
                    except (ValueError, TypeError):
                        slot_id_int = None

                    if slot_id_int: # Update existing
                        try:
                            time_slot_instance = instance.time_slots.get(id=slot_id_int)
                            time_slot_serializer = TimeSlotSerializer(
                                time_slot_instance,
                                data=slot_data,
                                partial=True
                            )
                            time_slot_serializer.is_valid(raise_exception=True)
                            time_slot_serializer.save()
                        except TimeSlot.DoesNotExist:
                            # If ID was provided but not found, create new (shouldn't happen with proper incoming_slot_ids check)
                            time_slot_serializer = TimeSlotSerializer(
                                data={**slot_data, 'trial_id': instance.id}
                            )
                            time_slot_serializer.is_valid(raise_exception=True)
                            time_slot_serializer.save()
                    else: # Create new
                        time_slot_serializer = TimeSlotSerializer(
                            data={**slot_data, 'trial_id': instance.id}
                        )
                        time_slot_serializer.is_valid(raise_exception=True)
                        time_slot_serializer.save()
        instance.update_time_range() # 确保更新试验的主时间范围
        return instance

class ScheduleSerializer(serializers.ModelSerializer):
    duty_person_id = serializers.PrimaryKeyRelatedField(
        queryset=Personnel.objects.all(),
        source='duty_person',
        write_only=True,
        required=True
    )
    duty_leader_id = serializers.PrimaryKeyRelatedField(
        queryset=Personnel.objects.all(),
        source='duty_leader',
        write_only=True,
        required=True
    )
    duty_person = PersonnelSerializer(read_only=True)
    duty_leader = PersonnelSerializer(read_only=True)

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
        fields = ['id', 'duty_person', 'duty_leader', 'duty_date', 'override', 'duty_person_id', 'duty_leader_id']
        extra_kwargs = {
            'duty_date': {'required': True},
            'id': {'read_only': False, 'required': False},
            'override': {'required': False, 'default': False}
        }

    def validate(self, data):
        """验证排班数据"""
        duty_person = data.get('duty_person')
        duty_leader = data.get('duty_leader')

        # 检查值班人和值班领导是否为同一人
        if duty_person and duty_leader and duty_person.id == duty_leader.id:
            raise serializers.ValidationError("值班人和值班领导不能为同一人。")

        # 唯一性检查将由 perform_create/perform_update 处理
        return data

    def create(self, validated_data):
        validated_data.pop('override', False)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        validated_data.pop('override', False)
        return super().update(instance, validated_data)

class AnnouncementSerializer(serializers.ModelSerializer):
    author = UserDataSerializer(read_only=True)
    author_id = serializers.PrimaryKeyRelatedField(
        queryset=CustomUser.objects.all(),
        write_only=True,
        source='author',
        required=False
    )

    class Meta:
        model = Announcement
        fields = ['id', 'title', 'content', 'author', 'author_id', 'created_at', 'updated_at']
        extra_kwargs = {
            'author': {'read_only': True}
        }
class UploadedImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = UploadedImage
        fields = ['id', 'image', 'uploaded_at']

class PersonnelSequenceSerializer(serializers.ModelSerializer):
    personnel_details = serializers.SerializerMethodField()
    holiday_personnel_details = serializers.SerializerMethodField()

    class Meta:
        model = PersonnelSequence
        fields = [
            'id', 'name', 'sequence', 'personnel_details',
            'holiday_sequence', 'holiday_personnel_details'
        ]

    def get_personnel_details(self, obj):
        personnel_ids = obj.sequence
        if not personnel_ids:
            return []
        personnel_queryset = Personnel.objects.filter(id__in=personnel_ids)
        personnel_map = {p.id: p for p in personnel_queryset}
        sorted_personnel = [personnel_map[pid] for pid in personnel_ids if pid in personnel_map]
        return PersonnelSerializer(sorted_personnel, many=True).data

    def get_holiday_personnel_details(self, obj):
        personnel_ids = obj.holiday_sequence
        if not personnel_ids:
            return []
        personnel_queryset = Personnel.objects.filter(id__in=personnel_ids)
        personnel_map = {p.id: p for p in personnel_queryset}
        sorted_personnel = [personnel_map[pid] for pid in personnel_ids if pid in personnel_map]
        return PersonnelSerializer(sorted_personnel, many=True).data

class HolidaySerializer(serializers.ModelSerializer):
    class Meta:
        model = Holiday
        fields = ['id', 'name', 'start_date', 'end_date']

class LeaderSequenceSerializer(serializers.ModelSerializer):
    personnel_details = serializers.SerializerMethodField()

    class Meta:
        model = LeaderSequence
        fields = ['id', 'name', 'sequence', 'personnel_details']

    def get_personnel_details(self, obj):
        personnel_ids = obj.sequence
        personnel_queryset = Personnel.objects.filter(id__in=personnel_ids)
        # 保持原始ID列表的顺序
        personnel_map = {p.id: p for p in personnel_queryset}
        sorted_personnel = [personnel_map[pid] for pid in personnel_ids if pid in personnel_map]
        return PersonnelSerializer(sorted_personnel, many=True).data
