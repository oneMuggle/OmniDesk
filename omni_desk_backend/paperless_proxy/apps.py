# omni_desk_backend/paperless_proxy/apps.py
from django.apps import AppConfig


class PaperlessProxyConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "paperless_proxy"
    verbose_name = "paperless 代理"
