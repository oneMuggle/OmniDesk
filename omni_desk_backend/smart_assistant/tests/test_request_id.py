"""Verify request_id flows through smart_assistant logs."""
import logging

import pytest

from observability.context import request_id_var


@pytest.fixture
def caplog_smart(caplog):
    caplog.set_level(logging.DEBUG, logger="smart_assistant")
    return caplog


def test_request_id_propagates_to_smart_assistant_logs(caplog_smart):
    token = request_id_var.set("smoke-001")
    try:
        from smart_assistant.agents.executor import logger as exec_logger

        exec_logger.info("hello", extra={"event": "smart_assistant.executor.test"})
        records = [
            r for r in caplog_smart.records if r.name.startswith("smart_assistant")
        ]
        assert records
        assert all(getattr(r, "request_id", None) == "smoke-001" for r in records)
    finally:
        request_id_var.reset(token)
