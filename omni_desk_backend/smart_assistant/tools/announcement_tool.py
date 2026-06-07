"""AnnouncementTool - 通信公告(Post)查询工具.

对应交接文档任务 1.1:
- 数据源:communication.Post
- 过滤:未过期 AND 未归档
- 关键词匹配:title / content
- 上限 10 条,按 created_at 倒序
- N+1 防护:select_related("author")
"""

from typing import TYPE_CHECKING, List

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

    def execute(self, query: str, context: "ToolContext") -> dict:
        # 1. 关键词抽取(去除停用字)
        # 单字停用词集合,与下方 char-by-char 迭代配合工作。
        stopwords = {"公", "告", "通", "知", "最", "近", "本", "周", "什", "么", "查", "看"}
        keywords = "".join(c for c in query if c not in stopwords).strip()

        # 2. 构造查询(未过期 AND 未归档)
        qs = (
            Post.objects.filter(is_archived=False)
            .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now()))
            .select_related("author")
            .order_by("-created_at")
        )

        if keywords and len(keywords) >= 2:
            # 关键词至少 2 字符,避免单字匹配过宽(如 "有" 在多数内容中都出现)
            qs = qs.filter(Q(title__icontains=keywords) | Q(content__icontains=keywords))

        posts: List[dict] = []
        for p in qs[:10]:
            raw_content = p.content or ""
            truncated = raw_content[:200] + ("..." if len(raw_content) > 200 else "")
            posts.append(
                {
                    "title": p.title,
                    "content": truncated,
                    "author": p.author.username if p.author else "系统",
                    "created_at": p.created_at.date().isoformat(),
                    "expires_at": p.expires_at.date().isoformat() if p.expires_at else None,
                }
            )

        if not posts:
            return {"found": False, "message": f'未找到与 "{keywords or query}" 相关的公告'}

        return {"found": True, "count": len(posts), "posts": posts}
