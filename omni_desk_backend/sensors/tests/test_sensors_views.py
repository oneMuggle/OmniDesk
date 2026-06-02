"""
Tests for sensors module (Sensor, CalibrationRecord).
"""
import pytest
from rest_framework import status


@pytest.mark.django_db
class TestSensorViewSet:
    def test_list_sensors_empty(self, api_client, regular_user_obj):
        api_client.force_authenticate(user=regular_user_obj)
        response = api_client.get('/api/sensors/sensors/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 0

    def test_create_sensor_unauthenticated(self, api_client):
        """未认证用户不能创建传感器"""
        response = api_client.post('/api/sensors/sensors/', {
            'name': 'Test Sensor',
            'serial_number': 'SN001',
            'calibration_range': '0-100',
        }, format='json')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_sensor_authenticated(self, api_client, regular_user_obj):
        api_client.force_authenticate(user=regular_user_obj)
        response = api_client.post('/api/sensors/sensors/', {
            'name': 'Test Sensor',
            'serial_number': 'SN001',
            'calibration_range': '0-100',
        }, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['name'] == 'Test Sensor'

    def test_retrieve_sensor(self, admin_client):
        from sensors.models import Sensor
        sensor = Sensor.objects.create(
            name='Test Sensor',
            serial_number='SN002',
            calibration_range='0-100',
        )
        response = admin_client.get(f'/api/sensors/sensors/{sensor.pk}/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['name'] == 'Test Sensor'

    def test_update_sensor(self, admin_client):
        from sensors.models import Sensor
        sensor = Sensor.objects.create(
            name='Old Name',
            serial_number='SN003',
            calibration_range='0-100',
        )
        response = admin_client.patch(f'/api/sensors/sensors/{sensor.pk}/', {
            'name': 'New Name',
        }, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['name'] == 'New Name'

    def test_delete_sensor(self, admin_client):
        from sensors.models import Sensor
        sensor = Sensor.objects.create(
            name='To Delete',
            serial_number='SN004',
            calibration_range='0-100',
        )
        response = admin_client.delete(f'/api/sensors/sensors/{sensor.pk}/')
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Sensor.objects.filter(pk=sensor.pk).exists()

    def test_list_sensors_authenticated(self, api_client, regular_user_obj):
        from sensors.models import Sensor
        api_client.force_authenticate(user=regular_user_obj)
        Sensor.objects.create(name='Sensor A', serial_number='SN005', calibration_range='0-50')
        Sensor.objects.create(name='Sensor B', serial_number='SN006', calibration_range='0-100')
        response = api_client.get('/api/sensors/sensors/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 2


@pytest.mark.django_db
class TestCalibrationRecordViewSet:
    def test_create_calibration_record(self, api_client, regular_user_obj):
        from sensors.models import Sensor
        api_client.force_authenticate(user=regular_user_obj)
        sensor = Sensor.objects.create(
            name='Test Sensor',
            serial_number='SN010',
            calibration_range='0-100',
        )
        response = api_client.post('/api/sensors/calibration-records/', {
            'sensor': sensor.pk,
            'room_temperature': 25.0,
            'relative_humidity': 60.0,
            'calibration_instrument': 'Test Instrument',
            'calibration_date': '2026-05-31',
            'main_table_data': {},
            'performance_indicators': {},
        }, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['sensor'] == sensor.pk

    def test_list_calibration_records(self, api_client, regular_user_obj):
        from sensors.models import CalibrationRecord, Sensor
        api_client.force_authenticate(user=regular_user_obj)
        sensor = Sensor.objects.create(
            name='Test Sensor',
            serial_number='SN011',
            calibration_range='0-100',
        )
        CalibrationRecord.objects.create(
            sensor=sensor,
            room_temperature=25.0,
            relative_humidity=60.0,
            calibration_instrument='Test Instrument',
            calibration_date='2026-05-31',
            main_table_data={},
            performance_indicators={},
        )
        response = api_client.get('/api/sensors/calibration-records/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 1
