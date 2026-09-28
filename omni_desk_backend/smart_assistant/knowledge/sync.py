"""同步单条来源到 RAGFlow，以及定期对账。

结果（``sync_source`` 返回值）：
``disabled`` 未配置 / ``noop`` 不需入库且无记录 / ``skipped`` 内容未变 / ``ingested`` 已上传
/ ``removed`` 已移除 / ``pending`` 内容暂未就绪 / ``failed`` 失败（已记录）。
"""

from __future__ import annotations

import hashlib
from collections import Counter

from django.utils import timezone

from observability import get_logger

from .config import ingest_settings, make_client
from .content import BUILDERS, ContentNotReady

logger = get_logger(__name__, "smart_assistant")

MAX_ATTEMPTS = 5
RECONCILE_LIMIT = 100


def _error_summary(exc: Exception) -> str:
    code = getattr(exc, "code", "")
    return (f"{type(exc).__name__}: {code}" if code else type(exc).__name__)[:500]


def _mark_failed(record, exc: Exception) -> str:
    record.status = record.STATUS_FAILED
    record.attempts += 1
    record.last_error = _error_summary(exc)
    record.save(update_fields=["status", "attempts", "last_error", "updated_at"])
    logger.warning(
        "知识入库失败: source=%s#%s type=%s attempts=%s",
        record.source_type,
        record.source_id,
        type(exc).__name__,
        record.attempts,
    )
    return "failed"


def _remove(record, config) -> str:
    if record.ragflow_document_id:
        client = make_client(config)
        try:
            client.delete_document(record.ragflow_dataset_id, [record.ragflow_document_id])
        except Exception as exc:
            return _mark_failed(record, exc)
        finally:
            client.close()
    record.status = record.STATUS_REMOVED
    record.ragflow_document_id = ""
    record.content_hash = ""
    record.attempts = 0
    record.last_error = ""
    record.save(update_fields=["status", "ragflow_document_id", "content_hash", "attempts", "last_error", "updated_at"])
    return "removed"


def sync_source(source_type: str, source_id: int) -> str:
    from smart_assistant.models import KnowledgeSource

    builder = BUILDERS.get(source_type)
    if builder is None:
        raise ValueError(f"未知来源类型: {source_type}")
    settings_pair = ingest_settings()
    if settings_pair is None:
        return "disabled"
    config, dataset_id = settings_pair

    record = KnowledgeSource.objects.filter(source_type=source_type, source_id=source_id).first()
    try:
        content = builder(source_id)
    except ContentNotReady:
        if record is None:
            KnowledgeSource.objects.get_or_create(source_type=source_type, source_id=source_id)
        elif record.status == KnowledgeSource.STATUS_REMOVED:
            record.status = KnowledgeSource.STATUS_PENDING
            record.save(update_fields=["status", "updated_at"])
        return "pending"
    except Exception as exc:
        record = record or KnowledgeSource.objects.get_or_create(source_type=source_type, source_id=source_id)[0]
        return _mark_failed(record, exc)

    if content is None:
        if record is None or record.status == KnowledgeSource.STATUS_REMOVED:
            return "noop"
        return _remove(record, config)

    rendered = content.render()
    content_hash = hashlib.sha256(rendered.encode("utf-8")).hexdigest()
    if (
        record is not None
        and record.status == KnowledgeSource.STATUS_INGESTED
        and record.content_hash == content_hash
        and record.ragflow_dataset_id == dataset_id
    ):
        return "skipped"
    if record is None:
        record, _ = KnowledgeSource.objects.get_or_create(source_type=source_type, source_id=source_id)

    client = make_client(config)
    try:
        if record.ragflow_document_id:
            # 旧文档删不掉也继续：记录改指向新文档后，旧文档的检索结果反查不到记录，会被过滤掉。
            try:
                client.delete_document(record.ragflow_dataset_id or dataset_id, [record.ragflow_document_id])
            except Exception as exc:
                logger.warning("删除旧入库文档失败: source=%s#%s type=%s", source_type, source_id, type(exc).__name__)
        uploaded = client.upload_document(
            dataset_id=dataset_id, file_name=content.file_name, file_content=rendered.encode("utf-8")
        )
        infos = uploaded if isinstance(uploaded, list) else [uploaded]
        first = (infos[0] or {}) if infos else {}
        document_id = first.get("id") or first.get("doc_id")
        if not document_id:
            raise ValueError("RAGFlow 未返回文档 ID")
        record.ragflow_dataset_id = dataset_id
        record.ragflow_document_id = document_id
        record.save(update_fields=["ragflow_dataset_id", "ragflow_document_id", "updated_at"])
        client.parse_documents(dataset_id=dataset_id, document_ids=[document_id])
    except Exception as exc:
        return _mark_failed(record, exc)
    finally:
        client.close()

    record.title = content.title[:255]
    record.content_hash = content_hash
    record.status = KnowledgeSource.STATUS_INGESTED
    record.attempts = 0
    record.last_error = ""
    record.ingested_at = timezone.now()
    record.save(
        update_fields=["title", "content_hash", "status", "attempts", "last_error", "ingested_at", "updated_at"]
    )
    return "ingested"


def _eligible() -> dict[str, dict[int, object]]:
    """应在知识库中的对象：``{source_type: {id: updated_at}}``。"""
    from events.models import Announcement
    from paperless_proxy.models import DocumentBinding

    return {
        "announcement": dict(
            Announcement.objects.filter(status=Announcement.STATUS_PUBLISHED).values_list("pk", "updated_at")
        ),
        "paperless_document": dict(
            DocumentBinding.objects.filter(paperless_id__isnull=False).values_list("pk", "updated_at")
        ),
    }


def reconcile_candidates(limit: int = RECONCILE_LIMIT) -> list[tuple[str, int]]:
    from smart_assistant.models import KnowledgeSource

    eligible = _eligible()
    records = {(r.source_type, r.source_id): r for r in KnowledgeSource.objects.all()}
    removals, missing, retries = [], [], []

    for (source_type, source_id), record in records.items():
        if source_id not in eligible.get(source_type, {}):
            if record.status != KnowledgeSource.STATUS_REMOVED:
                removals.append((source_type, source_id))
    for source_type, objects in eligible.items():
        for source_id, updated_at in objects.items():
            record = records.get((source_type, source_id))
            if record is None or record.status == KnowledgeSource.STATUS_REMOVED:
                missing.append((source_type, source_id))
            elif record.status == KnowledgeSource.STATUS_PENDING:
                retries.append((source_type, source_id))
            elif record.status == KnowledgeSource.STATUS_FAILED:
                if record.attempts < MAX_ATTEMPTS:
                    retries.append((source_type, source_id))
            elif record.ingested_at is None or (updated_at and updated_at > record.ingested_at):
                missing.append((source_type, source_id))
    # 移除优先（权限相关），再补漏，最后重试
    return (removals + missing + retries)[:limit]


def reconcile(limit: int = RECONCILE_LIMIT) -> dict:
    if ingest_settings() is None:
        return {"disabled": True}
    outcomes = Counter(sync_source(t, i) for t, i in reconcile_candidates(limit))
    return {"disabled": False, **dict(outcomes)}
