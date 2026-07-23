"""observability 模块测试。"""
import logging
import pytest

from observability import get_logger
from observability.events import AuthEvent, PermissionEvent, CeleryEvent


def test_get_logger_returns_adapter():
    """get_logger 返回 LoggerAdapter。"""
    logger = get_logger("test.module")
    assert isinstance(logger, logging.LoggerAdapter)


def test_event_field_auto_added_when_missing(caplog):
    """未传 event 字段时,自动填 'unspecified'。"""
    logger = get_logger("test.module")
    with caplog.at_level(logging.INFO):
        logger.info("hello world")
    assert len(caplog.records) == 1
    assert caplog.records[0].event == "unspecified"


def test_event_field_preserved_when_provided(caplog):
    """传了 event 字段,保持原值。"""
    logger = get_logger("test.module")
    with caplog.at_level(logging.INFO):
        logger.info("hello", extra={"event": "custom.event", "user_id": 42})
    assert caplog.records[0].event == "custom.event"
    assert caplog.records[0].user_id == 42


def test_event_constants_unique():
    """事件常量不重复。"""
    all_events = [
        AuthEvent.LOGIN_SUCCESS,
        AuthEvent.LOGIN_FAILURE,
        AuthEvent.LOGOUT,
        AuthEvent.JWT_REFRESH_SUCCESS,
        AuthEvent.JWT_REFRESH_FAILURE,
        PermissionEvent.PERMISSION_DENIED,
        CeleryEvent.TASK_START,
        CeleryEvent.TASK_SUCCESS,
        CeleryEvent.TASK_FAILURE,
        CeleryEvent.TASK_RETRY,
    ]
    assert len(all_events) == len(set(all_events))
