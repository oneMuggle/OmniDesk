from django.test import TestCase
from django.utils import timezone
from .models import Trial, TimeSlot, Equipment, Personnel

class TrialModelTest(TestCase):
    def setUp(self):
        self.trial = Trial.objects.create(
            title="Test Trial",
            client="Test Client",
            description="Test Description"
        )
        self.equipment = Equipment.objects.create(name="Test Equipment")
        self.person = Personnel.objects.create(name="Test Person")

    def test_trial_creation(self):
        """测试试验基础信息保存"""
        self.assertEqual(self.trial.status, 'planned')
        self.assertIsNone(self.trial.start_date)
        self.assertIsNone(self.trial.end_date)

    def test_time_period_calculation(self):
        """测试时间范围自动计算"""
        # 创建关联时间段
        start_time = timezone.now()
        end_time = start_time + timezone.timedelta(hours=2)
        TimeSlot.objects.create(
            trial=self.trial,
            start_time=start_time,
            end_time=end_time
        )

        # 刷新实例
        self.trial.refresh_from_db()
        self.assertEqual(self.trial.start_date, start_time)
        self.assertEqual(self.trial.end_date, end_time)

    def test_save_without_time_periods(self):
        """测试没有时间段的保存"""
        trial = Trial.objects.create(
            title="No Time Trial",
            client="Test Client",
            description="No time slots"
        )
        trial.refresh_from_db()
        self.assertIsNone(trial.start_date)
        self.assertIsNone(trial.end_date)

    def test_m2m_relationships(self):
        """测试多对多关系"""
        self.trial.equipments.add(self.equipment)
        self.trial.responsible_persons.add(self.person)
        
        self.assertEqual(self.trial.equipments.count(), 1)
        self.assertEqual(self.trial.responsible_persons.count(), 1)


from rest_framework.test import APIClient
from rest_framework import status
from users.models import CustomUser
from .models import Position, Personnel, Schedule, PersonnelSequence, LeaderSequence
from datetime import date, timedelta


class BaseTestCase(TestCase):
    def setUp(self):
        """基础测试设置，包含认证"""
        self.client = APIClient()
        self.admin_user = CustomUser.objects.create_user(
            username='admin',
            password='password',
            role='admin'
        )
        self.client.login(username='admin', password='password')

        self.position1 = Position.objects.create(name='员工')
        self.position2 = Position.objects.create(name='领导')

        self.person1 = Personnel.objects.create(name='张三', position=self.position1)
        self.person2 = Personnel.objects.create(name='李四', position=self.position1)
        self.leader1 = Personnel.objects.create(name='王五', position=self.position2)
        self.leader2 = Personnel.objects.create(name='赵六', position=self.position2)


class PersonnelViewSetTest(BaseTestCase):
    def test_list_personnel(self):
        """测试获取人员列表"""
        url = '/api/events/personnel/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 4)

    def test_create_personnel(self):
        """测试创建人员"""
        url = '/api/events/personnel/'
        data = {'name': '新人', 'position': self.position1.id}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Personnel.objects.count(), 5)
        self.assertEqual(response.data['name'], '新人')

    def test_retrieve_personnel(self):
        """测试获取单个人员信息"""
        url = f'/api/events/personnel/{self.person1.id}/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], self.person1.name)

    def test_update_personnel(self):
        """测试更新人员信息"""
        url = f'/api/events/personnel/{self.person1.id}/'
        data = {'name': '张三更新', 'position': self.position2.id}
        response = self.client.put(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.person1.refresh_from_db()
        self.assertEqual(self.person1.name, '张三更新')
        self.assertEqual(self.person1.position, self.position2)

    def test_delete_personnel(self):
        """测试删除人员"""
        url = f'/api/events/personnel/{self.person1.id}/'
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Personnel.objects.count(), 3)

    def test_list_all_action(self):
        """测试 list_all 自定义 action"""
        url = '/api/events/personnel/all/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 4)

    def test_create_personnel_with_phone_numbers(self):
        """测试创建人员时附带电话号码"""
        url = '/api/events/personnel/'
        data = {
            'name': '周七',
            'position': self.position1.id,
            'phone_numbers': [
                {'number': '13800138000'},
                {'number': '13900139000'}
            ]
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        personnel = Personnel.objects.get(id=response.data['id'])
        self.assertEqual(personnel.phone_numbers.count(), 2)
        self.assertEqual(personnel.phone_numbers.first().number, '13800138000')

    def test_update_personnel_with_phone_numbers(self):
        """测试更新人员时附带电话号码"""
        url = f'/api/events/personnel/{self.person1.id}/'
        data = {
            'name': '张三电话更新',
            'position': self.position1.id,
            'phone_numbers': [
                {'number': '11111111111'}
            ]
        }
        response = self.client.put(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.person1.refresh_from_db()
        self.assertEqual(self.person1.phone_numbers.count(), 1)
        self.assertEqual(self.person1.phone_numbers.first().number, '11111111111')


class ScheduleViewSetTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.today = date.today()
        self.schedule1 = Schedule.objects.create(
            duty_date=self.today,
            duty_person=self.person1,
            duty_leader=self.leader1
        )
        self.schedule2 = Schedule.objects.create(
            duty_date=self.today + timedelta(days=1),
            duty_person=self.person2,
            duty_leader=self.leader2
        )

    def test_list_schedules(self):
        """测试获取排班列表"""
        url = '/api/events/schedules/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)

    def test_create_schedule(self):
        """测试创建排班"""
        url = '/api/events/schedules/'
        new_date = self.today + timedelta(days=2)
        data = {
            'duty_date': new_date.strftime('%Y-%m-%d'),
            'duty_person': self.person1.id,
            'duty_leader': self.leader1.id
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Schedule.objects.count(), 3)

    def test_create_schedule_conflict(self):
        """测试创建排班时日期冲突"""
        url = '/api/events/schedules/'
        data = {
            'duty_date': self.today.strftime('%Y-%m-%d'),
            'duty_person': self.person2.id,
            'duty_leader': self.leader2.id
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_schedule_with_override(self):
        """测试创建排班时使用覆盖"""
        url = '/api/events/schedules/'
        data = {
            'duty_date': self.today.strftime('%Y-%m-%d'),
            'duty_person': self.person2.id,
            'duty_leader': self.leader2.id,
            'override': True
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Schedule.objects.count(), 2)
        updated_schedule = Schedule.objects.get(duty_date=self.today)
        self.assertEqual(updated_schedule.duty_person, self.person2)

    def test_update_schedule(self):
        """测试更新排班"""
        url = f'/api/events/schedules/{self.schedule1.id}/'
        data = {
            'duty_date': self.schedule1.duty_date.strftime('%Y-%m-%d'),
            'duty_person': self.person2.id,
            'duty_leader': self.leader2.id
        }
        response = self.client.put(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.schedule1.refresh_from_db()
        self.assertEqual(self.schedule1.duty_person, self.person2)

    def test_delete_schedule(self):
        """测试删除排班"""
        url = f'/api/events/schedules/{self.schedule1.id}/'
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Schedule.objects.count(), 1)

    def test_by_date_range_action(self):
        """测试 by_date_range 自定义 action"""
        start_date = self.today.strftime('%Y-%m-%d')
        end_date = (self.today + timedelta(days=1)).strftime('%Y-%m-%d')
        url = f'/api/events/schedules/by-date-range/?start_date={start_date}&end_date={end_date}'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    def test_bulk_delete_action(self):
        """测试 bulk_destroy 自定义 action"""
        url = '/api/events/schedules/bulk_destroy/'
        data = {'ids': [self.schedule1.id, self.schedule2.id]}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Schedule.objects.count(), 0)

    def test_swap_dates_action(self):
        """测试 swap_dates 自定义 action"""
        url = '/api/events/schedules/swap-dates/'
        data = {'schedule_id_1': self.schedule1.id, 'schedule_id_2': self.schedule2.id}
        
        original_person1 = self.schedule1.duty_person
        original_leader1 = self.schedule1.duty_leader
        original_person2 = self.schedule2.duty_person
        original_leader2 = self.schedule2.duty_leader

        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.schedule1.refresh_from_db()
        self.schedule2.refresh_from_db()

        self.assertEqual(self.schedule1.duty_person, original_person2)
        self.assertEqual(self.schedule1.duty_leader, original_leader2)
        self.assertEqual(self.schedule2.duty_person, original_person1)
        self.assertEqual(self.schedule2.duty_leader, original_leader1)

    def test_generate_schedules_action(self):
        """测试 generate_schedules 自定义 action"""
        Schedule.objects.all().delete()

        personnel_sequence = PersonnelSequence.objects.create(name='测试人员顺序')
        personnel_sequence.sequence = [self.person1.id, self.person2.id]
        personnel_sequence.save()

        leader_sequence = LeaderSequence.objects.create(name='测试领导顺序')
        leader_sequence.sequence = [self.leader1.id, self.leader2.id]
        leader_sequence.save()

        url = '/api/events/schedules/generate-schedules/'
        start_date = self.today
        data = {
            'personnel_sequence_id': personnel_sequence.id,
            'leader_sequence_id': leader_sequence.id,
            'start_date': start_date.strftime('%Y-%m-%d'),
            'duration_days': 14
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Schedule.objects.count(), 14)

        first_day_schedule = Schedule.objects.get(duty_date=start_date)
        self.assertEqual(first_day_schedule.duty_person, self.person1)
        self.assertEqual(first_day_schedule.duty_leader, self.leader1)

        second_day_schedule = Schedule.objects.get(duty_date=start_date + timedelta(days=1))
        self.assertEqual(second_day_schedule.duty_person, self.person2)
        self.assertEqual(second_day_schedule.duty_leader, self.leader1)

        eighth_day_schedule = Schedule.objects.get(duty_date=start_date + timedelta(days=7))
        self.assertEqual(eighth_day_schedule.duty_person, self.person1)
        self.assertEqual(eighth_day_schedule.duty_leader, self.leader2)
