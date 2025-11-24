from django.test import TestCase
from rest_framework.test import APIClient, APITestCase
from django.urls import reverse
from rest_framework import status
from users.models import CustomUser
from projects.models import Project
from .models import ComplianceIssue

class ComplianceIssueViewSetTests(APITestCase):
    def setUp(self):
        # 清理环境，确保每次测试都在干净的状态下运行
        ComplianceIssue.objects.all().delete()
        CustomUser.objects.all().delete()
        Project.objects.all().delete()

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
        self.assertEqual(len(response.data['results']), 1)

    def test_list_issues_as_manager(self):
        self.client.force_authenticate(user=self.manager_user)
        url = reverse('complianceissue-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)

    def test_list_issues_as_regular_user(self):
        self.client.force_authenticate(user=self.regular_user)
        url = reverse('complianceissue-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 0)

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
    def test_update_issue_as_manager(self):
        self.client.force_authenticate(user=self.manager_user)
        url = reverse('complianceissue-detail', args=[self.issue1.id])
        data = {'status': '已解决'}
        response = self.client.patch(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.issue1.refresh_from_db()
        self.assertEqual(self.issue1.status, '已解决')

    def test_delete_issue_as_manager(self):
        self.client.force_authenticate(user=self.manager_user)
        url = reverse('complianceissue-detail', args=[self.issue1.id])
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(ComplianceIssue.objects.count(), 0)

    def test_regular_user_cannot_update_issue(self):
        self.client.force_authenticate(user=self.regular_user)
        url = reverse('complianceissue-detail', args=[self.issue1.id])
        data = {'status': '已忽略'}
        response = self.client.patch(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_admin_can_update_any_issue(self):
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('complianceissue-detail', args=[self.issue1.id])
        data = {'severity': '高'}
        response = self.client.patch(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.issue1.refresh_from_db()
        self.assertEqual(self.issue1.severity, '高')

    def test_unread_count_for_admin(self):
        ComplianceIssue.objects.create(
            project=self.project2,
            issue_type='不规范',
            description='Another issue.',
            status='处理中'
        )
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('complianceissue-unread-count')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['unread_count'], 2)