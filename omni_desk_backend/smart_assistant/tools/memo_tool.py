from memos.models import Memo
from .base import BaseTool


class MemoTool(BaseTool):
    name = "memo_query"
    description = "查询备忘录/便签"
    intent_type = "memo_query"

    def execute(self, query: str, context: dict = None) -> dict:
        """搜索备忘录"""
        keywords = query.replace("搜索", "").replace("查找", "").replace("备忘录", "").replace("便签", "").strip()

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

    def build_base_queryset(self):
        """返回未过滤的备忘录 QuerySet。"""
        return Memo.objects.select_related("user").all()

    def _scope_self(self, qs, ctx):
        """本人范围:仅返回 ctx.user 名下的备忘录。"""
        return qs.filter(user=ctx.user)
