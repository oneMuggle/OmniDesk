"""补助计算公式。

final_amount = base_amount × grade_coefficient × attendance_ratio
"""
from decimal import Decimal

from joint_students.models import JointStudent, StipendRecord

BASE_AMOUNT_MASTER = Decimal("3000.00")
BASE_AMOUNT_PHD = Decimal("6000.00")

GRADE_COEFFICIENT_A = Decimal("1.00")
GRADE_COEFFICIENT_B = Decimal("0.80")


def compute_attendance_ratio(actual: Decimal, expected: Decimal) -> Decimal:
    """计算出勤比，最高为 1.0；应出勤不大于 0 时按满勤处理。"""
    if expected <= 0:
        return Decimal("1.00")

    return min(Decimal(actual) / Decimal(expected), Decimal("1.00"))


def compute_stipend_amount(
    js: JointStudent,
    grade: str,
    attendance_actual: Decimal,
    attendance_expected: Decimal,
) -> Decimal:
    """根据培养类型、档次和出勤情况计算最终补助金额。"""
    base_amount = (
        BASE_AMOUNT_MASTER
        if js.student_type == JointStudent.STUDENT_TYPE_MASTER
        else BASE_AMOUNT_PHD
    )
    grade_coefficient = (
        GRADE_COEFFICIENT_A if grade == StipendRecord.GRADE_A else GRADE_COEFFICIENT_B
    )
    attendance_ratio = compute_attendance_ratio(attendance_actual, attendance_expected)
    return (base_amount * grade_coefficient * attendance_ratio).quantize(Decimal("0.01"))
