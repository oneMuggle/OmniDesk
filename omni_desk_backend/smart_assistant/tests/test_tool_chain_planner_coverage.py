"""Tests for smart_assistant.agent.tool_chain_planner — 换班关键词覆盖(P0-1).

目标:验证 ``_matches_intent`` 的 intent_keywords 覆盖换班三分支,
使 tool_chain_planner 能识别"换班/替班/调班"相关查询(llm-swap-shift Phase 2)。
"""

from smart_assistant.agent.tool_chain_planner import _matches_intent


def _schema(name: str) -> dict:
    return {"name": name, "description": name}


class TestSwapKeywordMatching:
    """_matches_intent 对换班三分支的关键词命中."""

    def test_create_matches_huanban(self):
        assert _matches_intent("我想和李四换班", _schema("swap_request_create")) is True

    def test_create_matches_tiban(self):
        assert _matches_intent("明天能帮我替班吗", _schema("swap_request_create")) is True

    def test_create_matches_tiaoban(self):
        assert _matches_intent("申请调班", _schema("swap_request_create")) is True

    def test_decide_matches_accept(self):
        assert _matches_intent("同意换班", _schema("swap_request_decide")) is True

    def test_decide_matches_reject(self):
        assert _matches_intent("拒绝换班", _schema("swap_request_decide")) is True

    def test_query_matches_received(self):
        assert _matches_intent("我收到的换班申请", _schema("swap_request_query")) is True

    def test_query_matches_progress(self):
        assert _matches_intent("换班进度怎么样了", _schema("swap_request_query")) is True

    def test_unrelated_query_does_not_match_create(self):
        """与换班无关的查询不应命中 create(避免误触发)."""
        assert _matches_intent("今天谁值班", _schema("swap_request_create")) is False

    def test_swap_intent_not_matched_by_schedule_schema(self):
        """换班关键词不应错误命中 schedule_query 的关键词表."""
        # schedule_query 关键词为 排班/值班 等;"换班"不在其中
        assert _matches_intent("我想换班", _schema("schedule_query")) is False
