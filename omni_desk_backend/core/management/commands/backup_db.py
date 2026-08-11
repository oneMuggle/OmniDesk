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
import subprocess
import tarfile
from datetime import datetime, timezone
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = (
        "Backup database and media files. "
        "Default: paired batch (database.sql.gz + media.tar.gz + metadata.json + *.sha256). "
        "--db-only / --media-only: legacy single-file mode."
    )

    def add_arguments(self, parser):
        parser.add_argument("--media-only", action="store_true", help="Only backup media files (legacy single-file mode)")
        parser.add_argument("--db-only", action="store_true", help="Only backup database (legacy single-file mode)")
        parser.add_argument("--output-dir", type=str, default="/opt/omnidesk/backups", help="Backup output directory")
        parser.add_argument("--batch-id", help="Paired batch upgrade_id (default: UTC timestamp)")
        parser.add_argument("--verify", action="store_true", help="Mark restore_verified=true in metadata.json")
        parser.add_argument("--skip-media", action="store_true", help="Paired batch: skip media dump (writes empty media.tar.gz)")

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
            "restore_verified": bool(options["verify"]),
            "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        for path, digest in ((db_file, metadata["database_sha256"]), (media_file, metadata["media_sha256"])):
            path.with_name(path.name + ".sha256").write_text(f"{digest}  {path.name}\n")
        (output_dir / "metadata.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n"
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Paired backup batch written to {output_dir} (upgrade_id={batch_id}, restore_verified={metadata['restore_verified']})"
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
