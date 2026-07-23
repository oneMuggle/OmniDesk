"""登录事件日志测试。

对应 PR-2 Task 2.3:验证登录成功/失败有结构化日志。
"""
import logging

import pytest
from django.urls import reverse
from rest_framework import status


@pytest.mark.django_db
class TestLoginLogging:
    def test_login_success_emits_event(self, api_client, regular_user_obj, caplog):
        """登录成功应发 auth.login.success 事件。"""
        with caplog.at_level(logging.INFO):
            response = api_client.post(
                reverse("users_auth:token_obtain_pair"),
                {"username": "regular_test", "password": "user123"},
                format="json",
            )
        assert response.status_code == status.HTTP_200_OK
        events = [getattr(r, "event", None) for r in caplog.records]
        assert "auth.login.success" in events

        success_record = next(
            (r for r in caplog.records if getattr(r, "event", None) == "auth.login.success"),
            None,
        )
        assert success_record is not None
        assert getattr(success_record, "user_id", None) == regular_user_obj.id

    def test_login_failure_emits_event_with_reason(self, api_client, caplog):
        """登录失败应发 auth.login.failure 事件,含 reason 字段。"""
        with caplog.at_level(logging.WARNING):
            response = api_client.post(
                reverse("users_auth:token_obtain_pair"),
                {"username": "nonexistent", "password": "wrong"},
                format="json",
            )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        events = [getattr(r, "event", None) for r in caplog.records]
        assert "auth.login.failure" in events

        failure_record = next(
            (r for r in caplog.records if getattr(r, "event", None) == "auth.login.failure"),
            None,
        )
        assert failure_record is not None
        assert getattr(failure_record, "reason", None) == "invalid_credentials"
        # 确保密码未被记录
        assert "wrong" not in str(failure_record.__dict__.values())
