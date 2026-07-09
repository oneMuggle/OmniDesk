# omni_desk_backend/search_federation/tests/test_views.py
import pytest
from unittest.mock import patch
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from paperless_proxy.models import PaperlessHealth

CustomUser = get_user_model()


@pytest.fixture
def user(db):
    return CustomUser.objects.create_user(username='u', password='p')


@pytest.mark.django_db
class TestUnifiedSearch:
    @patch('paperless_proxy.services.search.PaperlessSearchService.search')
    def test_unified_search_merges_sources(self, mock_search, user):
        PaperlessHealth.objects.create(is_healthy=True)
        mock_search.return_value = [
            {'source': 'paperless', 'id': 50, 'title': '合同', 'highlight': '...', 'url': '/p/50/'}
        ]
        client = APIClient()
        client.force_authenticate(user)
        resp = client.post('/api/search/unified/', {'query': '合同'}, format='json')
        assert resp.status_code == 200
        sources = [r['source'] for r in resp.data['results']]
        assert 'paperless' in sources

    @patch('paperless_proxy.services.search.PaperlessSearchService.search')
    def test_skips_paperless_when_unhealthy(self, mock_search, user):
        PaperlessHealth.objects.create(is_healthy=False)
        client = APIClient()
        client.force_authenticate(user)
        resp = client.post('/api/search/unified/', {'query': 'x'}, format='json')
        assert resp.status_code == 200
        mock_search.assert_not_called()
        assert resp.data.get('degraded') is True
