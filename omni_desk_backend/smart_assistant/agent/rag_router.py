"""RAG 路由器：支持多数据集智能路由。

根据查询关键词匹配最相关的知识库数据集，并行搜索后合并结果。
"""

import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def get_ragflow_config():
    """获取默认的 Ragflow 配置（兼容旧版单配置模式）"""
    try:
        from ragflow_service.models import RagflowConfig

        config = RagflowConfig.objects.filter(is_active=True).first()
        if not config:
            return None
        return config
    except Exception:
        return None


class RAGRouter:
    """多数据集 RAG 路由器。"""

    def get_active_datasets(self) -> list:
        """获取所有活跃的数据集。"""
        try:
            from smart_assistant.models import KnowledgeDataset

            return list(KnowledgeDataset.objects.filter(is_active=True).order_by("priority", "name"))
        except Exception:
            return []

    def route_query(self, query: str) -> list:
        """根据查询匹配最相关的数据集。

        基于标签关键词匹配，返回按优先级排序的候选数据集列表。
        """
        datasets = self.get_active_datasets()
        if not datasets:
            # 回退到旧版单配置
            config = get_ragflow_config()
            if config:
                dataset_id = getattr(settings, "SMART_ASSISTANT_DATASET_ID", "")
                if dataset_id:
                    return [
                        {
                            "name": "默认知识库",
                            "ragflow_dataset_id": dataset_id,
                            "api_endpoint": config.api_endpoint,
                            "api_key": config.api_key,
                        }
                    ]
            return []

        # 基于标签匹配
        query_lower = query.lower()
        scored = []
        for ds in datasets:
            score = 0
            tags = ds.tags or []
            for tag in tags:
                if tag.lower() in query_lower:
                    score += 1
            if score > 0:
                scored.append((score, ds))

        # 按匹配分数降序，相同分数按优先级升序
        scored.sort(key=lambda x: (-x[0], x[1].priority))

        # 取前 2 个最相关的
        result = []
        for _score, ds in scored[:2]:
            config = get_ragflow_config()
            result.append(
                {
                    "name": ds.name,
                    "ragflow_dataset_id": ds.ragflow_dataset_id,
                    "api_endpoint": config.api_endpoint if config else "",
                    "api_key": config.api_key if config else "",
                }
            )

        # 如果没有匹配到任何标签，返回所有活跃数据集
        if not result:
            config = get_ragflow_config()
            for ds in datasets[:3]:  # 最多 3 个
                result.append(
                    {
                        "name": ds.name,
                        "ragflow_dataset_id": ds.ragflow_dataset_id,
                        "api_endpoint": config.api_endpoint if config else "",
                        "api_key": config.api_key if config else "",
                    }
                )

        return result

    def search_dataset(self, query: str, dataset: dict, top_k: int = 5) -> list:
        """搜索单个数据集。"""
        api_endpoint = dataset.get("api_endpoint", "").rstrip("/")
        api_key = dataset.get("api_key", "")
        dataset_id = dataset.get("ragflow_dataset_id", "")

        if not all([api_endpoint, api_key, dataset_id]):
            logger.warning("RAG 数据集配置不完整: %s", dataset.get("name"))
            return []

        url = f"{api_endpoint}/api/v1/retrieval"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        data = {
            "dataset_id": dataset_id,
            "query": query,
            "top_k": top_k,
        }

        try:
            resp = requests.post(url, headers=headers, json=data, timeout=15)
            resp.raise_for_status()
            result = resp.json()
            # resp.json() 无类型注解 → Any，显式声明为 list[dict] 收紧
            chunks: list[dict] = result.get("chunks", [])
            # 添加来源标记
            for chunk in chunks:
                chunk["_source"] = dataset.get("name", "未知")
            return chunks
        except Exception as e:
            logger.warning("RAG 数据集 %s 搜索失败: %s", dataset.get("name"), e)
            return []

    def search_multi(self, query: str, top_k: int = 5) -> list:
        """并行搜索多个数据集，合并去重结果。"""
        datasets = self.route_query(query)
        if not datasets:
            return []

        all_results = []
        for ds in datasets:
            results = self.search_dataset(query, ds, top_k=top_k)
            all_results.extend(results)

        # 简单去重（基于内容）
        seen = set()
        unique_results = []
        for r in all_results:
            content = r.get("content", r.get("text", ""))
            if content not in seen:
                seen.add(content)
                unique_results.append(r)

        return unique_results[:top_k]


# 单例
_router = None


def get_rag_router():
    global _router
    if _router is None:
        _router = RAGRouter()
    return _router
