"""通知中心的 AI 工具声明。

由 ``smart_assistant.capabilities`` 在启动时自动发现，见 ``docs/technical/46-ai-capability-catalog.md``。
"""

from smart_assistant.capabilities import ConfirmPolicy, DataScope, LOGIN_ONLY, ToolSpec, toolset, QuickPrompt
from smart_assistant.capabilities.helpers import clamp_limit, context_user, tool_params, truncate
from smart_assistant.tools.base import BaseTool


class NotificationQueryTool(BaseTool):
    """查询当前用户自己的站内通知（只读）。

    数据范围固定为本人（与 ``/api/notifications/`` 一致）：管理员的
    DEPARTMENT / GLOBAL scope 也不能看他人通知，因此不实现 scope 三件套。
    """

    name = "notification_query"
    description = "查询我的站内通知（未读数、最近通知，可按类型、关键词筛选）"
    intent_type = "notification_query"
    risk_level = "read"
    required_auth = True

    def execute(self, query=None, context=None, params=None, **_kwargs) -> dict:
        from notifications.models import Notification

        user = context_user(context)
        if user is None:
            return {"found": False, "message": "未识别到当前用户，无法查询通知", "module_label": "通知"}

        params = tool_params(params)
        base = Notification.objects.filter(user=user)
        unread_count = base.filter(is_read=False).count()

        unread_only = params.get("unread_only")
        if unread_only is None:
            # 旧意图路径只有自然语言：出现"未读"即按未读筛选
            unread_only = "未读" in str(params.get("query") or query or "")
        qs = base.filter(is_read=False) if unread_only else base

        type_filter = params.get("type")
        valid_types = {code for code, _ in Notification.TYPE_CHOICES}
        if type_filter in valid_types:
            qs = qs.filter(type=type_filter)

        keyword = str(params.get("keyword") or "").strip()
        if keyword:
            from django.db.models import Q

            qs = qs.filter(Q(title__icontains=keyword) | Q(content__icontains=keyword))

        limit = clamp_limit(params.get("limit"))
        items = [
            {
                "id": n.id,
                "type": n.type,
                "type_label": n.get_type_display(),
                "priority": n.get_priority_display(),
                "title": n.title,
                "content": truncate(n.content),
                "is_read": n.is_read,
                "created_at": n.created_at.isoformat(timespec="minutes"),
                "link": n.link,
            }
            for n in qs.order_by("-created_at")[:limit]
        ]
        result = {
            "unread_count": unread_count,
            "count": len(items),
            "notifications": items,
            "url": "/notifications",
            "module_label": "通知",
        }
        if not items:
            scope_text = "未读通知" if unread_only else "通知"
            return {"found": False, "message": f"没有符合条件的{scope_text}", **result}
        return {"found": True, **result}

    @classmethod
    def get_openai_tool_schema(cls) -> dict:
        from notifications.models import Notification

        return {
            "type": "function",
            "function": {
                "name": cls.intent_type,
                "description": (
                    "查询当前用户自己的站内通知，返回未读数和最近的通知列表。"
                    "示例：'我有几条未读通知'、'最近的排班变更通知'。只能看到本人的通知。"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "用户的原始问题（用于理解意图，不直接作为筛选词）"},
                        "keyword": {"type": "string", "description": "按标题或内容筛选的关键词（可选）"},
                        "unread_only": {"type": "boolean", "description": "是否只看未读（可选）"},
                        "type": {
                            "type": "string",
                            "enum": [code for code, _ in Notification.TYPE_CHOICES],
                            "description": "通知类型（可选）",
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
    "notifications",
    title="通知",
    routes=(r"^/notifications",),
    quick_prompts=(QuickPrompt("未读通知", "我有几条未读通知？都是什么？", routes=(r"^/$", r"^/notifications")),),
)
def notification_tools():
    from smart_assistant.tools.notify_tool import NotifyTool

    return [
        ToolSpec(
            tool=NotificationQueryTool,
            title="查询我的通知",
            required_permission=LOGIN_ONLY,
            data_scope=DataScope.OWNER,
        ),
        ToolSpec(
            tool=NotifyTool,
            title="发送站内通知",
            required_permission=LOGIN_ONLY,
            data_scope=DataScope.RECIPIENT,
            confirm=ConfirmPolicy.USER,
        ),
    ]
