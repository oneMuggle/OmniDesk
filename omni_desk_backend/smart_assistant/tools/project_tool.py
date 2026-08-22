from projects.models import Project
from .base import BaseTool


class ProjectTool(BaseTool):
    name = "project_status"
    description = "查询项目进度/状态/负责人"
    intent_type = "project_status"
    risk_level = "read"  # 显式声明:只读查询工具,无副作用
    # 领域停用词(R5-D2 收敛到 BaseTool.extract_keywords;顺序与旧 replace 链一致)
    stopwords = ("项目",)

    def execute(self, query=None, context=None, params=None, scope=None, qs=None) -> dict:
        """查询项目信息。

        支持两种调用方式(向后兼容):
        - 旧:execute(query, context) — 由原生 tool_calls 旧签名/直调路径使用
        - 新:execute(params, scope, qs) — 由 scope-aware 执行分支使用

        R5-D1 统一:两条路径都经 ``scoped_queryset`` 取数,SELF/DEPARTMENT/GLOBAL
        三级 scope 在两个入口下语义一致(修复旧路径 SELF scope 泄露)。
        """
        projects_qs = self.scoped_queryset(context, qs=qs, scope=scope)
        search_query = query
        if isinstance(params, dict) and params.get("query"):
            search_query = params["query"]
        keywords = self.extract_keywords(search_query or "")
        if projects_qs is None:
            # 非 scope-aware 兜底(不应发生:ProjectTool 实现了 build_base_queryset)
            projects_qs = Project.objects.select_related("manager").all()
        projects = projects_qs.filter(name__icontains=keywords)[:10]

        if not projects.exists():
            return {
                "found": False,
                "message": f'未找到与 "{keywords}" 相关的项目',
            }

        results = []
        for p in projects:
            results.append(
                {
                    "name": p.name,
                    "description": p.description[:100] + ("..." if len(p.description) > 100 else ""),
                    "manager": p.manager.username if p.manager else "未指定",
                    "status": p.status,
                    "start_date": str(p.start_date) if p.start_date else "未设置",
                    "end_date": str(p.end_date) if p.end_date else "未设置",
                }
            )

        return {
            "found": True,
            "count": len(results),
            "projects": results,
        }

    @classmethod
    def get_openai_tool_schema(cls) -> dict:
        """OpenAI strict mode tool schema — 查询项目进度/状态。"""
        return {
            "type": "function",
            "function": {
                "name": cls.intent_type,
                "description": (
                    "查询项目进度/状态/负责人/起止日期,按项目名模糊匹配。"
                    "示例 query: '查 OmniDesk 项目'、'本周项目进度'。"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "搜索关键词,匹配项目名",
                        },
                        "status": {
                            "type": "string",
                            "enum": ["planning", "in_progress", "completed", "on_hold", "cancelled"],
                            "description": "按项目状态过滤(可选)",
                        },
                        "manager": {
                            "type": "string",
                            "description": "按项目负责人用户名过滤(可选)",
                        },
                    },
                    "required": ["query"],
                    "additionalProperties": False,
                },
                "strict": True,
            },
        }

    def build_base_queryset(self):
        """返回未过滤的项目 QuerySet。"""
        return Project.objects.select_related("manager").all()

    def _scope_self(self, qs, ctx):
        """本人范围:仅返回 ctx.user 负责管理的项目(按 manager 字段)。"""
        return qs.filter(manager=ctx.user)
