"""R5-B5: AgentLog / AgentEvent 索引 + timeline subtask N+1 测试。

- AgentLog 按 -created_at 排序且被 stats.py / logs.py 反复 created_at__gte/__lte
  过滤,需 (-created_at) 与 (intent) 索引;
- AgentEvent 按 (task, sequence) 排序,需复合索引;
- timeline 视图(AgentTaskViewSet.timeline)序列化 events 时访问 subtask FK,
  修复前每个 event 一条查询(N+1),修复后 queryset 应 select_related 一次取齐。

索引存在性用 get_constraints 断言(SQLite 下 get_indexes 不存在)。
"""

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from smart_assistant.models import AgentEvent, AgentSubTask, AgentTask

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# 索引存在性(TDD RED → 加 indexes 后 GREEN)
# ---------------------------------------------------------------------------


def _constraint_columns(table):
    with connection.cursor() as cursor:
        constraints = connection.introspection.get_constraints(cursor, table)
    return constraints


class TestAgentLogIndexes:
    def test_created_at_index_exists(self):
        """AgentLog.created_at 需有索引支撑 -created_at 排序与时间窗过滤。"""
        constraints = _constraint_columns("smart_assistant_agentlog")
        index_columns = [
            c["columns"] for c in constraints.values() if c.get("index") and c.get("columns") == ["created_at"]
        ]
        assert index_columns, (
            "smart_assistant_agentlog.created_at 缺少索引,现有约束: "
            f"{[(n, c['columns']) for n, c in constraints.items()]}"
        )

    def test_intent_index_exists(self):
        """AgentLog.intent 需有索引支撑按意图过滤。"""
        constraints = _constraint_columns("smart_assistant_agentlog")
        index_columns = [name for name, c in constraints.items() if c.get("index") and c.get("columns") == ["intent"]]
        assert index_columns, (
            f"smart_assistant_agentlog.intent 缺少索引,现有约束: {[(n, c['columns']) for n, c in constraints.items()]}"
        )


class TestAgentEventIndexes:
    def test_task_sequence_composite_index_exists(self):
        """AgentEvent 需有显式 (task, sequence) 复合索引支撑排序与 sequence__gt 轮询。

        注:unique_together(task, sequence) 在部分后端(SQLite)也会生成带
        unique 标记的索引,故此处要求非 unique 的普通索引,保证断言真实覆盖
        显式 Index 定义。
        """
        constraints = _constraint_columns("smart_assistant_agentevent")
        index_columns = [
            name
            for name, c in constraints.items()
            if c.get("index") and not c.get("unique") and c.get("columns") == ["task_id", "sequence"]
        ]
        assert index_columns, (
            "smart_assistant_agentevent 缺少 (task, sequence) 复合索引,现有约束: "
            f"{[(n, c['columns']) for n, c in constraints.items()]}"
        )


# ---------------------------------------------------------------------------
# timeline N+1(TDD RED → select_related 后 GREEN)
# ---------------------------------------------------------------------------


@pytest.fixture
def agent_task_with_events(admin_user_obj):
    """1 个任务 + 2 个子任务 + 6 个事件(交替关联子任务)。"""
    task = AgentTask.objects.create(
        task_id="11111111-1111-1111-1111-111111111111",
        user=admin_user_obj,
        objective="R5-B5 timeline N+1 测试任务",
    )
    subtasks = [
        AgentSubTask.objects.create(
            task=task,
            subtask_id=f"st-{i}",
            role="researcher",
            objective=f"子任务 {i}",
        )
        for i in range(2)
    ]
    for seq in range(6):
        AgentEvent.objects.create(
            task=task,
            subtask=subtasks[seq % 2],
            sequence=seq,
            event_type="subtask.progress",
            payload={"step": seq},
        )
    return task


class TestTimelineQueryCount:
    def test_timeline_query_count_is_bounded(self, api_client, admin_user_obj, agent_task_with_events):
        """timeline 含 6 个事件时查询数不应随事件数线性增长。

        基线:1(task) + 1(subtasks) + 1(events+select_related) = 3;上限给足余量 5。
        """
        client = api_client
        client.force_authenticate(user=admin_user_obj)
        url = f"/api/smart-assistant/tasks/{agent_task_with_events.task_id}/timeline/"
        with CaptureQueriesContext(connection) as ctx:
            response = client.get(url)
        assert response.status_code == 200
        assert len(response.data["timeline"]) == 6
        assert len(ctx.captured_queries) <= 5, (
            f"timeline 执行了 {len(ctx.captured_queries)} 条查询(>5),存在 N+1: "
            f"{[q['sql'][:120] for q in ctx.captured_queries]}"
        )

    def test_timeline_subtask_ids_present(self, api_client, admin_user_obj, agent_task_with_events):
        """修复不得破坏 timeline 输出中的 subtask 字段(序列化为 subtask PK)。"""
        client = api_client
        client.force_authenticate(user=admin_user_obj)
        url = f"/api/smart-assistant/tasks/{agent_task_with_events.task_id}/timeline/"
        response = client.get(url)
        expected_pks = set(agent_task_with_events.subtasks.values_list("pk", flat=True))
        subtask_pks = {e["subtask"] for e in response.data["timeline"]}
        assert subtask_pks == expected_pks
