from rest_framework import serializers
from .models import Event, Personnel, DocumentTemplate, ResponsiblePerson

class EventSerializer(serializers.ModelSerializer):
    class Meta:
        model = Event
        fields = '__all__'

class PersonnelSerializer(serializers.ModelSerializer):
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())
    
    class Meta:
        model = Personnel
        fields = ['id', 'user', 'name', 'phone', 'department', 'position', 'created_at', 'updated_at']
        read_only_fields = ['user']
        extra_kwargs = {
            'department': {'required': False},
            'phone': {'required': True}
        }

class DocumentTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentTemplate
        fields = '__all__'

class ResponsiblePersonSerializer(serializers.ModelSerializer):
    class Meta:
        model = ResponsiblePerson
        fields = '__all__'
