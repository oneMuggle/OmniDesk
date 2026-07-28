from .base import BaseTool


class RAGTool(BaseTool):
    name = "knowledge_qa"
    description = "从知识库查询业务知识"
    intent_type = "knowledge_qa"
    risk_level = "read"  # 显式声明:只读查询工具,无副作用

    def execute(self, query: str, context: dict = None) -> dict:
        """使用 RAGRouter 搜索多个知识库，合并结果"""
        from ..agent.rag_router import get_rag_router

        rag_router = get_rag_router()
        chunks = rag_router.search_multi(query, top_k=5)

        if not chunks:
            return {
                "found": False,
                "message": "知识库中未找到相关信息",
            }

        context_parts = []
        sources = []
        for chunk in chunks:
            content = chunk.get("content", chunk.get("text", ""))
            if content:
                context_parts.append(content)
                sources.append(
                    {
                        "document": chunk.get("document_name", chunk.get("document", "")),
                        "score": chunk.get("similarity", chunk.get("score", 0)),
                        "source": chunk.get("_source", ""),
                    }
                )

        return {
            "found": True,
            "context": "\n\n".join(context_parts),
            "sources": sources,
        }

    def get_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "intent_type": self.intent_type,
            # 与 BaseTool.get_schema 保持一致:暴露风险等级供执行器/前端门控
            "risk_level": self.risk_level,
        }

    def build_base_queryset(self):
        """RAG 工具无 Django ORM 数据源;返回 RagflowConfig 的空 QuerySet 作为契约占位。

        实际数据来自 RAGFlow 外部服务,不走 Django ORM。
        """
        from ragflow_service.models import RagflowConfig

        return RagflowConfig.objects.none()

    def _scope_self(self, qs, ctx):
        """RAG 是公共知识库,无"本人"语义;本人范围返回空 QuerySet。"""
        return qs.none()
