from rest_framework import generics, permissions, status, exceptions
from .permissions import IsAdminOrManager, IsAdmin # 导入 IsAdmin
from rest_framework.views import APIView
from rest_framework.authtoken.models import Token
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import authenticate
from .serializers import (
    UserRegistrationSerializer,
    UserLoginSerializer,
    UserDetailSerializer,
    CustomTokenObtainPairSerializer,
    PersonnelSerializer,
    UserAdminSerializer # 导入 UserAdminSerializer
)


class LoginView(APIView):
    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        
        user = authenticate(username=username, password=password)
        if user:
            token, _ = Token.objects.get_or_create(user=user)
            return Response({'token': token.key})
        return Response({'error': 'Invalid Credentials'}, status=status.HTTP_401_UNAUTHORIZED)

from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView
from .models import CustomUser
from .serializers import (
    UserRegistrationSerializer,
    UserLoginSerializer,
    UserDetailSerializer,
    CustomTokenObtainPairSerializer,
    PersonnelSerializer
)

class UserRegistrationView(generics.CreateAPIView):
    serializer_class = UserRegistrationSerializer
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            user = serializer.save()
            
            return Response({
                "success": True,
                "message": "注册成功，请登录",
                "username": user.username
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

class UserLoginView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
            user = serializer.user
            print(f"User role in UserLoginView: {user.role}") # <-- 新增日志
            token = serializer.validated_data
            
            response_data = {
                "success": True,
                "user": UserDetailSerializer(user).data,
                "access": token['access'],
                "refresh": token['refresh'],
                "redirect_to": "/home",
                "permissions": token['permissions'] # Get permissions from the token
            }
            print(f"Login Response Data: {response_data}") # <-- 新增日志
            return Response(response_data)
        except exceptions.ValidationError as e:
            return Response({
                "success": False,
                "error": "invalid_credentials",
                "message": "用户名或密码错误"
            }, status=status.HTTP_401_UNAUTHORIZED)

class PersonnelListCreateView(generics.ListCreateAPIView):
    queryset = CustomUser.objects.all()
    serializer_class = PersonnelSerializer
    
    permission_classes = [IsAdminOrManager]

class PersonnelRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = CustomUser.objects.all()
    serializer_class = PersonnelSerializer
    
    permission_classes = [IsAdminOrManager]
    lookup_field = 'id'

class UserAdminListView(generics.ListAPIView):
    queryset = CustomUser.objects.all().order_by('id') # 按照id排序
    serializer_class = UserAdminSerializer
    permission_classes = [IsAdmin] # 只有管理员可以访问

class UserAdminDetailView(generics.RetrieveUpdateAPIView):
    queryset = CustomUser.objects.all()
    serializer_class = UserAdminSerializer
    permission_classes = [IsAdmin] # 只有管理员可以访问
    lookup_field = 'id'
