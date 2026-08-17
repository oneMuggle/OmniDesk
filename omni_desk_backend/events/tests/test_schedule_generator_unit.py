"""ScheduleGenerator 单元测试(P1-3)

覆盖 schedule_generator.py 各路径:
- 成功路径:工作日生成、含节假日裁剪、自定义起始偏移
- 错误路径:空序列、无效 ID、起始 ID 类型错、不在序列中、节假日无序列
- 静态方法:_clean_sequence / _expand_holidays / _find_index

注:ScheduleGenerator 是 service 层,不依赖 DRF auth/view,通过直接构造 + DB 操作测试。
"""

from datetime import date, timedelta

import pytest
from rest_framework.exceptions import ValidationError

from events.models import Holiday
from events.schedule_generator import ScheduleGenerator
from personnel.models import Personnel


@pytest.fixture
def sequences(db):
    """3 名值班人 + 2 名领导 + PersonnelSequence/LeaderSequence。

    序列构造:
      workday: [p1, p2, p3]
      holiday: [p1, p2]   (与 workday 不同,验证 holiday 分支)
      leader:  [l1, l2]
    """
    p1 = Personnel.objects.create(name="值班人甲")
    p2 = Personnel.objects.create(name="值班人乙")
    p3 = Personnel.objects.create(name="值班人丙")
    l1 = Personnel.objects.create(name="领导甲")
    l2 = Personnel.objects.create(name="领导乙")

    from events.models import LeaderSequence, PersonnelSequence

    workday_seq = PersonnelSequence.objects.create(
        name="主顺序",
        sequence=[p1.id, p2.id, p3.id],
        holiday_sequence=[p1.id, p2.id],
    )
    leader_seq = LeaderSequence.objects.create(name="领导顺序", sequence=[l1.id, l2.id])
    return {
        "p1": p1, "p2": p2, "p3": p3,
        "l1": l1, "l2": l2,
        "workday_seq": workday_seq,
        "leader_seq": leader_seq,
    }


def test_clean_sequence_filters_garbage():
    """_clean_sequence 必须过滤 None/非数字/空白字符串。"""
    raw = ["1", 2, " 3 ", None, "", "abc", "4.5"]
    assert ScheduleGenerator._clean_sequence(raw) == [1, 2, 3]


def test_clean_sequence_empty():
    assert ScheduleGenerator._clean_sequence([]) == []
    assert ScheduleGenerator._clean_sequence([None, "", "x"]) == []


def test_expand_holidays_clips_to_window():
    """节假日展开必须裁剪到 [start_date, end_date] 窗口内。"""
    start = date(2026, 5, 1)
    end = date(2026, 5, 10)

    h1 = Holiday(start_date=date(2026, 4, 28), end_date=date(2026, 5, 2), name="跨窗口1")
    h2 = Holiday(start_date=date(2026, 5, 5), end_date=date(2026, 5, 7), name="窗口内")
    h3 = Holiday(start_date=date(2026, 5, 11), end_date=date(2026, 5, 15), name="窗口外")

    result = ScheduleGenerator._expand_holidays([h1, h2, h3], start, end)

    assert date(2026, 5, 1) in result  # 来自 h1,起点裁剪
    assert date(2026, 5, 2) in result  # 来自 h1
    assert date(2026, 5, 4) not in result  # h1/h2 都不到
    assert date(2026, 5, 5) in result  # 来自 h2
    assert date(2026, 5, 7) in result  # 来自 h2
    assert date(2026, 5, 11) not in result  # h3 窗口外


def test_find_index_no_target_returns_zero():
    assert ScheduleGenerator._find_index([1, 2, 3], None, "workday") == 0
    assert ScheduleGenerator._find_index([1, 2, 3], "", "workday") == 0


def test_find_index_returns_position():
    assert ScheduleGenerator._find_index([10, 20, 30], 20, "workday") == 1


def test_find_index_invalid_type_raises():
    """起始 ID 非整数(字符串 "abc")必须抛 ValidationError。"""
    with pytest.raises(ValidationError) as exc:
        ScheduleGenerator._find_index([1, 2, 3], "abc", "workday")
    assert "start_workday_id" in exc.value.detail


def test_find_index_not_in_sequence_raises():
    """起始 ID 合法整数但不在序列中必须抛 ValidationError。"""
    with pytest.raises(ValidationError) as exc:
        ScheduleGenerator._find_index([1, 2, 3], 999, "holiday")
    assert "start_holiday_id" in exc.value.detail


@pytest.mark.django_db
def test_generate_creates_schedules_for_workday(sequences):
    """纯工作日范围(避开周末)→ duration_days 行排班,人员按 workday 序列轮转。"""
    # 找一个连续 5 天工作日:周一~周五
    start = date(2026, 5, 4)  # 周一
    gen = ScheduleGenerator(
        workday_sequence=sequences["workday_seq"],
        leader_sequence=sequences["leader_seq"],
        start_date=start,
        duration_days=5,
    )
    schedules, s_date, e_date = gen.generate()

    assert s_date == start
    assert e_date == start + timedelta(days=4)
    assert len(schedules) == 5

    duty_person_ids = [s.duty_person_id for s in schedules]
    duty_leader_ids = [s.duty_leader_id for s in schedules]
    # 5 天工作日 + 3 人轮转 → 应该是 p1,p2,p3,p1,p2
    assert duty_person_ids == [
        sequences["p1"].id, sequences["p2"].id, sequences["p3"].id,
        sequences["p1"].id, sequences["p2"].id,
    ]
    # 2 领导轮转,5 天跨 0 完整周 + 4 天第 2 周 → 领导都是 l1(weeks_passed=0)
    assert all(lid == sequences["l1"].id for lid in duty_leader_ids)


@pytest.mark.django_db
def test_generate_with_holiday_uses_holiday_sequence(sequences):
    """周末日落在范围内 → 必须用 holiday 序列的人员,不是 workday。"""
    # 2026-05-09 是周六
    start = date(2026, 5, 8)  # 周五
    gen = ScheduleGenerator(
        workday_sequence=sequences["workday_seq"],
        leader_sequence=sequences["leader_seq"],
        start_date=start,
        duration_days=3,  # 周五、周六、周日
    )
    schedules, _, _ = gen.generate()
    duty_person_ids = [s.duty_person_id for s in schedules]

    # 周五(workday)=p1, 周六/日(holiday,序列 [p1,p2])=p1,p2
    assert duty_person_ids == [
        sequences["p1"].id,
        sequences["p1"].id,
        sequences["p2"].id,
    ]


@pytest.mark.django_db
def test_generate_with_db_holiday(sequences):
    """DB 里的 Holiday 对象落入窗口 → 当日人员走 holiday 序列。"""
    Holiday.objects.create(
        name="五一补休", start_date=date(2026, 5, 6), end_date=date(2026, 5, 6),
    )
    start = date(2026, 5, 4)  # 周一,5 天
    gen = ScheduleGenerator(
        workday_sequence=sequences["workday_seq"],
        leader_sequence=sequences["leader_seq"],
        start_date=start,
        duration_days=5,
    )
    schedules, _, _ = gen.generate()
    # 5/6 是 holiday → 该日人员来自 holiday 序列 [p1,p2] 第 0 个 = p1
    holiday_day = next(s for s in schedules if s.duty_date == date(2026, 5, 6))
    assert holiday_day.duty_person_id == sequences["p1"].id


@pytest.mark.django_db
def test_generate_with_start_offset(sequences):
    """指定 start_personnel_id → 从该位置开始轮转,而非从序列头。"""
    start = date(2026, 5, 4)  # 周一
    gen = ScheduleGenerator(
        workday_sequence=sequences["workday_seq"],
        leader_sequence=sequences["leader_seq"],
        start_date=start,
        duration_days=3,
        start_personnel_id=sequences["p3"].id,  # 从 p3 开始
    )
    schedules, _, _ = gen.generate()
    duty_person_ids = [s.duty_person_id for s in schedules]
    # 起始 idx=2 → workday[2]=p3, workday[3]=p1, workday[4]=p2
    assert duty_person_ids == [
        sequences["p3"].id,
        sequences["p1"].id,
        sequences["p2"].id,
    ]


@pytest.mark.django_db
def test_generate_replaces_existing_schedules(sequences):
    """同一日期范围第二次 generate 必须删除旧排班,不重复。"""
    from events.models import Schedule

    start = date(2026, 5, 4)
    gen = ScheduleGenerator(
        workday_sequence=sequences["workday_seq"],
        leader_sequence=sequences["leader_seq"],
        start_date=start,
        duration_days=3,
    )
    gen.generate()
    assert Schedule.objects.filter(duty_date__gte=start).count() == 3

    # 第二次运行,同样窗口不应留下 6 条排班
    gen.generate()
    assert Schedule.objects.filter(duty_date__gte=start).count() == 3


@pytest.mark.django_db
def test_generate_empty_sequence_raises(sequences):
    """序列为空必须抛 ValidationError("排班序列不能为空")。"""
    sequences["workday_seq"].sequence = []
    sequences["workday_seq"].save()

    start = date(2026, 5, 4)
    gen = ScheduleGenerator(
        workday_sequence=sequences["workday_seq"],
        leader_sequence=sequences["leader_seq"],
        start_date=start,
        duration_days=3,
    )
    with pytest.raises(ValidationError) as exc:
        gen.generate()
    assert "排班序列不能为空" in str(exc.value)


@pytest.mark.django_db
def test_generate_invalid_personnel_id_raises(sequences):
    """序列里包含不存在的 Personnel ID 必须抛 ValidationError。"""
    sequences["workday_seq"].sequence = [sequences["p1"].id, 999999]
    sequences["workday_seq"].save()

    start = date(2026, 5, 4)
    gen = ScheduleGenerator(
        workday_sequence=sequences["workday_seq"],
        leader_sequence=sequences["leader_seq"],
        start_date=start,
        duration_days=3,
    )
    with pytest.raises(ValidationError) as exc:
        gen.generate()
    assert "无效" in str(exc.value)
    assert "999999" in str(exc.value)


@pytest.mark.django_db
def test_generate_holiday_sequence_none_falls_back_to_workday(sequences):
    """holiday_sequence=None → generate 内部走 holiday_ids = workday_ids 兜底。

    源码 line 46-48:if holiday_sequence and holiday_sequence.sequence → 取节假日序列;
    否则 holiday_ids = workday_ids。这条兜底是显式设计,验证它确实生效:
    窗口内周末 + holiday_sequence=None → 排班人员仍能产出,不抛错。
    """
    start = date(2026, 5, 8)  # 周五,3 天包含周末
    gen = ScheduleGenerator(
        workday_sequence=sequences["workday_seq"],
        leader_sequence=sequences["leader_seq"],
        start_date=start,
        duration_days=3,
    )
    gen.holiday_sequence = None  # 触发兜底
    schedules, _, _ = gen.generate()
    # 兜底下周末人员也来自 workday 序列
    duty_person_ids = [s.duty_person_id for s in schedules]
    assert all(pid in (sequences["p1"].id, sequences["p2"].id, sequences["p3"].id) for pid in duty_person_ids)
    assert len(schedules) == 3


@pytest.mark.django_db
def test_generate_invalid_start_personnel_type_raises(sequences):
    """start_personnel_id 类型错误(非整数) → ValidationError on start_workday_id。"""
    start = date(2026, 5, 4)
    gen = ScheduleGenerator(
        workday_sequence=sequences["workday_seq"],
        leader_sequence=sequences["leader_seq"],
        start_date=start,
        duration_days=3,
        start_personnel_id="not-a-number",
    )
    with pytest.raises(ValidationError) as exc:
        gen.generate()
    assert "start_workday_id" in exc.value.detail


@pytest.mark.django_db
def test_generate_start_id_not_in_sequence_raises(sequences):
    """start_personnel_id 是合法整数但不在序列中 → ValidationError。"""
    start = date(2026, 5, 4)
    gen = ScheduleGenerator(
        workday_sequence=sequences["workday_seq"],
        leader_sequence=sequences["leader_seq"],
        start_date=start,
        duration_days=3,
        start_personnel_id=888888,
    )
    with pytest.raises(ValidationError) as exc:
        gen.generate()
    assert "start_workday_id" in exc.value.detail