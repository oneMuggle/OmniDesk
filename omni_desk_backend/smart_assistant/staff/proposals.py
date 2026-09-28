"""数字员工待确认事项：确认 / 取消 / 过期（S4-1）。

确认时在行锁内检查状态与有效期，再按 ``kind`` 调用执行器。执行器必须重新校验业务
前提（排班是否变化、问题是否仍归当前用户负责等），不能直接信任创建时的数据。
返回结构与 S3 确认接口一致（``answer`` / ``confirmed`` / ``write_log_id`` / ``reversible``）。
"""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from .runtime import record_event


class ProposalError(Exception):
    def __init__(self, message: str, code: str, status: int):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status = status

    def as_body(self) -> dict:
        return {"detail": self.message, "code": self.code}


class ProposalConflict(Exception):
    """执行前校验失败（业务前提已变化），事项置为 failed，接口返回 409。"""


# ---------------------------------------------------------------------------
# 执行器
# ---------------------------------------------------------------------------


def execute_swap_request(proposal, user) -> dict:
    from events.models import Schedule, ScheduleSwapRequest
    from events.services.swap_service import SwapServiceError, create_swap_for_personnel
    from personnel.models import Personnel

    fields = proposal.fields or {}
    requester = getattr(user, "personnel", None)
    if requester is None or requester.pk != fields.get("requester_personnel_id"):
        raise ProposalConflict("你的人员档案已变化，无法代为发起换班申请。")
    schedule = Schedule.objects.select_for_update().filter(pk=fields.get("schedule_id")).first()
    if schedule is None or schedule.duty_person_id != requester.pk:
        raise ProposalConflict("该排班已变化，你已不是当天的值班人员。")
    if schedule.duty_date < timezone.localdate():
        raise ProposalConflict("值班日期已过。")
    if ScheduleSwapRequest.objects.filter(
        original_schedule=schedule, status=ScheduleSwapRequest.STATUS_PENDING
    ).exists():
        raise ProposalConflict("这一天已经有待处理的换班申请。")
    target = Personnel.objects.filter(pk=fields.get("target_personnel_id"), status="active").first()
    if target is None:
        raise ProposalConflict("推荐的接替人已不可用，请在智能助手里重新发起。")
    try:
        swap = create_swap_for_personnel(
            requester=requester, target_personnel=target, original_schedule=schedule, reason=fields.get("reason", "")
        )
    except SwapServiceError as exc:
        raise ProposalConflict(exc.message) from exc
    return {
        "summary": f"已向「{target.name}」发送 {schedule.duty_date.isoformat()} 的换班申请，对方同意后生效。",
        "swap_id": swap.pk,
        "write_log_id": None,
        "reversible": False,
    }


def execute_compliance_suggestion(proposal, user) -> dict:
    from compliance.models import ComplianceIssue
    from memos.models import Memo

    from ..tools.memo_write_tools_v2 import memo_snapshot
    from ..writes.write_log import record_write
    from .roles.compliance import ACTIVE_STATUSES, issue_label, reminder_for

    fields = proposal.fields or {}
    issue = ComplianceIssue.objects.select_related("project").filter(pk=fields.get("issue_id")).first()
    if issue is None or issue.project.manager_id != user.pk:
        raise ProposalConflict("该合规问题已不存在或已不归你负责。")
    if issue.status not in ACTIVE_STATUSES:
        raise ProposalConflict(f"该合规问题当前状态为「{issue.status}」，无需再整改。")
    content = f"{issue.description[:300]}\n\n整改建议：\n{fields.get('suggestion', '')}"
    memo = Memo.objects.create(
        user=user,
        title=f"整改：{issue_label(issue)}"[:200],
        content=content,
        reminder_time=reminder_for(issue.due_date, timezone.localdate()),
    )
    log = record_write(
        {},
        user,
        tool_name="agent_staff.compliance_suggestion",
        target_model="memos.Memo",
        target_pk=memo.pk,
        operation="create",
        before=None,
        after=memo_snapshot(memo),
    )
    return {"summary": "整改建议已存为你的备忘录。", "memo_id": memo.pk, "write_log_id": log.pk, "reversible": True}


EXECUTORS = {
    "swap_request": execute_swap_request,
    "compliance_suggestion": execute_compliance_suggestion,
}


# ---------------------------------------------------------------------------
# 确认 / 取消 / 过期
# ---------------------------------------------------------------------------


def _locked(user, proposal_id):
    from smart_assistant.models import AgentProposal

    proposal = (
        AgentProposal.objects.select_for_update().select_related("profile").filter(pk=proposal_id, user=user).first()
    )
    if proposal is None:
        raise ProposalError("待确认事项不存在。", "not_found", 404)
    if proposal.status != AgentProposal.STATUS_PENDING:
        raise ProposalError(f"该事项已处理（{proposal.get_status_display()}）。", "already_decided", 409)
    return proposal


def approve(user, proposal_id) -> tuple[object, dict]:
    """确认执行，返回 ``(proposal, result)``；失败抛 ``ProposalError``。"""
    from smart_assistant.models import AgentProposal

    error = None
    with transaction.atomic():
        proposal = _locked(user, proposal_id)
        now = timezone.now()
        if proposal.expires_at <= now:
            proposal.status = AgentProposal.STATUS_EXPIRED
            proposal.decided_at = now
            proposal.save(update_fields=["status", "decided_at"])
            record_event(proposal.profile, "proposal.expired", user=user, proposal_id=proposal.pk)
            error = ProposalError("该事项已过期。", "expired", 410)
        else:
            executor = EXECUTORS.get(proposal.kind)
            try:
                if executor is None:
                    raise ProposalConflict("不支持的事项类型。")
                with transaction.atomic():
                    result = executor(proposal, user)
            except ProposalConflict as exc:
                proposal.status = AgentProposal.STATUS_FAILED
                proposal.result = {"message": str(exc)}
                error = ProposalError(str(exc), "conflict", 409)
                event = "proposal.failed"
            else:
                proposal.status = AgentProposal.STATUS_APPROVED
                proposal.result = result
                event = "proposal.approved"
            proposal.decided_at = now
            proposal.save(update_fields=["status", "result", "decided_at"])
            record_event(proposal.profile, event, user=user, proposal_id=proposal.pk, kind=proposal.kind)
    if error is not None:
        raise error
    return proposal, result


def reject(user, proposal_id):
    from smart_assistant.models import AgentProposal

    with transaction.atomic():
        proposal = _locked(user, proposal_id)
        proposal.status = AgentProposal.STATUS_REJECTED
        proposal.decided_at = timezone.now()
        proposal.save(update_fields=["status", "decided_at"])
        record_event(proposal.profile, "proposal.rejected", user=user, proposal_id=proposal.pk, kind=proposal.kind)
    return proposal


def expire_stale() -> int:
    """把已过期的待确认事项置为 expired（beat 每小时执行），返回处理数量。"""
    from smart_assistant.models import AgentProposal

    from .runtime import expire_proposal

    count = 0
    stale = AgentProposal.objects.filter(status=AgentProposal.STATUS_PENDING, expires_at__lte=timezone.now())
    for proposal in stale.select_related("profile", "user")[:500]:
        expire_proposal(proposal)
        count += 1
    return count
