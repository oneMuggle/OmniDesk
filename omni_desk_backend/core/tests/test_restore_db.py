"""Tests for restore_db management command — Task 4: 安全恢复命令.

覆盖:
1. psql 命令必须带 -v ON_ERROR_STOP=1 与 --single-transaction(单事务失败即停)
2. psql 非零退出 → CommandError(失败立即停止,不静默)
3. --batch-dir 模式:校验 metadata.json 必填字段
4. --batch-dir 模式:sha256 不匹配 → CommandError
5. --batch-dir 模式:缺 metadata.json → CommandError
6. 失败时不污染原数据库(不会跑完一半)

实现策略:所有 subprocess 调用都被 mock,不依赖真实 psql/pg_dump。
test settings 用 SQLite — 每个用 psql 的测试用 _patch_postgres_db 把
DATABASES 切到 PostgreSQL,这样命令内的 engine 检查放行。
"""

import gzip
import hashlib
import json
from contextlib import contextmanager
from unittest.mock import patch, MagicMock

import pytest
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
    """在 SQLite test settings 下临时把 DATABASES 切到 PostgreSQL 配置.

    命令内的 engine 检查看到 PostgreSQL 才放行执行到 subprocess.run。
    """
    saved = dj_settings.DATABASES
    dj_settings.DATABASES = {"default": POSTGRES_DB_CONFIG}
    try:
        yield
    finally:
        dj_settings.DATABASES = saved


def _make_fake_process(returncode=0, stderr=b""):
    """构造一个伪 subprocess.CompletedProcess — 兼容 Popen/run 的子类."""
    fake = MagicMock()
    fake.returncode = returncode
    fake.stderr = stderr
    return fake


def _make_valid_batch(
    batch_dir,
    *,
    db_sql=b"CREATE TABLE sample(id integer);\n",
    media_bytes=b"placeholder-media-content",
    upgrade_id="test-batch-1",
    source_version="v0.7.0",
    channel="stable",
):
    """构造一个合法的成组备份目录,返回 metadata dict."""
    batch_dir.mkdir(parents=True, exist_ok=True)
    db_path = batch_dir / "database.sql.gz"
    media_path = batch_dir / "media.tar.gz"
    db_path.write_bytes(gzip.compress(db_sql))
    media_path.write_bytes(media_bytes)
    metadata = {
        "upgrade_id": upgrade_id,
        "channel": channel,
        "source_version": source_version,
        "database_file": db_path.name,
        "media_file": media_path.name,
        "database_sha256": hashlib.sha256(db_path.read_bytes()).hexdigest(),
        "media_sha256": hashlib.sha256(media_path.read_bytes()).hexdigest(),
        "database_size": db_path.stat().st_size,
        "media_size": media_path.stat().st_size,
        "restore_verified": True,
        "created_at": "2026-07-27T10:00:00Z",
    }
    (batch_dir / "metadata.json").write_text(json.dumps(metadata))
    return metadata


def test_restore_passes_on_error_stop_and_single_transaction_to_psql(tmp_path):
    """psql 命令必须带 ON_ERROR_STOP=1 与 --single-transaction."""
    backup = tmp_path / "db.sql.gz"
    backup.write_bytes(gzip.compress(b"SELECT 1;\n"))
    fake = _make_fake_process(returncode=0)
    with _patch_postgres_db(), patch("subprocess.run", return_value=fake) as runner:
        call_command("restore_db", str(backup), force=True)
    cmd = runner.call_args.args[0]
    assert "-v" in cmd and "ON_ERROR_STOP=1" in cmd, f"psql 必须带 -v ON_ERROR_STOP=1,实际={cmd}"
    assert "--single-transaction" in cmd, f"psql 必须带 --single-transaction 以保证原子回滚,实际={cmd}"


def test_restore_raises_command_error_on_psql_failure(tmp_path):
    """psql 非零退出 → CommandError;不能静默吞错."""
    backup = tmp_path / "db.sql.gz"
    backup.write_bytes(gzip.compress(b"BAD SQL;\n"))
    fake = _make_fake_process(returncode=1, stderr=b"ERROR: syntax error")
    with _patch_postgres_db(), patch("subprocess.run", return_value=fake), pytest.raises(CommandError) as exc:
        call_command("restore_db", str(backup), force=True)
    assert "psql failed" in str(exc.value).lower() or "ERROR" in str(exc.value)


def test_restore_propagates_stderr_in_command_error(tmp_path):
    """CommandError 必须携带 stderr 内容,便于运维定位."""
    backup = tmp_path / "db.sql.gz"
    backup.write_bytes(gzip.compress(b"BAD SQL;\n"))
    fake = _make_fake_process(returncode=3, stderr=b"psql:connect:Connection refused")
    with _patch_postgres_db(), patch("subprocess.run", return_value=fake), pytest.raises(CommandError) as exc:
        call_command("restore_db", str(backup), force=True)
    msg = str(exc.value)
    assert "Connection refused" in msg or "psql" in msg.lower()


def test_restore_validates_batch_metadata_when_batch_dir_given(tmp_path):
    """--batch-dir 模式:metadata.json 必填字段缺失 → CommandError."""
    batch = tmp_path / "batch"
    batch.mkdir()
    # 缺少 metadata.json — 必须立即拒绝
    (batch / "database.sql.gz").write_bytes(gzip.compress(b"CREATE TABLE t(i int);\n"))
    (batch / "media.tar.gz").write_bytes(b"placeholder")
    fake = _make_fake_process(returncode=0)
    with patch("subprocess.run", return_value=fake), pytest.raises(CommandError) as exc:
        call_command("restore_db", "--batch-dir", str(batch), force=True)
    assert "metadata" in str(exc.value).lower() or "missing" in str(exc.value).lower()


def test_restore_rejects_batch_with_missing_required_metadata_fields(tmp_path):
    """metadata.json 必填字段缺失(如缺 upgrade_id)→ CommandError."""
    batch = tmp_path / "batch"
    batch.mkdir()
    (batch / "database.sql.gz").write_bytes(gzip.compress(b"SELECT 1;\n"))
    (batch / "media.tar.gz").write_bytes(b"placeholder")
    # 故意缺几个字段
    bad_meta = {"upgrade_id": "x", "database_file": "database.sql.gz"}
    (batch / "metadata.json").write_text(json.dumps(bad_meta))
    fake = _make_fake_process(returncode=0)
    with patch("subprocess.run", return_value=fake), pytest.raises(CommandError):
        call_command("restore_db", "--batch-dir", str(batch), force=True)


def test_restore_rejects_batch_with_mismatched_checksum(tmp_path):
    """sha256 不匹配 → CommandError,绝不放行坏备份."""
    _make_valid_batch(tmp_path / "batch")
    # 篡改 database.sql.gz,让 sha256/size 与 metadata 不一致
    bad_batch = tmp_path / "batch"
    (bad_batch / "database.sql.gz").write_bytes(gzip.compress(b"MUTATED SQL;\n"))
    fake = _make_fake_process(returncode=0)
    with _patch_postgres_db(), patch("subprocess.run", return_value=fake), pytest.raises(CommandError) as exc:
        call_command("restore_db", "--batch-dir", str(bad_batch), force=True)
    msg = str(exc.value).lower()
    # 实现可能先报 size 不匹配,也可能直接报 checksum — 任一都说明校验生效
    assert "checksum" in msg or "sha256" in msg or "size mismatch" in msg


def test_restore_uses_database_file_from_metadata(tmp_path):
    """--batch-dir 模式:还原的 database 路径必须来自 metadata.json 的 database_file."""
    batch = tmp_path / "batch"
    _make_valid_batch(batch, db_sql=b"SELECT 42;\n")

    captured = {}

    def fake_run(*args, **kwargs):
        # 在 with gzip 块仍 open 时立即读 stdin
        stdin = kwargs.get("stdin")
        if stdin is not None and hasattr(stdin, "read"):
            try:
                # gzip.open 已经解压 — 读到的是明文 SQL
                captured["stdin_bytes"] = stdin.read()
            except ValueError:
                pass
        return _make_fake_process(returncode=0)

    with _patch_postgres_db(), patch("subprocess.run", side_effect=fake_run):
        call_command("restore_db", "--batch-dir", str(batch), force=True)

    assert "stdin_bytes" in captured, "psql 必须有 stdin 输入"
    assert captured["stdin_bytes"].startswith(b"SELECT 42;")


def test_restore_skips_subprocess_when_metadata_validation_fails(tmp_path):
    """metadata 校验失败时,不能调用 psql — 防止脏数据污染数据库."""
    batch = tmp_path / "batch"
    batch.mkdir()
    # 不写 metadata.json
    with patch("subprocess.run") as runner, pytest.raises(CommandError):
        call_command("restore_db", "--batch-dir", str(batch), force=True)
    assert runner.call_count == 0, "metadata 校验失败时 psql 不应被调用"


def test_restore_rejects_path_traversal_in_database_file_metadata(tmp_path):
    """metadata.json 的 database_file 不能含路径穿越(../../etc/passwd)."""
    batch = tmp_path / "batch"
    batch.mkdir()
    (batch / "database.sql.gz").write_bytes(gzip.compress(b"x"))
    (batch / "media.tar.gz").write_bytes(b"y")
    bad_meta = {
        "upgrade_id": "x",
        "channel": "stable",
        "source_version": "v1",
        "database_file": "../../etc/passwd",  # path traversal!
        "media_file": "media.tar.gz",
        "database_sha256": hashlib.sha256(b"x").hexdigest(),
        "media_sha256": hashlib.sha256(b"y").hexdigest(),
        "database_size": 1,
        "media_size": 1,
        "restore_verified": True,
        "created_at": "2026-07-27T10:00:00Z",
    }
    (batch / "metadata.json").write_text(json.dumps(bad_meta))
    fake = _make_fake_process(returncode=0)
    with patch("subprocess.run", return_value=fake), pytest.raises(CommandError):
        call_command("restore_db", "--batch-dir", str(batch), force=True)


def test_restore_does_not_swallow_subprocess_file_not_found(tmp_path):
    """psql 未安装 (FileNotFoundError) → CommandError,不能静默."""
    backup = tmp_path / "db.sql.gz"
    backup.write_bytes(gzip.compress(b"x"))
    with (
        _patch_postgres_db(),
        patch("subprocess.run", side_effect=FileNotFoundError("psql not found")),
        pytest.raises(CommandError),
    ):
        call_command("restore_db", str(backup), force=True)
