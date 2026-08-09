from django.utils import timezone
from rest_framework import serializers

from .models import Memo


class MemoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Memo
        fields = ["id", "title", "content", "reminder_time", "is_completed", "user", "created_at", "updated_at"]
        read_only_fields = ["user"]  # The user will be set automatically from the request

    def update(self, instance, validated_data):
        # P0-2:改期到未来时重置提醒标记,使新时间点可再次触发到期提醒
        new_reminder_time = validated_data.get("reminder_time")
        if (
            new_reminder_time is not None
            and new_reminder_time > timezone.now()
            and instance.reminder_sent
        ):
            validated_data["reminder_sent"] = False
        # 使用父类的 update 方法来处理所有字段的更新
        # 这是最健壮和推荐的做法
        instance = super().update(instance, validated_data)
        return instance
