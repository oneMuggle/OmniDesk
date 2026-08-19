"""Task 5 — tool_chain_runner.process_chain 轻量冒烟.

R3-A1 拆分:orchestrator._process_chain 提取为 tool_chain_runner.process_chain,
orchestrator 保留同名薄委托方法。行为零变化。
"""

from smart_assistant.agent.tool_chain_runner import process_chain


def test_process_chain_is_importable():
    assert callable(process_chain)


def test_orchestrator_keeps_process_chain_method():
    from smart_assistant.agent.orchestrator import AgentOrchestrator

    assert hasattr(AgentOrchestrator, "_process_chain")
