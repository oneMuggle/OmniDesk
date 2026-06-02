from rest_framework import serializers

from .models import Ebook


class EbookSerializer(serializers.ModelSerializer):
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta:
        model = Ebook
        fields = ["id", "title", "author", "file", "createdAt"]
        read_only_fields = ["id", "createdAt"]
