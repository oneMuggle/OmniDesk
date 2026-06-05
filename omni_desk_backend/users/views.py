from django.contrib.auth import login as django_login
from django.db import IntegrityError
from django.http import HttpResponseRedirect
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django_ratelimit.decorators import ratelimit
from rest_framework import exceptions, generics, permissions, status, viewsets
from rest_framework.decorators import api_view
from rest_framework.filters import SearchFilter
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken
from rest_framework_simplejwt.views import TokenObtainPairView

from personnel.models import Personnel

from .models import CustomUser
from .permissions import IsAdmin, IsAdminOrManager
from .serializers import (
    ChangePasswordSerializer,
    CustomTokenObtainPairSerializer,
    GuestLoginSerializer,
    UserAdminSerializer,
    UserDetailSerializer,
    UserPersonnelSerializer,
    UserRegistrationSerializer,
)

RATELIMIT_CONFIG = {
    "group": "auth",
    "key": "ip",
    "rate": "5/15m",
    "method": "POST",
    "block": False,
}


class UserRegistrationView(generics.CreateAPIView):
    serializer_class = UserRegistrationSerializer
    permission_classes = [permissions.AllowAny]

    @method_decorator(ratelimit(**RATELIMIT_CONFIG))
    def dispatch(self, request, *args, **kwargs):
        if getattr(request, "limited", False):
            return Response(
                {"success": False, "error": "rate_limit", "message": "请求过于频繁，请稍后再试"},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        return super().dispatch(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            user = serializer.save()

            return Response(
                {
                    "success": True,
                    "message": "注册成功，请登录",
                    "username": user.username,
                    "user": UserDetailSerializer(user).data,
                },
                status=status.HTTP_201_CREATED,
            )
        except exceptions.APIException as e:
            error_key = list(e.detail.keys())[0] if isinstance(e.detail, dict) else "validation_error"
            return Response(
                {"success": False, "error": error_key, "message": "注册验证失败", "validation_errors": e.detail},
                status=e.status_code,
            )
        except IntegrityError:
            import traceback

            traceback.print_exc()
            error_data = {
                "success": False,
                "error": "username_exists",
                "detail": "用户名已被使用",
                "validation_errors": serializer.errors if "serializer" in locals() else {},
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

    @method_decorator(ratelimit(**RATELIMIT_CONFIG))
    def dispatch(self, request, *args, **kwargs):
        if getattr(request, "limited", False):
            return Response(
                {"success": False, "error": "rate_limit", "message": "请求过于频繁，请稍后再试"},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        return super().dispatch(request, *args, **kwargs)


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
    queryset = (
        CustomUser.objects.select_related("personnel").prefetch_related("phone_numbers").order_by("id")
    )  # 按照id排序
    serializer_class = UserAdminSerializer
    permission_classes = [IsAdmin]  # 只有管理员可以访问


class UserAdminDetailView(generics.RetrieveUpdateAPIView):
    queryset = CustomUser.objects.all()
    serializer_class = UserAdminSerializer
    permission_classes = [IsAdmin]  # 只有管理员可以访问
    lookup_field = "id"

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        personnel_id = request.data.get("personnel_id")

        if personnel_id is not None:
            try:
                personnel = Personnel.objects.get(id=personnel_id)
                instance.personnel = personnel
                instance.real_name = personnel.name
                # Assuming personnel model has a phone_numbers field
                if hasattr(personnel, "phone_numbers") and personnel.phone_numbers.exists():
                    instance.phone_number = personnel.phone_numbers.first().number
                instance.save()
            except Personnel.DoesNotExist:
                return Response({"detail": "Personnel not found."}, status=status.HTTP_404_NOT_FOUND)

        return super().partial_update(request, *args, **kwargs)


class UserPersonnelViewSet(viewsets.ModelViewSet):
    queryset = CustomUser.objects.prefetch_related("phone_numbers").all().order_by("username")
    serializer_class = UserPersonnelSerializer  # 使用 UserPersonnelSerializer
    lookup_field = "id"
    pagination_class = None
    permission_classes = [IsAdminOrManager]  # 确保只有管理员和经理可以访问
    filter_backends = [SearchFilter]
    search_fields = ["real_name", "username"]

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        personnel_id = request.data.get("personnel_id")

        # 如果提供了 personnel_id，则处理关联
        if personnel_id is not None:
            if personnel_id == "":  # 解除关联
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
            queryset = CustomUser.objects.prefetch_related("phone_numbers").order_by("username")
            position = self.request.query_params.get("personnel__position", None)

            if position:
                queryset = queryset.filter(personnel__position_id=position)

            return queryset
        return CustomUser.objects.filter(id=self.request.user.id)


class GuestLoginView(generics.CreateAPIView):
    """游客登录端点：创建临时游客用户并返回 JWT token。"""

    serializer_class = GuestLoginSerializer
    permission_classes = [permissions.AllowAny]

    @method_decorator(ratelimit(**RATELIMIT_CONFIG))
    def dispatch(self, request, *args, **kwargs):
        if getattr(request, "limited", False):
            return Response(
                {"success": False, "error": "rate_limit", "message": "请求过于频繁，请稍后再试"},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        return super().dispatch(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        user = self.perform_create()
        refresh = RefreshToken.for_user(user)
        data = {
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "permissions": [],  # Guest 权限由组配置决定，前端通过 /users/me/ 获取
            "is_guest": True,
        }
        return Response(data, status=status.HTTP_200_OK)

    def perform_create(self):
        serializer = self.get_serializer()
        return serializer.create({})


@csrf_exempt
@api_view(["GET"])
def django_admin_login(request):
    """
    JWT → Session 转换端点。
    接受 token 查询参数，验证 JWT 后建立 Django session，
    然后重定向到 /admin/。

    使用 @csrf_exempt 因为此端点通过 URL 参数认证而非 session。
    """
    from rest_framework_simplejwt.exceptions import TokenError, InvalidToken

    token_str = request.GET.get("token")
    if not token_str:
        return Response({"detail": "缺少 token 参数"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        # 验证 JWT token
        token = AccessToken(token_str)
        user_id = token["user_id"]
        user = CustomUser.objects.get(id=user_id)
    except (TokenError, InvalidToken):
        return Response({"detail": "无效的 token"}, status=status.HTTP_401_UNAUTHORIZED)
    except CustomUser.DoesNotExist:
        return Response({"detail": "用户不存在"}, status=status.HTTP_401_UNAUTHORIZED)

    if not (user.is_staff or user.is_superuser):
        return Response({"detail": "需要管理员权限才能访问 Django 后台"}, status=status.HTTP_403_FORBIDDEN)

    # 建立 Django session
    django_login(request, user, backend="django.contrib.auth.backends.ModelBackend")

    # 获取 CSRF token 供 Django admin 后续使用
    csrf_token = get_token(request)

    # 重定向到 Django admin
    return HttpResponseRedirect("/admin/")


class MyPersonnelView(generics.RetrieveUpdateAPIView):
    """当前登录用户的人员信息自助维护端点。

    P2-3 引入。提供三层防护中的 L1 + L2:
    - L1:`PersonnelSelfSerializer` 字段白名单(可写:date_of_birth/phone_number/address)
    - L2:`perform_update` 服务端白名单再次过滤,即使客户端绕过 L1 也无效
    - 用户无关联 personnel → 404
    - 改字段后发"信息更新"通知(P2-3 简化版:任何 PATCH 成功都发一条)
    """

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = None  # 在 get_serializer_class 中按需选择
    queryset = Personnel.objects.all()  # DRF 要求,实际由 get_object 决定取哪条

    # L2 服务端白名单(必须与 PersonnelSelfSerializer 一致,纵深防御)
    L2_WRITABLE_FIELDS = {"date_of_birth", "phone_number", "address"}

    def get_serializer_class(self):
        from personnel.serializers import PersonnelSelfSerializer
        return PersonnelSelfSerializer

    def get_object(self):
        personnel = getattr(self.request.user, "personnel", None)
        if personnel is None:
            from rest_framework.exceptions import NotFound
            raise NotFound("当前用户尚未关联人员档案,请联系 HR")
        return personnel

    def perform_update(self, serializer):
        # L2 防御:从 validated_data 中剔除不在白名单的字段
        validated_data = serializer.validated_data
        for field in list(validated_data.keys()):
            if field not in self.L2_WRITABLE_FIELDS:
                validated_data.pop(field)
        super().perform_update(serializer)
        # 发"信息更新"通知
        try:
            from notifications.service import NotificationService
            NotificationService.create(
                user=self.request.user,
                type="system",
                title="个人信息已更新",
                content="您刚刚修改了个人信息的部分字段,如非本人操作请尽快联系 HR。",
                link="/me/personnel",
            )
        except Exception:
            # 通知失败不应阻塞主流程
            pass
