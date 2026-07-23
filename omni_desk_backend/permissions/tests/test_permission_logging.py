"""权限校验失败结构化日志测试。

对应 PR-2 Task 2.5:验证 IsAdminOrReadOnly 等 permission class
拒绝访问时是否发出 permission.denied 事件。

不使用 tests/factories.py(PR-1 已删除),改用 conftest.py 的
regular_user_obj fixture(以及 admin_user_obj)。
"""
import logging

import pytest


@pytest.mark.django_db
class TestPermissionDeniedLogging:
    def test_regular_user_denied_on_write_emits_event(
        self, api_client, regular_user_obj, caplog
    ):
        """普通用户写 IsAdminOrReadOnly 资源应被拒绝,并发 permission.denied 事件。

        用 GroupViewSet 的 POST 触发(IsAdminOrReadOnly 在 POST 时要求 Admin)。
        """
        api_client.force_authenticate(user=regular_user_obj)
        with caplog.at_level(logging.WARNING):
            response = api_client.post(
                "/api/permissions/groups/",
                {"name": "DeniedGroup"},
                format="json",
            )
        assert response.status_code == 403
        events = [getattr(r, "event", None) for r in caplog.records]
        assert "permission.denied" in events

        denied_record = next(
            (r for r in caplog.records if getattr(r, "event", None) == "permission.denied"),
            None,
        )
        assert denied_record is not None
        # 字段核对:user_id / resource / action
        assert getattr(denied_record, "user_id", None) == regular_user_obj.id
        assert getattr(denied_record, "resource", None) == "GroupViewSet"
        assert getattr(denied_record, "action", None) == "POST"

    def test_admin_user_allowed_does_not_emit_denial(
        self, api_client, admin_user_obj, caplog
    ):
        """管理员允许访问时不应发 permission.denied 事件。"""
        api_client.force_authenticate(user=admin_user_obj)
        with caplog.at_level(logging.WARNING):
            response = api_client.get("/api/permissions/groups/")
        assert response.status_code == 200
        events = [getattr(r, "event", None) for r in caplog.records]
        assert "permission.denied" not in events

    def test_regular_user_read_gets_no_denial(
        self, api_client, regular_user_obj, caplog
    ):
        """IsAdminOrReadOnly 的 SAFE_METHOD(GET)对普通用户放行,不应发 permission.denied。

        GroupViewSet GET 不需要 Admin(只 POST/PUT/DELETE 需要)。
        """
        api_client.force_authenticate(user=regular_user_obj)
        with caplog.at_level(logging.WARNING):
            response = api_client.get("/api/permissions/groups/")
        assert response.status_code == 200
        events = [getattr(r, "event", None) for r in caplog.records]
        assert "permission.denied" not in events
