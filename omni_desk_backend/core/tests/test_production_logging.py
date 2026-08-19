import importlib
import json
import logging
import os
from unittest.mock import patch

from pythonjsonlogger.jsonlogger import JsonFormatter

# production.py 顶层有 SECRET_KEY / POSTGRES_DB / MINERU_API_KEY 强检查,
# 需临时注入 env 才能 import 该模块读取其 LOGGING 配置
_PROD_ENV = {
    "SECRET_KEY": "test-secret",
    "POSTGRES_DB": "test-db",
    "POSTGRES_USER": "test-user",
    "POSTGRES_PASSWORD": "test-pass",
    "DB_HOST": "localhost",
    "MINERU_API_KEY": "test-mineru-key",
    "DJANGO_ALLOWED_HOSTS": "localhost",
}


def _load_production():
    with patch.dict(os.environ, _PROD_ENV):
        return importlib.import_module("omni_desk_backend.settings.production")


def test_production_json_format_declares_request_id_and_event():
    """format 串必须声明 request_id/event 字段(RED 驱动)"""
    fmt = _load_production().LOGGING["formatters"]["json"]["format"]
    assert "%(request_id)s" in fmt
    assert "%(event)s" in fmt


def test_json_formatter_output_includes_request_id_and_event():
    """用真实 JsonFormatter 格式化带 extra 的 record,断言 JSON 输出含两字段。

    防吞字段回归:rename_fields 若含 key==value(如 "request_id":"request_id")
    会移除该字段,本测试能抓住这种配置错误。
    """
    json_cfg = _load_production().LOGGING["formatters"]["json"]
    formatter = JsonFormatter(fmt=json_cfg["format"], rename_fields=json_cfg.get("rename_fields", {}))
    record = logging.LogRecord(
        name="test.prod.format", level=logging.INFO,
        pathname=__file__, lineno=1, msg="hello", args=(), exc_info=None,
    )
    record.request_id = "trace-abc"
    record.event = "test.event"
    data = json.loads(formatter.format(record))
    assert data["request_id"] == "trace-abc"
    assert data["event"] == "test.event"
