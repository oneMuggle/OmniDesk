import pytest
from django.apps import apps
from django.conf import settings


@pytest.mark.django_db
class TestPaperlessProxyApp:
    def test_app_is_registered(self):
        """验证:paperless_proxy 在 INSTALLED_APPS 中"""
        assert 'paperless_proxy' in settings.INSTALLED_APPS

    def test_app_config_class(self):
        """验证:AppConfig 正确加载"""
        config = apps.get_app_config('paperless_proxy')
        assert config.name == 'paperless_proxy'
        assert config.verbose_name == 'paperless 代理'
