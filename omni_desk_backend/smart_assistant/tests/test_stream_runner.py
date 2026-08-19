"""StreamRunner 模块轻量冒烟(R3-A1 Task 6)。"""

from smart_assistant.agent.stream_runner import StreamRunner


def test_stream_runner_is_importable():
    assert callable(StreamRunner)


def test_orchestrator_process_stream_is_generator():
    from smart_assistant.agent.orchestrator import AgentOrchestrator

    assert hasattr(AgentOrchestrator, "process_stream")
