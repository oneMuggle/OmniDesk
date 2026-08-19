"""批次生命周期测试: 创建/截止/算 grade + stipend。"""
from datetime import date
from decimal import Decimal

import pytest

from joint_students.models import AssessmentCycle, StipendRecord
from joint_students.services.cycle import close_cycle, create_cycle
from joint_students.tests.factories import (
    create_cycle as factory_create_cycle,
    create_joint_student,
    create_report,
    create_score,
    create_user,
)


@pytest.mark.django_db
class TestCreateCycle:
    def test_create_new_cycle(self):
        """正常创建新批次。"""
        cycle = create_cycle(year=2026, month=7, status="collecting")
        assert cycle.id is not None
        assert cycle.year == 2026
        assert cycle.month == 7
        assert cycle.status == "collecting"

    def test_create_cycle_idempotent(self):
        """同月二次创建不重复。"""
        c1 = create_cycle(year=2026, month=7)
        c2 = create_cycle(year=2026, month=7)
        assert c1.id == c2.id

    def test_create_cycle_auto_source(self):
        """trigger_source='auto' 用于 Celery 自动触发。"""
        cycle = create_cycle(year=2026, month=7, trigger_source="auto")
        assert cycle.trigger_source == "auto"

    def test_create_cycle_with_creator(self):
        """手动触发时记录 creator。"""
        user = create_user(username="manager1")
        cycle = create_cycle(year=2026, month=7, created_by=user)
        assert cycle.created_by == user


@pytest.mark.django_db
class TestCloseCycle:
    def test_close_creates_stipends_for_all_scored_students(self):
        """close_cycle 为每个有打分的联培生创建 StipendRecord。"""
        cycle = factory_create_cycle()
        js1 = create_joint_student()
        js2 = create_joint_student()
        create_report(joint_student=js1, year=2026, month=7, status="approved")
        create_report(joint_student=js2, year=2026, month=7, status="approved")
        create_score(cycle=cycle, joint_student=js1, expert=create_user(), score=Decimal("95"))
        create_score(cycle=cycle, joint_student=js2, expert=create_user(), score=Decimal("80"))

        close_cycle(cycle)

        cycle.refresh_from_db()
        assert cycle.status == "closed"
        assert StipendRecord.objects.filter(cycle=cycle).count() == 2

    def test_close_assigns_grade_a_to_top_40_percent(self):
        """3 人 → 1 A 2 B (floor(3*0.4)=1)。"""
        cycle = factory_create_cycle()
        js_high = create_joint_student()
        js_mid = create_joint_student()
        js_low = create_joint_student()
        for js in [js_high, js_mid, js_low]:
            create_report(joint_student=js, status="approved")
        create_score(cycle=cycle, joint_student=js_high, expert=create_user(), score=Decimal("95"))
        create_score(cycle=cycle, joint_student=js_mid, expert=create_user(), score=Decimal("85"))
        create_score(cycle=cycle, joint_student=js_low, expert=create_user(), score=Decimal("70"))

        close_cycle(cycle)

        stipend_high = StipendRecord.objects.get(cycle=cycle, joint_student=js_high)
        stipend_mid = StipendRecord.objects.get(cycle=cycle, joint_student=js_mid)
        stipend_low = StipendRecord.objects.get(cycle=cycle, joint_student=js_low)
        assert stipend_high.grade == "A"
        assert stipend_mid.grade == "B"
        assert stipend_low.grade == "B"

    def test_close_skips_students_without_scores(self):
        """无打分的联培生不会产生补助记录。"""
        cycle = factory_create_cycle()
        js_with = create_joint_student()
        js_without = create_joint_student()
        create_report(joint_student=js_with, status="approved")
        create_report(joint_student=js_without, status="approved")
        create_score(cycle=cycle, joint_student=js_with, expert=create_user(), score=Decimal("90"))

        close_cycle(cycle)

        assert StipendRecord.objects.filter(cycle=cycle, joint_student=js_with).exists()
        assert not StipendRecord.objects.filter(cycle=cycle, joint_student=js_without).exists()

    def test_close_sets_stipend_status_to_pending(self):
        """新建的 StipendRecord status 默认为 pending。"""
        cycle = factory_create_cycle()
        js = create_joint_student()
        create_report(joint_student=js, status="approved")
        create_score(cycle=cycle, joint_student=js, expert=create_user(), score=Decimal("90"))

        close_cycle(cycle)

        stipend = StipendRecord.objects.get(cycle=cycle, joint_student=js)
        assert stipend.status == "pending"

    def test_close_uses_correct_base_amount_by_student_type(self):
        """硕士 3000, 博士 6000。"""
        cycle = factory_create_cycle()
        js_master = create_joint_student(student_type="master")
        js_phd = create_joint_student(student_type="phd")
        for js in [js_master, js_phd]:
            create_report(joint_student=js, status="approved")
        create_score(cycle=cycle, joint_student=js_master, expert=create_user(), score=Decimal("90"))
        create_score(cycle=cycle, joint_student=js_phd, expert=create_user(), score=Decimal("90"))

        close_cycle(cycle)

        master_stipend = StipendRecord.objects.get(cycle=cycle, joint_student=js_master)
        phd_stipend = StipendRecord.objects.get(cycle=cycle, joint_student=js_phd)
        # 2 人 → floor(2*0.4)=0 → 全部 B 档
        assert master_stipend.grade == "B"
        assert phd_stipend.grade == "B"
        assert master_stipend.base_amount == Decimal("3000.00")
        assert phd_stipend.base_amount == Decimal("6000.00")