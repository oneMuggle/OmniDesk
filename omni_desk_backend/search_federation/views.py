# omni_desk_backend/search_federation/views.py
from concurrent.futures import ThreadPoolExecutor
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from paperless_proxy.models import PaperlessHealth
from paperless_proxy.services.search import PaperlessSearchService


def _search_internal(query: str) -> list:
    """OmniDesk 内部业务表搜索(项目/合同/人员/合规/备忘录)"""
    results = []
    try:
        from projects.models import Project
        for p in Project.objects.filter(name__icontains=query)[:5]:
            results.append({
                'source': 'project',
                'id': p.id,
                'title': p.name,
                'highlight': p.name,
                'url': f'/projects/{p.id}/',
                'score': 1.0,
            })
    except Exception:
        pass
    return results


class UnifiedSearchView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        query = request.data.get('query', '').strip()
        if not query:
            return Response({'results': [], 'degraded': False})

        results = []
        degraded = False
        health = PaperlessHealth.get_singleton()

        with ThreadPoolExecutor(max_workers=2) as ex:
            f_internal = ex.submit(_search_internal, query)
            f_paperless = None
            if health.is_healthy:
                f_paperless = ex.submit(PaperlessSearchService.search, query)
            else:
                degraded = True

            try:
                results.extend(f_internal.result(timeout=3))
            except Exception:
                pass
            if f_paperless:
                try:
                    results.extend(f_paperless.result(timeout=3))
                except Exception:
                    degraded = True

        return Response({'results': results, 'degraded': degraded})
