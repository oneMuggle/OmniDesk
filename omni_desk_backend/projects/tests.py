from django.test import TestCase
from rest_framework.test import APIClient, APITestCase
from django.urls import reverse
from rest_framework import status
from users.models import CustomUser
from .models import Project

class ProjectViewSetTests(APITestCase):
    def setUp(self):
        self.admin_user = CustomUser.objects.create_user(
            username='admin',
            password='password123',
            role='admin',
            is_staff=True
        )
        self.manager_user = CustomUser.objects.create_user(
            username='manager',
            password='password123',
            role='manager'
        )
        self.regular_user = CustomUser.objects.create_user(
            username='user',
            password='password123',
            role='user'
        )

        self.project1 = Project.objects.create(name='Project 1', manager=self.manager_user)
        self.project2 = Project.objects.create(name='Project 2')

        self.client = APIClient()

    def test_list_projects_as_admin(self):
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('project-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    def test_list_projects_as_manager(self):
        self.client.force_authenticate(user=self.manager_user)
        url = reverse('project-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_list_projects_as_regular_user(self):
        self.client.force_authenticate(user=self.regular_user)
        url = reverse('project-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)

    def test_create_project_as_manager(self):
        self.client.force_authenticate(user=self.manager_user)
        url = reverse('project-list')
        data = {
            'name': 'New Project',
            'description': 'A new project.',
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Project.objects.count(), 3)
        new_project = Project.objects.get(name='New Project')
        self.assertEqual(new_project.manager, self.manager_user)

    def test_create_project_with_specified_manager(self):
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('project-list')
        data = {
            'name': 'Another Project',
            'description': 'Another new project.',
            'manager': self.manager_user.id
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Project.objects.count(), 3)
        new_project = Project.objects.get(name='Another Project')
        self.assertEqual(new_project.manager, self.manager_user)