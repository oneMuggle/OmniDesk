from django.test import TestCase
from rest_framework.test import APIClient, APITestCase
from django.urls import reverse
from rest_framework import status
from users.models import CustomUser
from projects.models import Project
from .models import ComplianceIssue

class ComplianceIssueViewSetTests(APITestCase):
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
        ComplianceIssue.objects.all().delete()
        self.regular_user = CustomUser.objects.create_user(
            username='user',
            password='password123',
            role='user'
        )

        self.project1 = Project.objects.create(name='Project 1', manager=self.manager_user)
        self.project2 = Project.objects.create(name='Project 2')

        self.issue1 = ComplianceIssue.objects.create(
            project=self.project1,
            issue_type='不规范',
            description='This is a test issue.',
            status='待处理',
            severity='中'
        )

        self.client = APIClient()

    def test_list_issues_as_admin(self):
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('complianceissue-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_list_issues_as_manager(self):
        self.client.force_authenticate(user=self.manager_user)
        url = reverse('complianceissue-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_list_issues_as_regular_user(self):
        self.client.force_authenticate(user=self.regular_user)
        url = reverse('complianceissue-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)

    def test_create_issue_as_manager(self):
        self.client.force_authenticate(user=self.manager_user)
        url = reverse('complianceissue-list')
        data = {
            'project': self.project1.id,
            'issue_type': '内容缺失',
            'description': 'Missing content.',
            'status': '待处理',
            'severity': '高'
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(ComplianceIssue.objects.count(), 2)

    def test_create_issue_for_unmanaged_project(self):
        self.client.force_authenticate(user=self.manager_user)
        url = reverse('complianceissue-list')
        data = {
            'project': self.project2.id,
            'issue_type': '内容缺失',
            'description': 'Missing content.',
            'status': '待处理',
            'severity': '高'
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unread_count(self):
        self.client.force_authenticate(user=self.manager_user)
        url = reverse('complianceissue-unread-count')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['unread_count'], 1)