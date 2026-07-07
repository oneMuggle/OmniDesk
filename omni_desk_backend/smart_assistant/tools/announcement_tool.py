"""AnnouncementTool - 通信公告(Post)查询工具.

对应交接文档任务 1.1:
- 数据源:communication.Post
- 过滤:未过期 AND 未归档
- 关键词匹配:title / content
- 上限 10 条,按 created_at 倒序
- N+1 防护:select_related("author")
"""

from typing import TYPE_CHECKING

from django.db.models import Q
from django.utils import timezone

from communication.models import Post

from .base import BaseTool

if TYPE_CHECKING:
    from .tool_context import ToolContext


class AnnouncementTool(BaseTool):
    """查询公司公告/通知(communication.Post)."""

    name = "announcement_query"
    description = "查询公司公告/通知(communication.Post)"
    intent_type = "announcement_query"
    required_auth = True

    def execute(self, query=None, context=None, params=None, scope=None, qs=None) -> dict:
        """查询公告(支持新旧两种签名)"""
        stopwords = {"公", "告", "通", "知", "最", "近", "本", "周", "什", "么", "查", "看"}
        keywords = ""
        if query:
            keywords = "".join(c for c in query if c not in stopwords).strip()
        elif params and params.get("keywords"):
            keywords = params["keywords"]

        if qs is None:
            from communication.models import Post
            from django.utils import timezone
            from django.db.models import Q
            qs = (
                Post.objects.filter(is_archived=False)
                .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now()))
                .select_related("author")
                .order_by("-created_at")
            )

        if keywords and len(keywords) >= 2:
            from django.db.models import Q
            qs = qs.filter(Q(title__icontains=keywords) | Q(content__icontains=keywords))

        posts = []
        for p in qs[:10]:
            raw_content = p.content or ""
            truncated = raw_content[:200] + ("..." if len(raw_content) > 200 else "")
            posts.append({
                "title": p.title,
                "content": truncated,
                "author": p.author.username if p.author else "系统",
                "created_at": p.created_at.date().isoformat(),
                "expires_at": p.expires_at.date().isoformat() if p.expires_at else None,
                "sort_key": p.created_at.date().isoformat(),
            })

        if not posts:
            return {
                "found": False,
                "message": f'未找到与 "{keywords or query}" 相关的公告',
                "module_label": "公告",
            }
        return {
            "found": True,
            "count": len(posts),
            "posts": posts,
            "module_label": "公告",
        }

    def build_base_queryset(self):
        from django.db.models import Q
        from django.utils import timezone
        from communication.models import Post
        return (
            Post.objects.filter(is_archived=False)
            .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now()))
            .select_related("author")
        )

    def _scope_self(self, qs, ctx):
        """本人范围:仅返回 ctx.user 发布的公告。"""
        return qs.filter(author=ctx.user)
