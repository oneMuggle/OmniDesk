from celery import shared_task
from .services import FileProcessingService
from .models import UploadedFile
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def process_file_task(self, file_id):
    """异步处理文件"""
    try:
        # 获取文件记录
        uploaded_file = UploadedFile.objects.get(id=file_id)

        # 更新状态为处理中
        uploaded_file.status = 'processing'
        uploaded_file.save()

        # 处理文件
        service = FileProcessingService()
        service.process_file(uploaded_file)

        logger.info(f"文件处理成功: {uploaded_file.original_filename}")

    except UploadedFile.DoesNotExist:
        logger.error(f"文件不存在: {file_id}")
        raise

    except Exception as exc:
        logger.error(f"文件处理失败: {exc}")

        # 更新状态为失败
        try:
            uploaded_file = UploadedFile.objects.get(id=file_id)
            uploaded_file.status = 'failed'
            uploaded_file.error_message = str(exc)
            uploaded_file.save()
        except UploadedFile.DoesNotExist:
            pass

        # 重试（最多 3 次，指数退避）
        raise self.retry(exc=exc, countdown=60)
