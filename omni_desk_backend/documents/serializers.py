from rest_framework import serializers
from .models import DocumentTemplate, GeneratedDocument
from users.serializers import UserSerializer

class DocumentTemplateSerializer(serializers.ModelSerializer):
    owner = UserSerializer(read_only=True)
    template_type_display = serializers.CharField(source='get_template_type_display', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True, allow_null=True) # 新增
    
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

from .models import Book, Chapter, Comment, Annotation, Tag

class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = '__all__'

class CommentSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = Comment
        fields = ('id', 'user', 'content', 'created_at')
        read_only_fields = ('created_at',)

class AnnotationSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = Annotation
        fields = ('id', 'user', 'selected_text', 'note', 'created_at')
        read_only_fields = ('created_at',)

class ChapterSerializer(serializers.ModelSerializer):
    comments = CommentSerializer(many=True, read_only=True)
    annotations = AnnotationSerializer(many=True, read_only=True)

    class Meta:
        model = Chapter
        fields = ('id', 'title', 'content_html', 'order', 'comments', 'annotations', 'image_metadata', 'heading_structure')

class BookSerializer(serializers.ModelSerializer):
    chapters = ChapterSerializer(many=True, read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True, allow_null=True) # 新增

    class Meta:
        model = Book
        fields = ('id', 'title', 'author', 'description', 'cover_image', 'publication_date', 'tags', 'chapters', 'project_name') # 添加 'project_name'
