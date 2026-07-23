from documents.models import DocumentTemplate, GeneratedDocument
from .base import BaseTool


class DocumentTool(BaseTool):
    name = "document_search"
    description = "搜索公文/文档（按标题/类型/状态）"
    intent_type = "document_search"

    def execute(self, query: str, context: dict = None) -> dict:
        """搜索文档模板和生成的文档"""
        keywords = query.replace("搜索", "").replace("查找", "").replace("文档", "").replace("公文", "").strip()

        templates = DocumentTemplate.objects.filter(name__icontains=keywords).select_related("owner")[:10]

        # GeneratedDocument 无 name 字段,改用 template__name 反查
        generated_docs = GeneratedDocument.objects.filter(template__name__icontains=keywords).select_related(
            "template"
        )[:10]

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
                    "experiment_type": t.get_template_type_display(),
                    "owner": t.owner.username if t.owner else "未知",
                    "created_at": str(t.created_at.date()),
                }
            )

        for doc in generated_docs:
            # GeneratedDocument 无 name 字段,改用关联 template 的 name
            # 无 created_at 字段,改用 generated_at
            results.append(
                {
                    "type": "文档",
                    "title": doc.template.name if doc.template else "未命名",
                    "template": doc.template.name if doc.template else "未知",
                    "created_at": str(doc.generated_at.date()) if doc.generated_at else "未设置",
                }
            )

        return {
            "found": True,
            "count": len(results),
            "documents": results,
        }

    def build_base_queryset(self):
        """返回未过滤的文档模板 QuerySet(主模型;execute 同时查 GeneratedDocument)。"""
        return DocumentTemplate.objects.select_related("owner").all()

    def _scope_self(self, qs, ctx):
        """本人范围:仅返回 ctx.user 名下的文档模板(按 owner 字段)。"""
        return qs.filter(owner=ctx.user)
