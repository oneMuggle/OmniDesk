"""业务模块调用 paperless 上传的统一定入口"""

import os
import uuid
from contextlib import suppress

from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
from django.db import transaction
from django.utils.text import get_valid_filename
from .outbox import OutboxService
from ..models import DocumentBinding


class PaperlessUploadService:
    @staticmethod
    def queue_upload(
        file: UploadedFile,
        filename: str,
        title: str,
        source_type: str,
        source_id: int,
        owner,
        correspondent: int = None,
        document_type: int = None,
        tags: list = None,
    ) -> dict:
        """
        1. 保存文件到 MEDIA_ROOT/paperless_pending/<uuid>
        2. 创建 DocumentBinding(无 paperless_id,异步填充)
        3. 创建 OutboxItem
        4. 返回 {binding_id, outbox_id, status}
        """
        if source_type not in dict(DocumentBinding.SOURCE_CHOICES):
            raise ValueError(f"unsupported source_type: {source_type}")

        pending_path = PaperlessUploadService._save_pending_file(file, filename)
        try:
            with transaction.atomic():
                binding = DocumentBinding.objects.create(
                    source_type=source_type,
                    source_id=source_id,
                    paperless_id=None,  # 异步填充,worker 同步成功后回写
                    paperless_checksum="",
                    owner=owner,
                    title=title,
                    correspondent_id=correspondent,
                )
                outbox = OutboxService.enqueue(
                    operation="upload",
                    payload=PaperlessUploadService._build_payload(
                        pending_path, filename, title, correspondent, document_type, tags, owner
                    ),
                    binding=binding,
                    created_by=owner,
                )
        except Exception:
            PaperlessUploadService._remove_pending_file(pending_path)
            raise

        return {
            "binding_id": binding.id,
            "outbox_id": outbox.id,
            "status": outbox.status,
        }

    @staticmethod
    def _save_pending_file(file: UploadedFile, filename: str) -> str:
        pending_path = PaperlessUploadService._pending_path(filename)
        try:
            fd = os.open(pending_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as f:
                for chunk in file.chunks():
                    f.write(chunk)
        except Exception:
            PaperlessUploadService._remove_pending_file(pending_path)
            raise
        return pending_path

    @staticmethod
    def _pending_path(filename: str) -> str:
        media_root = os.path.abspath(settings.MEDIA_ROOT)
        pending_dir = os.path.abspath(os.path.join(media_root, settings.PAPERLESS_PENDING_DIR))
        if os.path.commonpath([media_root, pending_dir]) != media_root:
            raise ValueError("PAPERLESS_PENDING_DIR must be inside MEDIA_ROOT")

        os.makedirs(pending_dir, mode=0o700, exist_ok=True)
        safe_filename = get_valid_filename(os.path.basename(filename)) or "document"
        return os.path.join(pending_dir, f"{uuid.uuid4().hex}_{safe_filename}")

    @staticmethod
    def _build_payload(
        pending_path: str,
        filename: str,
        title: str,
        correspondent: int = None,
        document_type: int = None,
        tags: list = None,
        owner=None,
    ) -> dict:
        return {
            "file_path": pending_path,
            "filename": filename,
            "title": title,
            "correspondent": correspondent,
            "document_type": document_type,
            "tags": tags,
            "owner": PaperlessUploadService._paperless_owner_id(owner),
        }

    @staticmethod
    def _paperless_owner_id(owner):
        binding = getattr(owner, "paperless_bind", None)
        if binding is None or not binding.is_active:
            return None
        return binding.paperless_user_id

    @staticmethod
    def _remove_pending_file(pending_path: str) -> None:
        with suppress(OSError):
            os.remove(pending_path)
