from django.urls import path
from .views import (
    UserRegistrationView,
    UserLoginView,
    UserDetailView,
    CustomTokenObtainPairView,
    PersonnelListCreateView,
    PersonnelRetrieveUpdateDestroyView
)

urlpatterns = [
    path('registration/', UserRegistrationView.as_view(), name='registration'),
    path('login/', UserLoginView.as_view(), name='login'),
    path('login/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('profile/', UserDetailView.as_view(), name='user-profile'),
    # 人员管理接口
    path('', PersonnelListCreateView.as_view(), name='personnel-list'),
    path('<int:id>/', PersonnelRetrieveUpdateDestroyView.as_view(), name='personnel-detail'),
]
