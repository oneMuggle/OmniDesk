"""补助计算公式测试。"""
from decimal import Decimal

import pytest

from joint_students.services.stipend import compute_attendance_ratio, compute_stipend_amount
from joint_students.tests.factories import create_joint_student


@pytest.mark.django_db
class TestComputeStipendAmount:
    def test_master_a_full_attendance(self):
        """硕士 A 档 全勤: 3000 × 1.00 × 1.0 = 3000.00"""
        js = create_joint_student(student_type="master")
        result = compute_stipend_amount(js, "A", Decimal("22"), Decimal("22"))
        assert result == Decimal("3000.00")

    def test_master_b_full_attendance(self):
        """硕士 B 档 全勤: 3000 × 0.80 × 1.0 = 2400.00"""
        js = create_joint_student(student_type="master")
        result = compute_stipend_amount(js, "B", Decimal("22"), Decimal("22"))
        assert result == Decimal("2400.00")

    def test_phd_a_full_attendance(self):
        """博士 A 档 全勤: 6000 × 1.00 × 1.0 = 6000.00"""
        js = create_joint_student(student_type="phd")
        result = compute_stipend_amount(js, "A", Decimal("22"), Decimal("22"))
        assert result == Decimal("6000.00")

    def test_phd_b_partial_attendance(self):
        """博士 B 档 出勤 11/22 (50%): 6000 × 0.80 × 0.5 = 2400.00"""
        js = create_joint_student(student_type="phd")
        result = compute_stipend_amount(js, "B", Decimal("11"), Decimal("22"))
        assert result == Decimal("2400.00")

    def test_master_a_partial_attendance(self):
        """硕士 A 档 出勤 10/22: 3000 × 1.00 × (10/22) = 1363.64"""
        js = create_joint_student(student_type="master")
        result = compute_stipend_amount(js, "A", Decimal("10"), Decimal("22"))
        assert result == Decimal("1363.64")

    def test_attendance_over_expected_capped_at_1(self):
        """出勤 > 应出勤 → ratio 限制为 1.0"""
        js = create_joint_student(student_type="master")
        result = compute_stipend_amount(js, "A", Decimal("30"), Decimal("22"))
        assert result == Decimal("3000.00")  # 不会因为超勤变 4090.91

    def test_zero_expected_attendance_defensive(self):
        """应出勤 0 → ratio = 1.0 (防御, 按满勤)"""
        js = create_joint_student(student_type="master")
        result = compute_stipend_amount(js, "A", Decimal("0"), Decimal("0"))
        assert result == Decimal("3000.00")


@pytest.mark.django_db
class TestComputeAttendanceRatio:
    def test_normal_case(self):
        assert compute_attendance_ratio(Decimal("11"), Decimal("22")) == Decimal("0.50")

    def test_capped_at_one(self):
        assert compute_attendance_ratio(Decimal("30"), Decimal("22")) == Decimal("1.00")

    def test_zero_expected_returns_one(self):
        assert compute_attendance_ratio(Decimal("0"), Decimal("0")) == Decimal("1.00")

    def test_negative_expected_returns_one(self):
        assert compute_attendance_ratio(Decimal("0"), Decimal("-1")) == Decimal("1.00")
