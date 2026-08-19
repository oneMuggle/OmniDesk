"""API 权限矩阵测试。"""
from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from joint_students.tests.factories import (
    create_cycle,
    create_joint_student,
    create_personnel,
    create_report,
    create_stipend,
    create_user,
)


def create_group(name, user=None):
    """创建/获取 Group 并可选地把 user 加入。

    factories.py 未提供, 集中在此文件内避免污染其他测试。
    """
    g, _ = Group.objects.get_or_create(name=name)
    if user is not None:
        user.groups.add(g)
    return g


@pytest.mark.django_db
class TestJointStudentAPI:
    """联培生 CRUD API 权限矩阵。"""

    def test_unauthenticated_cannot_list(self):
        client = APIClient()
        resp = client.get("/api/joint-students/students/")
        assert resp.status_code == 401

    def test_manager_can_list(self):
        manager = create_user(username="manager1")
        create_group("联培生管理员", manager)
        client = APIClient()
        client.force_authenticate(manager)
        resp = client.get("/api/joint-students/students/")
        assert resp.status_code == 200

    def test_manager_can_create(self):
        manager = create_user(username="manager1")
        create_group("联培生管理员", manager)
        p = create_personnel()
        client = APIClient()
        client.force_authenticate(manager)
        resp = client.post(
            "/api/joint-students/students/",
            {
                "personnel": p.id,
                "student_type": "master",
                "student_id": "S999",
                "enrollment_date": "2024-09-01",
            },
            format="json",
        )
        assert resp.status_code == 201

    def test_non_manager_cannot_create(self):
        """非联培生管理员应被 403 拒绝 POST。"""
        user = create_user(username="nonmanager")
        create_group("考核专家组", user)  # 错误组
        p = create_personnel()
        client = APIClient()
        client.force_authenticate(user)
        resp = client.post(
            "/api/joint-students/students/",
            {
                "personnel": p.id,
                "student_type": "master",
                "student_id": "S888",
                "enrollment_date": "2024-09-01",
            },
            format="json",
        )
        assert resp.status_code == 403


@pytest.mark.django_db
class TestMonthlyReportAPI:
    """月度报告 submit 流转测试。"""

    def test_student_can_submit_own_report(self):
        """联培生管理员代为提交草稿 → submitted。"""
        user = create_user(username="student1")
        create_group("联培生管理员", user)
        client = APIClient()
        client.force_authenticate(user)
        js = create_joint_student()
        report = create_report(joint_student=js, year=2026, month=7)
        resp = client.post(f"/api/joint-students/reports/{report.id}/submit/")
        assert resp.status_code == 200
        report.refresh_from_db()
        assert report.status == "submitted"

    def test_manager_can_approve_submitted_report(self):
        """submitted → approved。"""
        user = create_user(username="manager_approve")
        create_group("联培生管理员", user)
        client = APIClient()
        client.force_authenticate(user)
        js = create_joint_student()
        report = create_report(joint_student=js, year=2026, month=8, status="submitted")
        resp = client.post(f"/api/joint-students/reports/{report.id}/approve/")
        assert resp.status_code == 200
        report.refresh_from_db()
        assert report.status == "approved"

    def test_manager_can_reject_submitted_report(self):
        """submitted → rejected (必须传 reviewer_comment)。"""
        user = create_user(username="manager_reject")
        create_group("联培生管理员", user)
        client = APIClient()
        client.force_authenticate(user)
        js = create_joint_student()
        report = create_report(joint_student=js, year=2026, month=9, status="submitted")
        # 缺 reviewer_comment → 400
        resp = client.post(f"/api/joint-students/reports/{report.id}/reject/", {}, format="json")
        assert resp.status_code == 400
        # 带 reviewer_comment → 200
        resp = client.post(
            f"/api/joint-students/reports/{report.id}/reject/",
            {"reviewer_comment": "请补充材料"},
            format="json",
        )
        assert resp.status_code == 200
        report.refresh_from_db()
        assert report.status == "rejected"
        assert report.reviewer_comment == "请补充材料"


@pytest.mark.django_db
class TestExpertScoreAPI:
    """专家打分 API 权限。"""

    def test_expert_can_score(self):
        expert = create_user(username="expert1")
        create_group("考核专家组", expert)
        client = APIClient()
        client.force_authenticate(expert)
        cycle = create_cycle()
        js = create_joint_student()
        resp = client.post(
            "/api/joint-students/scores/",
            {
                "cycle": cycle.id,
                "joint_student": js.id,
                "score": "85.00",
                "comment": "工作认真",
            },
            format="json",
        )
        assert resp.status_code == 201

    def test_non_expert_cannot_score(self):
        """非考核专家应 403。"""
        user = create_user(username="random_user")
        create_group("联培生管理员", user)  # 错误组
        client = APIClient()
        client.force_authenticate(user)
        cycle = create_cycle()
        js = create_joint_student()
        resp = client.post(
            "/api/joint-students/scores/",
            {
                "cycle": cycle.id,
                "joint_student": js.id,
                "score": "85.00",
            },
            format="json",
        )
        assert resp.status_code == 403


@pytest.mark.django_db
class TestCycleAPI:
    """考核批次 API 权限。"""

    def test_manager_can_manual_trigger(self):
        """联培生管理员手动触发批次 → 200/201。"""
        manager = create_user(username="manager1")
        create_group("联培生管理员", manager)
        client = APIClient()
        client.force_authenticate(manager)
        resp = client.post(
            "/api/joint-students/cycles/trigger/",
            {"year": 2026, "month": 11},
            format="json",
        )
        assert resp.status_code in (200, 201)


@pytest.mark.django_db
class TestStipendLockAPI:
    """补助记录 lock 端点。"""

    def test_manager_can_lock(self):
        manager = create_user(username="manager1")
        create_group("联培生管理员", manager)
        client = APIClient()
        client.force_authenticate(manager)
        cycle = create_cycle()
        js = create_joint_student()
        stipend = create_stipend(cycle=cycle, joint_student=js)
        resp = client.post(f"/api/joint-students/stipends/{stipend.id}/lock/")
        assert resp.status_code == 200
        stipend.refresh_from_db()
        assert stipend.status == "locked"


@pytest.mark.django_db
class TestPersonnelPoolAPI:
    """Personnel 池端点: 仅联培生管理员可访问, 含 has_joint_student 标记。"""

    def test_manager_can_list_pool(self):
        manager = create_user(username="pool_manager")
        create_group("联培生管理员", manager)
        client = APIClient()
        client.force_authenticate(manager)
        p1 = create_personnel(name="未关联人员")
        p2 = create_personnel(name="已关联人员")
        create_joint_student(personnel=p2)
        resp = client.get("/api/joint-students/personnel-pool/")
        assert resp.status_code == 200
        data = resp.json()
        # 返回列表, 每项包含 has_joint_student 字段
        assert isinstance(data, list)
        flags = {item["id"]: item["has_joint_student"] for item in data}
        assert flags[p1.id] is False
        assert flags[p2.id] is True

    def test_unauthenticated_blocked(self):
        client = APIClient()
        resp = client.get("/api/joint-students/personnel-pool/")
        assert resp.status_code in (401, 403)


@pytest.mark.django_db
class TestGraduateAction:
    """JointStudent.graduate 自定义 action。"""

    def test_manager_can_graduate_student(self):
        manager = create_user(username="manager1")
        create_group("联培生管理员", manager)
        client = APIClient()
        client.force_authenticate(manager)
        js = create_joint_student()
        resp = client.post(f"/api/joint-students/students/{js.id}/graduate/")
        assert resp.status_code == 200
        js.refresh_from_db()
        assert js.is_active is False
        assert js.graduation_date == date.today()
