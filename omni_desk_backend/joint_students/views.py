"""联培生模块 DRF ViewSets。"""

from datetime import datetime

from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from joint_students.models import (
    AssessmentCycle,
    ExpertScore,
    JointStudent,
    MonthlyReport,
    StipendRecord,
)
from joint_students.permissions import (
    MANAGER_GROUP,
    IsExpertGroupMember,
    IsJointStudentManager,
    IsJointStudentSelfOrManager,
    user_is_mentor,
)
from joint_students.serializers import (
    AssessmentCycleSerializer,
    ExpertScoreSerializer,
    JointStudentSerializer,
    MonthlyReportSerializer,
    StipendRecordSerializer,
)


def _user_can_see_all_reports(user) -> bool:
    """联培生管理员 / superuser 可见所有报告;否则仅自己。"""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user.groups.filter(name="联培生管理员").exists()


def _own_joint_student_ids(user):
    """返回该 user 名下 Personnel 关联的 JointStudent id 列表。"""
    return list(JointStudent.objects.filter(personnel__user_account=user).values_list("id", flat=True))


def _mentor_joint_student_ids(user):
    """返回该 user 作为导师时名下的 JointStudent id 列表。"""
    return list(JointStudent.objects.filter(mentor__user_account=user).values_list("id", flat=True))


def _user_can_see_all_students(user) -> bool:
    """联培生管理员 / superuser 可见全部联培生。"""
    if not user or not user.is_authenticated:
        return False
    return user.is_superuser or user.groups.filter(name=MANAGER_GROUP).exists()


class JointStudentViewSet(viewsets.ModelViewSet):
    """联培生 CRUD (管理员写入,本人/导师按关联范围读取)。"""

    queryset = JointStudent.objects.select_related("personnel", "mentor").order_by("id")
    serializer_class = JointStudentSerializer
    permission_classes = [IsJointStudentManager]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if _user_can_see_all_students(user):
            return qs
        scoped_ids = set(_own_joint_student_ids(user))
        if user_is_mentor(user):
            scoped_ids |= set(_mentor_joint_student_ids(user))
        return qs.filter(id__in=scoped_ids)

    @action(detail=True, methods=["post"])
    def graduate(self, request, pk=None):
        """标记毕业: is_active=False + graduation_date=今天。"""
        js = self.get_object()
        js.is_active = False
        js.graduation_date = datetime.now().date()
        js.save(update_fields=["is_active", "graduation_date"])
        return Response({"status": "graduated"})


class MonthlyReportViewSet(viewsets.ModelViewSet):
    """月度报告。

    联培生管理员可见所有;联培生本人仅可见自己的。
    """

    serializer_class = MonthlyReportSerializer
    permission_classes = [IsJointStudentSelfOrManager]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        qs = MonthlyReport.objects.select_related("joint_student__personnel").all()
        user = self.request.user
        if _user_can_see_all_reports(user):
            return qs
        scoped_ids = set(_own_joint_student_ids(user))
        if user_is_mentor(user):
            scoped_ids |= set(_mentor_joint_student_ids(user))
        return qs.filter(joint_student_id__in=scoped_ids)

    def perform_create(self, serializer):
        """仅管理员或报告所属联培生本人可创建报告。"""
        joint_student = serializer.validated_data["joint_student"]
        user = self.request.user
        if not _user_can_see_all_reports(user):
            owner = getattr(joint_student.personnel, "user_account", None)
            if owner != user:
                from rest_framework.exceptions import PermissionDenied

                raise PermissionDenied("只能创建本人报告")
        serializer.save()

    def perform_update(self, serializer):
        """普通报告接口不允许修改报告归属或终态内容。"""
        instance = getattr(self, "get_object", lambda: None)()
        if instance and instance.status in (
            MonthlyReport.STATUS_APPROVED,
            MonthlyReport.STATUS_REJECTED,
        ):
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied("已审核报告不可修改")
        if "joint_student" in self.request.data:
            from rest_framework.exceptions import ValidationError

            raise ValidationError({"joint_student": "报告归属不可修改"})
        serializer.save()

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        """联培生提交报告 (draft → submitted)。"""
        report = self.get_object()
        if report.status != MonthlyReport.STATUS_DRAFT:
            return Response(
                {"detail": "只有草稿可提交"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        report.status = MonthlyReport.STATUS_SUBMITTED
        report.submitted_at = timezone.now()
        report.save(update_fields=["status", "submitted_at"])
        return Response({"status": "submitted"})

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        """联培生管理员通过 (submitted → approved)。"""
        if not _user_can_see_all_reports(request.user):
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied("仅联培生管理员可审核")
        report = self.get_object()
        if report.status != MonthlyReport.STATUS_SUBMITTED:
            return Response(
                {"detail": "只有已提交可审核"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        report.status = MonthlyReport.STATUS_APPROVED
        report.reviewed_at = timezone.now()
        report.reviewer = request.user
        report.save(update_fields=["status", "reviewed_at", "reviewer"])
        return Response({"status": "approved"})

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        """联培生管理员驳回 (submitted → rejected)。需 reviewer_comment。"""
        if not _user_can_see_all_reports(request.user):
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied("仅联培生管理员可审核")
        report = self.get_object()
        if report.status != MonthlyReport.STATUS_SUBMITTED:
            return Response(
                {"detail": "只有已提交可驳回"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        comment = (request.data.get("reviewer_comment") or "").strip()
        if not comment:
            return Response(
                {"detail": "驳回必须填写审核意见"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        report.status = MonthlyReport.STATUS_REJECTED
        report.reviewed_at = timezone.now()
        report.reviewer = request.user
        report.reviewer_comment = comment
        report.save(
            update_fields=[
                "status",
                "reviewed_at",
                "reviewer",
                "reviewer_comment",
            ]
        )
        return Response({"status": "rejected"})


class AssessmentCycleViewSet(viewsets.ModelViewSet):
    """考核批次。

    只允许 GET 与 POST (含 trigger/force_close action)。
    不允许 PUT/PATCH/DELETE — 批次历史不可修改。
    """

    queryset = AssessmentCycle.objects.all()
    serializer_class = AssessmentCycleSerializer
    permission_classes = [IsJointStudentManager]
    http_method_names = ["get", "post", "head", "options"]

    @action(detail=False, methods=["post"], url_path="trigger")
    def trigger(self, request):
        """联培生管理员手动提前触发指定 (year, month) 批次。"""
        from joint_students.services.cycle import create_cycle

        year = int(request.data.get("year") or datetime.now().year)
        month = int(request.data.get("month") or datetime.now().month)
        cycle = create_cycle(
            year,
            month,
            trigger_source=AssessmentCycle.TRIGGER_MANUAL,
            creator=request.user,
        )
        return Response(
            AssessmentCycleSerializer(cycle).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"])
    def force_close(self, request, pk=None):
        """强制截止 (collecting → closed)。"""
        cycle = self.get_object()
        if cycle.status != AssessmentCycle.STATUS_COLLECTING:
            return Response(
                {"detail": "仅 collecting 状态可强制截止"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        from joint_students.services.cycle import close_cycle

        close_cycle(cycle)
        return Response({"status": "closed"})


class ExpertScoreViewSet(viewsets.ModelViewSet):
    """专家打分。

    专家只看到自己的打分;创建时强制 expert=request.user + is_locked=True;
    unlock 动作仅 superuser 可触发。
    """

    serializer_class = ExpertScoreSerializer
    permission_classes = [IsExpertGroupMember]

    def get_queryset(self):
        return ExpertScore.objects.filter(expert=self.request.user).select_related(
            "expert",
            "joint_student__personnel",
            "cycle",
        )

    def perform_create(self, serializer):
        serializer.save(
            expert=self.request.user,
            submitted_at=timezone.now(),
            is_locked=True,
        )

    @action(detail=True, methods=["post"], url_path="unlock")
    def unlock(self, request, pk=None):
        """仅 superuser 可解锁。"""
        if not request.user.is_superuser:
            return Response(
                {"detail": "仅 admin 可解锁"},
                status=status.HTTP_403_FORBIDDEN,
            )
        score = self.get_object()
        score.is_locked = False
        score.save(update_fields=["is_locked"])
        return Response({"status": "unlocked"})


class StipendRecordViewSet(viewsets.ReadOnlyModelViewSet):
    """补助记录 (只读 + lock action)。

    联培生管理员可见所有;联培生本人仅可见 status=locked 且是自己的记录。
    lock 动作: pending → locked + 通知联培生。
    """

    queryset = StipendRecord.objects.select_related(
        "joint_student__personnel",
        "cycle",
    ).all()
    serializer_class = StipendRecordSerializer
    permission_classes = [IsJointStudentManager]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if _user_can_see_all_reports(user):
            return qs
        own_ids = _own_joint_student_ids(user)
        return qs.filter(
            joint_student_id__in=own_ids,
            status=StipendRecord.STATUS_LOCKED,
        )

    @action(detail=True, methods=["post"])
    def lock(self, request, pk=None):
        """联培生管理员复核 + 锁定 (pending → locked, 联培生可见)。"""
        stipend = self.get_object()
        if stipend.status != StipendRecord.STATUS_PENDING:
            return Response(
                {"detail": "仅 pending 可锁定"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        stipend.status = StipendRecord.STATUS_LOCKED
        stipend.locked_at = timezone.now()
        stipend.locked_by = request.user
        stipend.notes = request.data.get("notes", stipend.notes)
        stipend.save(update_fields=["status", "locked_at", "locked_by", "notes"])
        # 通知联培生 (Personnel.user_account 可能为 None, 防御性跳过)
        owner = getattr(stipend.joint_student.personnel, "user_account", None)
        if owner is not None:
            # 复用 notifications app 的 Notification 模型 (与 services/cycle.py 一致)
            from notifications.models import Notification

            Notification.objects.create(
                user=owner,
                type="stipend_locked",
                title=(f"您 {stipend.cycle.year}-{stipend.cycle.month:02d} 的补助已锁定"),
                content=(f"本月补助: {stipend.final_amount} 元 ({stipend.get_grade_display()})"),
                link="/joint-students/student/stipends",
            )
        return Response({"status": "locked"})


class PersonnelPoolView(APIView):
    """可关联为联培生的 Personnel 池。

    返回所有 Personnel 列表 (含是否已关联 JointStudent 标记),
    供联培生管理员在创建 JointStudent 时选择。
    只允许 联培生管理员 Group 访问。
    """

    permission_classes = [IsJointStudentManager]

    def get(self, request):
        from personnel.models import Personnel

        personnel_qs = Personnel.objects.all().order_by("name")
        # 标记是否已有关联的 JointStudent
        js_personnel_ids = set(JointStudent.objects.values_list("personnel_id", flat=True))
        data = [
            {
                "id": p.id,
                "name": p.name,
                "department": p.department or "",
                "has_joint_student": p.id in js_personnel_ids,
            }
            for p in personnel_qs[:500]  # 显式封顶, 避免无界查询
        ]
        return Response(data)
