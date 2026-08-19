import pytest

from smart_assistant.agent.native_tool_runner import execute_native_tool


def test_execute_native_tool_is_importable():
    assert callable(execute_native_tool)


def test_orchestrator_still_has_execute_native_tool_method():
    # 保持 orchestrator 公共方法存在(视图/测试可能调用)
    from smart_assistant.agent.orchestrator import AgentOrchestrator

    assert hasattr(AgentOrchestrator, "_execute_native_tool")
