from django.core.exceptions import ValidationError
from django.db.models import Q
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..models import AgentLog
from ..serializers import AgentLogFeedbackSerializer, AgentLogSerializer


class AgentLogViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Agent 日志审计：列表（支持过滤）+ 详情

    归属隔离（防 IDOR）：
        - 普通用户：仅能 list/retrieve 自己的日志（经 session__user 关联）
        - staff：保留跨用户审计能力（user_id 过滤参数仅对 staff 生效）
        - 无主日志（session 为空，失败路径产生）：仅 staff 可见
    retrieve / feedback 均受同一归属约束（queryset 限定后越权访问自动 404，
    不泄露他人日志存在性）。
    """

    serializer_class = AgentLogSerializer
    permission_classes = [IsAuthenticated]
    ordering = ["-created_at"]

    def get_queryset(self):
        user = self.request.user

        if user.is_staff:
            # staff 跨用户审计：默认全量，支持 user_id 过滤指定用户
            qs = AgentLog.objects.all()
            user_id = self.request.query_params.get("user_id")
            if user_id:
                qs = qs.filter(session__user_id=user_id)
        else:
            # 普通用户仅可见自己 session 下的日志；
            # session 为空的无主日志不匹配该过滤，天然对普通用户隐藏
            qs = AgentLog.objects.filter(session__user=user)

        intent = self.request.query_params.get("intent")
        if intent:
            qs = qs.filter(intent=intent)

        start = self.request.query_params.get("start_time")
        end = self.request.query_params.get("end_time")
        if start:
            qs = qs.filter(created_at__gte=start)
        if end:
            qs = qs.filter(created_at__lte=end)

        keyword = self.request.query_params.get("keyword")
        if keyword:
            qs = qs.filter(Q(user_query__icontains=keyword) | Q(llm_response__icontains=keyword))

        return qs

    @action(detail=True, methods=["patch"])
    def feedback(self, request, pk=None):
        """PATCH /api/smart-assistant/agent-logs/{id}/feedback/ — 提交用户反馈（赞/踩）

        请求体：{"feedback": "up" | "down" | null}
            - "up"/"down" 写入 AgentLog.user_feedback，允许改选（up→down 覆盖）
            - null 清除已有反馈（落库为空字符串）

        响应：
            - 200 {"feedback": <写入值>}（清除时为 null）
            - 400 feedback 值非法或缺失
            - 404 日志不存在或不属于当前用户（先鉴权，避免泄露他人日志存在性）
        """
        # 归属校验：日志通过 session 关联用户；session 为空视为无主，一律 404
        try:
            log = AgentLog.objects.get(pk=pk, session__user=request.user)
        except (AgentLog.DoesNotExist, ValueError, ValidationError):
            # ValueError/ValidationError：pk 非整数等非法输入
            return Response({"detail": "日志不存在。"}, status=status.HTTP_404_NOT_FOUND)

        serializer = AgentLogFeedbackSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        value = serializer.validated_data["feedback"]

        log.user_feedback = value or ""  # null → 清除（与模型 default="" 对齐）
        log.save(update_fields=["user_feedback"])
        return Response({"feedback": value})
