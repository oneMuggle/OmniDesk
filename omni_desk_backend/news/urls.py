from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import NewsArticleViewSet, NewsStatsView, NewsTypeViewSet

router = DefaultRouter()
router.register(r'news-types', NewsTypeViewSet)
router.register(r'news-articles', NewsArticleViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('news-stats/', NewsStatsView.as_view(), name='news-stats'),
]
