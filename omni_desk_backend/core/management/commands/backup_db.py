"""Backup database and media files.

两种模式:

- 默认(无 --db-only / --media-only):**配对批次**,生成 `database.sql.gz` +
  `media.tar.gz` + `metadata.json` + `*.sha256` 副文件。offline-upgrade 安全
  链路(verify_backup_batch.sh / rollback.sh / deploy_offline.sh)依赖此结构。
- `--db-only` / `--media-only`:**legacy 单文件模式**,`backup_v*` / `media_v*`
  命名,兼容 smoke_tests.sh 阶段 11 与 backup.sh 透传参数。
"""

import gzip
import hashlib
import json
import os
import re
import subprocess
import tarfile
from datetime import datetime, timezone
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


# shadow DB 名前缀(默认生产用)。测试可通过 --verify-shadow-db-prefix 隔离。
_DEFAULT_SHADOW_PREFIX = "omnidesk_shadow_"
# shadow DB 名只允许 [a-zA-Z0-9_],避免 SQL 注入与 psql 参数解析问题。
_SHADOW_DB_NAME_RE = re.compile(r"[^a-zA-Z0-9_]")
# 4 张核心表,与 smoke_tests.sh 阶段 11 阈值保持一致(≥3/4 非空即视为可恢复)。
_SHADOW_TABLES = ("users_customuser", "memos_memo", "auth_group", "django_migrations")
_SHADOW_NON_EMPTY_THRESHOLD = 3


class Command(BaseCommand):
    help = (
        "Backup database and media files. "
        "Default: paired batch (database.sql.gz + media.tar.gz + metadata.json + *.sha256). "
        "--db-only / --media-only: legacy single-file mode."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--media-only", action="store_true", help="Only backup media files (legacy single-file mode)"
        )
        parser.add_argument("--db-only", action="store_true", help="Only backup database (legacy single-file mode)")
        parser.add_argument("--output-dir", type=str, default="/opt/omnidesk/backups", help="Backup output directory")
        parser.add_argument("--batch-id", help="Paired batch upgrade_id (default: UTC timestamp)")
        parser.add_argument(
            "--verify",
            action="store_true",
            help=(
                "Paired batch: end-to-end verify by restoring into a shadow DB and "
                "checking core tables. On success, metadata.restore_verified=true."
            ),
        )
        parser.add_argument(
            "--no-verify",
            action="store_true",
            help="Skip shadow verification even when --verify would otherwise default on (emergency bypass).",
        )
        parser.add_argument(
            "--verify-timeout",
            type=int,
            default=600,
            help="Timeout in seconds for each subprocess step of shadow verification (default: 600).",
        )
        parser.add_argument(
            "--verify-shadow-db-prefix",
            default=_DEFAULT_SHADOW_PREFIX,
            help="Prefix for the ephemeral shadow DB name (default: omnidesk_shadow_).",
        )
        parser.add_argument(
            "--skip-media", action="store_true", help="Paired batch: skip media dump (writes empty media.tar.gz)"
        )

    def handle(self, *args, **options):
        output_dir = Path(options["output_dir"])
        output_dir.mkdir(parents=True, exist_ok=True)

        if options["media_only"] or options["db_only"]:
            self._legacy_backup(output_dir, options)
        else:
            self._paired_backup(output_dir, options)

    # ─── legacy single-file mode ─────────────────────────────────
    def _legacy_backup(self, output_dir, options):
        version = getattr(settings, "APP_VERSION", "unknown")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        if not options["media_only"]:
            self._backup_db(output_dir, version, timestamp)
        if not options["db_only"]:
            self._backup_media(output_dir, version, timestamp)

        self._cleanup_old_backups(output_dir)

    def _backup_db(self, output_dir, version, timestamp):
        db = settings.DATABASES["default"]
        if db["ENGINE"] != "django.db.backends.postgresql":
            self.stdout.write(self.style.WARNING("Skipping DB backup — not using PostgreSQL."))
            return

        filename = f"backup_v{version}_{timestamp}.sql.gz"
        filepath = output_dir / filename

        self.stdout.write(f'Backing up database "{db["NAME"]}" ...')

        env = os.environ.copy()
        env["PGPASSWORD"] = db["PASSWORD"]

        cmd = [
            "pg_dump",
            "-h",
            db["HOST"],
            "-p",
            str(db["PORT"]),
            "-U",
            db["USER"],
            "-d",
            db["NAME"],
            "--no-owner",
            "--no-privileges",
        ]

        try:
            # Fix-12: 用 plain SQL format + Python gzip 显式流式压缩
            # 原因 1: subprocess.run(stdout=gzip.open(...)) 是 Python 已知 bug — 关闭顺序错位
            #         导致 .sql.gz 文件实际为 plain SQL 文本,gunzip 报 "invalid magic"
            # 原因 2: -Fc custom format 需要 pg_restore 还原,smoke_tests 阶段 11 用 psql
            #         plain SQL 才能 psql 直接管道还原(更通用,运维友好)
            with open(filepath, "wb") as out:
                result = subprocess.run(
                    cmd,  # 默认 plain SQL format,兼容 psql 直接还原
                    env=env,
                    capture_output=True,  # Ruff UP022:优于 stdout/stderr=PIPE
                    check=False,
                )
                if result.returncode != 0:
                    raise CommandError(f"pg_dump failed: {result.stderr.decode()}")
                # 用 Python gzip 流式压缩到文件 — 避免 subprocess+file-like 关闭顺序问题
                with gzip.GzipFile(fileobj=out, mode="wb") as gz:
                    gz.write(result.stdout)

            size_mb = filepath.stat().st_size / (1024 * 1024)
            self.stdout.write(self.style.SUCCESS(f"Database backup saved: {filepath} ({size_mb:.1f} MB)"))
        except FileNotFoundError:
            raise CommandError("pg_dump not found. Please install PostgreSQL client tools.")

    def _backup_media(self, output_dir, version, timestamp):
        media_root = Path(getattr(settings, "MEDIA_ROOT", ""))
        if not media_root.is_dir():
            self.stdout.write(self.style.WARNING(f"Media directory not found: {media_root}"))
            return

        filename = f"media_v{version}_{timestamp}.tar.gz"
        filepath = output_dir / filename

        self.stdout.write(f"Backing up media files from {media_root} ...")

        with tarfile.open(filepath, "w:gz") as tar:
            tar.add(media_root, arcname="media")

        size_mb = filepath.stat().st_size / (1024 * 1024)
        self.stdout.write(self.style.SUCCESS(f"Media backup saved: {filepath} ({size_mb:.1f} MB)"))

    def _cleanup_old_backups(self, output_dir, keep=10):
        """Keep only the latest N backup sets (db + media)."""
        db_backups = sorted(output_dir.glob("backup_v*.sql.gz"), reverse=True)
        media_backups = sorted(output_dir.glob("media_v*.tar.gz"), reverse=True)

        for old in db_backups[keep:]:
            old.unlink()
            self.stdout.write(f"Removed old backup: {old.name}")

        for old in media_backups[keep:]:
            old.unlink()
            self.stdout.write(f"Removed old media backup: {old.name}")

    # ─── paired batch mode ───────────────────────────────────────
    def _paired_backup(self, output_dir, options):
        batch_id = options["batch_id"] or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        channel = os.environ.get("CHANNEL", os.environ.get("RELEASE_CHANNEL", "stable"))
        source = os.environ.get("SOURCE_VERSION", getattr(settings, "APP_VERSION", "unknown"))
        db_file = output_dir / "database.sql.gz"
        media_file = output_dir / "media.tar.gz"

        self._dump_database(db_file)
        if options["skip_media"]:
            media_file.write_bytes(b"")
        else:
            self._dump_media(media_file)

        if not db_file.exists() or not media_file.exists():
            raise CommandError("database and media backups must both exist")

        # Shadow 验证:若任一步失败抛 CommandError,metadata.json 不会写盘,
        # 与 docs/superpowers/plans/2026-07-25-offline-upgrade-data-safety.md L210/L257 一致
        # (失败时不写 restore_verified=true,DB + media + shadow 全部成功才允许)。
        restore_verified = False
        want_verify = options["verify"] and not options["no_verify"]
        if want_verify:
            self._verify_restore_in_shadow(db_file, batch_id, options)
            restore_verified = True

        metadata = {
            "upgrade_id": batch_id,
            "channel": channel,
            "source_version": source,
            "database_file": db_file.name,
            "media_file": media_file.name,
            "database_sha256": self._checksum(db_file),
            "media_sha256": self._checksum(media_file),
            "database_size": db_file.stat().st_size,
            "media_size": media_file.stat().st_size,
            "restore_verified": restore_verified,
            "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        for path, digest in ((db_file, metadata["database_sha256"]), (media_file, metadata["media_sha256"])):
            path.with_name(path.name + ".sha256").write_text(f"{digest}  {path.name}\n")
        self._atomic_write_json(output_dir / "metadata.json", metadata)

        self.stdout.write(
            self.style.SUCCESS(
                f"Paired backup batch written to {output_dir} (upgrade_id={batch_id}, restore_verified={restore_verified})"
            )
        )

    def _dump_database(self, target):
        db = settings.DATABASES["default"]
        env = os.environ.copy()
        env["PGPASSWORD"] = db.get("PASSWORD", "")
        cmd = [
            "pg_dump",
            "-h",
            db["HOST"],
            "-p",
            str(db["PORT"]),
            "-U",
            db["USER"],
            "-d",
            db["NAME"],
            "--no-owner",
            "--no-privileges",
        ]
        temp = target.with_suffix(target.suffix + ".tmp")
        try:
            # 逐块读 pg_dump stdout 写入 gzip,避免整个转储载入内存
            # (plain SQL format,兼容 psql 直接管道还原,见 Fix-12)
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
            stdout_stream = process.stdout
            chunks = (
                stdout_stream
                if hasattr(stdout_stream, "__iter__") and not hasattr(stdout_stream, "readline")
                else iter(stdout_stream.readline, b"")
            )
            with temp.open("wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb") as gz:
                for chunk in chunks:
                    gz.write(chunk)
            stderr_stream = process.stderr
            stderr = (stderr_stream.read() if hasattr(stderr_stream, "read") else b"").decode(errors="replace")
            if process.wait() != 0:
                raise CommandError(f"pg_dump failed: {stderr}")
            temp.replace(target)
        except FileNotFoundError as exc:
            raise CommandError("pg_dump not found. Please install PostgreSQL client tools.") from exc
        finally:
            temp.unlink(missing_ok=True)

    def _dump_media(self, target):
        root = Path(getattr(settings, "MEDIA_ROOT", ""))
        if not root.is_dir():
            raise CommandError(f"Media directory not found: {root}")
        temp = target.with_suffix(target.suffix + ".tmp")
        with tarfile.open(temp, "w:gz") as archive:
            archive.add(root, arcname="media")
        temp.replace(target)

    @staticmethod
    def _checksum(path):
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    # ─── atomic write + shadow verification ────────────────────────
    @staticmethod
    def _atomic_write_json(target, payload):
        """Atomic JSON write: temp file + os.replace(POSIX rename 原子).

        写失败不会留 half-written metadata.json(.tmp 总在 finally 清理)。
        OSError 包装为 CommandError 以与其他失败路径一致。
        """
        target = Path(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = target.with_suffix(target.suffix + ".tmp")
        try:
            temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
            try:
                os.replace(temp, target)
            except OSError as exc:
                raise CommandError(f"Failed to atomically write {target}: {exc}") from exc
        finally:
            temp.unlink(missing_ok=True)

    def _verify_restore_in_shadow(self, db_file, batch_id, options):
        """Restore database.sql.gz into a shadow DB and validate core tables.

        4 步 + finally 清理:
          1. CREATE DATABASE <shadow>(冲突 → DROP 重试一次)
          2. gunzip <db_file> | psql -v ON_ERROR_STOP=1 -d <shadow>(Popen 流式)
          3. SELECT count(*) FROM <table> × 4 张核心表,≥3/4 非空
          4. DROP DATABASE <shadow>(finally 兜底)

        任一步失败抛 CommandError,**不写 metadata.json**,与
        docs/superpowers/plans/2026-07-25-offline-upgrade-data-safety.md L210/L257 一致。
        """
        db = settings.DATABASES["default"]
        if db["ENGINE"] != "django.db.backends.postgresql":
            raise CommandError(f"--verify requires PostgreSQL backend (current: {db['ENGINE']})")

        prefix = options["verify_shadow_db_prefix"] or _DEFAULT_SHADOW_PREFIX
        sanitized = _SHADOW_DB_NAME_RE.sub("", batch_id)[:20]
        shadow_db = f"{prefix}{sanitized}"
        timeout = options["verify_timeout"]

        env = os.environ.copy()
        env["PGPASSWORD"] = db.get("PASSWORD", "")
        base_psql = ["psql", "-h", db["HOST"], "-p", str(db["PORT"]), "-U", db["USER"]]

        # Step 1: CREATE DATABASE (冲突 → DROP 重试一次)
        self._psql_create_shadow(shadow_db, base_psql, env, timeout)

        try:
            # Step 2: gunzip | psql 流式还原
            self._psql_restore_shadow(db_file, shadow_db, base_psql, env, timeout)
            # Step 3: 4 表 count 校验
            non_empty = self._psql_count_shadow(shadow_db, base_psql, env, timeout)
            if non_empty < _SHADOW_NON_EMPTY_THRESHOLD:
                raise CommandError(
                    f"Shadow verification failed: only {non_empty}/{len(_SHADOW_TABLES)} "
                    f"core tables non-empty (threshold: {_SHADOW_NON_EMPTY_THRESHOLD})"
                )
            self.stdout.write(
                self.style.SUCCESS(f"Shadow verification OK ({non_empty}/{len(_SHADOW_TABLES)} core tables non-empty)")
            )
        finally:
            # Step 4: 清理 shadow DB(best-effort,失败仅 warning)
            drop_cmd = base_psql + ["-d", "postgres", "-c", f"DROP DATABASE IF EXISTS {shadow_db}"]
            try:
                drop_result = subprocess.run(drop_cmd, env=env, capture_output=True, timeout=timeout, check=False)
                if drop_result.returncode != 0:
                    self.stdout.write(
                        self.style.WARNING(
                            f"Failed to drop shadow DB {shadow_db}: {drop_result.stderr.decode(errors='replace')}"
                        )
                    )
            except Exception as exc:
                self.stdout.write(self.style.WARNING(f"Failed to drop shadow DB {shadow_db}: {exc}"))

    def _psql_create_shadow(self, shadow_db, base_psql, env, timeout):
        """CREATE DATABASE <shadow>;冲突时 DROP 并重试一次."""
        create_cmd = base_psql + ["-d", "postgres", "-c", f"CREATE DATABASE {shadow_db}"]
        try:
            result = subprocess.run(create_cmd, env=env, capture_output=True, timeout=timeout, check=False)
        except FileNotFoundError as exc:
            raise CommandError("psql not found. Please install PostgreSQL client tools.") from exc
        if result.returncode == 0:
            return
        # 冲突:DROP 重试
        self.stdout.write(self.style.WARNING(f"Shadow DB {shadow_db} exists, dropping and retrying"))
        drop_cmd = base_psql + ["-d", "postgres", "-c", f"DROP DATABASE {shadow_db}"]
        subprocess.run(drop_cmd, env=env, capture_output=True, timeout=timeout, check=False)
        result = subprocess.run(create_cmd, env=env, capture_output=True, timeout=timeout, check=False)
        if result.returncode != 0:
            raise CommandError(
                f"Shadow DB CREATE DATABASE failed after retry: {result.stderr.decode(errors='replace')}"
            )

    def _psql_restore_shadow(self, db_file, shadow_db, base_psql, env, timeout):
        """gunzip <db_file> | psql -d <shadow> -v ON_ERROR_STOP=1(流式,Popen pipe).

        用 subprocess.Popen + 明示 stdin 写 chunk,避免 Fix-12 关闭顺序 bug。
        """
        cmd = base_psql + ["-d", shadow_db, "-v", "ON_ERROR_STOP=1"]
        try:
            process = subprocess.Popen(cmd, stdin=subprocess.PIPE, env=env)
        except FileNotFoundError as exc:
            raise CommandError("psql not found. Please install PostgreSQL client tools.") from exc
        try:
            with db_file.open("rb") as raw, gzip.GzipFile(fileobj=raw, mode="rb") as gz:
                while True:
                    chunk = gz.read(64 * 1024)
                    if not chunk:
                        break
                    process.stdin.write(chunk)
            process.stdin.close()
            returncode = process.wait(timeout=timeout)
        except Exception:
            process.kill()
            raise
        if returncode != 0:
            raise CommandError(f"Shadow restore (psql) exited {returncode}")

    def _psql_count_shadow(self, shadow_db, base_psql, env, timeout):
        """对 _SHADOW_TABLES 每张表 SELECT count(*),返回非空表数."""
        non_empty = 0
        for table in _SHADOW_TABLES:
            cmd = base_psql + ["-d", shadow_db, "-tAc", f"SELECT count(*) FROM {table}"]
            try:
                result = subprocess.run(cmd, env=env, capture_output=True, timeout=timeout, check=False)
            except FileNotFoundError as exc:
                raise CommandError("psql not found.") from exc
            if result.returncode != 0:
                continue
            try:
                count = int(result.stdout.decode().strip())
            except (ValueError, UnicodeDecodeError):
                continue
            if count > 0:
                non_empty += 1
        return non_empty
