from rest_framework import serializers
from .models import Trial
from users.models import CustomUser
from .models import Trial, Equipment, Personnel, DocumentTemplate
from users.serializers import UserSerializer

class PersonnelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Personnel
        fields = '__all__'
        extra_kwargs = {
            'phone': {'required': False},
            'department': {'required': False}
        }

class EquipmentSerializer(serializers.ModelSerializer):
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
    responsible_persons = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Personnel.objects.all(),
        required=True
    )
    related_equipment = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Equipment.objects.all(),
        required=True,
        source='equipments'
    )

    class Meta:
        model = Trial
        fields = [
            'id', 'title', 'description', 
            'start_date', 'end_date', 'client',
            'related_equipment', 'responsible_persons',
            'status'
        ]
        extra_kwargs = {
            'title': {'required': True},
            'description': {'required': True},
            'start_date': {'required': True},
            'end_date': {'required': True},
            'client': {'required': True},
            'status': {'default': 'planned'}
        }

    def validate(self, data):
        """时间验证"""
        if data['start_date'] > data['end_date']:
            raise serializers.ValidationError("试验结束时间不能早于开始时间")
        return data
