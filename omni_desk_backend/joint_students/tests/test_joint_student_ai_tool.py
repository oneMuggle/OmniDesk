"""AI 工具 joint_student_query：可见范围必须与 /api/joint-students/students/ 一致。"""

import pytest
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from joint_students.ai_tools import JointStudentQueryTool
from joint_students.tests.factories import (
    create_joint_student,
    create_personnel,
    create_report,
    create_user,
)
from smart_assistant.scope import SmartAssistantScope
from smart_assistant.tools.tool_context import ToolContext


def _join(user, group_name):
    group, _ = Group.objects.get_or_create(name=group_name)
    user.groups.add(group)


def _bind(user, personnel):
    user.personnel = personnel
    user.save(update_fields=["personnel"])


def _tool_ids(user, scope=SmartAssistantScope.SELF, **params):
    result = JointStudentQueryTool().execute(
        query="联培生", context=ToolContext(user=user, scope=scope), params={"query": "联培生", **params}
    )
    return sorted(item["id"] for item in result.get("students", []))


def _api_ids(user):
    client = APIClient()
    client.force_authenticate(user)
    resp = client.get("/api/joint-students/students/")
    assert resp.status_code == 200
    return sorted(item["id"] for item in resp.json()["results"])


@pytest.fixture
def students():
    mentor_personnel = create_personnel(name="王导师")
    own_personnel = create_personnel(name="张同学")
    return {
        "mentor_personnel": mentor_personnel,
        "own_personnel": own_personnel,
        "own": create_joint_student(personnel=own_personnel, mentor=mentor_personnel),
        "assigned": create_joint_student(personnel=create_personnel(name="李同学"), mentor=mentor_personnel),
        "other": create_joint_student(
            personnel=create_personnel(name="赵同学"), mentor=create_personnel(name="孙导师")
        ),
    }


@pytest.mark.django_db
class TestJointStudentQueryTool:
    def test_student_only_sees_self_same_as_api(self, students):
        user = create_user(username="js_ai_student")
        _bind(user, students["own_personnel"])
        assert _tool_ids(user) == _api_ids(user) == [students["own"].id]

    def test_mentor_sees_assigned_same_as_api(self, students):
        user = create_user(username="js_ai_mentor")
        _join(user, "联培生导师")
        _bind(user, students["mentor_personnel"])
        expected = sorted([students["own"].id, students["assigned"].id])
        assert _tool_ids(user) == _api_ids(user) == expected

    def test_manager_sees_all_same_as_api(self, students):
        user = create_user(username="js_ai_manager")
        _join(user, "联培生管理员")
        assert (
            _tool_ids(user)
            == _api_ids(user)
            == sorted(s.id for s in [students["own"], students["assigned"], students["other"]])
        )

    def test_global_scope_does_not_widen_visibility(self, students):
        """智能助手 GLOBAL scope 的非联培生管理员也不能越过模块规则。"""
        user = create_user(username="js_ai_global", is_staff=True)
        assert _tool_ids(user, scope=SmartAssistantScope.GLOBAL) == _api_ids(user) == []

    def test_filters_and_latest_report(self, students):
        user = create_user(username="js_ai_filter")
        _join(user, "联培生管理员")
        create_report(joint_student=students["assigned"], year=2026, month=6, status="approved")
        create_report(joint_student=students["assigned"], year=2026, month=8, status="submitted")
        students["other"].is_active = False
        students["other"].save(update_fields=["is_active"])

        result = JointStudentQueryTool().execute(
            context=ToolContext(user=user), params={"query": "李同学月报", "keyword": "李同学"}
        )
        assert result["found"] is True
        (item,) = result["students"]
        assert item["name"] == "李同学"
        assert item["mentor"] == "王导师"
        assert item["latest_report"] == {"period": "2026-08", "status": "已提交"}

        assert students["other"].id not in _tool_ids(user)
        assert students["other"].id in _tool_ids(user, active_only=False)

    def test_legacy_dict_context_and_anonymous(self, students):
        user = create_user(username="js_ai_legacy")
        _bind(user, students["own_personnel"])
        result = JointStudentQueryTool().execute("我的联培信息", {"user": user})
        assert [s["id"] for s in result["students"]] == [students["own"].id]

        denied = JointStudentQueryTool().execute("联培生", {"user": None})
        assert denied["found"] is False

    def test_no_visible_records_message(self):
        user = create_user(username="js_ai_empty")
        result = JointStudentQueryTool().execute(context=ToolContext(user=user), params={"query": "联培生"})
        assert result == {"found": False, "message": "没有你可以查看的联培生记录", "module_label": "联培生"}
