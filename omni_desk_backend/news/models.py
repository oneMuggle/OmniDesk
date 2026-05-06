from django.conf import settings
from django.db import models


class NewsType(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

class NewsArticle(models.Model):
    title = models.CharField(max_length=200)
    link = models.URLField()
    publication_date = models.DateField()
    personnel = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='news_articles')
    news_type = models.ForeignKey(NewsType, on_delete=models.CASCADE, related_name='articles')

    def __str__(self):
        return self.title
