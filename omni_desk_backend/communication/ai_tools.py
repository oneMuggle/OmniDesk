"""交流模块的 AI 工具声明。

由 ``smart_assistant.capabilities`` 在启动时自动发现，见 ``docs/technical/46-ai-capability-catalog.md``。
"""

from smart_assistant.capabilities import DataScope, LOGIN_ONLY, ToolSpec, toolset
from smart_assistant.capabilities.helpers import clamp_limit, context_user, tool_params, truncate
from smart_assistant.tools.base import BaseTool

#: 每个帖子最多带回的评论数
_MAX_COMMENTS = 5


def _display_name(user) -> str:
    if user is None:
        return "Anonymous"
    return getattr(user, "real_name", "") or user.username


class CommunicationThreadQueryTool(BaseTool):
    """查询交流帖子及其最近评论（只读）。

    可见范围与 ``/api/communication/posts/`` 一致（``communication.selectors.visible_posts``）：
    已登录用户可读全部未归档帖子。``announcement_query`` 只列出公告标题和摘要，本工具
    额外返回评论数与最近评论，适合"大家对 XX 帖子怎么说""我发的帖子有什么回复"。
    """

    name = "communication_thread_query"
    description = "查询交流区帖子及最近评论（可按关键词、只看我发的帖子筛选）"
    intent_type = "communication_thread_query"
    risk_level = "read"
    required_auth = True

    def execute(self, query=None, context=None, params=None, **_kwargs) -> dict:
        from django.db.models import Count, Q

        from communication.selectors import visible_posts

        user = context_user(context)
        if user is None:
            return {"found": False, "message": "未识别到当前用户，无法查询交流帖子", "module_label": "交流"}

        params = tool_params(params)
        qs = visible_posts(user).select_related("author").annotate(comment_count=Count("comments"))

        post_id = params.get("post_id")
        if isinstance(post_id, int) and post_id > 0:
            qs = qs.filter(id=post_id)
        mine_only = params.get("mine_only")
        if mine_only is None:
            text = str(params.get("query") or query or "")
            mine_only = "我发的" in text or "我的帖子" in text
        if mine_only:
            qs = qs.filter(author=user)
        keyword = str(params.get("keyword") or "").strip()
        if keyword:
            qs = qs.filter(Q(title__icontains=keyword) | Q(content__icontains=keyword))

        limit = clamp_limit(params.get("limit"), default=5, maximum=10)
        posts = []
        for post in qs.order_by("-created_at")[:limit]:
            recent = list(post.comments.select_related("author").order_by("-created_at")[:_MAX_COMMENTS])
            posts.append(
                {
                    "id": post.id,
                    "title": post.title,
                    "content": truncate(post.content),
                    "author": _display_name(post.author),
                    "created_at": post.created_at.isoformat(timespec="minutes"),
                    "comment_count": post.comment_count,
                    "recent_comments": [
                        {
                            "author": _display_name(c.author),
                            "content": truncate(c.content, 120),
                            "created_at": c.created_at.isoformat(timespec="minutes"),
                        }
                        for c in reversed(recent)
                    ],
                    "url": f"/communication/{post.id}",
                }
            )

        if not posts:
            return {"found": False, "message": "没有找到符合条件的交流帖子", "module_label": "交流"}
        return {"found": True, "count": len(posts), "posts": posts, "module_label": "交流"}

    @classmethod
    def get_openai_tool_schema(cls) -> dict:
        return {
            "type": "function",
            "function": {
                "name": cls.intent_type,
                "description": (
                    "查询交流区帖子，返回摘要、评论数和最近几条评论。"
                    "示例：'交流区最近在讨论什么'、'我发的帖子有人回复吗'、'关于食堂的帖子大家怎么说'。"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "用户的原始问题（用于理解意图，不直接作为筛选词）"},
                        "keyword": {"type": "string", "description": "按标题或内容筛选的关键词（可选）"},
                        "mine_only": {"type": "boolean", "description": "是否只看我发的帖子（可选）"},
                        "post_id": {"type": "integer", "description": "指定帖子 ID（可选）"},
                        "limit": {"type": "integer", "description": "返回帖子数，默认 5，最多 10"},
                    },
                    "required": ["query"],
                    "additionalProperties": False,
                },
                "strict": True,
            },
        }


@toolset("communication", title="交流与公告")
def communication_tools():
    from smart_assistant.tools.announcement_tool import AnnouncementTool

    return [
        ToolSpec(
            tool=AnnouncementTool,
            title="查询公告",
            required_permission=LOGIN_ONLY,
            data_scope=DataScope.SCOPE,
        ),
        ToolSpec(
            tool=CommunicationThreadQueryTool,
            title="查询交流帖子",
            required_permission=LOGIN_ONLY,
            data_scope=DataScope.MODULE,
        ),
    ]
