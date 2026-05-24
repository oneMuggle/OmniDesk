from django.test import TestCase
from django.utils import timezone
from .models import Trial, TimeSlot, Equipment
from personnel.models import Personnel

class TrialModelTest(TestCase):
    def setUp(self):
        self.trial = Trial.objects.create(
            title="Test Trial",
            client="Test Client",
            description="Test Description"
        )
        self.equipment = Equipment.objects.create(name="Test Equipment")
        self.person = Personnel.objects.create(name="Test Person", id_card_number="unique_id_123")

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
        self.trial.refresh_from_db()
        self.assertIsNotNone(self.trial.start_date)
        self.assertIsNotNone(self.trial.end_date)
        self.assertEqual(self.trial.start_date, start_time)
        self.assertEqual(self.trial.end_date, end_time)

    def test_update_time_range_on_timeslot_update(self):
        """Test that updating a TimeSlot updates the Trial's time range."""
        start1 = timezone.now()
        end1 = start1 + timezone.timedelta(hours=1)
        ts = TimeSlot.objects.create(trial=self.trial, start_time=start1, end_time=end1)
        self.trial.refresh_from_db()
        self.assertEqual(self.trial.start_date, start1)

        # Now update the timeslot
        new_start = start1 - timezone.timedelta(hours=1)
        ts.start_time = new_start
        ts.save()
        self.trial.refresh_from_db()
        self.assertEqual(self.trial.start_date, new_start)

    def test_update_time_range_on_timeslot_delete(self):
        """Test that deleting a TimeSlot updates the Trial's time range."""
        start1 = timezone.now()
        end1 = start1 + timezone.timedelta(hours=1)
        start2 = timezone.now() + timezone.timedelta(days=1)
        end2 = start2 + timezone.timedelta(hours=1)
        ts1 = TimeSlot.objects.create(trial=self.trial, start_time=start1, end_time=end1)
        ts2 = TimeSlot.objects.create(trial=self.trial, start_time=start2, end_time=end2)
        self.trial.refresh_from_db()
        self.assertEqual(self.trial.start_date, start1)
        self.assertEqual(self.trial.end_date, end2)

        # Delete the earliest timeslot
        ts1.delete()
        self.trial.refresh_from_db()
        self.assertEqual(self.trial.start_date, start2)
        self.assertEqual(self.trial.end_date, end2)

        # Delete the last timeslot
        ts2.delete()
        self.trial.refresh_from_db()
        self.assertIsNone(self.trial.start_date)
        self.assertIsNone(self.trial.end_date)

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
from .models import Schedule, PersonnelSequence, LeaderSequence
from personnel.models import Position
from datetime import date, timedelta, datetime
from django.contrib.auth.models import Group


class BaseTestCase(TestCase):
    def setUp(self):
        """基础测试设置，包含认证"""
        self.client = APIClient()
        # 清理数据，确保测试环境的一致性
        CustomUser.objects.all().delete()
        Position.objects.all().delete()
        Personnel.objects.all().delete()
        Schedule.objects.all().delete()
        PersonnelSequence.objects.all().delete()
        LeaderSequence.objects.all().delete()
        from users.models import PhoneNumber
        PhoneNumber.objects.all().delete()

        admin_group, _ = Group.objects.get_or_create(name='Admin')
        self.admin_user = CustomUser.objects.create_user(
            username='admin',
            password='password'
        )
        self.admin_user.groups.add(admin_group)
        self.client.force_authenticate(user=self.admin_user)

        self.position1 = Position.objects.create(name='员工')
        self.position2 = Position.objects.create(name='领导')

        self.person1 = Personnel.objects.create(name='张三', position=self.position1, id_card_number='p1')
        self.person2 = Personnel.objects.create(name='李四', position=self.position1, id_card_number='p2')
        self.leader1 = Personnel.objects.create(name='王五', position=self.position2, id_card_number='l1')
        self.leader2 = Personnel.objects.create(name='赵六', position=self.position2, id_card_number='l2')




class ScheduleViewSetTest(BaseTestCase):
    def setUp(self):
        # 使用固定日期（2026-05-22 是星期五），使测试不依赖于运行日期
        self.today = date(2026, 5, 22)
        super().setUp()
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
            'duty_person_id': self.person1.id,
            'duty_leader_id': self.leader1.id
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Schedule.objects.count(), 3)

    def test_create_schedule_conflict(self):
        """测试创建排班时日期冲突"""
        url = '/api/events/schedules/'
        data = {
            'duty_date': self.today.strftime('%Y-%m-%d'),
            'duty_person_id': self.person2.id,
            'duty_leader_id': self.leader2.id
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_schedule_with_override(self):
        """测试创建排班时使用覆盖"""
        url = '/api/events/schedules/'
        data = {
            'duty_date': self.today.strftime('%Y-%m-%d'),
            'duty_person_id': self.person2.id,
            'duty_leader_id': self.leader2.id,
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
            'duty_person_id': self.person2.id,
            'duty_leader_id': self.leader2.id
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
            'workday_personnel_sequence_id': personnel_sequence.id,
            'leader_sequence_id': leader_sequence.id,
            'start_date': start_date.strftime('%Y-%m-%d'),
            'duration_days': 14
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Schedule.objects.count(), 14)

        # Day 0: first workday -> person1, leader1
        first_day_schedule = Schedule.objects.get(duty_date=start_date)
        self.assertEqual(first_day_schedule.duty_person, self.person1)
        self.assertEqual(first_day_schedule.duty_leader, self.leader1)

        # Day 1: weekend (holiday) -> holiday_count=0, same sequence -> person1, leader1
        second_day_schedule = Schedule.objects.get(duty_date=start_date + timedelta(days=1))
        self.assertEqual(second_day_schedule.duty_person, self.person1)
        self.assertEqual(second_day_schedule.duty_leader, self.leader1)

        # Day 3: Monday, workday_count=1 -> person2, leader1
        fourth_day_schedule = Schedule.objects.get(duty_date=start_date + timedelta(days=3))
        self.assertEqual(fourth_day_schedule.duty_person, self.person2)
        self.assertEqual(fourth_day_schedule.duty_leader, self.leader1)

        # Day 7: Friday, workday, weeks_passed=1 -> leader2
        eighth_day_schedule = Schedule.objects.get(duty_date=start_date + timedelta(days=7))
        self.assertEqual(eighth_day_schedule.duty_leader, self.leader2)

class EquipmentViewSetTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.equipment = Equipment.objects.create(name="Test Equipment", description="A test equipment.")
        self.url = '/api/events/equipments/'

    def test_list_equipments(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreater(len(response.data['results']), 0)

    def test_create_equipment(self):
        data = {'name': 'New Equipment', 'description': 'A new equipment.'}
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Equipment.objects.count(), 2)

    def test_update_equipment(self):
        update_url = f"{self.url}{self.equipment.id}/"
        data = {'name': 'Updated Equipment'}
        response = self.client.patch(update_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.equipment.refresh_from_db()
        self.assertEqual(self.equipment.name, 'Updated Equipment')

    def test_delete_equipment(self):
        delete_url = f"{self.url}{self.equipment.id}/"
        response = self.client.delete(delete_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Equipment.objects.count(), 0)

class TrialViewSetTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.equipment1 = Equipment.objects.create(name="Equipment 1", description="")
        self.trial = Trial.objects.create(title="Test Trial", client="Test Client", description="")
        self.trial.equipments.add(self.equipment1)
        self.trial.responsible_persons.add(self.person1)
        self.url = '/api/events/trials/'

    def test_list_trials(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)

    def test_create_trial_with_timeslot_data(self):
        """Test creating a trial with nested time_slots_data."""
        start_time = timezone.now()
        end_time = start_time + timedelta(hours=2)
        data = {
            'title': 'New Trial with Slots',
            'client': 'New Client',
            'description': 'A new trial.',
            'equipment_ids': [self.equipment1.id],
            'responsible_person_ids': [self.person1.id],
            'time_slots_data': [
                {'start_time': start_time.isoformat(), 'end_time': end_time.isoformat(), 'description': 'Slot 1'}
            ]
        }
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        new_trial = Trial.objects.get(id=response.data['id'])
        self.assertEqual(new_trial.time_slots.count(), 1)
        self.assertEqual(new_trial.start_date.strftime('%Y-%m-%dT%H:%M'), start_time.strftime('%Y-%m-%dT%H:%M'))

    def test_update_trial_with_timeslot_data(self):
        """Test updating a trial's timeslots via nested time_slots_data."""
        # Create initial timeslot
        ts1_start = timezone.now()
        ts1_end = ts1_start + timedelta(hours=1)
        ts1 = TimeSlot.objects.create(trial=self.trial, start_time=ts1_start, end_time=ts1_end)

        # New and updated timeslot data
        ts2_start = timezone.now() + timedelta(days=1)
        ts2_end = ts2_start + timedelta(hours=1)
        
        update_url = f"{self.url}{self.trial.id}/"
        data = {
            'title': 'Updated Trial Title',
            'time_slots_data': [
                {'id': ts1.id, 'start_time': ts1_start.isoformat(), 'end_time': (ts1_end + timedelta(hours=1)).isoformat()}, # Update existing
                {'start_time': ts2_start.isoformat(), 'end_time': ts2_end.isoformat(), 'description': 'New Slot'} # Add new
            ]
        }
        response = self.client.patch(update_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.trial.refresh_from_db()
        self.assertEqual(self.trial.title, 'Updated Trial Title')
        self.assertEqual(self.trial.time_slots.count(), 2)
        
        # Check that the trial's main date range was updated
        self.assertEqual(self.trial.end_date.strftime('%Y-%m-%dT%H:%M'), ts2_end.strftime('%Y-%m-%dT%H:%M'))

    def test_get_this_week_trials(self):
        # Ensure the trial is within this week
        today = timezone.now().date()
        start_of_week = today - timedelta(days=today.weekday())

        # Create a naive datetime for the start of the week
        start_time_naive = datetime.combine(start_of_week, datetime.min.time())

        # Make it timezone-aware
        start_time_aware = timezone.make_aware(start_time_naive)

        # Assign it to a new TimeSlot, which will update the Trial's dates
        TimeSlot.objects.create(
            trial=self.trial,
            start_time=start_time_aware,
            end_time=start_time_aware + timedelta(hours=1)
        )
        self.trial.refresh_from_db()

        url = f"{self.url}this-week/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 1)

class TimeSlotViewSetTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.trial = Trial.objects.create(title="Trial for TimeSlots", client="Client", description="")
        self.timeslot = TimeSlot.objects.create(trial=self.trial, start_time=timezone.now(), end_time=timezone.now() + timedelta(hours=1))
        self.url = '/api/events/time-slots/'

    def test_bulk_create_timeslots(self):
        start1 = timezone.now() + timedelta(days=1)
        end1 = start1 + timedelta(hours=1)
        start2 = timezone.now() + timedelta(days=2)
        end2 = start2 + timedelta(hours=1)
        data = {
            'trial': self.trial.id,
            'time_slots': [
                {'start_time': start1.isoformat(), 'end_time': end1.isoformat()},
                {'start_time': start2.isoformat(), 'end_time': end2.isoformat()}
            ]
        }
        url = f"{self.url}bulk-create/"
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(self.trial.time_slots.count(), 3) # 1 existing + 2 new
        self.trial.refresh_from_db()
        self.assertIsNotNone(self.trial.end_date)

class MeetingRoomBookingTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.meeting_room = Equipment.objects.create(name="Meeting Room 1", description="Conference room")
        self.url = '/api/events/trials/'

    def test_book_meeting_room(self):
        start_time = timezone.now() + timedelta(days=3)
        end_time = start_time + timedelta(hours=2)
        data = {
            'title': 'Team Meeting',
            'client': 'Internal',
            'description': 'Weekly team sync',
            'equipment_ids': [self.meeting_room.id],
            'responsible_person_ids': [self.person1.id],
            'time_periods': [
                {'start_time': start_time.isoformat(), 'end_time': end_time.isoformat()}
            ]
        }
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        booking = Trial.objects.get(id=response.data['id'])
        self.assertIn(self.meeting_room, booking.equipments.all())
        self.assertEqual(booking.title, "Team Meeting")
