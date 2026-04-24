from rest_framework.decorators import action
from rest_framework import generics, permissions, status, exceptions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.authtoken.models import Token
from django.contrib.auth import authenticate
from ratelimit.decorators import ratelimit
from .serializers import (
    UserRegistrationSerializer,
    UserLoginSerializer,
    UserDetailSerializer,
    CustomTokenObtainPairSerializer,
    PersonnelSerializer,
    UserAdminSerializer, # 导入 UserAdminSerializer
    ChangePasswordSerializer
)
from .permissions import IsAdminOrManager, IsAdmin # 导入 IsAdmin



from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView
from .models import CustomUser
from personnel.models import Personnel, Position
from .serializers import (
    UserRegistrationSerializer,
    UserLoginSerializer,
    UserDetailSerializer,
    CustomTokenObtainPairSerializer,
    PersonnelSerializer,
    UserPersonnelSerializer,
    PositionSerializer
)

RATELIMIT_CONFIG = {
    'group': 'auth',
    'key': 'ip',
    'rate': '5/15m',
    'method': 'POST',
    'block': False,
}

class UserRegistrationView(generics.CreateAPIView):
    serializer_class = UserRegistrationSerializer
    permission_classes = [permissions.AllowAny]

    @ratelimit(**RATELIMIT_CONFIG)
    def post(self, request, *args, **kwargs):
        if getattr(request, 'limited', False):
            return Response({
                "success": False,
                "error": "rate_limit",
                "message": "请求过于频繁，请稍后再试"
            }, status=status.HTTP_429_TOO_MANY_REQUESTS)
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            user = serializer.save()
            
            return Response({
                "success": True,
                "message": "注册成功，请登录",
                "username": user.username,
                "user": UserDetailSerializer(user).data # 返回 user 对象
            }, status=status.HTTP_201_CREATED)
        except exceptions.APIException as e:
            error_key = list(e.detail.keys())[0] if isinstance(e.detail, dict) else 'validation_error'
            return Response({
                "success": False,
                "error": error_key,
                "message": "注册验证失败",
                "validation_errors": e.detail
            }, status=e.status_code)
        except Exception as e:
            import traceback
            traceback.print_exc()
            error_data = {
                "success": False,
                "error": "username_exists",
                "detail": "用户名已被使用",
                "validation_errors": serializer.errors if 'serializer' in locals() else {}
            }
            return Response(error_data, status=status.HTTP_400_BAD_REQUEST)

class UserDetailView(generics.RetrieveAPIView):
    serializer_class = UserDetailSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_object(self):
        return self.request.user

class CurrentUserView(generics.RetrieveAPIView):
    serializer_class = UserDetailSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_object(self):
        return self.request.user
class UserProfileUpdateView(generics.RetrieveUpdateAPIView):
    serializer_class = UserDetailSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return CustomUser.objects.filter(id=self.request.user.id)

    def get_object(self):
        return self.request.user

class UserLoginView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer
    permission_classes = [permissions.AllowAny]

    @ratelimit(**RATELIMIT_CONFIG)
    def post(self, request, *args, **kwargs):
        if getattr(request, 'limited', False):
            return Response({
                "success": False,
                "error": "rate_limit",
                "message": "请求过于频繁，请稍后再试"
            }, status=status.HTTP_429_TOO_MANY_REQUESTS)
        return super().post(request, *args, **kwargs)


from django.db.models import Q
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter
from django.db import transaction


class ChangePasswordView(generics.UpdateAPIView):
    serializer_class = ChangePasswordSerializer
    model = CustomUser
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self, queryset=None):
        return self.request.user

    def update(self, request, *args, **kwargs):
        self.object = self.get_object()
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            if not self.object.check_password(serializer.data.get("old_password")):
                return Response({"old_password": ["Wrong password."]}, status=status.HTTP_400_BAD_REQUEST)
            self.object.set_password(serializer.data.get("new_password"))
            self.object.save()
            return Response(status=status.HTTP_204_NO_CONTENT)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class UserAdminListView(generics.ListAPIView):
    queryset = CustomUser.objects.select_related('personnel').prefetch_related('phone_numbers').order_by('id') # 按照id排序
    serializer_class = UserAdminSerializer
    permission_classes = [IsAdmin] # 只有管理员可以访问

class UserAdminDetailView(generics.RetrieveUpdateAPIView):
    queryset = CustomUser.objects.all()
    serializer_class = UserAdminSerializer
    permission_classes = [IsAdmin] # 只有管理员可以访问
    lookup_field = 'id'

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        personnel_id = request.data.get('personnel_id')

        if personnel_id is not None:
            try:
                personnel = Personnel.objects.get(id=personnel_id)
                instance.personnel = personnel
                instance.real_name = personnel.name
                # Assuming personnel model has a phone_numbers field
                if hasattr(personnel, 'phone_numbers') and personnel.phone_numbers.exists():
                    instance.phone_number = personnel.phone_numbers.first().number
                instance.save()
            except Personnel.DoesNotExist:
                return Response({"detail": "Personnel not found."}, status=status.HTTP_404_NOT_FOUND)

        return super().partial_update(request, *args, **kwargs)

from rest_framework import viewsets
class UserPersonnelViewSet(viewsets.ModelViewSet):
    queryset = CustomUser.objects.all().order_by('username')
    serializer_class = UserPersonnelSerializer # 使用 UserPersonnelSerializer
    lookup_field = 'id'
    pagination_class = None
    permission_classes = [IsAdminOrManager] # 确保只有管理员和经理可以访问
    filter_backends = [SearchFilter]
    search_fields = ['real_name', 'username']

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        personnel_id = request.data.get('personnel_id')

        # 如果提供了 personnel_id，则处理关联
        if personnel_id is not None:
            if personnel_id == '':  # 解除关联
                instance.personnel = None
            else:  # 关联
                try:
                    personnel = Personnel.objects.get(id=personnel_id)
                    instance.personnel = personnel
                    instance.real_name = personnel.name  # 强制设置为人员名称
                except Personnel.DoesNotExist:
                    return Response({"detail": "人员不存在。"}, status=status.HTTP_404_NOT_FOUND)
        
        # 不论 personnel_id 是否提供，都保存实例
        instance.save()
        
        # 在保存后序列化并返回
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    def get_queryset(self):
        # 允许管理员和经理查看所有用户，普通用户只能查看自己
        if self.request.user.is_authenticated and (self.request.user.is_staff or self.request.user.is_superuser):
            queryset = CustomUser.objects.all().order_by('username')
            position = self.request.query_params.get('personnel__position', None)

            if position:
                queryset = queryset.filter(personnel__position_id=position)
            
            return queryset
        return CustomUser.objects.filter(id=self.request.user.id)

from personnel.models import Position

class PositionListView(generics.ListAPIView):
    queryset = Position.objects.all()
    serializer_class = PositionSerializer
    permission_classes = [permissions.IsAuthenticated]




class PositionViewSet(viewsets.ModelViewSet):
    queryset = Position.objects.all()
    serializer_class = PositionSerializer
    permission_classes = [IsAdminOrManager] # 只有管理员和经理可以管理职位
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['name']
