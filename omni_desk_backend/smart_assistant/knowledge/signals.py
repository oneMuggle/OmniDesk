"""公告、文档库变更 → 入队同步（``SmartAssistantConfig.ready`` 中接线）。

公告「发布」接口走条件 ``update()``，不触发 ``post_save``，由接口显式调用 ``enqueue_sync``；
其余遗漏由定期对账兜底。
"""

from __future__ import annotations

from django.db.models.signals import post_delete, post_save

from .config import ingest_dataset_id
from .queue import enqueue_sync


def _has_record(source_type: str, source_id: int) -> bool:
    from smart_assistant.models import KnowledgeSource

    return KnowledgeSource.objects.filter(source_type=source_type, source_id=source_id).exists()


def _announcement_saved(sender, instance, **kwargs):
    if not ingest_dataset_id():
        return
    if instance.status != instance.STATUS_PUBLISHED and not _has_record("announcement", instance.pk):
        return  # 草稿且从未入库：无事可做
    enqueue_sync("announcement", instance.pk)


def _binding_saved(sender, instance, **kwargs):
    if not ingest_dataset_id():
        return
    if instance.paperless_id is None and not _has_record("paperless_document", instance.pk):
        return  # 还没同步到 Paperless
    enqueue_sync("paperless_document", instance.pk)


def _announcement_deleted(sender, instance, **kwargs):
    if ingest_dataset_id() and _has_record("announcement", instance.pk):
        enqueue_sync("announcement", instance.pk)


def _binding_deleted(sender, instance, **kwargs):
    if ingest_dataset_id() and _has_record("paperless_document", instance.pk):
        enqueue_sync("paperless_document", instance.pk)


def connect() -> None:
    from events.models import Announcement
    from paperless_proxy.models import DocumentBinding

    post_save.connect(_announcement_saved, sender=Announcement, dispatch_uid="knowledge_ingest_announcement_save")
    post_delete.connect(_announcement_deleted, sender=Announcement, dispatch_uid="knowledge_ingest_announcement_del")
    post_save.connect(_binding_saved, sender=DocumentBinding, dispatch_uid="knowledge_ingest_binding_save")
    post_delete.connect(_binding_deleted, sender=DocumentBinding, dispatch_uid="knowledge_ingest_binding_del")
