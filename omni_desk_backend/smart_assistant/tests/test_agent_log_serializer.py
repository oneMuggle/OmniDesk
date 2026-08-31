"""AgentLogSerializer 字段白名单测试 (R3-B1)。

契约：AgentLogSerializer 只暴露审计面板（AgentAuditPanel）消费的字段，
剔除 session FK、token/费用、tool_calls_meta、tool_call_path 等内部审计字段。
"""

import pytest

from smart_assistant.models import AgentLog, SmartAssistantSession
from smart_assistant.serializers import AgentLogSerializer
from users.models import CustomUser


@pytest.mark.django_db
class TestAgentLogSerializerWhitelist:
    def _create_log(self):
        user = CustomUser.objects.create_user(username="loguser", password="pw")
        session = SmartAssistantSession.objects.create(user=user, title="会话")
        return AgentLog.objects.create(
            session=session,
            user_query="明天谁值班？",
            intent="schedule_query",
            tool_used="schedule_query",
            tool_input={"query": "明天谁值班？"},
            tool_output={"found": True},
            llm_response="明天张三值班。",
        )

    def test_fields_whitelisted(self):
        log = self._create_log()

        data = AgentLogSerializer(log).data

        assert set(data.keys()) == {
            "id",
            "user_query",
            "intent",
            "tool_used",
            "tool_input",
            "tool_output",
            "llm_response",
            "created_at",
        }

    def test_sensitive_log_values_are_publicly_redacted(self):
        log = self._create_log()
        log.tool_input = {"apiKey": "sk-secret", "API_KEY": "secret2", "recipient_names": ["张三"], "safe": "ok"}
        log.tool_output = {"tool_output": "正文 secret=hidden", "nested": {"token": "tok"}, "count": 1}
        log.llm_response = "LLM 敏感文本 token=abc https://internal.example/x"
        log.save(update_fields=["tool_input", "tool_output", "llm_response"])

        data = AgentLogSerializer(log).data

        assert "sk-secret" not in str(data)
        assert "secret2" not in str(data)
        assert "张三" not in str(data)
        assert "正文 secret=hidden" not in str(data)
        assert "tok" not in str(data)
        assert "abc" not in data["llm_response"]
        assert data["tool_input"]["safe"] == "ok"

    def test_user_query_is_publicly_redacted(self):
        log = self._create_log()
        log.user_query = (
            '请联系 alice@example.com、13812345678；token=tok-secret；'
            '{"authorization":"Bearer raw-secret","visible":"普通文本"}'
        )

        data = AgentLogSerializer(log).data

        assert log.user_query not in data["user_query"]
        for sensitive in ("alice@example.com", "13812345678", "tok-secret", "raw-secret"):
            assert sensitive not in data["user_query"]
        assert "普通文本" in data["user_query"]

    def test_internal_fields_not_exposed(self):
        log = self._create_log()

        data = AgentLogSerializer(log).data

        for hidden in (
            "session",
            "model_name",
            "input_tokens",
            "output_tokens",
            "total_tokens",
            "estimated_cost",
            "response_time_ms",
            "tool_success",
            "user_feedback",
            "tool_call_path",
            "tool_calls_meta",
            "tool_calls_rounds",
        ):
            assert hidden not in data, f"内部字段 {hidden} 不应暴露"
