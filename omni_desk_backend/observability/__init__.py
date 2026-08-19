"""可观测性工具。

统一 logger 工厂:所有业务代码用 get_logger() 获取 logger,避免直接 logging.getLogger。

用法:
    from observability import get_logger
    logger = get_logger(__name__)
    logger.info("login.success", extra={"user_id": 42, "event": "login_success"})

_adapter 会自动在每条 LogRecord 的 extra 中注入:
- request_id:来自 observability.context.request_id_var(HTTP 请求 / Celery 任务生命周期内有效)
- event:logger 初始化时指定的 event_default(默认 "?")
调用方通过 extra 显式传入的 request_id / event 优先级最高,不会被覆盖。
"""

from __future__ import annotations

import logging

from observability.context import request_id_var


def get_logger(name: str, event_default: str = "?") -> logging.LoggerAdapter:
    """获取统一 logger,自动附加 request_id 与 event 字段。

    Args:
        name: 通常传 __name__,命名空间 omni_desk.<app>.<module>
        event_default: event 字段的默认值;调用方显式传 extra={"event": ...} 时覆盖

    Returns:
        LoggerAdapter 实例,调用 .info/.warning/.error 时自动注入 request_id 与 event。
    """
    base = logging.getLogger(name)
    return _EventLoggerAdapter(base, {"event_default": event_default})


class _EventLoggerAdapter(logging.LoggerAdapter):
    """确保每条日志都包含 event 字段(无则填 event_default,默认 "?"),并注入 request_id。"""

    def process(self, msg, kwargs):
        extra = kwargs.setdefault("extra", {})
        rid = request_id_var.get()
        if rid and "request_id" not in extra:
            extra["request_id"] = rid
        if "event" not in extra:
            extra["event"] = self.extra.get("event_default", "?")
        return msg, kwargs
