import pytest

from smart_assistant.agent.orchestrator import AgentOrchestrator


def test_legacy_process_has_decomposed_helpers():
    assert hasattr(AgentOrchestrator, "_classify_legacy_intent")
    assert hasattr(AgentOrchestrator, "_legacy_single_tool")
