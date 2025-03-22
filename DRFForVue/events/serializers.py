from rest_framework import serializers
from .models import Event, DocumentTemplate, ResponsiblePerson

class EventSerializer(serializers.ModelSerializer):
    created_by = serializers.StringRelatedField()
    
    class Meta:
        model = Event
        fields = [
            'id', 'title', 'description', 'start_time', 'end_time',
            'experiment_info', 'responsible_person', 'train_count',
            'created_by', 'created_at'
        ]
        read_only_fields = ('created_by', 'created_at')

class DocumentTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentTemplate
        fields = '__all__'
        read_only_fields = ('created_at',)

class ResponsiblePersonSerializer(serializers.ModelSerializer):
    created_by = serializers.StringRelatedField()
    
    class Meta:
        model = ResponsiblePerson
        fields = ['id', 'name', 'position', 'contact', 'event', 'created_by', 'created_at']
        read_only_fields = ('created_by', 'created_at')
