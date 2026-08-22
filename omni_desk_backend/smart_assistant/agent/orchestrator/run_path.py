"""运行路径决策(R5-D5 拆分:orchestrator/run_path.py)。

从 orchestrator.py 原样搬运的「use_native_tool_calls 决策 + endpoint 能力检查」逻辑,
行为零变化。
"""

from django.conf import settings

from observability import get_logger

from ...models import LlmAppConfig


logger = get_logger(__name__, "smart_assistant")


class RunPathResolver:
    """process/stream 共用的路径决策逻辑容器。

    行为零变化:所有判定与原 orchestrator.py 内联实现逐字等价。
    """

    @staticmethod
    def resolve_native_decision(
        *,
        use_native_tool_calls,
        tool_context,
        endpoint_supports_tool_calls_fn,
    ) -> bool:
        """原 process() 内联的 use_native 判定段(含 L1 staff 门控)。

        返回最终 ``use_native`` 布尔值。
        """
        if use_native_tool_calls is None:
            try:
                # L1 灰度(Task 12):默认仅 is_staff=True 用户启用原生 tool_calls
                # 路径;settings.USE_NATIVE_TOOL_CALLS_FOR_ALL=True 时全员开放。
                # 无用户上下文(内部调用)按非 staff 处理,降级到 JSON 路径更保守。
                user_is_staff = bool(
                    tool_context is not None
                    and getattr(tool_context, "user", None) is not None
                    and bool(getattr(tool_context.user, "is_staff", False))
                )
                return (
                    bool(getattr(settings, "USE_NATIVE_TOOL_CALLS", False))
                    and endpoint_supports_tool_calls_fn()
                    and (user_is_staff or bool(getattr(settings, "USE_NATIVE_TOOL_CALLS_FOR_ALL", False)))
                )
            except Exception:
                logger.warning("_endpoint_supports_tool_calls 检查失败,降级到 JSON 路径", exc_info=True)
                return False
        return bool(use_native_tool_calls)

    @staticmethod
    def endpoint_supports_tool_calls() -> bool:
        """检查当前激活的 LlmEndpoint 是否声明支持 native_tool_calls。

        读 ``LlmEndpoint.model_capabilities``(JSONField,默认为 list)。
        契约:若 model_capabilities 是 ``list[dict]``,且任一元素包含
        ``native_tool_calls=True``,则返回 ``True``。

        安全降级:无激活 endpoint / capabilities 为空 / 数据异常 → 返回
        ``False``,orchestrator 自动降级到 JSON 路径,避免老端点被错配。
        """
        try:
            config = (
                LlmAppConfig.objects.select_related("endpoint")
                .filter(is_active=True, app_name="smart_assistant", endpoint__is_active=True)
                .order_by("endpoint__priority", "endpoint__is_fallback")
                .first()
            )
        except Exception:
            logger.warning("查询 LlmAppConfig 失败,降级 JSON 路径", exc_info=True)
            return False

        if config is None:
            return False

        caps = getattr(config.endpoint, "model_capabilities", None)
        if not isinstance(caps, list):
            return False
        for cap in caps:
            if isinstance(cap, dict) and cap.get("native_tool_calls") is True:
                return True
        return False
