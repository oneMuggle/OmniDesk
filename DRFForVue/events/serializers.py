from rest_framework import serializers
from .models import Event, Personnel, DocumentTemplate, ResponsiblePerson, Equipment

class EventSerializer(serializers.ModelSerializer):
    class Meta:
        model = Event
        fields = '__all__'

class PersonnelSerializer(serializers.ModelSerializer):
    user = serializers.HiddenField(
        default=serializers.CurrentUserDefault(),
        required=False
    )

    class Meta:
        model = Personnel
        fields = '__all__'
        extra_kwargs = {
            'department': {'required': False},
            'phone': {'required': False}
        }

class DocumentTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentTemplate
        fields = '__all__'

class ResponsiblePersonSerializer(serializers.ModelSerializer):
    class Meta:
        model = ResponsiblePerson
        fields = '__all__'
        extra_kwargs = {
            'trials': {'required': False, 'allow_empty': True}
        }

class TrialSerializer(serializers.ModelSerializer):
    responsible_persons = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=ResponsiblePerson.objects.all(),
        required=False
    )

    class Meta:
        model = Event  # 假设Event模型对应试验
        fields = '__all__'
        extra_kwargs = {
            'responsible_persons': {'required': False, 'allow_empty': True}
        }

class EquipmentSerializer(serializers.ModelSerializer):
    user = serializers.HiddenField(
        default=serializers.CurrentUserDefault(),
        required=False
    )
    
    class Meta:
        model = Equipment
        fields = '__all__'
