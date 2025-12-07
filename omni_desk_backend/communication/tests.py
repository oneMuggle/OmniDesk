from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from django.urls import reverse
from .models import Post, Comment
from users.models import CustomUser

class PostModelTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        # Set up non-modified objects used by all test methods
        User = get_user_model()
        cls.user = User.objects.create_user(username='testuser', password='password')
        Post.objects.create(title='Test Post', content='This is a test post.', author=cls.user)

    def test_title_content(self):
        post = Post.objects.get(id=1)
        expected_title = f'{post.title}'
        self.assertEqual(expected_title, 'Test Post')

    def test_string_representation(self):
        post = Post.objects.get(id=1)
        self.assertEqual(str(post), post.title)


class CommentModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.user = User.objects.create_user(username='testuser_comment', password='password')
        cls.post = Post.objects.create(title='Post for Comment', content='Content', author=cls.user)
        cls.comment = Comment.objects.create(post=cls.post, author=cls.user, content='A test comment')

    def test_comment_content(self):
        self.assertEqual(self.comment.content, 'A test comment')

    def test_comment_string_representation(self):
        expected_str = f'Comment by {self.user} on {self.post}'
        self.assertEqual(str(self.comment), expected_str)


class CommunicationViewSetTests(APITestCase):
    def setUp(self):
        # Clean up data to ensure test isolation
        Post.objects.all().delete()
        Comment.objects.all().delete()
        CustomUser.objects.all().delete()

        self.user = CustomUser.objects.create_user(username='api_user', password='password', real_name='Api User')
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        self.post = Post.objects.create(title='API Test Post', content='Content', author=self.user)
        self.archived_post = Post.objects.create(title='Archived Post', content='Content', author=self.user, is_archived=True)

    def test_list_posts(self):
        """Ensure only non-archived posts are listed."""
        url = reverse('post-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['title'], 'API Test Post')

    def test_create_post(self):
        url = reverse('post-list')
        data = {'title': 'New API Post', 'content': 'Some content'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Post.objects.count(), 3) # Including setUp posts
        self.assertEqual(response.data['author'], 'Api User')

    def test_create_comment(self):
        url = reverse('comment-list')
        data = {'post': self.post.id, 'content': 'A new comment'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(self.post.comments.count(), 1)
        self.assertEqual(response.data['author'], 'Api User')

    def test_list_comments_for_post(self):
        """Ensure comments can be filtered by post_id."""
        Comment.objects.create(post=self.post, author=self.user, content='Comment 1')
        other_post = Post.objects.create(title='Other Post', content='Content', author=self.user)
        Comment.objects.create(post=other_post, author=self.user, content='Comment 2')

        url = reverse('comment-list')
        response = self.client.get(url, {'post_id': self.post.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['content'], 'Comment 1')

from .serializers import PostSerializer, CommentSerializer

class CommunicationSerializerTests(TestCase):
    def setUp(self):
        self.user_with_real_name = CustomUser.objects.create_user(username='user_real', password='password', real_name='Real Name')
        self.user_without_real_name = CustomUser.objects.create_user(username='user_no_real', password='password')
        self.post = Post.objects.create(title='Serializer Test Post', content='Content', author=self.user_with_real_name)

    def test_post_serializer_author_with_real_name(self):
        """Test author serialization when user has a real_name."""
        serializer = PostSerializer(instance=self.post)
        self.assertEqual(serializer.data['author'], 'Real Name')

    def test_post_serializer_author_without_real_name(self):
        """Test author serialization when user does not have a real_name."""
        self.post.author = self.user_without_real_name
        self.post.save()
        serializer = PostSerializer(instance=self.post)
        self.assertEqual(serializer.data['author'], 'user_no_real')

    def test_comment_serializer_author(self):
        """Test author serialization in CommentSerializer."""
        comment = Comment.objects.create(post=self.post, author=self.user_with_real_name, content='A comment')
        serializer = CommentSerializer(instance=comment)
        self.assertEqual(serializer.data['author'], 'Real Name')

    def test_serializer_author_is_anonymous(self):
        """Test author serialization when author is None."""
        self.post.author = None
        self.post.save()
        serializer = PostSerializer(instance=self.post)
        self.assertEqual(serializer.data['author'], 'Anonymous')
