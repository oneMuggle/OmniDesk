from rest_framework import serializers
from .models import Memo

class MemoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Memo
        fields = [
            'id', 
            'title', 
            'content', 
            'reminder_time', 
            'is_completed', 
            'user', 
            'created_at', 
            'updated_at'
        ]
        read_only_fields = ['user'] # The user will be set automatically from the request