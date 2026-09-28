"""检索结果按用户权限过滤（S4-2）。

带 ``_ingest`` 标记的结果（来自自动入库数据集）按 RAGFlow 文档 ID 反查 ``KnowledgeSource``，
再看当前用户能否看到**当前的**原对象：

- 公告：存在且已发布（所有登录用户可见）；
- 文档库：``paperless_proxy.selectors.visible_bindings(user)`` 内。

反查不到、记录不是已入库、用户识别不出 → 丢弃。未标记的结果（手动上传的公共知识库）原样保留。
"""

from __future__ import annotations


def _document_id(chunk: dict) -> str:
    return str(chunk.get("document_id") or chunk.get("doc_id") or "")


def _visible_ids(user, source_type: str, ids: set[int]) -> set[int]:
    if not ids:
        return set()
    if source_type == "announcement":
        from events.models import Announcement

        qs = Announcement.objects.filter(pk__in=ids, status=Announcement.STATUS_PUBLISHED)
        return set(qs.values_list("pk", flat=True))
    if source_type == "paperless_document":
        from paperless_proxy.models import DocumentBinding
        from paperless_proxy.selectors import visible_bindings

        return set(visible_bindings(user, DocumentBinding.objects.filter(pk__in=ids)).values_list("pk", flat=True))
    return set()


def filter_chunks(user, chunks: list[dict]) -> list[dict]:
    from smart_assistant.models import KnowledgeSource

    ingest_chunks = [c for c in chunks if c.get("_ingest")]
    if not ingest_chunks:
        return list(chunks)
    authenticated = user is not None and getattr(user, "is_authenticated", False)

    records = {}
    if authenticated:
        doc_ids = {_document_id(c) for c in ingest_chunks} - {""}
        for record in KnowledgeSource.objects.filter(
            ragflow_document_id__in=doc_ids, status=KnowledgeSource.STATUS_INGESTED
        ):
            records[record.ragflow_document_id] = record

    visible: dict[str, set[int]] = {}
    for source_type in {r.source_type for r in records.values()}:
        ids = {r.source_id for r in records.values() if r.source_type == source_type}
        visible[source_type] = _visible_ids(user, source_type, ids)

    kept = []
    for chunk in chunks:
        if not chunk.get("_ingest"):
            kept.append(chunk)
            continue
        record = records.get(_document_id(chunk))
        if record is None or record.source_id not in visible.get(record.source_type, set()):
            continue
        if record.title:
            chunk["_source"] = f"{record.get_source_type_display()}：{record.title}"
            chunk["document_name"] = record.title
        kept.append(chunk)
    return kept
