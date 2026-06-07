from dataclasses import dataclass, field
from typing import Any, List, Optional
from uuid import uuid4


@dataclass(frozen=True)
class ToolContext:
    user: Any
    request_id: str = field(default_factory=lambda: str(uuid4()))
    history: Optional[List[dict]] = field(default_factory=list)

    @classmethod
    def from_request(cls, request) -> "ToolContext":
        return cls(
            user=request.user,
            request_id=getattr(request, "request_id", None) or str(uuid4()),
            history=[],
        )
