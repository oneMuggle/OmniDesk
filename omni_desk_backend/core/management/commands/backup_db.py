"""Backup database and media files."""

import gzip
import os
import subprocess
import tarfile
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Backup database and media files. Usage: python manage.py backup_db [--media-only] [--db-only]"

    def add_arguments(self, parser):
        parser.add_argument("--media-only", action="store_true", help="Only backup media files")
        parser.add_argument("--db-only", action="store_true", help="Only backup database")
        parser.add_argument("--output-dir", type=str, default="/opt/omnidesk/backups", help="Backup output directory")

    def handle(self, *args, **options):
        output_dir = Path(options["output_dir"])
        output_dir.mkdir(parents=True, exist_ok=True)

        version = getattr(settings, "APP_VERSION", "unknown")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        media_only = options["media_only"]
        db_only = options["db_only"]

        if not media_only:
            self._backup_db(output_dir, version, timestamp)

        if not db_only:
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
                # Fix-13: Ruff UP022 — 用 capture_output=True 替代 stdout=PIPE, stderr=PIPE
                result = subprocess.run(
                    cmd,  # 默认 plain SQL format,兼容 psql 直接还原
                    env=env,
                    capture_output=True,
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
