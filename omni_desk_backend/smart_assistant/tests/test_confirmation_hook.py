"""ConfirmationHook 单元测试(I-1)。

验证:
- require_confirmation=True 的写工具 → Reject(error_code="confirmation_required")
- require_confirmation=False 的 read 工具 → 原样返回 params(放行)
- 经 apply_pre_execute_hooks 真实链路生效(非直调 hook)
"""

import pytest

from smart_assistant.hooks.base import HookEvent, Reject, get_registry
from smart_assistant.hooks.builtin.confirmation import ConfirmationHook
from smart_assistant.hooks.wiring import apply_pre_execute_hooks
from smart_assistant.tools.base import BaseTool


@pytest.fixture(autouse=True)
def _clean_registry():
    get_registry(reset=True)
    yield
    get_registry(reset=True)


class _WriteTool(BaseTool):
    name = "test_write_tool"
    risk_level = "write"
    require_confirmation = True

    def execute(self, query=None, context=None, **kwargs):
        return {"found": True, "result": "executed"}


class _ReadTool(BaseTool):
    name = "test_read_tool"
    risk_level = "read"
    require_confirmation = False

    def execute(self, query=None, context=None, **kwargs):
        return {"found": True, "result": "read"}


class _Ctx:
    user = None


@pytest.mark.django_db
class TestConfirmationHook:
    def test_write_tool_rejected(self):
        """写工具 → Reject(error_code=confirmation_required)"""
        get_registry().register(HookEvent.PRE_EXECUTE, ConfirmationHook(), priority=20)
        result = apply_pre_execute_hooks(_WriteTool(), _Ctx(), {"query": "生成"})
        assert isinstance(result, Reject)
        assert result.error_code == "confirmation_required"

    def test_read_tool_passthrough(self):
        """read 工具 → 原样返回 params"""
        get_registry().register(HookEvent.PRE_EXECUTE, ConfirmationHook(), priority=20)
        params = {"query": "查一下"}
        result = apply_pre_execute_hooks(_ReadTool(), _Ctx(), params)
        assert result == params
