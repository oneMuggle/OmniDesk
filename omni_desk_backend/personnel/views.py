from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from users.permissions import IsAdminOrManagerOrReadOnly

from .models import Contract, Education, FamilyMember, Personnel, Position, ProfessionalQualification, WorkExperience
from .permissions import IsOwnerOrManagerOrReadOnly, is_privileged_user
from .serializers import (
    ContractSerializer,
    EducationSerializer,
    FamilyMemberSerializer,
    PersonnelDetailSerializer,
    PersonnelSerializer,
    PositionSerializer,
    ProfessionalQualificationSerializer,
    WorkExperienceSerializer,
)


class PersonnelViewSet(viewsets.ModelViewSet):
    """
    一个用于查看和编辑人员信息的ViewSet。
    """

    def get_queryset(self):
        queryset = Personnel.objects.select_related("position")
        if self.action == "retrieve":
            queryset = queryset.prefetch_related(
                "contracts", "educations", "work_experiences", "qualifications", "family_members"
            )
        return queryset

    permission_classes = [IsAdminOrManagerOrReadOnly]
    filter_backends = [SearchFilter]
    search_fields = ["name", "id_card_number"]

    def get_serializer_class(self):
        """
        根据action的不同，返回不同的serializer。
        - 列表视图使用简化的PersonnelSerializer。
        - 详情视图使用包含完整关联信息的PersonnelDetailSerializer。
        """
        if self.action == "retrieve":
            return PersonnelDetailSerializer
        return PersonnelSerializer

    @action(detail=True, methods=["post"])
    def upload(self, request, pk=None):
        """上传人事档案,通过 paperless_proxy 异步投递到 paperless-ngx"""
        from paperless_proxy.services.upload import PaperlessUploadService

        personnel = self.get_object()
        file = request.FILES.get("file")
        if not file:
            return Response({"detail": "缺少 file 字段"}, status=400)
        try:
            result = PaperlessUploadService.queue_upload(
                file=file,
                filename=file.name,
                title=request.data.get("title") or file.name,
                source_type="personnel_file",
                source_id=personnel.id,
                owner=request.user,
                tags=request.data.get("tags"),
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response(result, status=201)


def _scoped_queryset(model, request):
    """行级过滤(P0-A):admin/hr/manager 可见全量,其他用户仅见本人 personnel 名下数据。"""
    queryset = model.objects.select_related("personnel").order_by("pk")
    if is_privileged_user(request.user):
        return queryset
    return queryset.filter(personnel__user_account=request.user)


class ContractViewSet(viewsets.ModelViewSet):
    """
    一个用于查看和编辑合同信息的ViewSet。
    """

    serializer_class = ContractSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrManagerOrReadOnly]

    def get_queryset(self):
        return _scoped_queryset(Contract, self.request)


class EducationViewSet(viewsets.ModelViewSet):
    """
    一个用于查看和编辑教育背景的ViewSet。
    """

    serializer_class = EducationSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrManagerOrReadOnly]

    def get_queryset(self):
        return _scoped_queryset(Education, self.request)


class WorkExperienceViewSet(viewsets.ModelViewSet):
    """
    一个用于查看和编辑工作经历的ViewSet。
    """

    serializer_class = WorkExperienceSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrManagerOrReadOnly]

    def get_queryset(self):
        return _scoped_queryset(WorkExperience, self.request)


class ProfessionalQualificationViewSet(viewsets.ModelViewSet):
    """
    一个用于查看和编辑职业资质的ViewSet。
    """

    serializer_class = ProfessionalQualificationSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrManagerOrReadOnly]

    def get_queryset(self):
        return _scoped_queryset(ProfessionalQualification, self.request)


class FamilyMemberViewSet(viewsets.ModelViewSet):
    """
    一个用于查看和编辑家庭成员的ViewSet。
    """

    serializer_class = FamilyMemberSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrManagerOrReadOnly]

    def get_queryset(self):
        return _scoped_queryset(FamilyMember, self.request)


class PositionViewSet(viewsets.ModelViewSet):
    """
    一个用于查看和编辑职位信息的ViewSet。
    """

    queryset = Position.objects.all()
    serializer_class = PositionSerializer
    permission_classes = [IsAdminOrManagerOrReadOnly]
