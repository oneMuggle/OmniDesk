"""create_smoke_user management command 测试(P0-5)

覆盖:
- 创建新账号 + 强制 is_staff=False is_superuser=False
- 幂等:已有账号 update 不重置密码
- --reset 强制更新密码
- --disable / 不存在的 disable 报错
- --dry-run 不写入
- 缺密码/缺 username 报错
- email 字段置空
- 环境变量 fallback
"""

import io

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError

User = get_user_model()


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """隔离 .env 变量,避免污染。"""
    for key in ("SMOKE_TEST_USER", "SMOKE_TEST_PASSWORD"):
        monkeypatch.delenv(key, raising=False)


def _invoke(*args, **kwargs):
    """helper: 跑 mgmt command,捕获 stdout/stderr。"""
    out = io.StringIO()
    err = io.StringIO()
    kwargs.setdefault("stdout", out)
    kwargs.setdefault("stderr", err)
    call_command("create_smoke_user", *args, **kwargs)
    return out.getvalue(), err.getvalue()


@pytest.mark.django_db
def test_create_new_user():
    """新账号:is_staff=False is_superuser=False,password 已设,email 空。"""
    out, _ = _invoke(username="smoke-bot", password="pw1")
    user = User.objects.get(username="smoke-bot")
    assert user.is_staff is False
    assert user.is_superuser is False
    assert user.is_active is True
    assert user.email in (None, "")
    assert user.check_password("pw1")
    assert "create 成功" in out


@pytest.mark.django_db
def test_existing_user_no_password_change():
    """已有账号 update:不传 --reset → 旧密码保留。"""
    User.objects.create_user(username="smoke-bot", password="old")
    _invoke(username="smoke-bot", password="new")
    user = User.objects.get(username="smoke-bot")
    assert user.check_password("old")  # 未被 new 覆盖
    assert not user.check_password("new")


@pytest.mark.django_db
def test_reset_updates_password():
    """已有账号 + --reset → 密码更新。"""
    User.objects.create_user(username="smoke-bot", password="old")
    _invoke(username="smoke-bot", password="new", reset=True)
    user = User.objects.get(username="smoke-bot")
    assert user.check_password("new")


@pytest.mark.django_db
def test_existing_user_email_cleared():
    """已有账号若 email 不为空,会被强制置空(防恢复攻击)。"""
    User.objects.create_user(username="smoke-bot", password="pw", email="leak@x.com")
    _invoke(username="smoke-bot", password="pw")
    user = User.objects.get(username="smoke-bot")
    assert user.email in (None, "")


@pytest.mark.django_db
def test_disable_existing_user():
    """--disable 禁用账号。"""
    User.objects.create_user(username="smoke-bot", password="pw")
    out, _ = _invoke(username="smoke-bot", disable=True)
    assert User.objects.get(username="smoke-bot").is_active is False
    assert "已禁用" in out


@pytest.mark.django_db
def test_disable_nonexistent_raises():
    """--disable 目标账号不存在 → CommandError。"""
    with pytest.raises(CommandError, match="不存在"):
        _invoke(username="ghost", disable=True)


@pytest.mark.django_db
def test_dry_run_no_write():
    """--dry-run:打印预期动作但不写入 DB。"""
    out, _ = _invoke(username="smoke-bot", password="pw", dry_run=True)
    assert "DRY-RUN" in out
    assert not User.objects.filter(username="smoke-bot").exists()


def test_missing_password_raises():
    """不传 password 且环境变量也没设 → CommandError。"""
    with pytest.raises(CommandError, match="password 不能为空"):
        _invoke(username="smoke-bot", password="")


def test_missing_username_raises(monkeypatch):
    """username 不能为空。"""
    monkeypatch.delenv("SMOKE_TEST_USER", raising=False)
    with pytest.raises(CommandError, match="username 不能为空"):
        _invoke(username="", password="pw")


@pytest.mark.django_db
def test_environment_variable_fallback(monkeypatch):
    """$SMOKE_TEST_USER / $SMOKE_TEST_PASSWORD 作为默认值。"""
    monkeypatch.setenv("SMOKE_TEST_USER", "env-user")
    monkeypatch.setenv("SMOKE_TEST_PASSWORD", "env-pw")
    _invoke()  # 不传 --username / --password
    user = User.objects.get(username="env-user")
    assert user.check_password("env-pw")
    assert user.is_staff is False


@pytest.mark.django_db
def test_re_enable_via_disable_path():
    """_set_active(active=True) 重新启用账号。"""
    from users.management.commands.create_smoke_user import Command

    User.objects.create_user(username="smoke-bot", password="pw", is_active=False)
    cmd = Command()
    cmd._set_active("smoke-bot", active=True, dry_run=False)
    assert User.objects.get(username="smoke-bot").is_active is True