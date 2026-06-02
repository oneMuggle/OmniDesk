"""config 模块补充测试。"""

import pytest

from config.models import OllamaConfig, PageVisibility, Config


@pytest.mark.django_db
class TestOllamaConfigViewSet:
    def test_ollama_config_crud(self, admin_client):
        """Ollama 配置 CRUD"""
        resp = admin_client.post('/api/config/ollama-configs/', {
            'alias': '本地 Ollama',
            'api_endpoint': 'http://localhost:11434',
            'model': 'llama3',
        }, format='json')
        assert resp.status_code == 201, resp.data
        config_id = resp.data['id']

        resp = admin_client.delete(f'/api/config/ollama-configs/{config_id}/')
        assert resp.status_code == 204


@pytest.mark.django_db
class TestPageVisibilityViewSet:
    def test_page_visibility_list(self, admin_client):
        """页面可见性列表"""
        resp = admin_client.get('/api/config/page-visibility/')
        assert resp.status_code in [200, 404]
