"""Tests for sensor_management app: SensorViewSet, SensorMovementViewSet, SensorCalibrationViewSet, CalibrationReminderViewSet."""
import pytest
from django.contrib.auth.models import Group
from rest_framework import status
from rest_framework.test import APIClient

from users.models import CustomUser

from ..models import Sensor, SensorCalibration, SensorCategory, SensorMovement, StorageLocation

pytestmark = pytest.mark.django_db


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def admin_user(db):
    admin_group, _ = Group.objects.get_or_create(name='Admin')
    user = CustomUser.objects.create_user(
        username='sensor_admin', password='admin123', is_staff=True, is_superuser=True,
    )
    user.groups.add(admin_group)
    return user


@pytest.fixture
def manager_user(db):
    manager_group, _ = Group.objects.get_or_create(name='Manager')
    user = CustomUser.objects.create_user(
        username='sensor_manager', password='manager123', is_staff=True,
    )
    user.groups.add(manager_group)
    return user


@pytest.fixture
def regular_user(db):
    user_group, _ = Group.objects.get_or_create(name='User')
    user = CustomUser.objects.create_user(username='sensor_user', password='user123')
    user.groups.add(user_group)
    return user


@pytest.fixture
def admin_client(api_client, admin_user):
    api_client.force_authenticate(user=admin_user)
    return api_client


@pytest.fixture
def manager_client(api_client, manager_user):
    api_client.force_authenticate(user=manager_user)
    return api_client


@pytest.fixture
def regular_client(api_client, regular_user):
    api_client.force_authenticate(user=regular_user)
    return api_client


@pytest.fixture
def sensor_category(db):
    return SensorCategory.objects.create(name='温度传感器')


@pytest.fixture
def storage_location(db):
    return StorageLocation.objects.create(name='Warehouse A', description='Test location')


@pytest.fixture
def sensor(db, sensor_category, storage_location):
    return Sensor.objects.create(
        name='TestSensor',
        sensor_number='SN001',
        sensor_category=sensor_category,
        location=storage_location,
        current_quantity=10,
    )


class TestSensorViewSet:
    def test_admin_can_list_sensors(self, admin_client, sensor):
        response = admin_client.get('/api/sensor-management/sensors/')
        assert response.status_code == status.HTTP_200_OK
        count = response.data.get('count', len(response.data))
        assert count >= 1

    def test_admin_can_create_sensor(self, admin_client, sensor_category, storage_location):
        response = admin_client.post('/api/sensor-management/sensors/', {
            'name': 'NewSensor', 'sensor_number': 'SN002',
            'category': sensor_category.id, 'storage_location': storage_location.id,
            'current_quantity': 5,
        })
        assert response.status_code == status.HTTP_201_CREATED

    def test_admin_can_update_sensor(self, admin_client, sensor):
        response = admin_client.patch(f'/api/sensor-management/sensors/{sensor.id}/', {'name': 'UpdatedSensor'})
        assert response.status_code == status.HTTP_200_OK
        sensor.refresh_from_db()
        assert sensor.name == 'UpdatedSensor'

    def test_admin_can_delete_sensor(self, admin_client, sensor):
        response = admin_client.delete(f'/api/sensor-management/sensors/{sensor.id}/')
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_regular_user_can_list_sensors(self, regular_client, sensor):
        response = regular_client.get('/api/sensor-management/sensors/')
        assert response.status_code == status.HTTP_200_OK

    def test_regular_user_cannot_create_sensor(self, regular_client, sensor_category, storage_location):
        response = regular_client.post('/api/sensor-management/sensors/', {
            'name': 'UnauthorizedSensor', 'sensor_number': 'SN999',
            'category': sensor_category.id, 'storage_location': storage_location.id,
        })
        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestSensorMovementViewSet:
    def test_admin_can_list_movements(self, admin_client):
        response = admin_client.get('/api/sensor-management/sensor-movements/')
        assert response.status_code == status.HTTP_200_OK


class TestSensorCalibrationViewSet:
    def test_admin_can_list_calibrations(self, admin_client):
        response = admin_client.get('/api/sensor-management/sensor-calibrations/')
        assert response.status_code == status.HTTP_200_OK


class TestCalibrationReminderViewSet:
    def test_admin_can_list_reminders(self, admin_client):
        response = admin_client.get('/api/sensor-management/calibration-reminders/')
        assert response.status_code == status.HTTP_200_OK

    def test_unauthenticated_cannot_create_sensor(self, api_client, sensor_category, storage_location):
        response = api_client.post('/api/sensor-management/sensors/', {
            'name': 'Hacked', 'sensor_number': 'SN999',
            'category': sensor_category.id, 'storage_location': storage_location.id,
        })
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
