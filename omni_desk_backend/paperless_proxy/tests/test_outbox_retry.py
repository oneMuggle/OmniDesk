"""P0-H Outbox 死信重试/丢弃管理端点测试

- POST /api/paperless/outbox/<pk>/retry/:dead → pending(清空错误与重试计数)
- DELETE /api/paperless/outbox/<pk>/discard/:删除
- 非 dead 拒绝重试;非管理员 403
"""
import pytest
from rest_framework.test import APIClient

from paperless_proxy.models import OutboxItem
from users.models import CustomUser


@pytest.fixture
def staff_admin(db):
    return CustomUser.objects.create_user(username="outbox_admin", password="pass12345", is_staff=True)


@pytest.fixture
def plain_user(db):
    return CustomUser.objects.create_user(username="outbox_plain", password="pass12345")


def _make_dead_item(created_by):
    return OutboxItem.objects.create(
        operation="upload",
        status="dead",
        created_by=created_by,
        last_error="boom",
        retry_count=10,
        payload={"file_path": "/tmp/x.pdf", "filename": "x.pdf"},
    )


@pytest.mark.django_db
class TestOutboxRetryView:
    def test_retry_dead_outbox(self, staff_admin):
        item = _make_dead_item(staff_admin)
        client = APIClient()
        client.force_authenticate(user=staff_admin)

        resp = client.post(f"/api/paperless/outbox/{item.id}/retry/")
        assert resp.status_code == 200
        item.refresh_from_db()
        assert item.status == "pending"
        assert item.last_error == ""
        assert item.retry_count == 0

    def test_retry_non_dead_rejected(self, staff_admin):
        item = _make_dead_item(staff_admin)
        item.status = "pending"
        item.save(update_fields=["status"])
        client = APIClient()
        client.force_authenticate(user=staff_admin)

        resp = client.post(f"/api/paperless/outbox/{item.id}/retry/")
        assert resp.status_code == 400
        item.refresh_from_db()
        assert item.status == "pending"

    def test_retry_requires_admin(self, staff_admin, plain_user):
        item = _make_dead_item(staff_admin)
        client = APIClient()
        client.force_authenticate(user=plain_user)

        resp = client.post(f"/api/paperless/outbox/{item.id}/retry/")
        assert resp.status_code == 403
        item.refresh_from_db()
        assert item.status == "dead"

    def test_retry_missing_returns_404(self, staff_admin):
        client = APIClient()
        client.force_authenticate(user=staff_admin)
        assert client.post("/api/paperless/outbox/999999/retry/").status_code == 404


@pytest.mark.django_db
class TestOutboxDiscardView:
    def test_discard_outbox(self, staff_admin):
        item = _make_dead_item(staff_admin)
        client = APIClient()
        client.force_authenticate(user=staff_admin)

        resp = client.delete(f"/api/paperless/outbox/{item.id}/discard/")
        assert resp.status_code == 204
        assert not OutboxItem.objects.filter(id=item.id).exists()

    def test_discard_requires_admin(self, staff_admin, plain_user):
        item = _make_dead_item(staff_admin)
        client = APIClient()
        client.force_authenticate(user=plain_user)

        resp = client.delete(f"/api/paperless/outbox/{item.id}/discard/")
        assert resp.status_code == 403
        assert OutboxItem.objects.filter(id=item.id).exists()
