"""A 档名额优先算法测试。"""
import itertools
from datetime import date
from decimal import Decimal

import pytest

from joint_students.services.grading import assign_grades
from joint_students.tests.factories import (
    create_cycle,
    create_joint_student,
    create_report,
    create_score,
    create_user,
)


# 测试模块内单调递增计数器, 保证每个 expert user username 唯一 (避免 UNIQUE 约束冲突)
_expert_username_counter = itertools.count()


def _setup_cycle_with_students(n, scores):
    """创建 cycle + n 个联培生 + 每个联培生指定分数的 expert score。
    scores: list of decimal, 与 n 个联培生一一对应。
    """
    cycle = create_cycle()
    js_list = [create_joint_student() for _ in range(n)]
    for js, s in zip(js_list, scores):
        create_report(joint_student=js, year=2026, month=7, status="approved")
        username = f"expert_{next(_expert_username_counter)}"
        create_score(cycle=cycle, joint_student=js, expert=create_user(username=username), score=s)
    return cycle, js_list


@pytest.mark.django_db
class TestAssignGrades:
    def test_assign_grades_basic_10_students(self):
        """10 人 → 4 A 6 B (40% 向下取整)。"""
        scores = [Decimal(str(x)) for x in [98, 95, 92, 88, 86, 82, 80, 78, 75, 70]]
        cycle, js_list = _setup_cycle_with_students(10, scores)
        result = assign_grades(cycle)
        grades = {r["js_id"]: r["grade"] for r in result}
        # 前 4 名 → A 档
        for i in range(4):
            assert grades[js_list[i].id] == "A", f"rank {i+1} 应为 A"
        # 后 6 名 → B 档
        for i in range(4, 10):
            assert grades[js_list[i].id] == "B", f"rank {i+1} 应为 B"

    def test_assign_grades_all_above_90_still_capped_at_40(self):
        """即使所有分数 ≥90, 名额硬限制仍生效。"""
        scores = [Decimal("95")] * 10
        cycle, js_list = _setup_cycle_with_students(10, scores)
        result = assign_grades(cycle)
        a_count = sum(1 for r in result if r["grade"] == "A")
        b_count = sum(1 for r in result if r["grade"] == "B")
        assert a_count == 4
        assert b_count == 6

    def test_assign_grades_below_3_all_b(self):
        """< 3 人全部 B 档 (避免单人硬升 A)。"""
        scores = [Decimal("95"), Decimal("90")]
        cycle, js_list = _setup_cycle_with_students(2, scores)
        result = assign_grades(cycle)
        assert all(r["grade"] == "B" for r in result)

    def test_assign_grades_exactly_3_one_a(self):
        """3 人 → 1 A 2 B。"""
        scores = [Decimal("95"), Decimal("88"), Decimal("80")]
        cycle, js_list = _setup_cycle_with_students(3, scores)
        result = assign_grades(cycle)
        a_count = sum(1 for r in result if r["grade"] == "A")
        assert a_count == 1
        # 最高分应为 A 档
        a_record = next(r for r in result if r["grade"] == "A")
        assert a_record["avg_score"] == Decimal("95")

    def test_assign_grades_tie_breaking_by_id(self):
        """同分时按 joint_student.id 升序稳定排序。"""
        scores = [Decimal("90"), Decimal("90"), Decimal("90"), Decimal("80")]
        cycle, js_list = _setup_cycle_with_students(4, scores)
        result = assign_grades(cycle)
        a_records = [r for r in result if r["grade"] == "A"]
        # 4 人 → 1 A 档 (floor(4*0.4)=1)，最低 ID 的同分者应优先 A 档
        assert len(a_records) == 1
        expected_a_id = min(js_list[i].id for i in range(3))  # 前 3 个同分中 ID 最小的
        assert a_records[0]["js_id"] == expected_a_id

    def test_assign_grades_no_scores_skipped(self):
        """无专家打分的联培生不参与 A/B 档分配。"""
        cycle = create_cycle()
        js_with_score = create_joint_student()
        js_without_score = create_joint_student()
        create_report(joint_student=js_with_score, status="approved")
        create_report(joint_student=js_without_score, status="approved")
        create_score(cycle=cycle, joint_student=js_with_score, expert=create_user(), score=Decimal("90"))
        result = assign_grades(cycle)
        assert len(result) == 1
        assert result[0]["js_id"] == js_with_score.id

    def test_assign_grades_returns_rank(self):
        """返回的 rank 从 1 开始递增。"""
        scores = [Decimal("95"), Decimal("88"), Decimal("80")]
        cycle, _ = _setup_cycle_with_students(3, scores)
        result = assign_grades(cycle)
        ranks = sorted(r["rank"] for r in result)
        assert ranks == [1, 2, 3]
