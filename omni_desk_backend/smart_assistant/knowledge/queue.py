"""业务对象变更后，事务提交时把同步任务放进 Celery。未配置入库时什么都不做。"""

from __future__ import annotations

from django.db import transaction

from observability import get_logger

from .config import ingest_dataset_id

logger = get_logger(__name__, "smart_assistant")


def _dispatch(source_type: str, source_id: int) -> None:
    from smart_assistant.tasks import sync_knowledge_source

    try:
        sync_knowledge_source.delay(source_type, source_id)
    except Exception as exc:  # 队列不可用时交给定期对账兜底
        logger.warning("知识入库任务入队失败: type=%s source=%s#%s", type(exc).__name__, source_type, source_id)


def enqueue_sync(source_type: str, source_id: int) -> bool:
    if not ingest_dataset_id():
        return False
    transaction.on_commit(lambda: _dispatch(source_type, source_id))
    return True
