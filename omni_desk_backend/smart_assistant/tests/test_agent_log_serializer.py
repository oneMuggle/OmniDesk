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
