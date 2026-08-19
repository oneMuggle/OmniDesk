"""容错 formatter。

dev 文本 formatter 引用 {request_id}/{event},但部分 LogRecord 缺这些字段:
- 未走 observability.get_logger 的直接 logging.getLogger 日志
- 走 adapter 但无请求上下文(管理命令、Celery 无传播时)的日志

裸 logging.Formatter 的 {}-style 对缺字段抛 ValueError,导致整条日志丢失。
SafeTextFormatter 在格式化前给 record 临时补缺键("?"),格式化后恢复,不污染 record。
"""

from __future__ import annotations

import logging

_MISSING_FIELDS = ("request_id", "event")


class SafeTextFormatter(logging.Formatter):
    """缺 request_id/event 字段时补占位符,避免整条日志丢失。"""

    missing = "?"

    def format(self, record: logging.LogRecord) -> str:
        patched: list[str] = []
        for key in _MISSING_FIELDS:
            if not hasattr(record, key):
                setattr(record, key, self.missing)
                patched.append(key)
        try:
            return super().format(record)
        finally:
            for key in patched:
                delattr(record, key)
