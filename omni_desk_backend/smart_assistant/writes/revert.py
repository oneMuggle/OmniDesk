"""写操作撤销处理器注册表（S3-1）。

``write-logs/{id}/revert/`` 按 ``AgentWriteLog.target_model`` 找到处理器并调用
``handler.revert(log, user)``。处理器负责：加行锁定位目标、校验当前值仍等于本次
写入后的值、执行撤销并返回 ``RevertResult``；任何不满足都抛 ``RevertConflict``（409）。

处理器在调用方的保存点内执行：抛异常时它做过的修改会整体回滚。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from django.utils.module_loading import import_string


class RevertConflict(Exception):
    """无法安全撤销（目标已变化、已删除、权限已变化等）。"""

    def __init__(self, detail: str, current: Any = None):
        super().__init__(detail)
        self.detail = detail
        self.current = current


@dataclass
class RevertResult:
    #: 撤销动作本身写入 AgentWriteLog 的 operation（create / update / delete）
    operation: str
    before: dict | None
    after: dict | None
    #: 撤销后目标的主键；重建记录时是新主键
    target_pk: str


class RevertHandler(Protocol):
    def revert(self, log, user) -> RevertResult: ...


#: target_model → 处理器类的点分路径（显式登记，便于检索和测试）
REVERT_HANDLERS: dict[str, str] = {
    "memos.Memo": "smart_assistant.tools.memo_write_tools_v2.MemoRevertHandler",
    "notifications.Notification": "smart_assistant.tools.notification_write_tools.NotificationReadRevertHandler",
    "meeting_rooms.MeetingRoomBooking": "smart_assistant.tools.meeting_room_write_tools.BookingRevertHandler",
    "compliance.ComplianceIssue": "smart_assistant.tools.compliance_write_tools.ComplianceStatusRevertHandler",
    "events.Announcement": "smart_assistant.tools.announcement_write_tools.AnnouncementDraftRevertHandler",
    "events.Trial": "smart_assistant.tools.trial_write_tools.TrialCreateRevertHandler",
}


def get_revert_handler(target_model: str) -> RevertHandler | None:
    path = REVERT_HANDLERS.get(target_model)
    if not path:
        return None
    return import_string(path)()
