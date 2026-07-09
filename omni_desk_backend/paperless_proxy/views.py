from rest_framework import viewsets, status, mixins
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend

from .models import OutboxItem
from .serializers import OutboxItemSerializer
from .permissions import IsAdmin
from .services.outbox import OutboxService


class OutboxViewSet(viewsets.ReadOnlyModelViewSet):
    """Outbox 管理(admin 限定)"""
    queryset = OutboxItem.objects.all()
    serializer_class = OutboxItemSerializer
    permission_classes = [IsAdmin]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status', 'operation']

    @action(detail=True, methods=['post'])
    def retry(self, request, pk=None):
        outbox = self.get_object()
        if outbox.status != 'dead':
            return Response(
                {'detail': f'只能重试死信(当前 status={outbox.status})'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        OutboxService.retry_dead(outbox)
        return Response(OutboxItemSerializer(outbox).data)