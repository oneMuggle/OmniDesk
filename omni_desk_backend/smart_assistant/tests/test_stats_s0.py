"""运营看板补充指标（方案 5.6 / S0）：回答成功率、P50 / P95、LLM 调用成功率、按模型分列。"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from smart_assistant.models import AgentLog, LlmUsageDaily, SmartAssistantSession
from smart_assistant.utils import percentile
from users.models import CustomUser

pytestmark = pytest.mark.django_db

OVERVIEW = "/api/smart-assistant/stats/overview/"
DAILY = "/api/smart-assistant/stats/daily/"


@pytest.fixture
def admin():
    return CustomUser.objects.create_user(username="stats_s0_admin", password="x", is_staff=True, is_superuser=True)


@pytest.fixture
def client(admin):
    c = APIClient()
    c.force_authenticate(user=admin)
    return c


@pytest.fixture
def log(admin):
    session = SmartAssistantSession.objects.create(user=admin, title="s0")

    def make(**kwargs):
        defaults = {
            "session": session,
            "user_query": "q",
            "intent": "memo_query",
            "tool_used": "memo_query",
            "llm_response": "好的",
            "response_time_ms": 100,
            "model_name": "qwen",
            "total_tokens": 10,
        }
        defaults.update(kwargs)
        return AgentLog.objects.create(**defaults)

    return make


def test_percentile_nearest_rank():
    assert percentile([], 95) == 0
    assert percentile([None, 5], 50) == 5
    assert percentile(list(range(1, 101)), 50) == 50
    assert percentile(list(range(1, 101)), 95) == 95
    assert percentile([100, 200, 3000], 95) == 3000


def test_overview_success_rate_latency_and_models(client, log):
    for ms in (100, 200, 300, 400):
        log(response_time_ms=ms)
    log(response_time_ms=5000, llm_response="回答生成失败: 超时", model_name="glm")
    log(response_time_ms=900, llm_response="[错误] 回答生成失败: 断开", model_name="")
    # 工具级审计（无响应时间）与工具链逐步记录不算对话
    log(response_time_ms=None, llm_response="回答生成失败: 审计里的", intent="tool_call")
    log(response_time_ms=10, intent="chain:memo_query", llm_response="")

    data = client.get(OVERVIEW).data
    assert data["conversation_count"] == 6
    assert data["answer_failures"] == 2
    assert data["answer_success_rate"] == 66.7
    assert data["p50_response_time_ms"] == 300
    assert data["p95_response_time_ms"] == 5000

    by_model = {row["model"]: row for row in data["by_model"]}
    assert list(by_model)[0] == "qwen"  # 按对话数降序
    assert by_model["qwen"]["conversations"] == 4
    assert by_model["qwen"]["answer_success_rate"] == 100.0
    assert by_model["qwen"]["p95_response_time_ms"] == 400
    assert by_model["qwen"]["avg_response_time_ms"] == 250
    assert by_model["glm"]["answer_success_rate"] == 0.0
    assert by_model["未记录"]["conversations"] == 1


def test_overview_llm_call_success_rate(client, admin):
    today = timezone.localdate()
    LlmUsageDaily.objects.create(date=today, user=admin, app_name="smart_assistant", calls=18, failed_calls=2)
    LlmUsageDaily.objects.create(
        date=today, user=None, app_name="smart_assistant", staff_key="s1", calls=0, failed_calls=0
    )
    # 其他应用、窗口外的不计
    LlmUsageDaily.objects.create(date=today, user=admin, app_name="office_assistant", calls=100, failed_calls=100)
    LlmUsageDaily.objects.create(
        date=today - timedelta(days=40), user=admin, app_name="smart_assistant", calls=100, failed_calls=100
    )

    data = client.get(OVERVIEW, {"days": 30}).data
    assert (data["llm_calls"], data["llm_failed_calls"], data["llm_call_success_rate"]) == (18, 2, 90.0)


def test_overview_empty_has_null_rates(client):
    data = client.get(OVERVIEW).data
    assert data["conversation_count"] == 0
    assert data["answer_success_rate"] is None
    assert data["llm_call_success_rate"] is None
    assert data["p95_response_time_ms"] == 0
    assert data["by_model"] == []


def test_daily_success_rate_and_p95(client, log):
    log(response_time_ms=100)
    log(response_time_ms=300, llm_response="回答生成失败: x")
    old = log(response_time_ms=50)
    AgentLog.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=2))
    # 只有审计日志的一天：有对话条目但成功率为空
    audit = log(response_time_ms=None, intent="tool_call")
    AgentLog.objects.filter(pk=audit.pk).update(created_at=timezone.now() - timedelta(days=5))

    rows = client.get(DAILY, {"days": 7}).data["daily_stats"]
    assert len(rows) == 3
    latest = rows[-1]
    assert latest["conversations"] == 2
    assert latest["answer_success_rate"] == 50.0
    assert latest["p95_response_time_ms"] == 300
    assert rows[1]["answer_success_rate"] == 100.0
    assert rows[0]["answer_success_rate"] is None
    assert rows[0]["p95_response_time_ms"] == 0


def test_stats_still_admin_only(log):
    user = CustomUser.objects.create_user(username="stats_s0_plain", password="x")
    c = APIClient()
    c.force_authenticate(user=user)
    assert c.get(OVERVIEW).status_code == 403
