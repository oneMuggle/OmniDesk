"""
Tests for communication module (Post, Comment CRUD).
"""
import pytest
from rest_framework import status


@pytest.mark.django_db
class TestPostViewSet:
    def test_list_posts_unauthenticated(self, api_client):
        response = api_client.get('/api/communication/posts/')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_post(self, api_client, regular_user_obj):
        api_client.force_authenticate(user=regular_user_obj)
        response = api_client.post('/api/communication/posts/', {
            'title': 'Test Post',
            'content': 'This is test post content.',
        }, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['title'] == 'Test Post'

    def test_list_posts(self, api_client, regular_user_obj):
        from communication.models import Post
        api_client.force_authenticate(user=regular_user_obj)
        Post.objects.create(title='Post 1', content='Content 1', author=regular_user_obj)
        Post.objects.create(title='Post 2', content='Content 2', author=regular_user_obj)
        response = api_client.get('/api/communication/posts/')
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 2

    def test_retrieve_post(self, api_client, regular_user_obj):
        from communication.models import Post
        api_client.force_authenticate(user=regular_user_obj)
        post = Post.objects.create(title='Retrieve Test', content='Content', author=regular_user_obj)
        response = api_client.get(f'/api/communication/posts/{post.pk}/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['title'] == 'Retrieve Test'

    def test_update_post(self, api_client, regular_user_obj):
        from communication.models import Post
        api_client.force_authenticate(user=regular_user_obj)
        post = Post.objects.create(title='Old Title', content='Content', author=regular_user_obj)
        response = api_client.patch(f'/api/communication/posts/{post.pk}/', {
            'title': 'New Title',
        }, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['title'] == 'New Title'

    def test_delete_post(self, api_client, regular_user_obj):
        from communication.models import Post
        api_client.force_authenticate(user=regular_user_obj)
        post = Post.objects.create(title='To Delete', content='Content', author=regular_user_obj)
        response = api_client.delete(f'/api/communication/posts/{post.pk}/')
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_archived_posts_not_listed(self, api_client, regular_user_obj):
        from communication.models import Post
        api_client.force_authenticate(user=regular_user_obj)
        Post.objects.create(title='Active Post', content='Content', author=regular_user_obj, is_archived=False)
        Post.objects.create(title='Archived Post', content='Content', author=regular_user_obj, is_archived=True)
        response = api_client.get('/api/communication/posts/')
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 1
        assert response.data['results'][0]['title'] == 'Active Post'


@pytest.mark.django_db
class TestCommentViewSet:
    def test_create_comment(self, api_client, regular_user_obj):
        from communication.models import Post
        api_client.force_authenticate(user=regular_user_obj)
        post = Post.objects.create(title='Post with Comments', content='Content', author=regular_user_obj)
        response = api_client.post(f'/api/communication/posts/{post.pk}/comments/', {
            'content': 'Test comment',
        }, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['content'] == 'Test comment'

    def test_list_comments(self, api_client, regular_user_obj):
        from communication.models import Comment, Post
        api_client.force_authenticate(user=regular_user_obj)
        post = Post.objects.create(title='Post for Comments', content='Content', author=regular_user_obj)
        Comment.objects.create(post=post, author=regular_user_obj, content='Comment 1')
        Comment.objects.create(post=post, author=regular_user_obj, content='Comment 2')
        response = api_client.get(f'/api/communication/posts/{post.pk}/comments/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 2
