"""AI 抽屉上下文接口（S2）：当前页面的记录标签 + 快捷问题。"""

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..capabilities import capabilities
from ..capabilities.page_context import normalize_route, public_page_context, resolve_page_context

FORMAT_VERSION = 1


class AssistantContextView(APIView):
    """``GET /api/smart-assistant/assistant-context/?route=/communication/12``

    - ``page_context``：只含记录类型与记录名（让用户知道这条上下文会被带上），
      不返回字段；记录不可见 / 路由未匹配时为 ``null``。
    - ``quick_prompts``：匹配该路由、且用户至少能调用所属工具集中一个工具的快捷问题。

    ``route`` 不合法时按空路由处理（返回空列表），不报 400。
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        route = normalize_route(request.query_params.get("route", ""))
        page_context = public_page_context(resolve_page_context(route, request.user)) if route else None
        quick_prompts = capabilities.quick_prompts_for(route, request.user) if route else []
        return Response(
            {
                "format_version": FORMAT_VERSION,
                "route": route,
                "page_context": page_context,
                "quick_prompts": quick_prompts,
            }
        )
