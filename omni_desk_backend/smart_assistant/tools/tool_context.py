from dataclasses import dataclass, field
from typing import Any, List
from uuid import uuid4


@dataclass(frozen=True)
class ToolContext:
    """工具执行上下文,替代裸 dict。

    设计原则:
    - frozen=True 防误改
    - user 必填(NEW 工具要求 auth)
    - request_id 默认生成,用于日志关联
    - history 可选,工具内可读但不应改
    """
    user: Any
    request_id: str = field(default_factory=lambda: str(uuid4()))
    history: List[dict] = field(default_factory=list)

    @classmethod
    def from_request(cls, request: Any) -> "ToolContext":
        """从 DRF Request 构造 ToolContext。

        request.user 必填(由调用方保证已认证);
        request.request_id 可选,缺失时自动生成 uuid4。
        """
        return cls(
            user=request.user,
            request_id=getattr(request, "request_id", None) or str(uuid4()),
            history=[],
        )
