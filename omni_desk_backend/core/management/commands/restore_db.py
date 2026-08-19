"""Restore database from a backup file or batch directory.

Task 4 安全增强:
- psql 必须带 -v ON_ERROR_STOP=1 与 --single-transaction
  (单事务失败即停,失败时回滚事务,数据库保持干净)
- 支持 --batch-dir 模式:校验 metadata.json + sha256,失败立即拒绝
  (不放行坏备份到生产数据库)
"""

import gzip
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


REQUIRED_METADATA_KEYS = frozenset(
    {
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
)

# 拒绝任何含 .. 或以 / 开头的相对/绝对路径(防止路径穿越)
_PATH_TRAVERSAL_RE = re.compile(r"(^|/)\.\.|^\/")

# psql 命令固定的 ON_ERROR_STOP+single-transaction 旗标
_PSQL_SAFETY_FLAGS = ("-v", "ON_ERROR_STOP=1", "--single-transaction")


class Command(BaseCommand):
    help = (
        "Restore database from a .sql.gz backup file or a batch directory. "
        "Usage: python manage.py restore_db <backup_file.sql.gz>  OR  "
        "python manage.py restore_db --batch-dir <path>"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "backup_file",
            nargs="?",
            type=str,
            help="Path to the .sql.gz backup file (omit when using --batch-dir)",
        )
        parser.add_argument(
            "--batch-dir",
            type=str,
            default=None,
            help="Restore from a paired backup batch directory (metadata.json + database.sql.gz + media.tar.gz)",
        )
        parser.add_argument("--force", action="store_true", help="Skip confirmation prompt")
        parser.add_argument(
            "--skip-metadata-verify",
            action="store_true",
            help=("Skip sha256 checksum verification of the batch metadata. EMERGENCY ONLY — not for production use."),
        )

    def handle(self, *args, **options):
        batch_dir = options.get("batch_dir")
        backup_file_arg = options.get("backup_file")

        if not batch_dir and not backup_file_arg:
            raise CommandError("Either provide a backup_file argument or --batch-dir option.")
        if batch_dir and backup_file_arg:
            raise CommandError("backup_file positional argument and --batch-dir are mutually exclusive; pick one.")

        if batch_dir:
            db_path = self._validate_batch(Path(batch_dir), skip_verify=options["skip_metadata_verify"])
        else:
            db_path = Path(backup_file_arg)
            if not db_path.is_file():
                raise CommandError(f"Backup file not found: {db_path}")

        if not options["force"]:
            self.stdout.write(
                self.style.WARNING(
                    f'WARNING: This will OVERWRITE the current database "{settings.DATABASES["default"]["NAME"]}".'
                )
            )
            confirm = input('Type "yes" to continue: ')
            if confirm.strip().lower() != "yes":
                self.stdout.write("Restore cancelled.")
                return

        self._run_restore(db_path)

    # ─── batch metadata 校验 ──────────────────────────────────────
    def _validate_batch(self, batch_dir, *, skip_verify=False):
        """校验 batch 目录的 metadata.json + 文件 sha256,返回合法的 database 路径.

        任何校验失败均抛 CommandError — 不放行坏备份.
        """
        if not batch_dir.is_dir():
            raise CommandError(f"Batch directory not found: {batch_dir}")

        meta_path = batch_dir / "metadata.json"
        if not meta_path.is_file():
            raise CommandError(f"Batch directory missing required metadata.json: {batch_dir}")

        try:
            metadata = json.loads(meta_path.read_text())
        except json.JSONDecodeError as exc:
            raise CommandError(f"Batch metadata.json is not valid JSON: {exc}") from exc

        if not isinstance(metadata, dict):
            raise CommandError("Batch metadata.json must be a JSON object.")

        missing = REQUIRED_METADATA_KEYS - set(metadata)
        if missing:
            raise CommandError(f"Batch metadata missing required fields: {sorted(missing)}")

        # 拒绝 database_file / media_file 含路径穿越 — 防 zip-slip 等攻击
        for key in ("database_file", "media_file"):
            value = metadata.get(key, "")
            if not value or _PATH_TRAVERSAL_RE.search(value) or value.startswith("/"):
                raise CommandError(f"Batch metadata {key} contains invalid path: {value!r}")

        db_path = batch_dir / metadata["database_file"]
        media_path = batch_dir / metadata["media_file"]

        # sha256 + size 双重校验 (确保文件未被篡改)
        if not skip_verify:
            self._verify_checksum(db_path, metadata["database_sha256"], metadata["database_size"], "database")
            self._verify_checksum(media_path, metadata["media_sha256"], metadata["media_size"], "media")
        else:
            self.stdout.write(
                self.style.WARNING(
                    "Skipping sha256 verification (--skip-metadata-verify); batch integrity NOT guaranteed."
                )
            )

        return db_path

    @staticmethod
    def _verify_checksum(path, expected_sha256, expected_size, kind):
        if not path.is_file():
            raise CommandError(f"Batch {kind} file missing: {path}")
        actual_size = path.stat().st_size
        if actual_size != expected_size:
            raise CommandError(f"Batch {kind} size mismatch: actual={actual_size} expected={expected_size}")
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        actual_sha = digest.hexdigest()
        if actual_sha != expected_sha256:
            raise CommandError(f"Batch {kind} checksum mismatch: actual={actual_sha} expected={expected_sha256}")

    # ─── 实际还原 ─────────────────────────────────────────────────
    def _run_restore(self, db_path):
        self.stdout.write(f"Restoring from {db_path} ...")
        db = settings.DATABASES["default"]

        if db["ENGINE"] != "django.db.backends.postgresql":
            raise CommandError("Restore only supports PostgreSQL.")

        env = os.environ.copy()
        env["PGPASSWORD"] = db.get("PASSWORD", "")

        cmd = [
            "psql",
            "-h",
            db["HOST"],
            "-p",
            str(db["PORT"]),
            "-U",
            db["USER"],
            "-d",
            db["NAME"],
            *_PSQL_SAFETY_FLAGS,  # -v ON_ERROR_STOP=1 --single-transaction
        ]

        try:
            with gzip.open(db_path, "rb") as gz:
                result = subprocess.run(
                    cmd,
                    stdin=gz,
                    env=env,
                    capture_output=True,
                    check=False,
                )
                if result.returncode != 0:
                    err = result.stderr
                    if isinstance(err, bytes):
                        err = err.decode(errors="replace")
                    raise CommandError(
                        f"psql failed (rc={result.returncode}); ON_ERROR_STOP triggers abort: {err.strip()}"
                    )
        except FileNotFoundError as exc:
            raise CommandError("psql not found. Please install PostgreSQL client tools.") from exc

        self.stdout.write(self.style.SUCCESS("Database restored successfully."))
