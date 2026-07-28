"""测试用工厂函数。"""
from datetime import date
from decimal import Decimal

from personnel.models import Personnel
from users.models import CustomUser

from joint_students.models import (
    AssessmentCycle,
    ExpertScore,
    JointStudent,
    MonthlyReport,
    StipendRecord,
)


def create_personnel(name="测试人员", **kwargs) -> Personnel:
    defaults = {
        "name": name,
        "hire_date": date(2024, 1, 1),
        "department": "测试部",
        "status": "active",
    }
    defaults.update(kwargs)
    return Personnel.objects.create(**defaults)


def create_user(username="testuser", is_superuser=False, **kwargs) -> CustomUser:
    defaults = {
        "username": username,
        "is_superuser": is_superuser,
        "is_staff": is_superuser,
        "email": f"{username}@example.com",
    }
    defaults.update(kwargs)
    return CustomUser.objects.create(**defaults)


def create_joint_student(personnel=None, student_type="master", mentor=None, **kwargs) -> JointStudent:
    if personnel is None:
        personnel = create_personnel()
    defaults = {
        "personnel": personnel,
        "student_type": student_type,
        "student_id": f"S{personnel.id:08d}",
        "enrollment_date": date(2024, 9, 1),
        "mentor": mentor,
        "is_active": True,
    }
    defaults.update(kwargs)
    return JointStudent.objects.create(**defaults)


def create_cycle(year=2026, month=7, **kwargs) -> AssessmentCycle:
    defaults = {
        "year": year,
        "month": month,
        "cycle_start_date": date(year, month, 1),
        "cycle_end_date": date(year, month, 25),
        "scoring_deadline": date(year, month, 28),
        "status": "collecting",
        "trigger_source": "manual",
    }
    defaults.update(kwargs)
    return AssessmentCycle.objects.create(**defaults)


def create_report(joint_student=None, year=2026, month=7, status="draft", **kwargs) -> MonthlyReport:
    if joint_student is None:
        joint_student = create_joint_student()
    defaults = {
        "joint_student": joint_student,
        "year": year,
        "month": month,
        "work_progress": "本月完成了 X 工作",
        "work_highlights": "亮点 Y",
        "attendance_days_actual": Decimal("22.0"),
        "attendance_days_expected": Decimal("22.0"),
        "status": status,
    }
    defaults.update(kwargs)
    return MonthlyReport.objects.create(**defaults)


def create_score(cycle=None, expert=None, joint_student=None, score=Decimal("85.0"), **kwargs) -> ExpertScore:
    defaults = {
        "cycle": cycle,
        "expert": expert,
        "joint_student": joint_student,
        "score": score,
        "submitted_at": date(2026, 7, 26),
        "is_locked": True,
    }
    defaults.update(kwargs)
    return ExpertScore.objects.create(**defaults)


def create_stipend(cycle=None, joint_student=None, grade="B", **kwargs) -> StipendRecord:
    defaults = {
        "cycle": cycle,
        "joint_student": joint_student,
        "average_score": Decimal("85.0"),
        "rank_in_cycle": 1,
        "grade": grade,
        "base_amount": Decimal("3000.00"),
        "grade_coefficient": Decimal("0.80"),
        "attendance_ratio": Decimal("1.00"),
        "final_amount": Decimal("2400.00"),
        "status": "pending",
    }
    defaults.update(kwargs)
    return StipendRecord.objects.create(**defaults)
