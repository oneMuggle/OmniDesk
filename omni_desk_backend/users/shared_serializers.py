from django.contrib.auth import get_user_model
from rest_framework import serializers

CustomUser = get_user_model()

class UserDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ('id', 'username', 'real_name')
