from rest_framework import viewsets
from .models import Personnel, Contract, Education, WorkExperience
from .serializers import (
    PersonnelSerializer, 
    PersonnelDetailSerializer,
    ContractSerializer, 
    EducationSerializer, 
    WorkExperienceSerializer
)

class PersonnelViewSet(viewsets.ModelViewSet):
    """
    一个用于查看和编辑人员信息的ViewSet。
    """
    queryset = Personnel.objects.all()

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

class EducationViewSet(viewsets.ModelViewSet):
    """
    一个用于查看和编辑教育背景的ViewSet。
    """
    queryset = Education.objects.all()
    serializer_class = EducationSerializer

class WorkExperienceViewSet(viewsets.ModelViewSet):
    """
    一个用于查看和编辑工作经历的ViewSet。
    """
    queryset = WorkExperience.objects.all()
    serializer_class = WorkExperienceSerializer