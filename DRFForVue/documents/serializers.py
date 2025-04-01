from rest_framework import serializers
from .models import DocumentTemplate, GeneratedDocument
from users.serializers import UserSerializer

class DocumentTemplateSerializer(serializers.ModelSerializer):
    owner = UserSerializer(read_only=True)
    template_type_display = serializers.CharField(source='get_template_type_display', read_only=True)
    
    class Meta:
        model = DocumentTemplate
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at')

class GeneratedDocumentSerializer(serializers.ModelSerializer):
    template = serializers.PrimaryKeyRelatedField(queryset=DocumentTemplate.objects.all())
    generated_by = UserSerializer(read_only=True)
    content_preview = serializers.SerializerMethodField()
    
    class Meta:
        model = GeneratedDocument
        fields = '__all__'
        read_only_fields = ('generated_at',)

    def get_content_preview(self, obj):
        return obj.content[:100] + '...' if len(obj.content) > 100 else obj.content
