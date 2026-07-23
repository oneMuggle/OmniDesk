"""可观测性工具。

统一 logger 工厂:所有业务代码用 get_logger() 获取 logger,避免直接 logging.getLogger。

用法:
    from observability import get_logger
    logger = get_logger(__name__)
    logger.info("login.success", extra={"user_id": 42, "event": "login_success"})
"""

from __future__ import annotations

import logging


def get_logger(name: str, level: int | None = None) -> logging.LoggerAdapter:
    """获取统一 logger,自动附加 event 字段。

    Args:
        name: 通常传 __name__,命名空间 omni_desk.<app>.<module>
        level: 可选覆盖 level

    Returns:
        LoggerAdapter 实例,调用 .info/.warning/.error 时第一参数为 event 字符串。
    """
    base = logging.getLogger(name)
    if level is not None:
        base.setLevel(level)
    return _EventLoggerAdapter(base, {})


class _EventLoggerAdapter(logging.LoggerAdapter):
    """确保每条日志都包含 event 字段(无则填 'unspecified')。"""

    def process(self, msg, kwargs):
        extra = kwargs.get("extra", {})
        if "event" not in extra:
            extra["event"] = "unspecified"
        kwargs["extra"] = extra
        return msg, kwargs
