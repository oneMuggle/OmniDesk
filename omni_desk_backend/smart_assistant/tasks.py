import requests
from celery import shared_task


@shared_task
def process_document_embedding(document_id):
    """异步处理文档向量化：上传到 Ragflow 并触发解析"""
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

        base_url = config.api_endpoint.rstrip("/")
        headers = {"Authorization": f"Bearer {config.api_key}"}

        # Step 1: 上传文档到 Ragflow dataset
        dataset_id = getattr(settings, "SMART_ASSISTANT_DATASET_ID", None)
        if not dataset_id:
            raise ValueError("SMART_ASSISTANT_DATASET_ID 未配置")

        upload_url = f"{base_url}/api/v1/datasets/{dataset_id}/documents"
        with doc.file.open("rb") as f:
            response = requests.post(
                upload_url,
                headers={"Authorization": headers["Authorization"]},
                files={"file": (doc.file.name, f)},
                timeout=60,
            )
        response.raise_for_status()
        upload_data = response.json()

        # Ragflow 返回文档 ID
        doc_infos = upload_data.get("data", [])
        if not doc_infos:
            raise ValueError("文档上传到 Ragflow 失败，未返回文档信息")

        ragflow_doc_id = doc_infos[0].get("id") or doc_infos[0].get("doc_id")
        if not ragflow_doc_id:
            raise ValueError("未能获取 Ragflow 文档 ID")

        doc.ragflow_document_id = ragflow_doc_id
        doc.save(update_fields=["ragflow_document_id"])

        # Step 2: 触发文档解析
        parse_url = f"{base_url}/api/v1/datasets/{dataset_id}/documents/chunks"
        parse_response = requests.post(
            parse_url,
            headers={**headers, "Content-Type": "application/json"},
            json={"document_ids": [ragflow_doc_id]},
            timeout=60,
        )
        parse_response.raise_for_status()

        doc.embedding_status = "completed"
        doc.save(update_fields=["embedding_status"])
    except KnowledgeBaseDocument.DoesNotExist:
        pass
    except Exception as e:
        from smart_assistant.models import KnowledgeBaseDocument

        try:
            doc = KnowledgeBaseDocument.objects.get(id=document_id)
            doc.embedding_status = "failed"
            doc.content_text = str(e)
            doc.save(update_fields=["embedding_status", "content_text"])
        except KnowledgeBaseDocument.DoesNotExist:
            pass
        raise


@shared_task
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
            result.final_output if isinstance(result.final_output, (dict, list))
            else {"raw": result.final_output}
            if result.final_output
            else None
        )
        task.save(update_fields=[
            "status", "tokens_used", "completed_at", "final_output"
        ])

        # 更新每个 subtask 的状态
        for subtask_result in result.subtask_results:
            try:
                subtask_obj = AgentSubTask.objects.get(
                    task=task, subtask_id=subtask_result.subtask_id
                )
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
            except AgentSubTask.DoesNotExist:
                pass

        # 记录 task.completed / task.failed 事件
        event_type = (
            "task.completed" if result.status == "success"
            else "task.failed" if result.status == "failed"
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
