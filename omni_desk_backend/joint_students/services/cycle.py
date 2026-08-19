"""考核批次生命周期管理。"""
import logging
from datetime import date

from django.contrib.auth.models import Group

from joint_students.models import (
    AssessmentCycle,
    MonthlyReport,
    StipendRecord,
)
from notifications.models import Notification
from joint_students.services.grading import assign_grades
from joint_students.services.stipend import (
    BASE_AMOUNT_MASTER,
    BASE_AMOUNT_PHD,
    GRADE_COEFFICIENT_A,
    GRADE_COEFFICIENT_B,
    compute_attendance_ratio,
    compute_stipend_amount,
)

logger = logging.getLogger(__name__)


def notify_experts(cycle: AssessmentCycle) -> None:
    """批次创建后, 通知 考核专家组 成员。"""
    experts = Group.objects.filter(name="考核专家组").first()
    if not experts:
        logger.warning("考核专家组 不存在, 跳过通知")
        return
    # CustomUser.groups 显式设置 related_name='custom_user_groups', 故反向访问器为 custom_user_groups
    for user in experts.custom_user_groups.all():
        Notification.objects.create(
            user=user,
            type="assessment_cycle_started",
            title=f"{cycle.year}-{cycle.month:02d} 考核批次已发起",
            content=f"请于 {cycle.scoring_deadline} 前完成对本月联培生的打分",
            link=f"/joint-students/expert/scoring?cycle={cycle.id}",
        )


def notify_managers_to_review_stipends(cycle: AssessmentCycle) -> None:
    """批次截止后, 通知联培生管理员复核补助。"""
    managers = Group.objects.filter(name="联培生管理员").first()
    if not managers:
        logger.warning("联培生管理员 组不存在, 跳过通知")
        return
    # CustomUser.groups 显式设置 related_name='custom_user_groups', 故反向访问器为 custom_user_groups
    for user in managers.custom_user_groups.all():
        Notification.objects.create(
            user=user,
            type="stipend_review_required",
            title=f"{cycle.year}-{cycle.month:02d} 补助待复核",
            content="请进入补助复核页面确认本月补助明细",
            link=f"/joint-students/admin/stipends?cycle={cycle.id}",
        )


def create_cycle(
    year: int,
    month: int,
    trigger_source: str = AssessmentCycle.TRIGGER_AUTO,
    creator=None,
    **overrides,
) -> AssessmentCycle:
    """幂等创建考核批次。

    同一 (year, month) 仅创建一条 AssessmentCycle (数据库唯一约束保证)。
    仅在首次创建时通知 考核专家组, 重复调用无副作用。

    Args:
        year: 年份。
        month: 月份 (1-12)。
        trigger_source: 触发来源 (auto/manual), 默认 auto (Celery 触发)。
        creator: 创建人 (User 实例), 可为 None (Celery 自动触发)。
        **overrides: 额外字段覆盖, 支持 status= 和 created_by= 别名。

    Returns:
        已存在的或新建的 AssessmentCycle。
    """
    # 兼容测试/调用方的 kwargs 别名: created_by= → creator=, status= → status=
    if creator is None:
        creator = overrides.pop("created_by", None)
    status = overrides.pop("status", AssessmentCycle.STATUS_COLLECTING)

    defaults = {
        "cycle_start_date": date(year, month, 1),
        "cycle_end_date": date(year, month, 25),
        "scoring_deadline": date(year, month, 28),
        "status": status,
        "trigger_source": trigger_source,
        "created_by": creator,
    }
    # 其余 overrides 允许覆盖默认值 (例如 cycle_start_date)
    defaults.update(overrides)

    cycle, created = AssessmentCycle.objects.get_or_create(
        year=year,
        month=month,
        defaults=defaults,
    )
    if created:
        logger.info(f"周期 {year}-{month:02d} 创建成功 (id={cycle.id})")
        notify_experts(cycle)
    else:
        logger.info(f"周期 {year}-{month:02d} 已存在 (id={cycle.id}), 跳过")
    return cycle


def close_cycle(cycle: AssessmentCycle) -> None:
    """批次截止: 算 grade + 创建 StipendRecord (status=pending) + 通知管理员复核。

    执行步骤:
    1. 将 cycle.status 置为 closed 并保存。
    2. 调用 assign_grades 计算所有有打分的联培生的 A/B 档。
    3. 为每个档位记录创建 StipendRecord (status=pending, 待管理员复核)。
    4. 通知 联培生管理员 进入补助复核页面。
    """
    cycle.status = AssessmentCycle.STATUS_CLOSED
    cycle.save(update_fields=["status"])

    grade_records = assign_grades(cycle)
    if not grade_records:
        logger.warning(f"周期 {cycle.year}-{cycle.month:02d} 无任何打分记录, 无补助生成")
        return

    # 循环内 import 避免循环依赖 (JointStudent 与 grading 的潜在关联)
    from joint_students.models import JointStudent

    for gr in grade_records:
        js = JointStudent.objects.get(id=gr["js_id"])
        report = MonthlyReport.objects.get(
            joint_student=js,
            year=cycle.year,
            month=cycle.month,
        )
        final_amount = compute_stipend_amount(
            js,
            gr["grade"],
            report.attendance_days_actual,
            report.attendance_days_expected,
        )
        StipendRecord.objects.create(
            cycle=cycle,
            joint_student=js,
            average_score=gr["avg_score"],
            rank_in_cycle=gr["rank"],
            grade=gr["grade"],
            base_amount=(
                BASE_AMOUNT_MASTER
                if js.student_type == JointStudent.STUDENT_TYPE_MASTER
                else BASE_AMOUNT_PHD
            ),
            grade_coefficient=(
                GRADE_COEFFICIENT_A
                if gr["grade"] == "A"
                else GRADE_COEFFICIENT_B
            ),
            attendance_ratio=compute_attendance_ratio(
                report.attendance_days_actual,
                report.attendance_days_expected,
            ),
            final_amount=final_amount,
            status=StipendRecord.STATUS_PENDING,
        )

    notify_managers_to_review_stipends(cycle)
