from memos.models import Memo
from .base import BaseTool


class MemoTool(BaseTool):
    name = "memo_query"
    description = "查询备忘录/便签"
    intent_type = "memo_query"
    risk_level = "read"  # 显式声明:只读查询工具,无副作用

    def execute(self, query=None, context=None, params=None, scope=None, qs=None) -> dict:
        """搜索备忘录。

        支持两种调用方式(向后兼容):
        - 旧:execute(query, context) — 由原生 tool_calls 旧签名/直调路径使用
        - 新:execute(params, scope, qs) — 由 scope-aware 执行分支使用
          (C-1 修复:原生路径必须复用 build_base_queryset +
          get_queryset_for_scope 的 scoped queryset,否则 SELF scope
          用户会查到他人备忘录)。
        """
        # 新路径(scope-aware):用调用方注入的 scoped queryset 替代全量表查询
        if qs is not None and scope is not None:
            search_query = query
            if isinstance(params, dict) and params.get("query"):
                search_query = params["query"]
            keywords = self._extract_keywords(search_query or "")
            memos = qs.filter(title__icontains=keywords)[:10]
        else:
            keywords = self._extract_keywords(query or "")
            memos = Memo.objects.filter(title__icontains=keywords).select_related("user")[:10]
        if not memos.exists():
            return {
                "found": False,
                "message": f'未找到与 "{keywords}" 相关的备忘录',
            }

        results = []
        for m in memos:
            results.append(
                {
                    "title": m.title,
                    "content": m.content[:100] + ("..." if len(m.content) > 100 else ""),
                    "user": m.user.username if m.user else "未知",
                    "is_completed": m.is_completed,
                    "reminder_time": str(m.reminder_time) if m.reminder_time else "无提醒",
                    "created_at": str(m.created_at.date()),
                }
            )

        return {
            "found": True,
            "count": len(results),
            "memos": results,
        }

    @staticmethod
    def _extract_keywords(query: str) -> str:
        """从查询文本中剥离停用词(新旧路径共用,保证关键词口径一致)。"""
        return query.replace("搜索", "").replace("查找", "").replace("备忘录", "").replace("便签", "").strip()

    @classmethod
    def get_openai_tool_schema(cls) -> dict:
        """OpenAI strict mode tool schema — 查询备忘录/便签。"""
        return {
            "type": "function",
            "function": {
                "name": cls.intent_type,
                "description": (
                    "查询备忘录/便签,按标题关键词模糊匹配。"
                    "示例 query: '找一下会议纪要'、'搜索本周的便签'。"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "搜索关键词,可含标题/内容词",
                        },
                        "is_completed": {
                            "type": "boolean",
                            "description": "是否仅返回已完成/未完成(可选)",
                        },
                    },
                    "required": ["query"],
                    "additionalProperties": False,
                },
                "strict": True,
            },
        }

    def build_base_queryset(self):
        """返回未过滤的备忘录 QuerySet。"""
        return Memo.objects.select_related("user").all()

    def _scope_self(self, qs, ctx):
        """本人范围:仅返回 ctx.user 名下的备忘录。"""
        return qs.filter(user=ctx.user)
