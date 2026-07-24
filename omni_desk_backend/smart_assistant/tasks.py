import logging

from celery import shared_task

from ragflow_service.client import RagflowClient, RagflowClientError

logger = logging.getLogger(__name__)


@shared_task(
    autoretry_for=(RagflowClientError,),
    retry_backoff=60,
    retry_kwargs={"max_retries": 3},
)
def process_document_embedding(document_id):
    """异步处理文档向量化：上传到 Ragflow 并触发解析。

    使用 RagflowClient 统一封装 API 调用。
    """
    from smart_assistant.models import KnowledgeBaseDocument
    from ragflow_service.models import RagflowConfig
    from django.conf import settings

    try:
        doc = KnowledgeBaseDocument.objects.get(id=document_id)
        doc.embedding_status = "processing"
        doc.save(update_fields=["embedding_status"])

        config = RagflowConfig.objects.filter(is_active=True).first()
        if not config:
            raise ValueError("Ragflow 配置未激活")

        dataset_id = getattr(settings, "SMART_ASSISTANT_DATASET_ID", None)
        if not dataset_id:
            raise ValueError("SMART_ASSISTANT_DATASET_ID 未配置")

        client = RagflowClient(api_endpoint=config.api_endpoint, api_key=config.api_key)

        # Step 1: 上传文档到 Ragflow dataset
        with doc.file.open("rb") as f:
            file_content = f.read()

        upload_result = client.upload_document(
            dataset_id=dataset_id,
            file_name=doc.file.name,
            file_content=file_content,
        )

        # Ragflow 返回文档 ID
        doc_infos = upload_result if isinstance(upload_result, list) else [upload_result]
        if not doc_infos:
            raise ValueError("文档上传到 Ragflow 失败，未返回文档信息")

        ragflow_doc_id = doc_infos[0].get("id") or doc_infos[0].get("doc_id")
        if not ragflow_doc_id:
            raise ValueError("未能获取 Ragflow 文档 ID")

        doc.ragflow_document_id = ragflow_doc_id
        doc.save(update_fields=["ragflow_document_id"])

        # Step 2: 触发文档解析
        client.parse_documents(dataset_id=dataset_id, document_ids=[ragflow_doc_id])

        doc.embedding_status = "completed"
        doc.save(update_fields=["embedding_status"])

    except KnowledgeBaseDocument.DoesNotExist:
        pass
    except Exception as e:
        logger.error("文档向量化失败: %s", e)
        from smart_assistant.models import KnowledgeBaseDocument

        try:
            doc = KnowledgeBaseDocument.objects.get(id=document_id)
            doc.embedding_status = "failed"
            doc.content_text = str(e)
            doc.save(update_fields=["embedding_status", "content_text"])
        except KnowledgeBaseDocument.DoesNotExist:
            pass
        raise


@shared_task(
    autoretry_for=(Exception,),
    retry_backoff=60,
    retry_kwargs={"max_retries": 2},
    task_time_limit=300,  # 硬超时 5 分钟
    task_soft_time_limit=240,  # 软超时 4 分钟(触发 SoftTimeLimitExceeded)
)
def execute_agent_task(task_id: str):
    """异步执行多 Agent 协作任务

    流程:
    1. 从数据库加载 AgentTask
    2. 构造 TaskPacket
    3. 创建 MultiAgentExecutor
    4. 执行任务
    5. 保存结果到数据库
    6. 记录 AgentEvent(供 SSE 推送)

    Args:
        task_id: AgentTask 的 task_id(UUID 字符串)
    """
    from django.utils import timezone

    from smart_assistant.models import AgentEvent, AgentSubTask, AgentTask
    from smart_assistant.agents.task_packet import TaskPacket
    from smart_assistant.agents.executor import MultiAgentExecutor
    from llm_service.router import get_router
    from smart_assistant.tools.registry import ToolRegistry

    try:
        # 1. 加载 AgentTask
        task = AgentTask.objects.get(task_id=task_id)

        # 2. 构造 TaskPacket
        task_packet = TaskPacket.from_dict(task.task_packet, task_id=str(task.task_id))

        # 3. 更新状态为 running
        task.status = "running"
        task.started_at = timezone.now()
        task.save(update_fields=["status", "started_at"])

        # 记录 task.started 事件
        AgentEvent.objects.create(
            task=task,
            sequence=AgentEvent.objects.filter(task=task).count() + 1,
            event_type="task.started",
            payload={"task_id": str(task.task_id)},
        )

        # 4. 创建执行器
        llm_router = get_router()
        executor = MultiAgentExecutor(
            task_packet=task_packet,
            llm_router=llm_router,
            tool_registry=ToolRegistry,
        )

        # 5. 执行任务
        result = executor.execute()

        # 6. 保存结果到数据库
        task.status = result.status
        task.tokens_used = result.total_tokens_used
        task.completed_at = timezone.now()
        task.final_output = (
            result.final_output
            if isinstance(result.final_output, (dict, list))
            else {"raw": result.final_output}
            if result.final_output
            else None
        )
        task.save(update_fields=["status", "tokens_used", "completed_at", "final_output"])

        # 更新每个 subtask 的状态(批量查询替代循环 get,修复 N+1)
        subtask_ids = [r.subtask_id for r in result.subtask_results]
        subtask_objs = {
            str(obj.subtask_id): obj for obj in AgentSubTask.objects.filter(task=task, subtask_id__in=subtask_ids)
        }

        for subtask_result in result.subtask_results:
            subtask_obj = subtask_objs.get(str(subtask_result.subtask_id))
            if subtask_obj is None:
                continue
            subtask_obj.status = subtask_result.status
            subtask_obj.output = (
                subtask_result.output
                if isinstance(subtask_result.output, (dict, list))
                else {"raw": subtask_result.output}
            )
            subtask_obj.tokens_used = subtask_result.tokens_used
            subtask_obj.completed_at = timezone.now()
            subtask_obj.retry_count = subtask_result.retry_count
            subtask_obj.error_message = subtask_result.error_message
            subtask_obj.save()

        # 记录 task.completed / task.failed 事件
        event_type = (
            "task.completed"
            if result.status == "success"
            else "task.failed"
            if result.status == "failed"
            else "task.completed"  # partial 也算完成
        )
        AgentEvent.objects.create(
            task=task,
            sequence=AgentEvent.objects.filter(task=task).count() + 1,
            event_type=event_type,
            payload={
                "task_id": str(task.task_id),
                "status": result.status,
                "total_tokens": result.total_tokens_used,
                "total_duration_ms": result.total_duration_ms,
            },
        )

        return {
            "task_id": str(task.task_id),
            "status": result.status,
            "total_tokens": result.total_tokens_used,
        }

    except AgentTask.DoesNotExist:
        raise ValueError(f"AgentTask {task_id} 不存在")
    except Exception as e:
        # 任务失败,记录错误
        try:
            task = AgentTask.objects.get(task_id=task_id)
            task.status = "failed"
            task.completed_at = timezone.now()
            task.save(update_fields=["status", "completed_at"])

            AgentEvent.objects.create(
                task=task,
                sequence=AgentEvent.objects.filter(task=task).count() + 1,
                event_type="task.failed",
                payload={"task_id": str(task.task_id), "error": str(e)},
            )
        except AgentTask.DoesNotExist:
            pass
        raise
