from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from .models import Experiment, Personnel, Equipment, DocumentTemplate
from .serializers import ExperimentSerializer, PersonnelSerializer, EquipmentSerializer, DocumentTemplateSerializer
from users.permissions import IsOwnerOrReadOnly
from django_filters.rest_framework import DjangoFilterBackend

class DocumentTemplateViewSet(viewsets.ModelViewSet):
    queryset = DocumentTemplate.objects.all()
    serializer_class = DocumentTemplateSerializer
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['name', 'experiment_type', 'created_at']

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

class EquipmentViewSet(viewsets.ModelViewSet):
    queryset = Equipment.objects.all()
    serializer_class = EquipmentSerializer
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['name', 'category', 'status']

class ResponsiblePersonViewSet(viewsets.ModelViewSet):
    queryset = Personnel.objects.all()
    serializer_class = PersonnelSerializer
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['name', 'department', 'position']

class ExperimentViewSet(viewsets.ModelViewSet):
    queryset = Experiment.objects.all().prefetch_related('equipments', 'responsible_persons')
    serializer_class = ExperimentSerializer
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = [
        'status',
        'equipments__name',
        'responsible_persons__name',
        'start_time',
        'end_time'
    ]

    def get_queryset(self):
        """查询集配置（参照设备管理视图）"""
        return super().get_queryset().order_by('-start_time')

    def perform_create(self, serializer):
        """创建时处理多对多关系（与人员管理逻辑一致）"""
        instance = serializer.save()
        
        # 批量处理关联关系更新
        relations = {
            'equipments': self.request.data.get('equipments', []),
            'responsible_persons': self.request.data.get('responsible_persons', [])
        }
        
        for field_name, ids in relations.items():
            if isinstance(ids, list):
                getattr(instance, field_name).set(ids)
