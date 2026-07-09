# omni_desk_backend/paperless_proxy/services/search.py
"""paperless 搜索结果标准化"""
from .client import PaperlessClient


class PaperlessSearchService:
    @staticmethod
    def search(query: str, page: int = 1, page_size: int = 20) -> list:
        client = PaperlessClient()
        data = client.search(query, page=page, page_size=page_size)
        results = []
        for item in data.get('results', []):
            hit = item.get('__search_hit__', {})
            results.append({
                'source': 'paperless',
                'id': item.get('id'),
                'title': item.get('title', ''),
                'correspondent': item.get('correspondent'),
                'tags': item.get('tags', []),
                'created': item.get('created'),
                'score': hit.get('score', 0),
                'highlight': hit.get('highlights', ''),
                'url': f"/api/paperless/documents/{item.get('id')}/",
                'open_in_paperless_url': f"/paperless/documents/{item.get('id')}/details",
            })
        return results
