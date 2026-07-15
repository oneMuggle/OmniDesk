from documents.models import DocumentTemplate, GeneratedDocument
from .base import BaseTool


class DocumentTool(BaseTool):
    name = "document_search"
    description = "搜索公文/文档（按标题/类型/状态）"
    intent_type = "document_search"

    def execute(self, query: str, context: dict | None = None) -> dict:
        """搜索文档模板和生成的文档"""
        keywords = query.replace("搜索", "").replace("查找", "").replace("文档", "").replace("公文", "").strip()

        templates = DocumentTemplate.objects.filter(name__icontains=keywords).select_related("owner")[:10]

        generated_docs = GeneratedDocument.objects.filter(name__icontains=keywords).select_related("template")[:10]

        if not templates.exists() and not generated_docs.exists():
            return {
                "found": False,
                "message": f'未找到与 "{keywords}" 相关的文档',
            }

        results = []
        for t in templates:
            results.append(
                {
                    "type": "模板",
                    "title": t.name,
                    "experiment_type": t.get_experiment_type_display(),
                    "owner": t.owner.username if t.owner else "未知",
                    "created_at": str(t.created_at.date()),
                }
            )

        for doc in generated_docs:
            results.append(
                {
                    "type": "文档",
                    "title": doc.name,
                    "template": doc.template.name if doc.template else "未知",
                    "created_at": str(doc.created_at.date()) if doc.created_at else "未设置",
                }
            )

        return {
            "found": True,
            "count": len(results),
            "documents": results,
        }
