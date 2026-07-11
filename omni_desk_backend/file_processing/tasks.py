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

    except ValueError as exc:
        # 不可重试的错误（如不支持的文件类型、格式错误）
        logger.error(f"文件处理失败（不可重试）: {exc}")
        try:
            uploaded_file = UploadedFile.objects.get(id=file_id)
            uploaded_file.status = 'failed'
            uploaded_file.error_message = '文件格式不支持或内容有误，请检查后重试'
            uploaded_file.save()
        except UploadedFile.DoesNotExist:
            pass
        # 不重试，直接失败
        return

    except Exception as exc:
        # 可重试的错误（IO 错误、临时服务不可用等）
        logger.error(f"文件处理失败（可重试）: {exc}", exc_info=True)

        # 更新状态为失败，但不暴露详细错误信息
        try:
            uploaded_file = UploadedFile.objects.get(id=file_id)
            uploaded_file.status = 'failed'
            uploaded_file.error_message = '文件处理失败，请稍后重试'
            uploaded_file.save()
        except UploadedFile.DoesNotExist:
            pass

        # 重试（最多 3 次，指数退避）
        raise self.retry(exc=exc, countdown=60)
