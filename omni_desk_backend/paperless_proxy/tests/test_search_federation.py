# omni_desk_backend/paperless_proxy/tests/test_search_federation.py
import pytest
from unittest.mock import patch
from ..services.search import PaperlessSearchService


class TestPaperlessSearchService:
    @patch('paperless_proxy.services.client.PaperlessClient.search')
    def test_search_normalizes_results(self, mock_search):
        """验证:返回统一格式的结果列表"""
        mock_search.return_value = {
            'count': 1,
            'results': [{
                'id': 50,
                'title': '合同文件',
                'correspondent': 3,
                'tags': [1, 2],
                'created': '2026-01-01',
                '__search_hit__': {
                    'score': 0.9,
                    'highlights': '这是<span class="match">合同</span>',
                    'rank': 0,
                },
            }],
        }
        results = PaperlessSearchService.search('合同')
        assert len(results) == 1
        assert results[0]['source'] == 'paperless'
        assert results[0]['id'] == 50
        assert '<span' in results[0]['highlight']
        assert results[0]['score'] == 0.9
        assert results[0]['url'] == '/api/paperless/documents/50/'
