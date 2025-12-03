from rest_framework import serializers
from django.contrib.auth import get_user_model

CustomUser = get_user_model()

class UserDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ('id', 'username', 'real_name')