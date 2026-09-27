"""文档库（Paperless）的 AI 工具声明。

由 ``smart_assistant.capabilities`` 在启动时自动发现，见 ``docs/technical/46-ai-capability-catalog.md``。
"""

from smart_assistant.capabilities import DataScope, LOGIN_ONLY, ToolSpec, toolset, QuickPrompt
from smart_assistant.capabilities.helpers import clamp_limit, context_user, tool_params
from smart_assistant.tools.base import BaseTool


def _display_name(user) -> str:
    if user is None:
        return ""
    return getattr(user, "real_name", "") or user.username


class DocumentLibraryQueryTool(BaseTool):
    """按标题检索文档库中的文档（只读）。

    只查询本地 ``DocumentBinding`` 表，不调用 Paperless 服务账号，因此不会越过
    用户权限。可见范围与 ``/api/paperless/documents/`` 一致
    （``paperless_proxy.selectors.visible_bindings``）：staff 看全部，其他人只看
    自己上传的文档。
    """

    name = "document_library_query"
    description = "按标题检索文档库（Paperless）中我能看到的文档，返回类型、上传人和同步状态"
    intent_type = "document_library_query"
    risk_level = "read"
    required_auth = True

    def execute(self, query=None, context=None, params=None, **_kwargs) -> dict:
        from django.db.models import Prefetch

        from paperless_proxy.models import DocumentBinding, OutboxItem
        from paperless_proxy.selectors import visible_bindings

        user = context_user(context)
        if user is None:
            return {"found": False, "message": "未识别到当前用户，无法查询文档库", "module_label": "文档库"}

        params = tool_params(params)
        qs = visible_bindings(
            user,
            DocumentBinding.objects.select_related("owner").prefetch_related(
                Prefetch("outbox", queryset=OutboxItem.objects.order_by("-created_at")[:1], to_attr="latest_outbox")
            ),
        )
        source_type = params.get("source_type")
        if source_type in {code for code, _ in DocumentBinding.SOURCE_CHOICES}:
            qs = qs.filter(source_type=source_type)
        keyword = str(params.get("keyword") or "").strip()
        if keyword:
            qs = qs.filter(title__icontains=keyword)

        limit = clamp_limit(params.get("limit"))
        documents = []
        for binding in qs.order_by("-created_at")[:limit]:
            latest = binding.latest_outbox[0] if binding.latest_outbox else None
            documents.append(
                {
                    "id": binding.id,
                    "title": binding.title,
                    "source_type": binding.get_source_type_display(),
                    "owner": _display_name(binding.owner),
                    "created_at": binding.created_at.isoformat(timespec="minutes"),
                    "synced": binding.paperless_id is not None,
                    "sync_status": latest.get_status_display() if latest else None,
                }
            )

        result = {
            "count": len(documents),
            "documents": documents,
            "url": "/documents-library",
            "module_label": "文档库",
        }
        if not documents:
            return {"found": False, "message": "文档库中没有找到你可以查看的相关文档", **result}
        return {"found": True, **result}

    @classmethod
    def get_openai_tool_schema(cls) -> dict:
        return {
            "type": "function",
            "function": {
                "name": cls.intent_type,
                "description": (
                    "按标题检索文档库（Paperless）中当前用户可见的文档：管理员可见全部，"
                    "其他人只能看到自己上传的文档。返回标题、类型、上传人和同步状态，不返回正文。"
                    "示例：'文档库里有没有采购合同'、'我上传的制度文件'。"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "用户的原始问题（用于理解意图，不直接作为筛选词）"},
                        "keyword": {"type": "string", "description": "标题关键词（可选）"},
                        "source_type": {
                            "type": "string",
                            "enum": ["project_document", "contract", "policy", "compliance_report", "personnel_file"],
                            "description": "文档类型：项目文档 / 合同 / 制度文件 / 合规检查报告 / 人事档案（可选）",
                        },
                        "limit": {"type": "integer", "description": "返回条数，默认 10，最多 20"},
                    },
                    "required": ["query"],
                    "additionalProperties": False,
                },
                "strict": True,
            },
        }


@toolset(
    "document_library",
    title="文档库",
    routes=(r"^/documents-library",),
    quick_prompts=(QuickPrompt("最近文档", "文档库里最近上传了哪些文档？"),),
)
def document_library_tools():
    return [
        ToolSpec(
            tool=DocumentLibraryQueryTool,
            title="检索文档库",
            required_permission=LOGIN_ONLY,
            data_scope=DataScope.MODULE,
        ),
    ]
