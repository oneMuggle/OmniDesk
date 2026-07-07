from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from smart_assistant.scope import SmartAssistantScope, resolve_scope


@dataclass(frozen=True)
class ToolContext:
    """工具执行上下文,替代裸 dict。

    设计原则:
    - frozen=True 防误改
    - user 必填(NEW 工具要求 auth)
    - request_id 默认生成,用于日志关联
    - history 可选,工具内可读但不应改
    - scope:权限范围,默认 SELF(由 from_request 自动派生)
    """

    user: Any
    request_id: str = field(default_factory=lambda: str(uuid4()))
    history: list[dict] = field(default_factory=list)
    scope: SmartAssistantScope = SmartAssistantScope.SELF

    @classmethod
    def from_request(cls, request: Any) -> "ToolContext":
        """从 DRF Request 构造 ToolContext。

        request.user 必填(由调用方保证已认证);
        request.request_id 可选,缺失时自动生成 uuid4;
        scope 由 resolve_scope(user) 派生。
        """
        return cls(
            user=request.user,
            request_id=getattr(request, "request_id", None) or str(uuid4()),
            history=[],
            scope=resolve_scope(request.user),
        )
