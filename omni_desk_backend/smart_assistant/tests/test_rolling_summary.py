"""任务 3(P1):启用滚动摘要。

覆盖:
- build_effective_history:有摘要时以「摘要 + 最近消息」代替全量历史
- truncate_to_recent_turns:按轮截断
- generate_rolling_summary:LLM 生成摘要;异常/失败响应时返回 None(静默降级)
- apply_rolling_summary:超阈值时写摘要并截断 messages;失败时保留全量
- view 层集成:长会话触发摘要与截断;摘要失败不影响主对话;
  有摘要的会话以摘要历史送入 orchestrator
- 失败退避(修复「重试风暴」):失败后写按会话隔离的退避标记,
  退避期内不再调用 LLM;退避过期(或手动清除)后恢复尝试;成功清除标记
"""

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from smart_assistant.agent.conversation_context import (
    RECENT_TURNS_SOFT,
    apply_rolling_summary,
    build_effective_history,
    clear_summary_backoff,
    generate_rolling_summary,
    is_summary_in_backoff,
    mark_summary_backoff,
    should_summarize,
    truncate_to_recent_turns,
)
from smart_assistant.models import SmartAssistantSession


def _long_history(turns=8, filler="历史对话内容" * 100):
    """构造长对话历史。每条 600+ 汉字 ≈ 400 token,8 轮 ≈ 6400 token > SOFT_TOKEN_LIMIT。"""
    msgs = []
    for i in range(turns):
        msgs.append({"role": "user", "content": f"{filler} 问{i}"})
        msgs.append({"role": "assistant", "content": f"{filler} 答{i}"})
    return msgs


def _fake_session(messages, summary_text=""):
    """构造鸭子类型的 session 对象(apply_rolling_summary 只读写属性,不 save)。"""
    return SimpleNamespace(
        messages=messages,
        summary_text=summary_text,
        summary_token_count=None,
        turn_count=sum(1 for m in messages if m.get("role") == "user"),
    )


# =============================================================================
# 纯函数:历史构造与截断
# =============================================================================


class TestBuildEffectiveHistory:
    def test_without_summary_returns_full_history(self):
        """无摘要时返回全量历史。"""
        history = _long_history(3)
        effective = build_effective_history(history, summary_text="")
        assert effective == history

    def test_with_summary_returns_summary_plus_recent(self):
        """有摘要时返回 system 摘要消息 + 最近 N 轮。"""
        history = _long_history(8)
        effective = build_effective_history(history, summary_text="既有摘要")

        assert effective[0]["role"] == "system"
        assert "既有摘要" in effective[0]["content"]
        # 摘要 + 最近 RECENT_TURNS_SOFT 轮
        assert len(effective) == 1 + RECENT_TURNS_SOFT * 2
        # 最近消息来自原历史末尾
        assert effective[-1] == history[-1]

    def test_empty_messages_with_summary(self):
        """空历史 + 摘要时仅返回摘要消息。"""
        effective = build_effective_history([], summary_text="摘要")
        assert len(effective) == 1
        assert effective[0]["role"] == "system"


class TestTruncateToRecentTurns:
    def test_truncates_to_n_turns(self):
        history = _long_history(8)
        recent = truncate_to_recent_turns(history, recent_turns=3)
        assert len(recent) == 6
        assert recent == history[-6:]

    def test_short_history_unchanged(self):
        history = _long_history(2)
        assert truncate_to_recent_turns(history) == history


# =============================================================================
# 摘要生成与降级
# =============================================================================


class TestGenerateRollingSummary:
    @patch("llm_service.router.get_router")
    def test_success_returns_summary(self, mock_get_router):
        mock_get_router.return_value.generate.return_value = ("摘要正文", None)
        assert generate_rolling_summary(_long_history(2)) == "摘要正文"

    @patch("llm_service.router.get_router")
    def test_exception_returns_none_silently(self, mock_get_router):
        """LLM 异常时返回 None,不抛出(静默降级)。"""
        mock_get_router.return_value.generate.side_effect = Exception("LLM 不可用")
        assert generate_rolling_summary(_long_history(2)) is None

    @patch("llm_service.router.get_router")
    def test_failed_answer_returns_none(self, mock_get_router):
        """LLM 返回失败响应时视为降级,返回 None。"""
        mock_get_router.return_value.generate.return_value = ("回答生成失败: 超时", None)
        assert generate_rolling_summary(_long_history(2)) is None

    def test_empty_messages_returns_none(self):
        assert generate_rolling_summary([]) is None


class TestApplyRollingSummary:
    @patch("llm_service.router.get_router")
    def test_long_session_summarized_and_truncated(self, mock_get_router):
        """超阈值会话:写入摘要、截断为最近 N 轮、同步 token/轮数统计。"""
        mock_get_router.return_value.generate.return_value = ("早期对话摘要", None)
        session = _fake_session(_long_history(8))

        changed = apply_rolling_summary(session)

        assert changed is True
        assert session.summary_text == "早期对话摘要"
        assert session.summary_token_count > 0
        assert len(session.messages) == RECENT_TURNS_SOFT * 2
        assert session.turn_count == RECENT_TURNS_SOFT

    @patch("llm_service.router.get_router")
    def test_summary_failure_keeps_full_history(self, mock_get_router):
        """摘要失败时静默降级:session 保持全量历史。"""
        mock_get_router.return_value.generate.side_effect = Exception("LLM 不可用")
        history = _long_history(8)
        session = _fake_session(history)

        changed = apply_rolling_summary(session)

        assert changed is False
        assert session.summary_text == ""
        assert session.messages == history

    @patch("llm_service.router.get_router")
    def test_short_session_not_summarized(self, mock_get_router):
        """未超阈值时不触发摘要,不调用 LLM。"""
        session = _fake_session(_long_history(2, filler="短"))

        changed = apply_rolling_summary(session)

        assert changed is False
        mock_get_router.assert_not_called()

    @patch("llm_service.router.get_router")
    def test_existing_summary_skips(self, mock_get_router):
        """已有摘要时不再重复生成。"""
        session = _fake_session(_long_history(8), summary_text="已有摘要")

        changed = apply_rolling_summary(session)

        assert changed is False
        assert len(session.messages) == 16
        mock_get_router.assert_not_called()


# =============================================================================
# view 层集成
# =============================================================================


@pytest.mark.django_db
class TestViewRollingSummary:
    """POST /api/smart-assistant/chat/ 的滚动摘要集成行为。"""

    @patch("smart_assistant.views.chat.AgentOrchestrator")
    def test_chat_triggers_summary_and_truncates(self, mock_cls, admin_client, admin_user_obj, mock_llm_router):
        """长会话新一轮后触发摘要:summary_text 写入,messages 截断。"""
        mock_llm_router.generate.return_value = ("这是早期对话的摘要", None)
        session = SmartAssistantSession.objects.create(
            user=admin_user_obj,
            title="长会话",
            messages=_long_history(8),
            turn_count=8,
        )
        mock_cls.return_value.process.return_value = {
            "answer": "新回答",
            "intent": "general_chat",
            "tool_used": None,
            "tool_result": None,
            "sources": None,
            "usage": None,
            "error": False,
        }

        resp = admin_client.post(
            "/api/smart-assistant/chat/",
            {"query": "新问题", "conversation_id": session.id},
            format="json",
        )

        assert resp.status_code == 200
        session.refresh_from_db()
        assert session.summary_text == "这是早期对话的摘要"
        assert session.summary_token_count > 0
        assert len(session.messages) == RECENT_TURNS_SOFT * 2
        assert session.turn_count == RECENT_TURNS_SOFT
        # 最近消息包含本轮新对话
        assert session.messages[-2]["content"] == "新问题"
        assert session.messages[-1]["content"] == "新回答"

    @patch("smart_assistant.views.chat.AgentOrchestrator")
    def test_summary_failure_does_not_break_chat(self, mock_cls, admin_client, admin_user_obj, mock_llm_router):
        """摘要生成失败:主对话正常返回,历史保留全量。"""
        mock_llm_router.generate.side_effect = Exception("LLM 不可用")
        session = SmartAssistantSession.objects.create(
            user=admin_user_obj,
            title="长会话",
            messages=_long_history(8),
            turn_count=8,
        )
        mock_cls.return_value.process.return_value = {
            "answer": "正常回答",
            "intent": "general_chat",
            "tool_used": None,
            "tool_result": None,
            "sources": None,
            "usage": None,
            "error": False,
        }

        resp = admin_client.post(
            "/api/smart-assistant/chat/",
            {"query": "新问题", "conversation_id": session.id},
            format="json",
        )

        assert resp.status_code == 200
        assert resp.json()["error"] is False
        session.refresh_from_db()
        assert session.summary_text == ""
        # 全量保留:原 16 条 + 本轮 2 条
        assert len(session.messages) == 18
        assert session.turn_count == 9

    @patch("smart_assistant.views.chat.AgentOrchestrator")
    def test_session_with_summary_sends_summary_history(self, mock_cls, admin_client, admin_user_obj):
        """有摘要的会话:送入 orchestrator 的历史为「摘要 + 最近消息」。"""
        session = SmartAssistantSession.objects.create(
            user=admin_user_obj,
            title="有摘要的会话",
            messages=_long_history(8),
            turn_count=8,
            summary_text="既有摘要",
        )
        mock_cls.return_value.process.return_value = {
            "answer": "回答",
            "intent": "general_chat",
            "tool_used": None,
            "tool_result": None,
            "sources": None,
            "usage": None,
            "error": False,
        }

        resp = admin_client.post(
            "/api/smart-assistant/chat/",
            {"query": "新问题", "conversation_id": session.id},
            format="json",
        )

        assert resp.status_code == 200
        args, _ = mock_cls.return_value.process.call_args
        history = args[1]
        assert history[0]["role"] == "system"
        assert "既有摘要" in history[0]["content"]
        assert len(history) == 1 + RECENT_TURNS_SOFT * 2


# =============================================================================
# 失败退避(修复 2 — HIGH:滚动摘要失败重试风暴)
# =============================================================================


def _fake_session_with_pk(messages, pk, summary_text=""):
    """带主键的鸭子类型 session(pk 是退避标记的隔离维度)。"""
    session = _fake_session(messages, summary_text=summary_text)
    session.pk = pk
    return session


class TestSummaryBackoff:
    """LLM 摘要失败后的退避:退避期内不再调用 LLM,过期后恢复。"""

    @patch("llm_service.router.get_router")
    def test_failure_writes_backoff_and_suppresses_retry(self, mock_get_router):
        """失败 → 写退避标记 → 退避期内第二次调用不再触达 LLM。"""
        mock_get_router.return_value.generate.side_effect = Exception("LLM 不可用")
        session = _fake_session_with_pk(_long_history(8), pk=42)

        assert apply_rolling_summary(session) is False
        assert mock_get_router.return_value.generate.call_count == 1
        # 退避标记已按 session id 写入
        assert is_summary_in_backoff(42) is True

        # 退避期内重复调用:直接跳过,LLM 调用次数不增长
        assert apply_rolling_summary(session) is False
        assert apply_rolling_summary(session) is False
        assert mock_get_router.return_value.generate.call_count == 1
        # session 保持全量历史(静默降级)
        assert session.summary_text == ""
        assert len(session.messages) == 16

    @patch("llm_service.router.get_router")
    def test_backoff_expiry_resumes_attempt(self, mock_get_router):
        """退避过期(手动删除标记模拟 TTL 失效)后恢复尝试。"""
        mock_get_router.return_value.generate.side_effect = Exception("LLM 不可用")
        session = _fake_session_with_pk(_long_history(8), pk=43)

        apply_rolling_summary(session)
        assert mock_get_router.return_value.generate.call_count == 1
        assert is_summary_in_backoff(43) is True

        # 模拟 TTL 到期:手动删除退避标记
        clear_summary_backoff(43)
        assert is_summary_in_backoff(43) is False

        apply_rolling_summary(session)
        assert mock_get_router.return_value.generate.call_count == 2

    @patch("llm_service.router.get_router")
    def test_success_after_backoff_expiry_keeps_marker_cleared(self, mock_get_router):
        """完整故障周期:失败 → 退避 → 过期 → LLM 恢复 → 摘要成功,标记保持清除。"""
        mock_get_router.return_value.generate.side_effect = Exception("LLM 不可用")
        session_fail = _fake_session_with_pk(_long_history(8), pk=44)
        apply_rolling_summary(session_fail)
        assert is_summary_in_backoff(44) is True

        # 退避到期(模拟 TTL 失效)后 LLM 恢复
        clear_summary_backoff(44)
        mock_get_router.return_value.generate.side_effect = None
        mock_get_router.return_value.generate.return_value = ("早期对话摘要", None)
        session_ok = _fake_session_with_pk(_long_history(8), pk=44)

        assert apply_rolling_summary(session_ok) is True
        assert session_ok.summary_text == "早期对话摘要"
        # 成功路径显式清除标记,无残留
        assert is_summary_in_backoff(44) is False

    @patch("llm_service.router.get_router")
    def test_should_summarize_respects_backoff(self, mock_get_router):
        """should_summarize 传入 session_id 时受退避标记抑制。"""
        long_history = _long_history(8)

        # 无退避:超阈值 → True
        assert should_summarize(long_history, session_id=45) is True

        mark_summary_backoff(45)
        try:
            # 退避期内:即使超阈值且无摘要也跳过
            assert should_summarize(long_history, session_id=45) is False
            # 未传 session_id 的旧调用方不受影响(向后兼容)
            assert should_summarize(long_history) is True
        finally:
            clear_summary_backoff(45)

        assert should_summarize(long_history, session_id=45) is True
        mock_get_router.assert_not_called()

    @patch("llm_service.router.get_router")
    def test_backoff_isolated_per_session(self, mock_get_router):
        """退避标记按会话隔离:其他会话不受影响。"""
        mock_get_router.return_value.generate.side_effect = Exception("LLM 不可用")
        session_a = _fake_session_with_pk(_long_history(8), pk=46)
        apply_rolling_summary(session_a)
        assert is_summary_in_backoff(46) is True
        assert is_summary_in_backoff(47) is False

        # 会话 47 不受会话 46 的退避影响,仍会尝试(同样失败 → 各自退避)
        session_b = _fake_session_with_pk(_long_history(8), pk=47)
        apply_rolling_summary(session_b)
        assert mock_get_router.return_value.generate.call_count == 2
        assert is_summary_in_backoff(47) is True
