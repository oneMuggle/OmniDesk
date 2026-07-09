"""paperless_proxy Celery 任务"""
import logging
import os
from celery import shared_task

from .services.outbox import OutboxService, OutboxDeadError
from .services.client import PaperlessClient
from .exceptions import PaperlessError

logger = logging.getLogger(__name__)


@shared_task(name='paperless_proxy.process_outbox')
def process_paperless_outbox():
    """处理 Outbox 中的 pending 项,推送到 paperless"""
    items = OutboxService.fetch_pending()
    if not items:
        return {'processed': 0, 'succeeded': 0, 'failed': 0}

    client = PaperlessClient()
    succeeded = 0
    failed = 0
    for item in items:
        try:
            if item.operation == 'upload':
                _process_upload(item, client)
            elif item.operation == 'delete':
                _process_delete(item, client)
            elif item.operation == 'update_metadata':
                _process_update_metadata(item, client)
            else:
                raise PaperlessError(f'unknown operation: {item.operation}')
            OutboxService.mark_synced(item)
            succeeded += 1
        except PaperlessError as e:
            try:
                OutboxService.mark_failed(item, str(e))
            except OutboxDeadError:
                logger.error(f'Outbox#{item.id} dead: {e}')
            failed += 1
        except Exception as e:
            logger.exception(f'Outbox#{item.id} unexpected error: {e}')
            try:
                OutboxService.mark_failed(item, f'unexpected: {e}')
            except OutboxDeadError:
                pass
            failed += 1

    return {'processed': len(items), 'succeeded': succeeded, 'failed': failed}


def _process_upload(item, client: PaperlessClient) -> None:
    payload = item.payload
    file_path = payload['file_path']
    if not os.path.exists(file_path):
        raise PaperlessError(f'pending file not found: {file_path}')
    with open(file_path, 'rb') as f:
        result = client.upload(
            file_obj=f,
            filename=payload['filename'],
            title=payload.get('title', payload['filename']),
            owner=payload.get('owner'),
            correspondent=payload.get('correspondent'),
            document_type=payload.get('document_type'),
            tags=payload.get('tags'),
        )
    if item.binding and not item.binding.paperless_id:
        item.binding.paperless_id = result['id']
        item.binding.paperless_checksum = result.get('checksum', '')
        item.binding.save(update_fields=['paperless_id', 'paperless_checksum', 'updated_at'])
    # 删除本地待同步文件
    try:
        os.remove(file_path)
    except OSError:
        pass


def _process_delete(item, client: PaperlessClient) -> None:
    # paperless 暂不实现删除 API 代理,留空
    raise PaperlessError('delete not implemented in v1')


def _process_update_metadata(item, client: PaperlessClient) -> None:
    # 留给后续阶段
    raise PaperlessError('update_metadata not implemented in v1')
