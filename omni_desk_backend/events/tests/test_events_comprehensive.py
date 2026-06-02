"""events 模块综合测试：Schedule、Trial、TimeSlot、Holiday、Sequence 等。"""

import pytest
from datetime import date, datetime, timedelta
from django.utils import timezone as django_timezone
from django.utils import timezone

from users.models import CustomUser
from personnel.models import Personnel
from events.models import (
    Schedule, Trial, TimeSlot, Equipment, Holiday,
    PersonnelSequence, LeaderSequence, Announcement,
)


@pytest.fixture
def personnel_obj(db):
    return Personnel.objects.create(name='测试人员')


@pytest.fixture
def leader_obj(db):
    return Personnel.objects.create(name='值班领导')


@pytest.fixture
def trial_obj(db):
    return Trial.objects.create(
        title='测试试验',
        client='测试客户',
        description='测试描述',
    )


# ==================== Schedule ViewSet 测试 ====================

@pytest.mark.django_db
class TestScheduleViewSet:
    def test_create_schedule(self, admin_client):
        """创建排班记录"""
        person = Personnel.objects.create(name='排班人员')
        data = {
            'duty_date': '2026-06-15',
            'duty_person_id': person.id,
            'duty_leader_id': person.id,
        }
        resp = admin_client.post('/api/events/schedules/', data)
        assert resp.status_code == 201, resp.data
        assert Schedule.objects.filter(duty_date='2026-06-15').exists()

    def test_create_duplicate_schedule_conflict(self, admin_client):
        """同一天创建第二个排班应返回 400"""
        person = Personnel.objects.create(name='排班人员2')
        data = {'duty_date': '2026-07-01', 'duty_person_id': person.id, 'duty_leader_id': person.id}
        admin_client.post('/api/events/schedules/', data)
        resp = admin_client.post('/api/events/schedules/', data)
        assert resp.status_code == 400

    def test_create_schedule_with_override(self, admin_client):
        """设置 override=True 应覆盖已有排班"""
        person1 = Personnel.objects.create(name='人员A')
        person2 = Personnel.objects.create(name='人员B')
        data1 = {'duty_date': '2026-07-01', 'duty_person_id': person1.id, 'duty_leader_id': person1.id}
        admin_client.post('/api/events/schedules/', data1)
        data2 = {'duty_date': '2026-07-01', 'duty_person_id': person2.id, 'duty_leader_id': person2.id, 'override': 'true'}
        resp = admin_client.post('/api/events/schedules/', data2)
        assert resp.status_code == 201, resp.data
        assert Schedule.objects.filter(duty_date='2026-07-01', duty_person=person2).exists()

    def test_by_date_range(self, admin_client):
        """按日期范围查询"""
        person = Personnel.objects.create(name='范围查询人员')
        Schedule.objects.create(duty_date='2026-06-10', duty_person=person, duty_leader=person)
        Schedule.objects.create(duty_date='2026-06-20', duty_person=person, duty_leader=person)
        resp = admin_client.get('/api/events/schedules/by-date-range/', {
            'start_date': '2026-06-01',
            'end_date': '2026-06-15',
        })
        assert resp.status_code == 200
        assert len(resp.data) == 1

    def test_by_date_range_missing_params(self, admin_client):
        """缺少日期参数应返回 400"""
        resp = admin_client.get('/api/events/schedules/by-date-range/', {'start_date': '2026-06-01'})
        assert resp.status_code == 400

    def test_bulk_update(self, admin_client):
        """批量更新排班"""
        person = Personnel.objects.create(name='批量更新人员')
        data = {
            'schedules': [
                {'duty_date': '2026-08-01', 'duty_person_id': person.id, 'duty_leader_id': person.id},
                {'duty_date': '2026-08-02', 'duty_person_id': person.id, 'duty_leader_id': person.id},
            ],
            'clear_existing': True,
        }
        resp = admin_client.post('/api/events/schedules/bulk-update/', data, format='json')
        assert resp.status_code == 201, resp.data
        assert Schedule.objects.filter(duty_date='2026-08-01').exists()
        assert Schedule.objects.filter(duty_date='2026-08-02').exists()

    def test_bulk_destroy(self, admin_client):
        """批量删除排班"""
        person = Personnel.objects.create(name='批量删除人员')
        s1 = Schedule.objects.create(duty_date='2026-09-01', duty_person=person, duty_leader=person)
        s2 = Schedule.objects.create(duty_date='2026-09-02', duty_person=person, duty_leader=person)
        resp = admin_client.post('/api/events/schedules/bulk_destroy/', {'ids': [s1.id, s2.id]}, format='json')
        assert resp.status_code == 204
        assert Schedule.objects.count() == 0

    def test_swap_dates(self, admin_client):
        """交换两个排班的人员"""
        p1 = Personnel.objects.create(name='交换人员1')
        p2 = Personnel.objects.create(name='交换人员2')
        s1 = Schedule.objects.create(duty_date='2026-10-01', duty_person=p1, duty_leader=p1)
        s2 = Schedule.objects.create(duty_date='2026-10-02', duty_person=p2, duty_leader=p2)
        resp = admin_client.post('/api/events/schedules/swap-dates/', {
            'schedule_id_1': s1.id,
            'schedule_id_2': s2.id,
        }, format='json')
        assert resp.status_code == 200, resp.data
        s1.refresh_from_db()
        s2.refresh_from_db()
        assert s1.duty_person == p2
        assert s2.duty_person == p1

    def test_update_date_conflict(self, admin_client):
        """更新日期到已有排班的日期应返回 400"""
        person = Personnel.objects.create(name='冲突人员')
        s1 = Schedule.objects.create(duty_date='2026-11-01', duty_person=person, duty_leader=person)
        s2 = Schedule.objects.create(duty_date='2026-11-02', duty_person=person, duty_leader=person)
        resp = admin_client.put(f'/api/events/schedules/{s2.id}/', {
            'duty_date': '2026-11-01',
            'duty_person_id': person.id,
            'duty_leader_id': person.id,
        }, format='json')
        assert resp.status_code == 400


# ==================== Trial ViewSet 测试 ====================

@pytest.mark.django_db
class TestTrialViewSet:
    def test_create_trial_with_time_slots(self, admin_client):
        """创建试验并关联时间段"""
        data = {
            'title': '新试验',
            'client': '新客户',
            'description': '新描述',
            'time_periods': [
                {'start_time': '2026-06-15T09:00:00Z', 'end_time': '2026-06-15T12:00:00Z'},
            ],
        }
        resp = admin_client.post('/api/events/trials/', data, format='json')
        assert resp.status_code == 201, resp.data
        trial = Trial.objects.get(title='新试验')
        assert trial.time_slots.count() == 1
        assert trial.start_date is not None

    def test_update_trial_optimistic_lock(self, admin_client):
        """版本号不匹配时应拒绝更新"""
        trial = Trial.objects.create(title='乐观锁试验', client='客户', description='描述', version=1)
        data = {
            'title': '更新标题',
            'client': '客户',
            'description': '描述',
            'version': 0,  # 错误版本
        }
        resp = admin_client.put(f'/api/events/trials/{trial.id}/', data, format='json')
        assert resp.status_code == 400

    def test_update_trial_success(self, admin_client):
        """正确版本号应成功更新"""
        trial = Trial.objects.create(title='版本试验', client='客户', description='描述', version=2)
        data = {
            'title': '新标题',
            'client': '客户',
            'description': '描述',
            'version': 2,
        }
        resp = admin_client.put(f'/api/events/trials/{trial.id}/', data, format='json')
        assert resp.status_code == 200, resp.data
        trial.refresh_from_db()
        assert trial.version == 3
        assert trial.title == '新标题'

    def test_this_week_trials(self, admin_client):
        """获取本周试验 — 验证 API 端点可用"""
        resp = admin_client.get('/api/events/trials/this-week/')
        assert resp.status_code == 200
        assert isinstance(resp.data, list)

    def test_update_time_slots(self, admin_client):
        """原子化更新时间段"""
        trial = Trial.objects.create(title='时间段试验', client='客户', description='描述')
        time_periods = [
            {'start_time': '2026-07-01T08:00:00Z', 'end_time': '2026-07-01T10:00:00Z'},
            {'start_time': '2026-07-01T14:00:00Z', 'end_time': '2026-07-01T16:00:00Z'},
        ]
        resp = admin_client.post(
            f'/api/events/trials/{trial.id}/update-time-slots/',
            time_periods, format='json'
        )
        assert resp.status_code == 201, resp.data
        assert trial.time_slots.count() == 2


# ==================== TimeSlot 模型测试 ====================

@pytest.mark.django_db
class TestTimeSlotModel:
    def test_save_updates_trial_time_range(self, trial_obj):
        """TimeSlot 保存时应自动更新 trial 的时间范围"""
        slot = TimeSlot.objects.create(
            trial=trial_obj,
            start_time=django_timezone.make_aware(datetime(2026, 6, 15, 9, 0)),
            end_time=django_timezone.make_aware(datetime(2026, 6, 15, 12, 0)),
        )
        trial_obj.refresh_from_db()
        assert trial_obj.start_date is not None
        assert trial_obj.end_date is not None

    def test_delete_updates_trial_time_range(self, trial_obj):
        """TimeSlot 删除时应自动更新 trial 的时间范围"""
        slot1 = TimeSlot.objects.create(
            trial=trial_obj,
            start_time=django_timezone.make_aware(datetime(2026, 6, 15, 9, 0)),
            end_time=django_timezone.make_aware(datetime(2026, 6, 15, 12, 0)),
        )
        slot2 = TimeSlot.objects.create(
            trial=trial_obj,
            start_time=django_timezone.make_aware(datetime(2026, 6, 16, 9, 0)),
            end_time=django_timezone.make_aware(datetime(2026, 6, 16, 12, 0)),
        )
        trial_obj.refresh_from_db()
        assert trial_obj.end_date is not None

        slot2.delete()
        trial_obj.refresh_from_db()
        # 剩余 slot1 的时间
        assert trial_obj.end_date == django_timezone.make_aware(datetime(2026, 6, 15, 12, 0))

    def test_no_slots_clears_trial_dates(self, trial_obj):
        """无时间段时 update_time_range 应清空日期"""
        # 手动创建 slot 并验证 update_time_range 逻辑
        slot = TimeSlot(
            trial=trial_obj,
            start_time=django_timezone.make_aware(datetime(2026, 6, 15, 9, 0)),
            end_time=django_timezone.make_aware(datetime(2026, 6, 15, 12, 0)),
        )
        slot.save()
        trial_obj.refresh_from_db()
        assert trial_obj.end_date is not None

        # 直接删除 slot 并调用 update_time_range
        TimeSlot.objects.filter(trial=trial_obj).delete()
        trial_obj.update_time_range()
        assert trial_obj.start_date is None
        assert trial_obj.end_date is None


# ==================== TimeSlot ViewSet 测试 ====================

@pytest.mark.django_db
class TestTimeSlotViewSet:
    def test_bulk_create(self, admin_client, trial_obj):
        """批量创建时间段"""
        data = {
            'trial': trial_obj.id,
            'time_slots': [
                {'start_time': '2026-06-15T09:00:00Z', 'end_time': '2026-06-15T12:00:00Z'},
                {'start_time': '2026-06-16T09:00:00Z', 'end_time': '2026-06-16T12:00:00Z'},
            ],
        }
        resp = admin_client.post('/api/events/time-slots/bulk-create/', data, format='json')
        assert resp.status_code == 201, resp.data
        assert TimeSlot.objects.filter(trial=trial_obj).count() == 2

    def test_bulk_create_missing_trial(self, admin_client):
        """缺少 trial 应返回 400"""
        resp = admin_client.post('/api/events/time-slots/bulk-create/', {'time_slots': []}, format='json')
        assert resp.status_code == 400

    def test_bulk_create_trial_not_found(self, admin_client):
        """trial 不存在应返回 404"""
        resp = admin_client.post('/api/events/time-slots/bulk-create/', {
            'trial': 99999,
            'time_slots': [{'start_time': '2026-06-15T09:00:00Z', 'end_time': '2026-06-15T12:00:00Z'}],
        }, format='json')
        assert resp.status_code == 404


# ==================== Holiday ViewSet 测试 ====================

@pytest.mark.django_db
class TestHolidayViewSet:
    def test_filter_by_year(self, admin_client):
        """按年份过滤节假日"""
        # 删除已有数据避免干扰
        Holiday.objects.all().delete()
        Holiday.objects.create(name='元旦', start_date=date(2026, 1, 1), end_date=date(2026, 1, 1))
        Holiday.objects.create(name='国庆', start_date=date(2025, 10, 1), end_date=date(2025, 10, 7))
        resp = admin_client.get('/api/events/holidays/', {'year': '2026'})
        assert resp.status_code == 200
        results = resp.data.get('results', resp.data)
        assert len(results) >= 1
        names = [h['name'] for h in results]
        assert '元旦' in names

    def test_crud(self, admin_client):
        """节假日 CRUD"""
        # Create
        resp = admin_client.post('/api/events/holidays/', {
            'name': '测试假日',
            'start_date': '2026-12-25',
            'end_date': '2026-12-25',
        }, format='json')
        assert resp.status_code == 201
        holiday_id = resp.data['id']

        # Read
        resp = admin_client.get(f'/api/events/holidays/{holiday_id}/')
        assert resp.status_code == 200
        assert resp.data['name'] == '测试假日'

        # Update
        resp = admin_client.patch(f'/api/events/holidays/{holiday_id}/', {'name': '圣诞节'}, format='json')
        assert resp.status_code == 200

        # Delete
        resp = admin_client.delete(f'/api/events/holidays/{holiday_id}/')
        assert resp.status_code == 204


# ==================== PersonnelSequence & LeaderSequence 测试 ====================

@pytest.mark.django_db
class TestSequenceViewSet:
    def test_personnel_sequence_crud(self, admin_client):
        """人员顺序 CRUD"""
        p1 = Personnel.objects.create(name='序列人员1')
        p2 = Personnel.objects.create(name='序列人员2')

        resp = admin_client.post('/api/events/personnel-sequences/', {
            'name': '测试序列',
            'sequence': [p1.id, p2.id],
            'personnel': [p1.id, p2.id],
            'holiday_sequence': [],
        }, format='json')
        assert resp.status_code == 201, resp.data
        seq_id = resp.data['id']

        resp = admin_client.get(f'/api/events/personnel-sequences/{seq_id}/')
        assert resp.status_code == 200
        assert resp.data['name'] == '测试序列'

        resp = admin_client.delete(f'/api/events/personnel-sequences/{seq_id}/')
        assert resp.status_code == 204

    def test_leader_sequence_crud(self, admin_client):
        """领导顺序 CRUD"""
        p = Personnel.objects.create(name='领导人员')
        resp = admin_client.post('/api/events/leader-sequences/', {
            'name': '领导序列',
            'sequence': [p.id],
            'personnel': [p.id],
        }, format='json')
        assert resp.status_code == 201, resp.data


# ==================== Announcement ViewSet 测试 ====================

@pytest.mark.django_db
class TestAnnouncementViewSet:
    def test_create_announcement_auto_author(self, admin_client, admin_user_obj):
        """创建公告应自动关联当前用户为 author"""
        resp = admin_client.post('/api/events/announcements/', {
            'title': '测试公告',
            'content': '公告内容',
        }, format='json')
        assert resp.status_code == 201, resp.data
        announcement = Announcement.objects.get(title='测试公告')
        assert announcement.author == admin_user_obj

    def test_list_announcements(self, admin_client):
        """公告列表按创建时间倒序"""
        # 清除已有数据
        Announcement.objects.all().delete()
        Announcement.objects.create(title='公告A', content='内容A')
        Announcement.objects.create(title='公告B', content='内容B')
        resp = admin_client.get('/api/events/announcements/')
        assert resp.status_code == 200
        results = resp.data.get('results', resp.data)
        assert len(results) == 2
        # 按 -created_at 排序，后创建的在前
        assert results[0]['title'] == '公告B'


# ==================== Equipment ViewSet 测试 ====================

@pytest.mark.django_db
class TestEquipmentViewSet:
    def test_crud(self, admin_client):
        """设备 CRUD"""
        resp = admin_client.post('/api/events/equipments/', {
            'name': '测试设备',
            'description': '设备描述',
        }, format='json')
        assert resp.status_code == 201
        eq_id = resp.data['id']

        resp = admin_client.get(f'/api/events/equipments/{eq_id}/')
        assert resp.status_code == 200

        resp = admin_client.patch(f'/api/events/equipments/{eq_id}/', {'name': '新设备名'}, format='json')
        assert resp.status_code == 200

        resp = admin_client.delete(f'/api/events/equipments/{eq_id}/')
        assert resp.status_code == 204

    def test_read_only_for_regular_user(self, regular_client):
        """普通用户只能读"""
        Equipment.objects.create(name='只读设备', description='描述')
        resp = regular_client.post('/api/events/equipments/', {
            'name': '新设备',
            'description': '描述',
        }, format='json')
        # 普通用户无写入权限
        assert resp.status_code in [401, 403]


# ==================== Trial 模型测试 ====================

@pytest.mark.django_db
class TestTrialModel:
    def test_update_time_range_with_slots(self):
        """有时间段时应正确计算时间范围"""
        trial = Trial.objects.create(title='时间范围试验', client='客户', description='描述')
        TimeSlot.objects.create(
            trial=trial,
            start_time=django_timezone.make_aware(datetime(2026, 6, 10, 9, 0)),
            end_time=django_timezone.make_aware(datetime(2026, 6, 10, 12, 0)),
        )
        TimeSlot.objects.create(
            trial=trial,
            start_time=django_timezone.make_aware(datetime(2026, 6, 12, 8, 0)),
            end_time=django_timezone.make_aware(datetime(2026, 6, 12, 17, 0)),
        )
        trial.update_time_range()
        assert trial.start_date == django_timezone.make_aware(datetime(2026, 6, 10, 9, 0))
        assert trial.end_date == django_timezone.make_aware(datetime(2026, 6, 12, 17, 0))

    def test_update_time_range_no_slots(self):
        """无时间段时应清空日期"""
        trial = Trial.objects.create(title='空试验', client='客户', description='描述')
        trial.update_time_range()
        assert trial.start_date is None
        assert trial.end_date is None

    def test_get_time_slots(self):
        """get_time_slots 应返回排序后的时间段"""
        trial = Trial.objects.create(title='时间段试验', client='客户', description='描述')
        ts2 = TimeSlot.objects.create(trial=trial, start_time=django_timezone.make_aware(datetime(2026, 6, 15, 14, 0)), end_time=django_timezone.make_aware(datetime(2026, 6, 15, 17, 0)))
        ts1 = TimeSlot.objects.create(trial=trial, start_time=django_timezone.make_aware(datetime(2026, 6, 15, 9, 0)), end_time=django_timezone.make_aware(datetime(2026, 6, 15, 12, 0)))
        slots = trial.get_time_slots()
        assert slots.first() == ts1
