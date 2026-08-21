"""R5-A4: permissions 敏感写操作审计留痕测试。

GroupViewSet 的 create/update/destroy 与 GroupPermissionView.put
应写入 AuditLogEntry(category=group_change / permission_change)。
"""
import pytest

from users.models import AuditLogEntry

pytestmark = [pytest.mark.django_db]


class TestGroupAudit:
    def test_group_create_writes_audit(self, admin_client):
        response = admin_client.post(
            "/api/permissions/groups/", {"name": "AuditGroup"}, format="json"
        )
        assert response.status_code == 201
        entry = AuditLogEntry.objects.filter(category="group_change").latest("id")
        assert entry.action == "create"
        assert "AuditGroup" in str(entry.metadata)

    def test_group_update_writes_audit(self, admin_client):
        group = admin_client.post(
            "/api/permissions/groups/", {"name": "OldName"}, format="json"
        ).data
        response = admin_client.patch(
            f"/api/permissions/groups/{group['id']}/", {"name": "NewName"}, format="json"
        )
        assert response.status_code == 200
        entry = AuditLogEntry.objects.filter(
            category="group_change", action="update"
        ).latest("id")
        assert entry.metadata["before"]["name"] == "OldName"
        assert entry.metadata["after"]["name"] == "NewName"

    def test_group_delete_writes_audit(self, admin_client):
        group = admin_client.post(
            "/api/permissions/groups/", {"name": "Doomed"}, format="json"
        ).data
        response = admin_client.delete(f"/api/permissions/groups/{group['id']}/")
        assert response.status_code == 204
        entry = AuditLogEntry.objects.filter(
            category="group_change", action="delete"
        ).latest("id")
        assert entry.metadata["name"] == "Doomed"


class TestGroupPermissionAudit:
    def test_put_permissions_writes_audit(self, admin_client):
        from django.contrib.auth.models import Group, Permission

        group = Group.objects.create(name="PermTarget")
        perm = Permission.objects.first()
        response = admin_client.put(
            f"/api/permissions/groups/{group.id}/permissions/",
            {"permissions": [perm.id]},
            format="json",
        )
        assert response.status_code == 204
        entry = AuditLogEntry.objects.filter(category="permission_change").latest("id")
        assert entry.action == "set"
        assert entry.metadata["group_id"] == group.id
        assert entry.metadata["permission_ids"] == [perm.id]
