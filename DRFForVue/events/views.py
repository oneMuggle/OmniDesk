from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser
from .models import Experiment, DocumentTemplate, ResponsiblePerson, Personnel, Equipment
from .serializers import ExperimentSerializer, DocumentTemplateSerializer, ResponsiblePersonSerializer, PersonnelSerializer, EquipmentSerializer

class ExperimentViewSet(viewsets.ModelViewSet):
    queryset = Experiment.objects.all()
    serializer_class = ExperimentSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

class EquipmentViewSet(viewsets.ModelViewSet):
    queryset = Equipment.objects.all()
    serializer_class = EquipmentSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        """自动关联当前用户"""
        if not self.request.user.is_staff:
            serializer.save(user=self.request.user)
        else:
            serializer.save()

class PersonnelViewSet(viewsets.ModelViewSet):
    queryset = Personnel.objects.all().order_by('id')
    serializer_class = PersonnelSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        """允许管理员设置其他用户，普通用户只能关联自己"""
        if not self.request.user.is_staff:
            serializer.save(user=self.request.user)
        else:
            serializer.save()

class DocumentTemplateViewSet(viewsets.ModelViewSet):
    queryset = DocumentTemplate.objects.all()
    serializer_class = DocumentTemplateSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser]

    def get_queryset(self):
        return self.queryset.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

class ResponsiblePersonViewSet(viewsets.ModelViewSet):
    queryset = ResponsiblePerson.objects.all()
    serializer_class = ResponsiblePersonSerializer
    permission_classes = [IsAuthenticated]

    def create(self, request, *args, **kwargs):
        if isinstance(request.data, list):
            serializer = self.get_serializer(data=request.data, many=True)
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
