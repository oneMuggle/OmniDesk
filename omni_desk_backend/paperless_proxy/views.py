from rest_framework import viewsets, status, mixins
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend

from .models import OutboxItem, PaperlessHealth, UserPaperlessBinding
from .serializers import OutboxItemSerializer, PaperlessHealthSerializer, UserPaperlessBindingSerializer
from .permissions import IsAdmin
from .services.outbox import OutboxService
from .services.client import PaperlessClient
from .exceptions import PaperlessAuthError, PaperlessNotFoundError


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


class HealthView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        health = PaperlessHealth.get_singleton()
        return Response(PaperlessHealthSerializer(health).data)


class BindView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        bind = UserPaperlessBinding.objects.filter(user=request.user, is_active=True).first()
        if not bind:
            return Response({'bound': False})
        return Response({
            'bound': True,
            **UserPaperlessBindingSerializer(bind).data,
        })

    def delete(self, request):
        UserPaperlessBinding.objects.filter(user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        if not username or not password:
            return Response({'detail': 'username and password required'}, status=400)
        client = PaperlessClient()
        try:
            client.post_token(username, password)
            user_info = client.get_user_by_username(username)
        except PaperlessAuthError as e:
            return Response({'detail': str(e)}, status=401)
        except PaperlessNotFoundError:
            return Response({'detail': f'paperless 用户 {username} 不存在'}, status=404)
        bind, _ = UserPaperlessBinding.objects.update_or_create(
            user=request.user,
            defaults={
                'paperless_user_id': user_info['id'],
                'paperless_username': user_info['username'],
                'is_active': True,
            },
        )
        return Response(UserPaperlessBindingSerializer(bind).data, status=201)


class BindStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return BindView().get(request)