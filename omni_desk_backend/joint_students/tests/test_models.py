"""模型层测试: 验证字段约束。"""
import pytest
from django.db import IntegrityError

from joint_students.tests.factories import (
    create_cycle,
    create_joint_student,
    create_personnel,
    create_report,
    create_score,
    create_stipend,
    create_user,
)


@pytest.mark.django_db
class TestJointStudent:
    def test_unique_personnel_constraint(self):
        """OneToOne 约束: 同一 personnel 不能创建两次。"""
        p = create_personnel()
        from joint_students.models import JointStudent
        JointStudent.objects.create(
            personnel=p, student_type="master", student_id="S001",
            enrollment_date="2024-09-01",
        )
        with pytest.raises(IntegrityError):
            JointStudent.objects.create(
                personnel=p, student_type="phd", student_id="S002",
                enrollment_date="2024-09-01",
            )

    def test_student_id_unique(self):
        """student_id 全局唯一。"""
        p1 = create_personnel(name="张三")
        p2 = create_personnel(name="李四")
        from joint_students.models import JointStudent
        JointStudent.objects.create(
            personnel=p1, student_type="master", student_id="SAME001",
            enrollment_date="2024-09-01",
        )
        with pytest.raises(IntegrityError):
            JointStudent.objects.create(
                personnel=p2, student_type="master", student_id="SAME001",
                enrollment_date="2024-09-01",
            )


@pytest.mark.django_db
class TestMonthlyReport:
    def test_unique_per_month(self):
        """同一联培生同月只能一份报告。"""
        js = create_joint_student()
        create_report(joint_student=js, year=2026, month=7)
        with pytest.raises(IntegrityError):
            create_report(joint_student=js, year=2026, month=7)

    def test_different_months_allowed(self):
        """不同月份的报告可以共存。"""
        js = create_joint_student()
        r1 = create_report(joint_student=js, year=2026, month=7)
        r2 = create_report(joint_student=js, year=2026, month=8)
        assert r1.id != r2.id


@pytest.mark.django_db
class TestAssessmentCycle:
    def test_unique_per_year_month(self):
        create_cycle(year=2026, month=7)
        with pytest.raises(IntegrityError):
            create_cycle(year=2026, month=7)

    def test_different_months_allowed(self):
        c1 = create_cycle(year=2026, month=7)
        c2 = create_cycle(year=2026, month=8)
        assert c1.id != c2.id


@pytest.mark.django_db
class TestExpertScore:
    def test_unique_per_cycle_expert_student(self):
        cycle = create_cycle()
        expert = create_user(username="expert1")
        js = create_joint_student()
        create_score(cycle=cycle, expert=expert, joint_student=js)
        with pytest.raises(IntegrityError):
            create_score(cycle=cycle, expert=expert, joint_student=js)


@pytest.mark.django_db
class TestStipendRecord:
    def test_unique_per_cycle_student(self):
        cycle = create_cycle()
        js = create_joint_student()
        create_stipend(cycle=cycle, joint_student=js)
        with pytest.raises(IntegrityError):
            create_stipend(cycle=cycle, joint_student=js)
