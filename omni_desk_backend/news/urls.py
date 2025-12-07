from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import NewsTypeViewSet, NewsArticleViewSet, NewsStatsView

router = DefaultRouter()
router.register(r'news-types', NewsTypeViewSet)
router.register(r'news-articles', NewsArticleViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('news-stats/', NewsStatsView.as_view(), name='news-stats'),
]