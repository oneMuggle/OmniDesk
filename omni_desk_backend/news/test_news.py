from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from users.models import CustomUser
from .models import NewsType, NewsArticle
import datetime

class TestNewsModels(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(username='testuser', password='password')
        self.news_type = NewsType.objects.create(name='Breaking News')

    def test_news_type_creation(self):
        self.assertEqual(str(self.news_type), 'Breaking News')

    def test_news_article_creation(self):
        article = NewsArticle.objects.create(
            title='Test Article',
            link='http://example.com',
            publication_date=datetime.date.today(),
            personnel=self.user,
            news_type=self.news_type
        )
        self.assertEqual(str(article), 'Test Article')

class TestNewsViews(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = CustomUser.objects.create_user(username='testuser', password='password', role='admin')
        self.client.force_authenticate(user=self.user)
        
        self.news_type = NewsType.objects.create(name='Technology')
        self.article = NewsArticle.objects.create(
            title='AI Breakthrough',
            link='http://example.com/ai',
            publication_date=datetime.date(2023, 1, 15),
            personnel=self.user,
            news_type=self.news_type
        )

    def test_news_type_viewset(self):
        # List
        response = self.client.get(reverse('news:newstype-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

        # Create
        response = self.client.post(reverse('news:newstype-list'), {'name': 'Sports'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(NewsType.objects.filter(name='Sports').exists())

    def test_news_article_viewset(self):
        # List
        response = self.client.get(reverse('news:newsarticle-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

        # Create
        data = {
            'title': 'New Gadget',
            'link': 'http://example.com/gadget',
            'publication_date': '2023-02-20',
            'personnel_id': self.user.id,
            'news_type_id': self.news_type.id
        }
        response = self.client.post(reverse('news:newsarticle-list'), data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(NewsArticle.objects.count(), 2)

        # Filter by personnel
        response = self.client.get(reverse('news:newsarticle-list'), {'personnel_id': self.user.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

        # Filter by month
        response = self.client.get(reverse('news:newsarticle-list'), {'month': '2023-01'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_news_stats_view(self):
        # Create more articles for stats
        user2 = CustomUser.objects.create_user(username='testuser2', password='password')
        NewsArticle.objects.create(
            title='Another Article',
            link='http://example.com/another',
            publication_date=datetime.date(2023, 1, 20),
            personnel=user2,
            news_type=self.news_type
        )
        NewsArticle.objects.create(
            title='February News',
            link='http://example.com/feb',
            publication_date=datetime.date(2023, 2, 5),
            personnel=self.user,
            news_type=self.news_type
        )

        response = self.client.get(reverse('news:news-stats'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        stats = response.data
        self.assertEqual(stats['total_articles'], 3)
        self.assertEqual(stats['by_person']['testuser']['total'], 2)
        self.assertEqual(stats['by_person']['testuser']['monthly']['2023-01'], 1)
        self.assertEqual(stats['by_person']['testuser']['monthly']['2023-02'], 1)
        self.assertEqual(stats['by_person']['testuser2']['total'], 1)
