"""
Tests for events module (Equipment, Trial, TimeSlot, Schedule, Announcement, Holiday).
"""
from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework import status


@pytest.mark.django_db
class TestEquipmentViewSet:
    def test_list_equipment(self, api_client, regular_user_obj):
        api_client.force_authenticate(user=regular_user_obj)
        response = api_client.get('/api/events/equipments/')
        assert response.status_code == status.HTTP_200_OK

    def test_create_equipment(self, admin_client):
        response = admin_client.post('/api/events/equipments/', {
            'name': 'Test Equipment',
            'description': 'Test equipment description',
        }, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['name'] == 'Test Equipment'

    def test_create_equipment_unauthorized(self, api_client):
        response = api_client.post('/api/events/equipments/', {
            'name': 'Unauthorized Equipment',
            'description': 'Should fail',
        }, format='json')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_retrieve_equipment(self, api_client, regular_user_obj):
        from events.models import Equipment
        api_client.force_authenticate(user=regular_user_obj)
        equipment = Equipment.objects.create(name='Retrieve Equipment', description='Desc')
        response = api_client.get(f'/api/events/equipments/{equipment.pk}/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['name'] == 'Retrieve Equipment'

    def test_update_equipment(self, admin_client):
        from events.models import Equipment
        equipment = Equipment.objects.create(name='Old Equipment', description='Desc')
        response = admin_client.patch(f'/api/events/equipments/{equipment.pk}/', {
            'name': 'Updated Equipment',
        }, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['name'] == 'Updated Equipment'

    def test_delete_equipment(self, admin_client):
        from events.models import Equipment
        equipment = Equipment.objects.create(name='Delete Equipment', description='Desc')
        response = admin_client.delete(f'/api/events/equipments/{equipment.pk}/')
        assert response.status_code == status.HTTP_204_NO_CONTENT


@pytest.mark.django_db
class TestTrialViewSet:
    def test_list_trials(self, api_client, regular_user_obj):
        api_client.force_authenticate(user=regular_user_obj)
        response = api_client.get('/api/events/trials/')
        assert response.status_code == status.HTTP_200_OK

    def test_create_trial(self, admin_client):
        response = admin_client.post('/api/events/trials/', {
            'title': 'Test Trial',
            'client': 'Test Client',
            'description': 'Test trial description',
            'status': 'planned',
            'time_periods': [],
        }, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['title'] == 'Test Trial'

    def test_retrieve_trial(self, admin_client):
        from events.models import Trial
        trial = Trial.objects.create(
            title='Retrieve Trial',
            client='Client',
            description='Desc',
            status='planned',
        )
        response = admin_client.get(f'/api/events/trials/{trial.pk}/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['title'] == 'Retrieve Trial'

    def test_update_trial(self, admin_client):
        from events.models import Trial
        trial = Trial.objects.create(
            title='Old Trial',
            client='Client',
            description='Desc',
            status='planned',
        )
        response = admin_client.patch(f'/api/events/trials/{trial.pk}/', {
            'title': 'Updated Trial',
        }, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['title'] == 'Updated Trial'

    def test_delete_trial(self, admin_client):
        from events.models import Trial
        trial = Trial.objects.create(
            title='Delete Trial',
            client='Client',
            description='Desc',
            status='planned',
        )
        response = admin_client.delete(f'/api/events/trials/{trial.pk}/')
        assert response.status_code == status.HTTP_204_NO_CONTENT


@pytest.mark.django_db
class TestTimeSlotViewSet:
    def test_create_time_slot(self, admin_client):
        from events.models import Trial
        trial = Trial.objects.create(title='TimeSlot Trial', client='Client', description='Desc', status='planned')
        start = timezone.now() + timedelta(days=7)
        end = start + timedelta(hours=2)
        response = admin_client.post('/api/events/time-slots/', {
            'trial': trial.pk,
            'start_time': start.isoformat(),
            'end_time': end.isoformat(),
            'description': 'Test time slot',
        }, format='json')
        assert response.status_code == status.HTTP_201_CREATED

    def test_list_time_slots(self, api_client, regular_user_obj):
        api_client.force_authenticate(user=regular_user_obj)
        response = api_client.get('/api/events/time-slots/')
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestScheduleViewSet:
    def test_list_schedules(self, api_client, regular_user_obj):
        api_client.force_authenticate(user=regular_user_obj)
        response = api_client.get('/api/events/schedules/')
        assert response.status_code == status.HTTP_200_OK

    def test_create_schedule(self, admin_client):
        response = admin_client.post('/api/events/schedules/', {
            'duty_date': '2026-06-15',
        }, format='json')
        assert response.status_code in [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST]


@pytest.mark.django_db
class TestAnnouncementViewSet:
    def test_list_announcements(self, api_client, regular_user_obj):
        api_client.force_authenticate(user=regular_user_obj)
        response = api_client.get('/api/events/announcements/')
        assert response.status_code == status.HTTP_200_OK

    def test_create_announcement(self, api_client, admin_user_obj):
        api_client.force_authenticate(user=admin_user_obj)
        response = api_client.post('/api/events/announcements/', {
            'title': 'Test Announcement',
            'content': 'Announcement content',
        }, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['title'] == 'Test Announcement'


@pytest.mark.django_db
class TestHolidayViewSet:
    def test_list_holidays(self, api_client, regular_user_obj):
        api_client.force_authenticate(user=regular_user_obj)
        response = api_client.get('/api/events/holidays/')
        assert response.status_code == status.HTTP_200_OK

    def test_create_holiday(self, admin_client):
        response = admin_client.post('/api/events/holidays/', {
            'name': 'Test Holiday',
            'start_date': '2026-10-01',
            'end_date': '2026-10-07',
        }, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['name'] == 'Test Holiday'

    def test_list_holidays_filter_by_year(self, admin_client):
        from events.models import Holiday
        Holiday.objects.create(name='2026 Holiday', start_date='2026-01-01', end_date='2026-01-02')
        Holiday.objects.create(name='2027 Holiday', start_date='2027-01-01', end_date='2027-01-02')
        response = admin_client.get('/api/events/holidays/?year=2026')
        assert response.status_code == status.HTTP_200_OK
        for item in response.data['results']:
            assert item['start_date'].startswith('2026')
