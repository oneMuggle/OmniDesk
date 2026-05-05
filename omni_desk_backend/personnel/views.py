from django.db import IntegrityError
from rest_framework import viewsets, permissions, serializers
from rest_framework.filters import SearchFilter
from users.permissions import IsAdminOrReadOnly
from .models import Personnel, Contract, Education, WorkExperience, ProfessionalQualification, FamilyMember, Position
from .serializers import (
    PositionSerializer,
    PersonnelSerializer,
    PersonnelDetailSerializer,
    ContractSerializer,
    EducationSerializer,
    WorkExperienceSerializer,
    ProfessionalQualificationSerializer,
    FamilyMemberSerializer
)

class PersonnelViewSet(viewsets.ModelViewSet):
    """
    一个用于查看和编辑人员信息的ViewSet。
    """
    queryset = Personnel.objects.select_related('position').prefetch_related(
        'contracts', 'educations', 'work_experiences', 'qualifications', 'family_members'
    )
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [SearchFilter]
    search_fields = ['name', 'id_card_number']

    def get_serializer_class(self):
        """
        根据action的不同，返回不同的serializer。
        - 列表视图使用简化的PersonnelSerializer。
        - 详情视图使用包含完整关联信息的PersonnelDetailSerializer。
        """
        if self.action == 'retrieve':
            return PersonnelDetailSerializer
        return PersonnelSerializer


class ContractViewSet(viewsets.ModelViewSet):
    """
    一个用于查看和编辑合同信息的ViewSet。
    """
    queryset = Contract.objects.all()
    serializer_class = ContractSerializer
    permission_classes = [permissions.IsAuthenticated]

class EducationViewSet(viewsets.ModelViewSet):
    """
    一个用于查看和编辑教育背景的ViewSet。
    """
    queryset = Education.objects.all()
    serializer_class = EducationSerializer
    permission_classes = [permissions.IsAuthenticated]

class WorkExperienceViewSet(viewsets.ModelViewSet):
    """
    一个用于查看和编辑工作经历的ViewSet。
    """
    queryset = WorkExperience.objects.all()
    serializer_class = WorkExperienceSerializer
    permission_classes = [permissions.IsAuthenticated]

class ProfessionalQualificationViewSet(viewsets.ModelViewSet):
    """
    一个用于查看和编辑职业资质的ViewSet。
    """
    queryset = ProfessionalQualification.objects.all()
    serializer_class = ProfessionalQualificationSerializer
    permission_classes = [permissions.IsAuthenticated]

class FamilyMemberViewSet(viewsets.ModelViewSet):
    """
    一个用于查看和编辑家庭成员的ViewSet。
    """
    queryset = FamilyMember.objects.all()
    serializer_class = FamilyMemberSerializer
    permission_classes = [permissions.IsAuthenticated]

class PositionViewSet(viewsets.ModelViewSet):
    """
    一个用于查看和编辑职位信息的ViewSet。
    """
    queryset = Position.objects.all()
    serializer_class = PositionSerializer
    permission_classes = [IsAdminOrReadOnly]