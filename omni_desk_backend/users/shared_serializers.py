from rest_framework import serializers
from django.contrib.auth import get_user_model

CustomUser = get_user_model()

class AuthorSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ('username', 'real_name')