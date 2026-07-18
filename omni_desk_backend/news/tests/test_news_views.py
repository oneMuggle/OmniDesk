"""
Tests for news module (NewsType, NewsArticle CRUD + Stats).
"""

from datetime import date
import pytest
from rest_framework import status


@pytest.mark.django_db
class TestNewsTypeViewSet:
    def test_list_news_types(self, api_client, regular_user_obj):
        api_client.force_authenticate(user=regular_user_obj)
        response = api_client.get("/api/news-types/")
        assert response.status_code == status.HTTP_200_OK

    def test_create_news_type(self, admin_client):
        response = admin_client.post(
            "/api/news-types/",
            {
                "name": "Test Type",
            },
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["name"] == "Test Type"

    def test_create_news_type_unauthorized(self, api_client, regular_user_obj):
        api_client.force_authenticate(user=regular_user_obj)
        response = api_client.post(
            "/api/news-types/",
            {
                "name": "Unauthorized Type",
            },
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestNewsArticleViewSet:
    def test_list_articles(self, api_client, regular_user_obj):
        api_client.force_authenticate(user=regular_user_obj)
        response = api_client.get("/api/news-articles/")
        assert response.status_code == status.HTTP_200_OK

    def test_create_article(self, admin_client, regular_user_obj):
        from news.models import NewsType

        news_type = NewsType.objects.create(name="Article Type")
        response = admin_client.post(
            "/api/news-articles/",
            {
                "title": "Test Article",
                "link": "https://example.com/article",
                "publication_date": "2026-05-31",
                "personnel_id": regular_user_obj.pk,
                "news_type_id": news_type.pk,
            },
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["title"] == "Test Article"

    def test_list_articles_filter_by_personnel(self, api_client, regular_user_obj):
        from news.models import NewsArticle, NewsType

        api_client.force_authenticate(user=regular_user_obj)
        news_type = NewsType.objects.create(name="Filter Type")
        NewsArticle.objects.create(
            title="Article A",
            link="https://example.com/a",
            publication_date=date.today(),
            personnel=regular_user_obj,
            news_type=news_type,
        )
        response = api_client.get(f"/api/news-articles/?personnel_id={regular_user_obj.pk}")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1

    def test_list_articles_filter_by_type(self, api_client, regular_user_obj):
        from news.models import NewsArticle, NewsType

        api_client.force_authenticate(user=regular_user_obj)
        news_type = NewsType.objects.create(name="Type Filter")
        NewsArticle.objects.create(
            title="Type Article",
            link="https://example.com/type",
            publication_date=date.today(),
            personnel=regular_user_obj,
            news_type=news_type,
        )
        response = api_client.get(f"/api/news-articles/?type_id={news_type.pk}")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1

    def test_delete_article(self, admin_client, regular_user_obj):
        from news.models import NewsArticle, NewsType

        news_type = NewsType.objects.create(name="Delete Type")
        article = NewsArticle.objects.create(
            title="To Delete",
            link="https://example.com/delete",
            publication_date=date.today(),
            personnel=regular_user_obj,
            news_type=news_type,
        )
        response = admin_client.delete(f"/api/news-articles/{article.pk}/")
        assert response.status_code == status.HTTP_204_NO_CONTENT


@pytest.mark.django_db
class TestNewsStatsView:
    def test_stats_returns_data(self, regular_client, regular_user_obj):
        from news.models import NewsArticle, NewsType

        news_type = NewsType.objects.create(name="Stats Type")
        NewsArticle.objects.create(
            title="Stats Article",
            link="https://example.com/stats",
            publication_date=date.today(),
            personnel=regular_user_obj,
            news_type=news_type,
        )
        response = regular_client.get("/api/news-stats/")
        assert response.status_code == status.HTTP_200_OK
        assert "total_articles" in response.data
        assert response.data["total_articles"] >= 1
