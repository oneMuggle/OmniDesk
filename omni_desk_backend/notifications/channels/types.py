from dataclasses import dataclass


@dataclass(frozen=True)
class NotifyResult:
    success: bool
    message: str = ""
    notification_id: int | None = None
