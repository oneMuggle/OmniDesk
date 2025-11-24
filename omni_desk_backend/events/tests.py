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
