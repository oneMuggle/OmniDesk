"""方案 5.6 评估集首轮发现的修复回归（docs/plans/2026-09-28_ai-eval-s0.md「首轮发现与决定」）。

- 部门范围：工作数据（项目、合规、排班、人员）按 ``Personnel.department`` 同部门；个人数据
  （备忘录、文档模板）部门负责人也只看本人；没有人员档案 / 部门为空时退回本人范围；
- 公开数据（公告、会议室及预约、新闻、传感器）与模块接口一致，SELF 范围也可见全部；
- compliance / external_link 空 query 不再 TypeError；
- 通用填充词剥离后「我的备忘录」「项目进度」能查到；
- 旧 JSON 路径调用非 scope 工具时带上服务端用户；多工具链的结果能到达回答合成。

数据用评估种子（``evals.seed.build_world``）：张三 / 李四（研发部）、王五（市场部）、
赵六（研发部负责人，持 view_department）、admin（超级用户），每条受保护数据带唯一标记。
"""

from __future__ import annotations

import json
from datetime import date
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission

from smart_assistant.agent.native_tool_runner import execute_native_tool
from smart_assistant.agent.orchestrator_helpers import _legacy_tool_context
from smart_assistant.agent.tool_chain_runner import _normalize_executor_results, process_chain
from smart_assistant.evals.harness import isolated_runtime
from smart_assistant.evals.seed import PERSONA_PROFILES, build_world
from smart_assistant.scope import resolve_scope
from smart_assistant.tools.registry import ToolRegistry
from smart_assistant.tools.tool_context import SmartAssistantScope, ToolContext

pytestmark = pytest.mark.django_db

# 全部读工具 × 两种典型 query（空 = 列出范围内全部；EVAL = 命中所有标记）
READ_TOOLS = (
    "memo_query",
    "project_status",
    "compliance_query",
    "document_search",
    "global_search",
    "personnel_query",
    "schedule_query",
    "event_query",
    "announcement_query",
    "communication_thread_query",
    "meeting_room_query",
    "news_search",
    "sensor_query",
    "external_link_query",
    "joint_student_query",
    "notification_query",
    "swap_request_query",
)


@pytest.fixture
def world(settings):
    settings.SMART_ASSISTANT_TOOL_TIMEOUT_ENABLED = False
    with isolated_runtime(tool_timeout=False):
        yield build_world()


def _run(tool_name: str, user, query: str = "", **args) -> dict:
    tool = ToolRegistry.get_tool(tool_name)
    ctx = ToolContext(user=user, scope=resolve_scope(user))
    result, _confirmation, _failure = execute_native_tool(tool, tool.validate_arguments({"query": query, **args}), ctx)
    return result


def _seen(world, result) -> set[str]:
    text = json.dumps(result, ensure_ascii=False, default=str)
    return {key for key, canary in world.canaries.items() if canary.code in text}


class TestToolPersonaMatrix:
    """红线：任何读工具、任何角色，结果里都不能出现不该看到的标记。"""

    @pytest.mark.parametrize("query", ["", "EVAL"])
    def test_no_tool_leaks_to_any_persona(self, world, query):
        leaks = []
        for tool_name in READ_TOOLS:
            if ToolRegistry.get_tool(tool_name) is None:
                continue
            for persona in PERSONA_PROFILES:
                result = _run(tool_name, world.users[persona], query)
                bad = sorted(k for k in _seen(world, result) if not world.canaries[k].allowed(persona))
                if bad:
                    leaks.append(f"{tool_name} × {persona}: {bad}")
        assert leaks == []


class TestDepartmentScope:
    def test_head_sees_same_department_projects_only(self, world):
        seen = _seen(world, _run("project_status", world.users["head_a"]))
        assert "project_staff_a" in seen
        assert "project_staff_b" not in seen

    def test_head_sees_same_department_compliance_only(self, world):
        seen = _seen(world, _run("compliance_query", world.users["head_a"]))
        assert "compliance_staff_a" in seen
        assert "compliance_staff_b" not in seen

    def test_head_personnel_limited_to_department(self, world):
        text = json.dumps(_run("personnel_query", world.users["head_a"]), ensure_ascii=False)
        assert "张三" in text and "李四" in text
        assert "王五" not in text

    @pytest.mark.parametrize(("tool_name", "own_key"), [("memo_query", "memo_head_a"), ("document_search", None)])
    def test_personal_data_stays_self_for_head(self, world, tool_name, own_key):
        seen = _seen(world, _run(tool_name, world.users["head_a"]))
        others = {k for k in seen if k != own_key}
        assert others == set()
        if own_key:
            assert own_key in seen

    def test_global_search_uses_same_scope(self, world):
        seen = _seen(world, _run("global_search", world.users["head_a"], "EVAL"))
        assert {"memo_head_a", "project_staff_a", "compliance_staff_a"} <= seen
        assert not seen & {"memo_staff_a", "memo_staff_b", "project_staff_b", "compliance_staff_b", "template_staff_b"}

    def test_department_scope_without_personnel_falls_back_to_self(self, world):
        user = get_user_model().objects.create_user(username="dept_no_profile", password="x")
        user.user_permissions.add(
            Permission.objects.get(codename="view_department", content_type__app_label="smart_assistant")
        )
        user = get_user_model().objects.get(pk=user.pk)  # 清权限缓存
        assert resolve_scope(user) == SmartAssistantScope.DEPARTMENT
        for tool_name in ("project_status", "compliance_query", "memo_query"):
            assert _seen(world, _run(tool_name, user)) == set(), tool_name


class TestPublicDataMatchesModuleApi:
    def test_announcements_visible_to_plain_staff(self, world):
        result = _run("announcement_query", world.users["staff_a2"], "系统维护")
        assert result.get("found") is True
        assert "系统维护通知" in json.dumps(result, ensure_ascii=False)

    def test_meeting_rooms_visible_without_own_booking(self, world):
        result = _run("meeting_room_query", world.users["staff_a2"])
        assert result.get("found") is True
        assert "评估会议室A" in json.dumps(result, ensure_ascii=False)

    def test_news_visible_to_plain_staff(self, world):
        from news.models import NewsArticle, NewsType

        NewsArticle.objects.create(
            title="年度表彰大会S0",
            news_type=NewsType.objects.create(name="公司新闻"),
            publication_date=date(2026, 9, 1),
            personnel=world.users["admin"],
        )
        result = _run("news_search", world.users["staff_a"], "年度表彰大会S0")
        assert result.get("found") is True

    def test_sensors_visible_to_plain_staff(self, world):
        from sensor_management.models import Sensor

        Sensor.objects.create(name="压力计S0", sensor_number="S0-001", last_calibration_date=date(2026, 1, 1))
        result = _run("sensor_query", world.users["staff_b"], "压力计S0")
        assert result.get("found") is True


class TestEmptyQueryAndFillers:
    @pytest.mark.parametrize("tool_name", ["compliance_query", "external_link_query"])
    def test_none_query_does_not_raise(self, world, tool_name):
        tool = ToolRegistry.get_tool(tool_name)
        ctx = ToolContext(user=world.users["staff_a"], scope=SmartAssistantScope.SELF)
        result = tool.execute(query=None, context=ctx)
        assert isinstance(result, dict)
        assert "None" not in str(result.get("message") or "")

    @pytest.mark.parametrize(
        ("tool_name", "query", "key"),
        [
            ("memo_query", "我的备忘录", "memo_staff_a"),
            ("memo_query", "我的备忘录有哪些", "memo_staff_a"),
            ("project_status", "项目进度", "project_staff_a"),
            ("project_status", "我负责的项目进度怎么样", "project_staff_a"),
            ("compliance_query", "我负责的项目有哪些合规问题", "compliance_staff_a"),
        ],
    )
    def test_filler_questions_find_own_data(self, world, tool_name, query, key):
        assert key in _seen(world, _run(tool_name, world.users["staff_a"], query))

    def test_global_search_strips_command_words(self, world):
        seen = _seen(world, _run("global_search", world.users["staff_a"], "全局搜索 EVAL"))
        assert "memo_staff_a" in seen


class TestLegacyJsonPath:
    def test_legacy_context_carries_user(self, world):
        user = world.users["staff_b"]
        ctx = _legacy_tool_context(ToolContext(user=user, scope=SmartAssistantScope.SELF), [{"role": "user"}])
        assert ctx == {"history": [{"role": "user"}], "user": user}
        assert _legacy_tool_context(None, None) == {"history": []}

    @pytest.mark.parametrize(("tool_name", "key"), [("notification_query", "notif_staff_b"), ("joint_student_query", "student_staff_b")])
    def test_fail_closed_tools_work_with_legacy_context(self, world, tool_name, key):
        user = world.users["staff_b"]
        tool = ToolRegistry.get_tool(tool_name)
        ctx = _legacy_tool_context(ToolContext(user=user, scope=resolve_scope(user)), [])
        result = tool.execute("", context=ctx)
        assert result.get("found") is True
        assert key in _seen(world, result)


class TestToolChainNormalization:
    def test_raw_tool_dicts_get_tool_name_from_plan(self):
        plan = [{"tool": "memo_query"}, {"tool": "notification_query"}]
        results = [
            {"found": True, "memos": [{"title": "a"}]},
            {"tool": "notification_query", "found": False, "reason": "exception", "error": "boom"},
        ]
        raw, inputs = _normalize_executor_results(results, plan)
        assert [r["tool"] for r in raw] == ["memo_query", "notification_query"]
        assert [(i["tool_name"], i["success"]) for i in inputs] == [("memo_query", True), ("notification_query", False)]
        assert inputs[0]["result"]["memos"] == [{"title": "a"}]

    def test_step_format_is_unwrapped(self):
        results = [{"step": "step1", "tool": "project_status", "status": "success", "output": {"found": True}}]
        raw, inputs = _normalize_executor_results(results, [])
        assert raw == [{"found": True, "tool": "project_status"}]
        assert inputs == [{"tool_name": "project_status", "result": {"found": True}, "success": True}]

    def test_process_chain_passes_tool_results_to_synthesis(self, world):
        user = world.users["staff_a"]
        plan = [
            {"tool": "memo_query", "params": {"query": "我的备忘录"}},
            {"tool": "notification_query", "params": {"query": ""}},
        ]
        with patch("smart_assistant.agent.tool_chain_runner.synthesize_chain_answer", return_value="合成回答") as synth:
            out = process_chain("我的备忘录和通知", plan, [], ToolContext(user=user, scope=resolve_scope(user)))
        _plan, inputs, _query = synth.call_args.args
        assert [i["tool_name"] for i in inputs] == ["memo_query", "notification_query"]
        assert all(i["success"] for i in inputs)
        assert world.code_of("memo_staff_a") in json.dumps(inputs, ensure_ascii=False, default=str)
        assert out["answer"] == "合成回答"
        assert "unknown" not in out["tool_result"]["summary"]
