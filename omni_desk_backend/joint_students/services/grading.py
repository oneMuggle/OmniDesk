"""A 档名额优先算法 (名额硬限制 ≤ 40%)。"""

import logging
import math
from decimal import Decimal

from django.db.models import Avg

from joint_students.models import AssessmentCycle, ExpertScore, MonthlyReport

logger = logging.getLogger(__name__)


def assign_grades(cycle: AssessmentCycle) -> list[dict]:
    """根据专家打分的均分给本月联培生分 A/B 档。

    Args:
        cycle: 本月考核批次。

    Returns:
        列表, 每项: {js_id, rank, grade, avg_score}。
        - grade: 'A' (前 40%) 或 'B' (其余)
        - 联培生 < 3 人 → 全部 B
        - 无打分的联培生跳过
        - 同分时按 joint_student.id 升序稳定排序
    """
    # 1. 找本月所有已审核通过的月度报告对应的联培生
    approved_student_ids = (
        MonthlyReport.objects.filter(year=cycle.year, month=cycle.month, status=MonthlyReport.STATUS_APPROVED)
        .values_list("joint_student_id", flat=True)
        .distinct()
    )

    # 2. 计算每位联培生的专家均分
    student_scores: list[tuple[int, Decimal]] = []
    for js_id in approved_student_ids:
        avg = ExpertScore.objects.filter(
            cycle=cycle,
            joint_student_id=js_id,
        ).aggregate(avg=Avg("score"))["avg"]
        if avg is None:
            continue
        student_scores.append((js_id, Decimal(avg).quantize(Decimal("0.01"))))

    if not student_scores:
        return []

    # 3. 按分数降序排序 (同分按 ID 升序稳定排序)
    student_scores.sort(key=lambda x: (-x[1], x[0]))

    # 4. 前 40% 为 A 档 (向下取整, < 3 全 B)
    total = len(student_scores)
    a_count = math.floor(total * 0.4)

    records = []
    for rank, (js_id, avg_score) in enumerate(student_scores, start=1):
        grade = "A" if rank <= a_count else "B"
        records.append(
            {
                "js_id": js_id,
                "rank": rank,
                "grade": grade,
                "avg_score": avg_score,
            }
        )

    if a_count == 0 and total > 0:
        logger.info(f"周期 {cycle.year}-{cycle.month:02d} 总人数 {total} < 3, 全部 B 档")

    return records
