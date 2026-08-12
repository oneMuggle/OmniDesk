"""_EventLoggerAdapter 自动注入 request_id / event 的测试。"""
import logging

from observability import get_logger
from observability.context import request_id_var


def test_adapter_injects_request_id_into_record(caplog):
    logger = get_logger("test.module", "test.event")
    caplog.set_level(logging.INFO, logger="test.module")
    token = request_id_var.set("trace-xyz")
    try:
        logger.info("hello")
    finally:
        request_id_var.reset(token)
    record = caplog.records[0]
    assert getattr(record, "request_id", None) == "trace-xyz"
    assert getattr(record, "event", None) == "test.event"


def test_adapter_event_default_when_not_provided(caplog):
    logger = get_logger("test.module2")
    caplog.set_level(logging.INFO, logger="test.module2")
    logger.info("hello")
    record = caplog.records[0]
    assert getattr(record, "event", "?") == "?"


def test_adapter_extra_kwargs_override_default_event(caplog):
    logger = get_logger("test.module3", "default.event")
    caplog.set_level(logging.INFO, logger="test.module3")
    logger.info("hi", extra={"event": "override.event"})
    record = caplog.records[0]
    assert getattr(record, "event") == "override.event"
