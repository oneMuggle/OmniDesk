"""Tests for memos app: MemoViewSet."""
import pytest
from rest_framework import status
from rest_framework.test import APIClient

from users.models import CustomUser

from ..models import Memo

pytestmark = pytest.mark.django_db


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user_a(db):
    return CustomUser.objects.create_user(username='memo_user_a', password='pass123')


@pytest.fixture
def user_b(db):
    return CustomUser.objects.create_user(username='memo_user_b', password='pass123')


@pytest.fixture
def client_a(api_client, user_a):
    api_client.force_authenticate(user=user_a)
    return api_client


@pytest.fixture
def client_b(api_client, user_b):
    api_client.force_authenticate(user=user_b)
    return api_client


class TestMemoViewSet:
    def test_user_can_create_memo(self, client_a):
        response = client_a.post('/api/memos/', {'title': 'Test Memo', 'content': 'Some content'})
        assert response.status_code == status.HTTP_201_CREATED
        assert Memo.objects.count() == 1
        assert Memo.objects.first().user.username == 'memo_user_a'

    def test_user_sees_only_own_memos(self, client_a, user_a, user_b):
        Memo.objects.create(user=user_a, title='My Memo')
        Memo.objects.create(user=user_b, title='Other Memo')
        response = client_a.get('/api/memos/')
        assert response.status_code == status.HTTP_200_OK
        count = response.data.get('count', len(response.data))
        results = response.data.get('results', response.data)
        assert count == 1
        assert results[0]['title'] == 'My Memo'

    def test_user_can_update_own_memo(self, client_a, user_a):
        memo = Memo.objects.create(user=user_a, title='Old Title')
        response = client_a.patch(f'/api/memos/{memo.id}/', {'title': 'New Title'})
        assert response.status_code == status.HTTP_200_OK
        memo.refresh_from_db()
        assert memo.title == 'New Title'

    def test_user_cannot_update_other_memo(self, client_a, user_b):
        memo = Memo.objects.create(user=user_b, title='Other Memo')
        response = client_a.patch(f'/api/memos/{memo.id}/', {'title': 'Hacked'})
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_user_can_delete_own_memo(self, client_a, user_a):
        memo = Memo.objects.create(user=user_a, title='ToDelete')
        response = client_a.delete(f'/api/memos/{memo.id}/')
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Memo.objects.filter(id=memo.id).exists()

    def test_unauthenticated_cannot_access(self, api_client):
        response = api_client.get('/api/memos/')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_memo_creation_without_content(self, client_a):
        response = client_a.post('/api/memos/', {'title': 'No Content Memo'})
        assert response.status_code == status.HTTP_201_CREATED
