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

    @classmethod
    def get_openai_tool_schema(cls) -> dict:
        """OpenAI strict mode tool schema — 从知识库查询业务知识。

        dataset_ids 为 array(items 也是 object 时也要 strict);
        多数据集选择是非典型场景,description 显式说明避免 LLM 误用。
        """
        return {
            "type": "function",
            "function": {
                "name": cls.intent_type,
                "description": (
                    "从知识库(RAGFlow)查询业务知识,合并多个数据集的检索结果。"
                    "示例 query: '公司的报销流程是什么'、'查询质量手册'。"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "自然语言问题,作为 RAG 检索 query",
                        },
                        "dataset_ids": {
                            "type": "array",
                            "description": "限定检索的数据集 ID 列表(可选,空则查所有)",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "id": {"type": "string", "description": "数据集 ID"},
                                },
                                "required": ["id"],
                                "additionalProperties": False,
                            },
                        },
                        "top_k": {
                            "type": "integer",
                            "description": "返回片段数上限,默认 5",
                        },
                    },
                    "required": ["query"],
                    "additionalProperties": False,
                },
                "strict": True,
            },
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
