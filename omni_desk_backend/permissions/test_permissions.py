from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from users.models import CustomUser
from .models import PageRoute, GroupPagePermission

class TestPermissionModels(TestCase):
    def test_page_route_creation(self):
        route = PageRoute.objects.create(name='Home', path='/home', component='HomePage')
        self.assertEqual(str(route), 'Home')

    def test_group_page_permission_creation(self):
        group = Group.objects.create(name='Test Group')
        route = PageRoute.objects.create(name='Dashboard', path='/dashboard', component='DashboardPage')
        permission = GroupPagePermission.objects.create(group=group, page=route)
        self.assertEqual(str(permission), 'Test Group - Dashboard')

class TestPermissionViews(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin_user = CustomUser.objects.create_user(username='admin', password='password', role='admin', is_staff=True)
        self.regular_user = CustomUser.objects.create_user(username='user', password='password', role='user')
        
        self.group = Group.objects.create(name='Editors')
        self.route = PageRoute.objects.create(name='News', path='/news', component='NewsPage')
        GroupPagePermission.objects.create(group=self.group, page=self.route)
        self.regular_user.groups.add(self.group)

        # Create some permissions
        content_type = ContentType.objects.get_for_model(CustomUser)
        self.permission = Permission.objects.create(codename='can_edit_user', name='Can edit user', content_type=content_type)
        self.group.permissions.add(self.permission)

    def test_group_viewset_list_as_admin(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(reverse('permissions:group-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_group_viewset_create_as_admin(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post(reverse('permissions:group-list'), {'name': 'New Group'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Group.objects.filter(name='New Group').exists())

    def test_page_route_viewset_list_as_admin(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(reverse('permissions:pageroute-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_group_permission_view_get_as_admin(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(reverse('permissions:group-permissions', args=[self.group.id]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(self.permission.id, response.data)

    def test_group_permission_view_put_as_admin(self):
        self.client.force_authenticate(user=self.admin_user)
        new_permission = Permission.objects.create(codename='can_delete_user', name='Can delete user', content_type=ContentType.objects.get_for_model(CustomUser))
        response = self.client.put(reverse('permissions:group-permissions', args=[self.group.id]), {'permissions': [new_permission.id]}, format='json')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.group.refresh_from_db()
        self.assertIn(new_permission, self.group.permissions.all())
        self.assertNotIn(self.permission, self.group.permissions.all())

    def test_user_permission_view_get_as_regular_user(self):
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.get(reverse('permissions:user-permissions'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], 'News')

    def test_grouped_permissions_view_get_as_admin(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(reverse('permissions:grouped-permissions'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('users | user', response.data)
