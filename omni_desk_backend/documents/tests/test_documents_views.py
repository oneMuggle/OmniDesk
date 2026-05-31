"""
Tests for documents module (DocumentTemplate, GeneratedDocument, Book, Chapter).
"""
import pytest
from rest_framework import status


@pytest.mark.django_db
class TestDocumentTemplateViewSet:
    def test_list_templates(self, api_client, regular_user_obj):
        api_client.force_authenticate(user=regular_user_obj)
        response = api_client.get('/api/documents/templates/')
        assert response.status_code == status.HTTP_200_OK

    def test_create_template(self, api_client, regular_user_obj):
        api_client.force_authenticate(user=regular_user_obj)
        response = api_client.post('/api/documents/templates/', {
            'name': 'Test Template',
            'template_type': 'tech_design',
            'content': 'Template content here',
            'owner': regular_user_obj.pk,
        }, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['name'] == 'Test Template'

    def test_retrieve_template(self, api_client, regular_user_obj):
        from documents.models import DocumentTemplate
        api_client.force_authenticate(user=regular_user_obj)
        template = DocumentTemplate.objects.create(
            name='Retrieve Template',
            template_type='test_case',
            content='Content',
            owner=regular_user_obj,
        )
        response = api_client.get(f'/api/documents/templates/{template.pk}/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['name'] == 'Retrieve Template'

    def test_update_template(self, api_client, regular_user_obj):
        from documents.models import DocumentTemplate
        api_client.force_authenticate(user=regular_user_obj)
        template = DocumentTemplate.objects.create(
            name='Old Template',
            template_type='meeting_minutes',
            content='Content',
            owner=regular_user_obj,
        )
        response = api_client.patch(f'/api/documents/templates/{template.pk}/', {
            'name': 'Updated Template',
        }, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['name'] == 'Updated Template'

    def test_delete_template(self, api_client, regular_user_obj):
        from documents.models import DocumentTemplate
        api_client.force_authenticate(user=regular_user_obj)
        template = DocumentTemplate.objects.create(
            name='To Delete',
            template_type='progress_report',
            content='Content',
            owner=regular_user_obj,
        )
        response = api_client.delete(f'/api/documents/templates/{template.pk}/')
        assert response.status_code == status.HTTP_204_NO_CONTENT


@pytest.mark.django_db
class TestGeneratedDocumentViewSet:
    def test_create_generated_document(self, api_client, regular_user_obj):
        from documents.models import DocumentTemplate
        api_client.force_authenticate(user=regular_user_obj)
        template = DocumentTemplate.objects.create(
            name='Gen Template',
            template_type='tech_design',
            content='Content',
            owner=regular_user_obj,
        )
        response = api_client.post('/api/documents/generated/', {
            'template': template.pk,
            'content': 'Generated content',
            'variables_used': {'var1': 'value1'},
        }, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['template'] == template.pk

    def test_list_generated_documents(self, api_client, regular_user_obj):
        from documents.models import DocumentTemplate, GeneratedDocument
        api_client.force_authenticate(user=regular_user_obj)
        template = DocumentTemplate.objects.create(
            name='List Gen Template',
            template_type='tech_design',
            content='Content',
            owner=regular_user_obj,
        )
        GeneratedDocument.objects.create(
            template=template,
            content='Doc 1',
            generated_by=regular_user_obj,
        )
        GeneratedDocument.objects.create(
            template=template,
            content='Doc 2',
            generated_by=regular_user_obj,
        )
        response = api_client.get('/api/documents/generated/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 2


@pytest.mark.django_db
class TestBookViewSet:
    def test_list_books(self, api_client, regular_user_obj):
        api_client.force_authenticate(user=regular_user_obj)
        response = api_client.get('/api/documents/books/')
        assert response.status_code == status.HTTP_200_OK

    def test_create_book(self, admin_client):
        response = admin_client.post('/api/documents/books/', {
            'title': 'Test Book',
            'author': 'Test Author',
            'description': 'Test book description',
        }, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['title'] == 'Test Book'

    def test_retrieve_book(self, admin_client):
        from documents.models import Book
        book = Book.objects.create(title='Retrieve Book', author='Author')
        response = admin_client.get(f'/api/documents/books/{book.pk}/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['title'] == 'Retrieve Book'

    def test_update_book(self, admin_client):
        from documents.models import Book
        book = Book.objects.create(title='Old Book', author='Author')
        response = admin_client.patch(f'/api/documents/books/{book.pk}/', {
            'title': 'Updated Book',
        }, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['title'] == 'Updated Book'

    def test_delete_book(self, admin_client):
        from documents.models import Book
        book = Book.objects.create(title='To Delete Book', author='Author')
        response = admin_client.delete(f'/api/documents/books/{book.pk}/')
        assert response.status_code == status.HTTP_204_NO_CONTENT


@pytest.mark.django_db
class TestChapterViewSet:
    def test_create_chapter(self, admin_client):
        from documents.models import Book
        book = Book.objects.create(title='Chapter Book', author='Author')
        response = admin_client.post('/api/documents/chapters/', {
            'book': book.pk,
            'title': 'Test Chapter',
            'content_md': 'Chapter content in markdown',
            'order': 1,
        }, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['title'] == 'Test Chapter'

    def test_list_chapters(self, admin_client):
        from documents.models import Book, Chapter
        book = Book.objects.create(title='List Chapter Book', author='Author')
        Chapter.objects.create(book=book, title='Chapter 1', content_md='Content', order=1)
        Chapter.objects.create(book=book, title='Chapter 2', content_md='Content', order=2)
        response = admin_client.get('/api/documents/chapters/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 2
