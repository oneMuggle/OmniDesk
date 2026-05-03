import requests
from ragflow_service.models import RagflowConfig
from .base import BaseTool


class RAGTool(BaseTool):
    name = "knowledge_qa"
    description = "从知识库查询业务知识"
    intent_type = "knowledge_qa"

    def execute(self, query: str, context: dict = None) -> dict:
        """调用 Ragflow API 检索知识库"""
        config = RagflowConfig.objects.filter(is_active=True).first()
        if not config:
            return {
                'found': False,
                'message': '知识库服务未配置',
            }

        try:
            dataset_id = None
            if context:
                dataset_id = context.get('dataset_id')

            url = f"{config.api_endpoint.rstrip('/')}/api/v1/retrieval"
            headers = {
                'Authorization': f"Bearer {config.api_key}",
                'Content-Type': 'application/json',
            }
            payload = {
                'query': query,
                'top_k': 5,
            }
            if dataset_id:
                payload['dataset_id'] = dataset_id

            response = requests.post(url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()

            chunks = data.get('data', {}).get('chunks', [])
            if not chunks:
                return {
                    'found': False,
                    'message': '知识库中未找到相关信息',
                }

            context_parts = []
            sources = []
            for chunk in chunks:
                context_parts.append(chunk.get('content', ''))
                sources.append({
                    'document': chunk.get('document_name', ''),
                    'score': chunk.get('similarity', 0),
                })

            return {
                'found': True,
                'context': '\n\n'.join(context_parts),
                'sources': sources,
            }
        except requests.RequestException as e:
            return {
                'found': False,
                'message': f'知识库查询失败: {str(e)}',
            }

    def get_schema(self) -> dict:
        return {
            'name': self.name,
            'description': self.description,
            'intent_type': self.intent_type,
        }
