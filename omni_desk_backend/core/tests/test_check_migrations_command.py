"""check_migrations 命令测试 — 枚举所有迁移、识别 destructive 操作。

Task 5 of offline-upgrade-data-safety: 真实枚举 Django migration graph,覆盖
DeleteModel / RemoveField / RemoveConstraint 三类 destructive 操作,并提供
--fail-on-destructive 选项在检测到 destructive 时返回 exit 2。
"""
import io
from unittest.mock import patch, MagicMock

import pytest
from django.core.management import call_command


def _make_migration(name, operations=None):
    """构造 Migration 节点 mock。"""
    migration = MagicMock()
    migration.name = f"{name}.py"
    migration.operations = operations or []
    return migration


def _make_op(op_class, **attrs):
    """构造 operation 实例,isinstance(op, op_class) 必须返回 True。

    用真实 op_class 跳过 __init__, 直接 __new__ 后设置属性,避免 spec 限制
    让 isinstance 正常工作。
    """
    op = op_class.__new__(op_class)
    for k, v in attrs.items():
        setattr(op, k, v)
    return op


def _loader_mock(nodes, applied=None):
    """构造 MigrationLoader mock:graph.nodes + applied_migrations。"""
    loader_mock = MagicMock()
    graph_mock = MagicMock()
    graph_mock.nodes = nodes
    loader_mock.graph = graph_mock
    loader_mock.applied_migrations = applied if applied is not None else set()
    return loader_mock


@pytest.mark.django_db
class TestCheckMigrationsCommand:
    """check_migrations 命令覆盖枚举 + destructive 检测 + exit code。"""

    def test_command_runs_without_pending_migrations(self):
        """无 pending 时打印成功信息。"""
        out = io.StringIO()
        call_command("check_migrations", stdout=out)
        output = out.getvalue()
        assert "No pending migrations" in output or "Found 0 pending" in output

    def test_command_lists_all_apps_via_migration_graph(self):
        """命令必须基于 MigrationLoader.graph 枚举,而非 app_config.migrations。"""
        from django.db.migrations import DeleteModel

        fake_delete = _make_op(DeleteModel, name="FakeModel")
        migration = _make_migration("0001_drop_fake", [fake_delete])
        node_key = ("fake_app", "0001_drop_fake")
        loader_mock = _loader_mock({node_key: migration})

        with patch("core.management.commands.check_migrations.MigrationLoader") as ML:
            ML.return_value = loader_mock
            out = io.StringIO()
            call_command("check_migrations", stdout=out)
            output = out.getvalue()
            # 应发现 fake_app 的 destructive migration
            assert "fake_app" in output
            assert "DELETE MODEL: FakeModel" in output or "DeleteModel" in output

    def test_command_detects_remove_constraint_as_destructive(self):
        """RemoveConstraint 必须被识别为 destructive。"""
        from django.db.migrations import RemoveConstraint

        op = _make_op(RemoveConstraint, model_name="mymodel", name="my_constraint")
        migration = _make_migration("0001_drop_constraint", [op])
        node_key = ("fake_app", "0001_drop_constraint")
        loader_mock = _loader_mock({node_key: migration})

        with patch("core.management.commands.check_migrations.MigrationLoader") as ML:
            ML.return_value = loader_mock
            out = io.StringIO()
            call_command("check_migrations", stdout=out)
            output = out.getvalue()
            assert "REMOVE CONSTRAINT" in output or "RemoveConstraint" in output

    def test_command_detects_delete_model_and_remove_field_as_destructive(self):
        """DeleteModel / RemoveField 都要被识别为 destructive。"""
        from django.db.migrations import DeleteModel, RemoveField

        op1 = _make_op(DeleteModel, name="OldModel")
        op2 = _make_op(RemoveField, model_name="kept", name="deprecated")
        migration = _make_migration("0001_drop_stuff", [op1, op2])
        node_key = ("fake_app", "0001_drop_stuff")
        loader_mock = _loader_mock({node_key: migration})

        with patch("core.management.commands.check_migrations.MigrationLoader") as ML:
            ML.return_value = loader_mock
            out = io.StringIO()
            call_command("check_migrations", stdout=out)
            output = out.getvalue()
            assert "DELETE MODEL" in output
            assert "REMOVE FIELD" in output

    def test_command_no_destructive_returns_zero(self):
        """无 destructive 时(默认行为)返回 exit 0。

        默认行为不主动 sys.exit(0),因为 Django BaseCommand 自然返回即视为 0。
        测试通过 mock _loader 让命令无 destructive,并断言命令正常返回。
        """
        from django.db.migrations import AddField

        op = _make_op(AddField, model_name="mymodel", name="new_field")
        migration = _make_migration("0001_add_field", [op])
        node_key = ("fake_app", "0001_add_field")
        loader_mock = _loader_mock({node_key: migration})

        with patch("core.management.commands.check_migrations.MigrationLoader") as ML:
            ML.return_value = loader_mock
            # 默认行为:无 destructive 时不触发 SystemExit
            call_command("check_migrations")  # 不抛 SystemExit 即视为成功

    def test_command_fail_on_destructive_returns_two(self):
        """--fail-on-destructive 检测到 destructive 时返回 exit 2。"""
        from django.db.migrations import DeleteModel

        op = _make_op(DeleteModel, name="DangerousModel")
        migration = _make_migration("0001_drop_danger", [op])
        node_key = ("fake_app", "0001_drop_danger")
        loader_mock = _loader_mock({node_key: migration})

        with patch("core.management.commands.check_migrations.MigrationLoader") as ML:
            ML.return_value = loader_mock
            with pytest.raises(SystemExit) as exc_info:
                call_command("check_migrations", "--fail-on-destructive")
            assert exc_info.value.code == 2

    def test_command_fail_on_destructive_passes_when_safe(self):
        """--fail-on-destructive 在无 destructive 时返回 exit 0(不抛 SystemExit)。"""
        from django.db.migrations import AddField

        op = _make_op(AddField, model_name="mymodel", name="new_field")
        migration = _make_migration("0001_add", [op])
        node_key = ("fake_app", "0001_add")
        loader_mock = _loader_mock({node_key: migration})

        with patch("core.management.commands.check_migrations.MigrationLoader") as ML:
            ML.return_value = loader_mock
            # 无 destructive + --fail-on-destructive → 不抛 SystemExit
            call_command("check_migrations", "--fail-on-destructive")

    def test_command_enumerates_loader_graph_not_app_config(self):
        """命令的核心数据源是 MigrationLoader.graph.nodes。

        模拟一个 app_config 不存在 migrations 模块但 loader.graph 包含节点的情况,
        验证命令仍能枚举该 app 的 pending 迁移。"""
        from django.db.migrations import AddField

        op = _make_op(AddField, model_name="ghostmodel", name="new")
        migration = _make_migration("0001_initial", [op])
        node_key = ("ghost_app", "0001_initial")
        loader_mock = _loader_mock({node_key: migration})

        with patch("core.management.commands.check_migrations.MigrationLoader") as ML:
            ML.return_value = loader_mock
            out = io.StringIO()
            call_command("check_migrations", stdout=out)
            output = out.getvalue()
            # 必须出现 ghost_app 的迁移条目
            assert "[ghost_app] 0001_initial" in output or "ghost_app" in output
