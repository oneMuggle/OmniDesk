from django.test import TestCase
from rest_framework.test import APIClient, APITestCase
from django.urls import reverse
from rest_framework import status
from users.models import CustomUser
from .models import Project
from django.contrib.auth.models import Group

class ProjectViewSetTests(APITestCase):
    def setUp(self):
        admin_group, _ = Group.objects.get_or_create(name='Admin')
        manager_group, _ = Group.objects.get_or_create(name='Manager')
        user_group, _ = Group.objects.get_or_create(name='User')

        self.admin_user = CustomUser.objects.create_user(
            username='admin',
            password='password123',
            is_staff=True
        )
        self.admin_user.groups.add(admin_group)

        self.manager_user = CustomUser.objects.create_user(
            username='manager',
            password='password123'
        )
        self.manager_user.groups.add(manager_group)

        self.regular_user = CustomUser.objects.create_user(
            username='user',
            password='password123'
        )
        self.regular_user.groups.add(user_group)

        self.project1 = Project.objects.create(name='Project 1', manager=self.manager_user)
        self.project2 = Project.objects.create(name='Project 2')

        self.client = APIClient()

    def test_list_projects_as_admin(self):
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('project-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)

    def test_list_projects_as_manager(self):
        self.client.force_authenticate(user=self.manager_user)
        url = reverse('project-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)

    def test_list_projects_as_regular_user(self):
        self.client.force_authenticate(user=self.regular_user)
        url = reverse('project-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 0)

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
    def test_update_project_as_manager(self):
        self.client.force_authenticate(user=self.manager_user)
        url = reverse('project-detail', args=[self.project1.id])
        data = {'name': 'Project 1 Updated'}
        response = self.client.patch(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.project1.refresh_from_db()
        self.assertEqual(self.project1.name, 'Project 1 Updated')

    def test_delete_project_as_manager(self):
        self.client.force_authenticate(user=self.manager_user)
        url = reverse('project-detail', args=[self.project1.id])
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Project.objects.count(), 1)

    def test_regular_user_cannot_update_project(self):
        self.client.force_authenticate(user=self.regular_user)
        url = reverse('project-detail', args=[self.project1.id])
        data = {'name': 'Unauthorized Update'}
        response = self.client.patch(url, data, format='json')
        # This should fail because the queryset in get_queryset will not find the project
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_regular_user_cannot_delete_project(self):
        self.client.force_authenticate(user=self.regular_user)
        url = reverse('project-detail', args=[self.project1.id])
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_unauthenticated_user_cannot_access_projects(self):
        self.client.force_authenticate(user=None)
        url = reverse('project-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)