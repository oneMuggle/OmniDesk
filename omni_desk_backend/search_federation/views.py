# omni_desk_backend/search_federation/views.py
from observability import get_logger
from concurrent.futures import ThreadPoolExecutor
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from paperless_proxy.models import PaperlessHealth
from paperless_proxy.services.search import PaperlessSearchService
from smart_assistant.tools.tool_context import ToolContext

from .providers import SOURCE_CHOICES, normalize_query, search_internal

logger = get_logger(__name__, "search_federation.views")


class UnifiedSearchView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        query = normalize_query(request.data.get("query", ""))
        if not query:
            return Response({"results": [], "degraded": False})

        sources = request.data.get("sources")
        if isinstance(sources, (list, tuple)):
            sources = [s for s in sources if s in SOURCE_CHOICES] or None
        else:
            sources = None

        degraded = False
        health = PaperlessHealth.get_singleton()

        # Paperless 是外部 HTTP 调用，放进线程池与内部检索并行；
        # 内部检索涉及 ORM，留在请求线程内执行（避免跨线程数据库连接问题）。
        with ThreadPoolExecutor(max_workers=1) as ex:
            f_paperless = None
            if health.is_healthy:
                f_paperless = ex.submit(PaperlessSearchService.search, query)
            else:
                degraded = True

            context = ToolContext.from_request(request)
            results = search_internal(context, query, sources=sources)

            if f_paperless:
                try:
                    results.extend(f_paperless.result(timeout=3))
                except Exception:
                    logger.warning("Paperless search future failed", exc_info=True)
                    degraded = True

        return Response({"results": results, "degraded": degraded})
