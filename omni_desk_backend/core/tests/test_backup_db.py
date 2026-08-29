"""Tests for backup_db management command.

覆盖:
1. 默认 verify=True 时 pg_dump + gzip 流式压缩 + paired metadata 写入
2. shadow DB 验证 4 步流程(创建→还原→计数→清理)
3. verify 关闭时(shadow 验证被旁路)行为
4. CREATE DATABASE 冲突重试
5. threshold 校验失败抛错
6. atomic write 半成品不污染目录
7. metadata 校验失败时不写 metadata.json
"""

import gzip
import json
from contextlib import contextmanager
from unittest.mock import MagicMock

from django.conf import settings as dj_settings
from django.core.management import CommandError, call_command


POSTGRES_DB_CONFIG = {
    "ENGINE": "django.db.backends.postgresql",
    "NAME": "omnidesk",
    "USER": "omnidesk",
    "PASSWORD": "test-pass",
    "HOST": "db",
    "PORT": "5432",
}


@contextmanager
def _patch_postgres_db():
    """把 SQLite test settings 临时切到 PostgreSQL,以让 backup_db 命令的 engine 检查放行."""
    saved = dj_settings.DATABASES
    dj_settings.DATABASES = {"default": POSTGRES_DB_CONFIG}
    try:
        yield
    finally:
        dj_settings.DATABASES = saved


class _FakeDumpPopen:
    """用作 pg_dump Popen 替换:stdout 给出一段 plain SQL."""

    returncode = 0
    stderr = iter([])

    def __init__(self, *args, **kwargs):
        self.stdout = iter([b"CREATE TABLE sample(id integer);\n"])

    def wait(self):
        return 0


class _FakePsqlPopen:
    """用作 psql Popen 替换:接受 stdin 写入并成功返回."""

    returncode = 0

    def __init__(self, *args, **kwargs):
        self.stdin = MagicMock()

    def poll(self):
        # 模拟进程仍在运行(broken-pipe 防御分支不触发)
        return None

    def wait(self, timeout=None):
        return 0

    def kill(self):
        self.returncode = -9


def _fake_completed(returncode=0, stdout=b"", stderr=b""):
    fake = MagicMock()
    fake.returncode = returncode
    fake.stdout = stdout
    fake.stderr = stderr
    return fake


def _popen_router(cmd, *args, **kwargs):
    """根据 cmd 第一个可执行体选择 fake:pg_dump 用 stdout 流;psql 用 stdin 接受."""
    if cmd and cmd[0] == "pg_dump":
        return _FakeDumpPopen()
    return _FakePsqlPopen()


# ─── 原始测试:verify=True 现在会调 shadow verify,所以 mock 整个 shadow 流程 ───
def test_backup_streams_pg_dump_and_writes_paired_metadata(tmp_path):
    """pg_dump + gzip 流式 + paired metadata;verify=True 走 shadow 全过."""
    from unittest.mock import patch

    output_dir = tmp_path / "batch"
    output_dir.mkdir()

    with (
        _patch_postgres_db(),
        patch("subprocess.Popen", side_effect=_popen_router) as popen,
        # shadow verify 内部所有 subprocess.run 都返 OK(5 行/表 > 0)
        patch("subprocess.run", return_value=_fake_completed(returncode=0, stdout=b"5")),
    ):
        call_command(
            "backup_db",
            batch_id="test",
            output_dir=str(output_dir),
            verify=True,
            skip_media=True,
            verify_shadow_db_prefix="test_shadow_",
        )
    assert "capture_output" not in popen.call_args.kwargs
    with gzip.open(output_dir / "database.sql.gz", "rb") as gz:
        assert gz.read().startswith(b"CREATE")
    metadata = json.loads((output_dir / "metadata.json").read_text())
    assert set(metadata) == {
        "upgrade_id",
        "channel",
        "source_version",
        "database_file",
        "media_file",
        "database_sha256",
        "media_sha256",
        "database_size",
        "media_size",
        "restore_verified",
        "created_at",
    }
    assert metadata["restore_verified"] is True
    assert (output_dir / "media.tar.gz").exists()


# ─── 新增 7 个 shadow verify 测试 ───
def test_verify_runs_shadow_db_end_to_end_when_flag_set(tmp_path):
    """--verify 必跑 4 步:CREATE → restore → count×4 → DROP."""
    from unittest.mock import patch

    output_dir = tmp_path / "batch"
    output_dir.mkdir()
    calls = []

    def fake_run(cmd, *args, **kwargs):
        calls.append(tuple(cmd))
        return _fake_completed(returncode=0, stdout=b"5")

    with (
        _patch_postgres_db(),
        patch("subprocess.Popen", side_effect=_popen_router),
        patch("subprocess.run", side_effect=fake_run),
    ):
        call_command(
            "backup_db",
            batch_id="verify-test",
            output_dir=str(output_dir),
            verify=True,
            skip_media=True,
            verify_shadow_db_prefix="tt_shadow_",
        )

    joined = " | ".join(" ".join(c) for c in calls)
    assert "CREATE DATABASE" in joined, f"CREATE DATABASE 应被调用,实际={joined}"
    assert "DROP DATABASE" in joined, f"DROP DATABASE 应被调用,实际={joined}"

    metadata = json.loads((output_dir / "metadata.json").read_text())
    assert metadata["restore_verified"] is True


def test_verify_does_not_run_shadow_when_flag_absent(tmp_path):
    """verify=False:CREATE DATABASE 一次都不调;metadata.restore_verified=false."""
    from unittest.mock import patch

    output_dir = tmp_path / "batch"
    output_dir.mkdir()

    def fake_run(cmd, *args, **kwargs):
        raise AssertionError(f"subprocess.run 不应被调用,实际 cmd={cmd}")

    with (
        _patch_postgres_db(),
        patch("subprocess.Popen", side_effect=_popen_router),
        patch("subprocess.run", side_effect=fake_run),
    ):
        call_command(
            "backup_db",
            batch_id="no-verify",
            output_dir=str(output_dir),
            skip_media=True,
            verify=False,
        )

    metadata = json.loads((output_dir / "metadata.json").read_text())
    assert metadata["restore_verified"] is False


def test_verify_drops_shadow_db_even_when_psql_fails(tmp_path):
    """restore 步骤失败时,finally 仍 DROP shadow DB(避免残留)."""
    import pytest
    from unittest.mock import patch

    output_dir = tmp_path / "batch"
    output_dir.mkdir()
    drop_calls = []

    def fake_run(cmd, *args, **kwargs):
        if any("DROP DATABASE" in s for s in cmd):
            drop_calls.append(cmd)
            return _fake_completed(returncode=0)
        if any("CREATE DATABASE" in s for s in cmd):
            return _fake_completed(returncode=0)
        return _fake_completed(returncode=0)

    with (
        _patch_postgres_db(),
        patch("subprocess.Popen", side_effect=_popen_router),
        patch("subprocess.run", side_effect=fake_run),
        patch(
            "core.management.commands.backup_db.Command._psql_restore_shadow",
            side_effect=Exception("simulated restore boom"),
        ),
        pytest.raises(Exception, match="simulated restore boom"),
    ):
        call_command(
            "backup_db",
            batch_id="drop-test",
            output_dir=str(output_dir),
            verify=True,
            skip_media=True,
            verify_shadow_db_prefix="drop_shadow_",
        )

    assert drop_calls, "shadow DB DROP 应在 finally 中触发"


def test_verify_raises_when_shadow_restore_count_too_low(tmp_path):
    """4 张核心表只 0 张有数据(<3 threshold)→ CommandError."""
    import pytest
    from unittest.mock import patch

    output_dir = tmp_path / "batch"
    output_dir.mkdir()

    def fake_run(cmd, *args, **kwargs):
        if any("CREATE DATABASE" in s for s in cmd) or any("DROP DATABASE" in s for s in cmd):
            return _fake_completed(returncode=0)
        # count 全 0
        return _fake_completed(returncode=0, stdout=b"0")

    with (
        _patch_postgres_db(),
        patch("subprocess.Popen", side_effect=_popen_router),
        patch("subprocess.run", side_effect=fake_run),
        pytest.raises(CommandError) as exc_info,
    ):
        call_command(
            "backup_db",
            batch_id="count-low",
            output_dir=str(output_dir),
            verify=True,
            skip_media=True,
            verify_shadow_db_prefix="cl_shadow_",
        )
    assert "non-empty" in str(exc_info.value).lower() or "threshold" in str(exc_info.value).lower()


def test_verify_retries_create_database_on_conflict(tmp_path):
    """CREATE DATABASE 首次冲突 → DROP → CREATE 重试;第二次成功."""
    from unittest.mock import patch

    output_dir = tmp_path / "batch"
    output_dir.mkdir()
    state = {"create_calls": 0}

    def fake_run(cmd, *args, **kwargs):
        if any("CREATE DATABASE" in s for s in cmd):
            state["create_calls"] += 1
            if state["create_calls"] == 1:
                return _fake_completed(returncode=1, stderr=b"database already exists")
            return _fake_completed(returncode=0)
        if any("DROP DATABASE" in s for s in cmd):
            return _fake_completed(returncode=0)
        return _fake_completed(returncode=0, stdout=b"5")

    with (
        _patch_postgres_db(),
        patch("subprocess.Popen", side_effect=_popen_router),
        patch("subprocess.run", side_effect=fake_run),
    ):
        call_command(
            "backup_db",
            batch_id="retry-test",
            output_dir=str(output_dir),
            verify=True,
            skip_media=True,
            verify_shadow_db_prefix="rt_shadow_",
        )

    assert state["create_calls"] == 2, f"CREATE 应被调 2 次,实际={state['create_calls']}"


def test_verify_metadata_is_atomic_write(tmp_path):
    """os.replace 失败时,metadata.json 不应存在(无 half-written)."""
    import pytest
    from unittest.mock import patch

    output_dir = tmp_path / "batch"
    output_dir.mkdir()

    with (
        _patch_postgres_db(),
        patch("subprocess.Popen", side_effect=_popen_router),
        patch("subprocess.run", return_value=_fake_completed(returncode=0, stdout=b"5")),
        patch("os.replace", side_effect=OSError("simulated replace failure")),
        pytest.raises(CommandError) as exc_info,
    ):
        call_command(
            "backup_db",
            batch_id="atomic",
            output_dir=str(output_dir),
            verify=True,
            skip_media=True,
            verify_shadow_db_prefix="at_shadow_",
        )
    assert "atomically write" in str(exc_info.value).lower()
    assert not (output_dir / "metadata.json").exists(), "os.replace 失败后 metadata.json 不应存在"
    assert not (output_dir / "metadata.json.tmp").exists()


def test_verify_omits_metadata_when_validation_fails(tmp_path):
    """shadow verify 任何一步抛 CommandError → metadata.json 不写盘."""
    import pytest
    from unittest.mock import patch

    output_dir = tmp_path / "batch"
    output_dir.mkdir()

    def fake_run(cmd, *args, **kwargs):
        if any("CREATE DATABASE" in s for s in cmd) or any("DROP DATABASE" in s for s in cmd):
            return _fake_completed(returncode=0)
        return _fake_completed(returncode=0, stdout=b"0")

    with (
        _patch_postgres_db(),
        patch("subprocess.Popen", side_effect=_popen_router),
        patch("subprocess.run", side_effect=fake_run),
        pytest.raises(CommandError),
    ):
        call_command(
            "backup_db",
            batch_id="fail-meta",
            output_dir=str(output_dir),
            verify=True,
            skip_media=True,
            verify_shadow_db_prefix="fm_shadow_",
        )

    assert not (output_dir / "metadata.json").exists(), "verify 失败时 metadata.json 不应写盘"


def test_verify_lowercases_shadow_db_name_for_postgres(tmp_path):
    """shadow DB 名必须 lowercase — PostgreSQL 在 CREATE DATABASE 时会把未加引号的
    标识符自动小写化;若保留 batch_id 中的大写字母,后续 `psql -d <shadow>` 会以原
    大小写查询 → "database does not exist"。修法:sanitized[:20].lower()。
    """
    from unittest.mock import patch

    output_dir = tmp_path / "batch"
    output_dir.mkdir()
    captured_shadow_db = []

    def fake_run(cmd, *args, **kwargs):
        # 抓 CREATE DATABASE 命令的 DB 名
        for s in cmd:
            if isinstance(s, str) and s.startswith("CREATE DATABASE "):
                captured_shadow_db.append(s.split()[-1])
        return _fake_completed(returncode=0, stdout=b"5")

    with (
        _patch_postgres_db(),
        patch("subprocess.Popen", side_effect=_popen_router),
        patch("subprocess.run", side_effect=fake_run),
    ):
        call_command(
            "backup_db",
            batch_id="Mixed-Case-Batch-Id-ABC-XYZ-12345",
            output_dir=str(output_dir),
            verify=True,
            skip_media=True,
        )

    assert captured_shadow_db, "应至少调用一次 CREATE DATABASE"
    for name in captured_shadow_db:
        assert name == name.lower(), f"shadow DB 名必须 lowercase,实际={name!r}"
        # 默认前缀 omnidesk_shadow_ + sanitized[:20].lower()
        assert name.startswith("omnidesk_shadow_"), f"shadow DB 必须以默认前缀开头,实际={name!r}"
