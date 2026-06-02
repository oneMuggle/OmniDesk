import pytest
from django.urls import reverse
from rest_framework import status

from ebooks.models import Ebook


@pytest.mark.django_db
class TestEbookModel:
    def test_ebook_creation(self):
        ebook = Ebook.objects.create(
            title='Test Book',
            author='Test Author',
        )
        assert ebook.pk is not None
        assert str(ebook) == 'Test Book'

    def test_ebook_optional_fields(self):
        ebook = Ebook.objects.create(title='Minimal Book')
        assert ebook.author == ''
        assert not ebook.file  # FieldFile is falsy when no file is attached


@pytest.mark.django_db
class TestEbookViewSet:
    def test_list_ebooks(self, regular_client, regular_user_obj):
        Ebook.objects.create(title='Book 1', author='Author 1')
        Ebook.objects.create(title='Book 2', author='Author 2')

        response = regular_client.get(reverse('ebook-list'))
        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 2

    def test_create_ebook(self, regular_client):
        data = {'title': 'New Book', 'author': 'New Author'}
        response = regular_client.post(reverse('ebook-list'), data, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        assert Ebook.objects.filter(title='New Book').exists()

    def test_retrieve_ebook(self, regular_client):
        ebook = Ebook.objects.create(title='Retrieve Me', author='Author')
        response = regular_client.get(reverse('ebook-detail', kwargs={'pk': ebook.pk}))
        assert response.status_code == status.HTTP_200_OK
        assert response.data['title'] == 'Retrieve Me'

    def test_update_ebook(self, regular_client):
        ebook = Ebook.objects.create(title='Old Title', author='Author')
        response = regular_client.patch(
            reverse('ebook-detail', kwargs={'pk': ebook.pk}),
            {'title': 'New Title'},
            format='json',
        )
        assert response.status_code == status.HTTP_200_OK
        ebook.refresh_from_db()
        assert ebook.title == 'New Title'

    def test_delete_ebook(self, regular_client):
        ebook = Ebook.objects.create(title='Delete Me', author='Author')
        response = regular_client.delete(reverse('ebook-detail', kwargs={'pk': ebook.pk}))
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert Ebook.objects.filter(pk=ebook.pk).count() == 0

    def test_unauthenticated_access(self, api_client):
        response = api_client.get(reverse('ebook-list'))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
