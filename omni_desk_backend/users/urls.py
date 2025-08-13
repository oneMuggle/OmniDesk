from django.urls import path
from .views import CurrentUserView

urlpatterns = [
    path('me/', CurrentUserView.as_view(), name='current-user'),  # 完整路径将是 /api/users/me/
]
