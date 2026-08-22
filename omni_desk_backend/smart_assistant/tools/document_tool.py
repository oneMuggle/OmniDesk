from documents.models import DocumentTemplate, GeneratedDocument
from .base import BaseTool


class DocumentTool(BaseTool):
    name = "document_search"
    description = "搜索公文/文档（按标题/类型/状态）"
    intent_type = "document_search"
    risk_level = "read"  # 显式声明:只读查询工具,无副作用
    # 领域停用词(R5-D2 收敛到 BaseTool.extract_keywords;顺序与旧 replace 链一致)
    stopwords = ("文档", "公文")

    def execute(self, query=None, context=None, params=None, scope=None, qs=None) -> dict:
        """搜索文档模板和生成的文档。

        支持两种调用方式(向后兼容):
        - 旧:execute(query, context) — 由原生 tool_calls 旧签名/直调路径使用
        - 新:execute(params, scope, qs) — 由 scope-aware 执行分支使用
          (C-1 修复:模板从 scoped queryset 取,生成的文档按 template__in=qs
          反查,确保 SELF/DEPARTMENT/GLOBAL 三级 scope 生效)。
        """
        # R5-D1 统一:两条路径都经 ``scoped_queryset`` 取数(注入 qs 优先,未注入
        # 时自取),SELF/DEPARTMENT/GLOBAL 三级 scope 在两个入口下语义一致
        # (修复旧路径 SELF scope 泄露)。生成文档按 template__in=templates_qs 反查
        # 同一 scope(GeneratedDocument 无 owner 字段)。
        templates_qs = self.scoped_queryset(context, qs=qs, scope=scope)
        search_query = query
        if isinstance(params, dict) and params.get("query"):
            search_query = params["query"]
        keywords = self.extract_keywords(search_query or "")
        if templates_qs is None:
            # 非 scope-aware 兜底(不应发生:DocumentTool 实现了 build_base_queryset)
            templates_qs = DocumentTemplate.objects.select_related("owner").all()
        # I-2:limit 结构化字段替换硬编码 [:10](缺失时保持 10)
        limit = params.get("limit") if isinstance(params, dict) and params.get("limit") else 10
        templates = templates_qs.filter(name__icontains=keywords)[:limit]
        generated_docs = GeneratedDocument.objects.filter(
            template__in=templates_qs, template__name__icontains=keywords
        ).select_related("template")[:limit]

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

    @classmethod
    def get_openai_tool_schema(cls) -> dict:
        """OpenAI strict mode tool schema — 搜索公文/文档模板与生成文档。"""
        return {
            "type": "function",
            "function": {
                "name": cls.intent_type,
                "description": (
                    "搜索公文/文档(DocumentTemplate 与 GeneratedDocument),"
                    "按名称模糊匹配。"
                    "示例 query: '查设备验收模板'、'搜索最近的公文'。"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "搜索关键词,匹配模板/公文名",
                        },
                        "doc_type": {
                            "type": "string",
                            "enum": ["模板", "文档"],
                            "description": "按类型过滤(模板 vs 已生成文档)",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "返回条目数上限,默认 10",
                        },
                    },
                    "required": ["query"],
                    "additionalProperties": False,
                },
                "strict": True,
            },
        }

    def build_base_queryset(self):
        """返回未过滤的文档模板 QuerySet(主模型;execute 同时查 GeneratedDocument)。"""
        return DocumentTemplate.objects.select_related("owner").all()

    def _scope_self(self, qs, ctx):
        """本人范围:仅返回 ctx.user 名下的文档模板(按 owner 字段)。"""
        return qs.filter(owner=ctx.user)
