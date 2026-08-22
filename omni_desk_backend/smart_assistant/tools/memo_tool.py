from memos.models import Memo
from .base import BaseTool


class MemoTool(BaseTool):
    name = "memo_query"
    description = "查询备忘录/便签"
    intent_type = "memo_query"
    risk_level = "read"  # 显式声明:只读查询工具,无副作用
    # 领域停用词(R5-D2 收敛到 BaseTool.extract_keywords;顺序与旧 replace 链一致)
    stopwords = ("备忘录", "便签")

    def execute(self, query=None, context=None, params=None, scope=None, qs=None) -> dict:
        """搜索备忘录。

        支持两种调用方式(向后兼容):
        - 旧:execute(query, context) — 由原生 tool_calls 旧签名/直调路径使用
        - 新:execute(params, scope, qs) — 由 scope-aware 执行分支使用

        R5-D1 统一:两条路径都经 ``scoped_queryset`` 取数 —— 注入 qs 优先,
        未注入时经 build_base_queryset + get_queryset_for_scope 自取,
        SELF/DEPARTMENT/GLOBAL 三级 scope 在两个入口下语义一致。
        """
        memos = self.scoped_queryset(context, qs=qs, scope=scope)
        search_query = query
        if isinstance(params, dict) and params.get("query"):
            search_query = params["query"]
        keywords = self.extract_keywords(search_query or "")
        if memos is None:
            # 非 scope-aware 兜底(不应发生:MemoTool 实现了 build_base_queryset)
            memos = Memo.objects.select_related("user").all()
        # I-2:is_completed 布尔过滤(缺失时回退到纯关键词)
        if isinstance(params, dict) and params.get("is_completed") is not None:
            memos = memos.filter(is_completed=bool(params["is_completed"]))
        memos = memos.filter(title__icontains=keywords)[:10]
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

    @classmethod
    def get_openai_tool_schema(cls) -> dict:
        """OpenAI strict mode tool schema — 查询备忘录/便签。"""
        return {
            "type": "function",
            "function": {
                "name": cls.intent_type,
                "description": (
                    "查询备忘录/便签,按标题关键词模糊匹配。示例 query: '找一下会议纪要'、'搜索本周的便签'。"
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
