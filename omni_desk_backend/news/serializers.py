from rest_framework import serializers
from .models import NewsType, NewsArticle
from users.serializers import UserSerializer

class NewsTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = NewsType
        fields = '__all__'

class NewsArticleSerializer(serializers.ModelSerializer):
    personnel = UserSerializer(read_only=True)
    news_type = NewsTypeSerializer(read_only=True)
    personnel_id = serializers.IntegerField(write_only=True)
    news_type_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = NewsArticle
        fields = ('id', 'title', 'link', 'publication_date', 'personnel', 'news_type', 'personnel_id', 'news_type_id')
