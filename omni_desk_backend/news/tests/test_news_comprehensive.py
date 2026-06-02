"""news 模块补充测试。"""

import pytest
from datetime import date

from news.models import NewsArticle, NewsType
from users.models import CustomUser


@pytest.mark.django_db
class TestNewsTypeViewSet:
    def test_news_type_crud(self, admin_client):
        """新闻类型 CRUD"""
        resp = admin_client.post('/api/news-types/', {'name': '技术新闻'}, format='json')
        assert resp.status_code == 201, resp.data
        type_id = resp.data['id']

        resp = admin_client.delete(f'/api/news-types/{type_id}/')
        assert resp.status_code == 204


@pytest.mark.django_db
class TestNewsArticleViewSet:
    def test_article_crud(self, admin_client, admin_user_obj):
        """新闻文章 CRUD"""
        news_type = NewsType.objects.create(name='公司新闻')
        resp = admin_client.post('/api/news-articles/', {
            'title': '测试新闻',
            'link': 'https://example.com/news/1',
            'publication_date': '2026-06-15',
            'news_type_id': news_type.id,
            'personnel_id': admin_user_obj.id,
        }, format='json')
        assert resp.status_code == 201, resp.data
        article_id = resp.data['id']

        resp = admin_client.get(f'/api/news-articles/{article_id}/')
        assert resp.status_code == 200

        resp = admin_client.delete(f'/api/news-articles/{article_id}/')
        assert resp.status_code == 204

    def test_filter_by_news_type(self, admin_client, admin_user_obj):
        """按新闻类型过滤"""
        t1 = NewsType.objects.create(name='类型A')
        t2 = NewsType.objects.create(name='类型B')
        NewsArticle.objects.create(title='新闻A', link='https://a.com', publication_date=date.today(), news_type=t1, personnel=admin_user_obj)
        NewsArticle.objects.create(title='新闻B', link='https://b.com', publication_date=date.today(), news_type=t2, personnel=admin_user_obj)
        resp = admin_client.get('/api/news-articles/', {'news_type': t1.id})
        assert resp.status_code == 200
        results = resp.data.get('results', resp.data)
        assert len(results) >= 1
