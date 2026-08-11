"""core/api.py migration_status API 测试 — 复用 loader.graph,识别 destructive。

Task 5 of offline-upgrade-data-safety: migration_status endpoint 必须基于
MigrationLoader.graph 真实枚举迁移(而非 apps.get_app_configs() + app_config.migrations),
保证对第三方 app 与无 migrations 模块属性的 app 同样生效。

识别 DeleteModel / RemoveField / RemoveConstraint 三类 destructive 操作。
"""

from unittest.mock import patch, MagicMock

import pytest
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model


def _make_migration(name, operations=None):
    migration = MagicMock()
    migration.name = f"{name}.py"
    migration.operations = operations or []
    return migration


def _make_op(op_class, **attrs):
    op = op_class.__new__(op_class)
    for k, v in attrs.items():
        setattr(op, k, v)
    return op


def _loader_mock(nodes, applied=None):
    loader_mock = MagicMock()
    graph_mock = MagicMock()
    graph_mock.nodes = nodes
    loader_mock.graph = graph_mock
    loader_mock.applied_migrations = applied if applied is not None else set()
    return loader_mock


@pytest.mark.django_db
class TestMigrationStatusAPI:
    """GET /api/system/migrations/ — 真实 graph 枚举 + destructive 检测。"""

    @pytest.fixture
    def auth_client(self):
        from django.contrib.auth.models import Group

        User = get_user_model()
        admin_group, _ = Group.objects.get_or_create(name="Admin")
        user = User.objects.create_user(
            username="api_admin",
            password="pw",
            is_staff=True,
            is_superuser=True,
        )
        user.groups.add(admin_group)
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    def test_api_uses_loader_graph_not_app_config(self, auth_client):
        """API 必须基于 MigrationLoader.graph 而非 app_config.migrations。

        模拟一个 app_config 不存在但 loader.graph 包含节点的情况。"""
        from django.db.migrations import AddField

        op = _make_op(AddField, model_name="ghostmodel", name="new")
        migration = _make_migration("0001_initial", [op])
        loader_mock = _loader_mock(
            {("ghost_app", "0001_initial"): migration},
            applied=set(),
        )

        with patch("core.api.MigrationLoader") as ML:
            ML.return_value = loader_mock
            response = auth_client.get("/api/system/migrations/")

        assert response.status_code == 200
        body = response.json()
        assert "pending" in body
        # ghost_app 必须出现在 pending 中
        app_labels = [p["app"] for p in body["pending"]]
        assert "ghost_app" in app_labels

    def test_api_detects_remove_constraint_as_destructive(self, auth_client):
        """RemoveConstraint 必须被识别为 destructive 操作。"""
        from django.db.migrations import RemoveConstraint

        op = _make_op(RemoveConstraint, model_name="mymodel", name="ck_constraint")
        migration = _make_migration("0001_drop_constraint", [op])
        loader_mock = _loader_mock(
            {("fake_app", "0001_drop_constraint"): migration},
            applied=set(),
        )

        with patch("core.api.MigrationLoader") as ML:
            ML.return_value = loader_mock
            response = auth_client.get("/api/system/migrations/")

        assert response.status_code == 200
        body = response.json()
        assert body["has_destructive"] is True
        # 在 pending 中找到该操作
        pending_ops = body["pending"][0]["operations"]
        assert any(op["type"] == "RemoveConstraint" for op in pending_ops)
        assert any(op.get("destructive") is True for op in pending_ops)

    def test_api_detects_delete_model_and_remove_field_as_destructive(self, auth_client):
        """DeleteModel / RemoveField 都标记为 destructive=True。"""
        from django.db.migrations import DeleteModel, RemoveField

        op1 = _make_op(DeleteModel, name="OldModel")
        op2 = _make_op(RemoveField, model_name="kept", name="deprecated")
        migration = _make_migration("0001_drop_stuff", [op1, op2])
        loader_mock = _loader_mock(
            {("fake_app", "0001_drop_stuff"): migration},
            applied=set(),
        )

        with patch("core.api.MigrationLoader") as ML:
            ML.return_value = loader_mock
            response = auth_client.get("/api/system/migrations/")

        assert response.status_code == 200
        body = response.json()
        assert body["has_destructive"] is True
        ops = body["pending"][0]["operations"]
        destructive_types = {op["type"] for op in ops if op.get("destructive")}
        assert "DeleteModel" in destructive_types
        assert "RemoveField" in destructive_types

    def test_api_non_destructive_has_destructive_false(self, auth_client):
        """无 destructive 操作时 has_destructive=False。"""
        from django.db.migrations import AddField, CreateModel

        op1 = _make_op(AddField, model_name="m", name="f")
        op2 = _make_op(CreateModel, name="NewModel")
        migration = _make_migration("0001_safe", [op1, op2])
        loader_mock = _loader_mock(
            {("fake_app", "0001_safe"): migration},
            applied=set(),
        )

        with patch("core.api.MigrationLoader") as ML:
            ML.return_value = loader_mock
            response = auth_client.get("/api/system/migrations/")

        assert response.status_code == 200
        body = response.json()
        assert body["has_destructive"] is False
        # pending 中所有操作都应有 destructive=False 或不存在 destructive 字段
        for pending in body["pending"]:
            for op in pending["operations"]:
                assert op.get("destructive", False) is False

    def test_api_reports_pending_count_and_applied_count(self, auth_client):
        """API 必须正确报告 pending_count / applied_count。"""
        from django.db.migrations import AddField

        op = _make_op(AddField, model_name="m", name="f")
        # 3 nodes, 2 applied, 1 pending
        migration1 = _make_migration("0001", [])
        migration2 = _make_migration("0002", [])
        migration3 = _make_migration("0003_add", [op])

        loader_mock = _loader_mock(
            {
                ("a", "0001"): migration1,
                ("b", "0002"): migration2,
                ("c", "0003_add"): migration3,
            },
            applied={("a", "0001"), ("b", "0002")},
        )

        with patch("core.api.MigrationLoader") as ML:
            ML.return_value = loader_mock
            response = auth_client.get("/api/system/migrations/")

        assert response.status_code == 200
        body = response.json()
        assert body["applied_count"] == 2
        assert body["pending_count"] == 1
        assert body["pending"][0]["app"] == "c"

    def test_api_requires_authentication(self):
        """未认证访问应返回 401。"""
        client = APIClient()
        response = client.get("/api/system/migrations/")
        assert response.status_code == 401
