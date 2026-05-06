from rest_framework import serializers

from .models import Comment, Post


class CommentSerializer(serializers.ModelSerializer):
    author = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = ['id', 'post', 'author', 'content', 'created_at']
        read_only_fields = ('post',)

    def get_author(self, obj):
        if obj.author and hasattr(obj.author, 'real_name'):
            return obj.author.real_name or obj.author.username
        elif obj.author:
            return obj.author.username
        return "Anonymous"


class PostSerializer(serializers.ModelSerializer):
    author = serializers.SerializerMethodField()
    comments = CommentSerializer(many=True, read_only=True)

    class Meta:
        model = Post
        fields = ['id', 'title', 'content', 'author', 'created_at', 'updated_at', 'expires_at', 'is_archived', 'comments']

    def get_author(self, obj):
        if obj.author and hasattr(obj.author, 'real_name'):
            return obj.author.real_name or obj.author.username
        elif obj.author:
            return obj.author.username
        return "Anonymous"
