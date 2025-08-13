from django.urls import path
from . import views
from .views import CurrentUserView

urlpatterns = [
    path('me/', CurrentUserView.as_view(), name='user-me'),
    path('login/', views.LoginView.as_view(), name='login'),
]
