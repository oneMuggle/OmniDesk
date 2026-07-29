import re
from datetime import datetime
from urllib.parse import quote

from django.http import HttpResponse
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..agent.conversation_context import count_turns
from ..models import SmartAssistantSession
from ..serializers import SessionForkSerializer, SmartAssistantSessionSerializer

# fork 标题后缀（与模型 title max_length=255 对齐）
FORK_TITLE_SUFFIX = "（副本）"
TITLE_MAX_LENGTH = 255

# 导出文件名中不允许的字符（Windows/Unix 文件名安全）
_EXPORT_FILENAME_INVALID_CHARS = re.compile(r'[\\/:*?"<>|\r\n\t]+')

# 消息 role → Markdown 角色标签
_ROLE_LABELS = {
    "user": "用户",
    "assistant": "助手",
    "system": "系统",
}


def build_fork_title(original_title: str) -> str:
    """生成副本标题，超长时截断原标题以适配模型 max_length。"""
    max_original = TITLE_MAX_LENGTH - len(FORK_TITLE_SUFFIX)
    return f"{original_title[:max_original]}{FORK_TITLE_SUFFIX}"


def render_session_markdown(session: SmartAssistantSession) -> str:
    """将会话渲染为 Markdown 文档：标题 + 元信息 + 逐条消息段落。"""
    created = timezone.localtime(session.created_at).strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        f"# {session.title}",
        "",
        f"- 创建时间：{created}",
        f"- 对话轮数：{session.turn_count}",
        "",
        "---",
        "",
    ]
    for msg in session.messages or []:
        role_label = _ROLE_LABELS.get(msg.get("role"), msg.get("role") or "未知")
        content = (msg.get("content") or "").strip()
        lines.append(f"**{role_label}**:")
        lines.append("")
        lines.append(content)
        lines.append("")
    return "\n".join(lines)


def build_export_filename(session: SmartAssistantSession) -> str:
    """构造导出文件名：清洗标题中的非法字符 + 导出日期。"""
    safe_title = _EXPORT_FILENAME_INVALID_CHARS.sub("_", session.title).strip() or f"session-{session.pk}"
    export_date = datetime.now().strftime("%Y%m%d")
    return f"{safe_title}-{export_date}.md"


class SessionViewSet(viewsets.ModelViewSet):
    """会话管理：列表/创建/查看/删除/复制（fork）/导出（export）"""

    serializer_class = SmartAssistantSessionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return SmartAssistantSession.objects.filter(user=self.request.user).order_by("-updated_at")

    def perform_destroy(self, instance):
        if instance.user == self.request.user:
            instance.delete()

    @action(detail=True, methods=["post"])
    def fork(self, request, pk=None):
        """复制当前会话为属于请求用户的新会话（借鉴 claw-code 的 session fork）。

        请求体（均可选）：
            - at_message: 非负整数，仅复制前 N 条消息（默认全量复制）
            - title: 新会话标题（默认「原标题（副本）」）

        返回 201 + 新会话序列化数据。
        get_queryset 已限定本人会话，访问他人会话自动 404。
        """
        session = self.get_object()

        fork_serializer = SessionForkSerializer(data=request.data or {})
        fork_serializer.is_valid(raise_exception=True)
        at_message = fork_serializer.validated_data.get("at_message")
        title = fork_serializer.validated_data.get("title") or build_fork_title(session.title)

        messages = list(session.messages or [])
        if at_message is not None:
            messages = messages[:at_message]

        new_session = SmartAssistantSession.objects.create(
            user=request.user,
            title=title,
            messages=messages,
            # 截断后消息数变化，按截断结果重算轮数（与 chat 视图逻辑一致）
            turn_count=count_turns(messages),
            # 截断后旧摘要可能与消息不匹配，置空由后续对话按需重建
            summary_text="",
        )
        return Response(self.get_serializer(new_session).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"])
    def export(self, request, pk=None):
        """导出会话为 Markdown 文档（附件下载）。

        响应：Content-Type 为 text/markdown，Content-Disposition 附件文件名
        含会话标题与导出日期（RFC 5987 编码支持中文）。
        get_queryset 已限定本人会话，访问他人会话自动 404。
        """
        session = self.get_object()
        markdown = render_session_markdown(session)

        response = HttpResponse(markdown, content_type="text/markdown; charset=utf-8")
        filename = build_export_filename(session)
        # 兼容 ASCII 兜底文件名 + RFC 5987 编码的中文文件名
        response["Content-Disposition"] = (
            f"attachment; filename=\"session-{session.pk}.md\"; filename*=UTF-8''{quote(filename)}"
        )
        return response
