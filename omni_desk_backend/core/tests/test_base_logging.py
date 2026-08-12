import io
import logging
from importlib import import_module

# test.py 用 LOGGING={} 显式关闭日志(避免测试输出噪音),
# settings.LOGGING 拿不到 formatters 配置,需直接读 base 模块的真实 LOGGING。
# base 模块已被 test.py 的 `from .base import *` 导入并缓存,直接 import 是安全的。
_BASE = import_module("omni_desk_backend.settings.base")


def _make_handler():
    """从 base 的真实 LOGGING 配置构建一个 console handler 实例。"""
    log_cfg = _BASE.LOGGING
    formatter_cfg = log_cfg["formatters"]["verbose"]
    formatter = logging.Formatter(
        fmt=formatter_cfg["format"],
        style=formatter_cfg.get("style", "%"),
    )
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(formatter)
    return handler, stream


def test_text_formatter_declares_request_id_and_event():
    """format 串必须声明 request_id/event 字段(RED 驱动)"""
    fmt = _BASE.LOGGING["formatters"]["verbose"]["format"]
    assert "{request_id}" in fmt
    assert "{event}" in fmt


def test_text_formatter_includes_request_id_and_event():
    """用真实 formatter 格式化带 extra 的 record,断言输出含 req=/evt="""
    handler, stream = _make_handler()
    logger = logging.getLogger("test.base.format")
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    try:
        logger.info("hello", extra={"request_id": "trace-xyz", "event": "test.event"})
    finally:
        logger.removeHandler(handler)
    output = stream.getvalue()
    assert "req=trace-xyz" in output
    assert "evt=test.event" in output
