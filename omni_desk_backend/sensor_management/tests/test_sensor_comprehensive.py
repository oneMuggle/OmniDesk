"""sensor_management 模块补充测试。"""

import pytest

from sensor_management.models import Sensor, SensorCategory, SensorMovement, SensorCalibration, CalibrationReminder


@pytest.mark.django_db
class TestSensorViewSet:
    def test_sensor_model(self):
        """传感器模型"""
        cat = SensorCategory.objects.create(name='温度传感器')
        sensor = Sensor(name='测试传感器', sensor_number='SN-001')
        assert sensor.name == '测试传感器'
        assert sensor.sensor_number == 'SN-001'

    def test_sensor_list(self, admin_client):
        """传感器列表"""
        resp = admin_client.get('/api/sensor-management/sensors/')
        assert resp.status_code == 200


@pytest.mark.django_db
class TestSensorMovementViewSet:
    def test_movement_list(self, admin_client):
        """传感器移动记录列表"""
        resp = admin_client.get('/api/sensor-management/sensor-movements/')
        assert resp.status_code in [200, 405]


@pytest.mark.django_db
class TestSensorCalibrationViewSet:
    def test_calibration_list(self, admin_client):
        """校准记录列表"""
        resp = admin_client.get('/api/sensor-management/sensor-calibrations/')
        assert resp.status_code == 200
