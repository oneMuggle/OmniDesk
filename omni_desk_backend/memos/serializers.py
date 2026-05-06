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

    def update(self, instance, validated_data):
        # 使用父类的 update 方法来处理所有字段的更新
        # 这是最健壮和推荐的做法
        instance = super().update(instance, validated_data)
        return instance
