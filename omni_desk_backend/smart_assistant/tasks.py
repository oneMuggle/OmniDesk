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
        doc.embedding_status = 'processing'
        doc.save(update_fields=['embedding_status'])

        config = RagflowConfig.objects.filter(is_active=True).first()
        if not config:
            raise ValueError('Ragflow 配置未激活')

        base_url = config.api_endpoint.rstrip('/')
        headers = {'Authorization': f"Bearer {config.api_key}"}

        # Step 1: 上传文档到 Ragflow dataset
        dataset_id = getattr(settings, 'SMART_ASSISTANT_DATASET_ID', None)
        if not dataset_id:
            raise ValueError('SMART_ASSISTANT_DATASET_ID 未配置')

        upload_url = f"{base_url}/api/v1/datasets/{dataset_id}/documents"
        with doc.file.open('rb') as f:
            response = requests.post(
                upload_url,
                headers={'Authorization': headers['Authorization']},
                files={'file': (doc.file.name, f)},
                timeout=60,
            )
        response.raise_for_status()
        upload_data = response.json()

        # Ragflow 返回文档 ID
        doc_infos = upload_data.get('data', [])
        if not doc_infos:
            raise ValueError('文档上传到 Ragflow 失败，未返回文档信息')

        ragflow_doc_id = doc_infos[0].get('id') or doc_infos[0].get('doc_id')
        if not ragflow_doc_id:
            raise ValueError('未能获取 Ragflow 文档 ID')

        doc.ragflow_document_id = ragflow_doc_id
        doc.save(update_fields=['ragflow_document_id'])

        # Step 2: 触发文档解析
        parse_url = f"{base_url}/api/v1/datasets/{dataset_id}/documents/chunks"
        parse_response = requests.post(
            parse_url,
            headers={**headers, 'Content-Type': 'application/json'},
            json={'document_ids': [ragflow_doc_id]},
            timeout=60,
        )
        parse_response.raise_for_status()

        doc.embedding_status = 'completed'
        doc.save(update_fields=['embedding_status'])
    except KnowledgeBaseDocument.DoesNotExist:
        pass
    except Exception as e:
        from smart_assistant.models import KnowledgeBaseDocument
        try:
            doc = KnowledgeBaseDocument.objects.get(id=document_id)
            doc.embedding_status = 'failed'
            doc.content_text = str(e)
            doc.save(update_fields=['embedding_status', 'content_text'])
        except KnowledgeBaseDocument.DoesNotExist:
            pass
        raise
