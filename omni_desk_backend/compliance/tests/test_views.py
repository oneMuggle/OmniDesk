"""Compliance ViewSet tests for paperless upload action.

Adapts brief for ComplianceIssue model:
- Issue has no `reporter` field; permission is driven by `issue.project.manager`.
- Compliance URL prefix is `compliance/` (no `issues/` segment).
"""
import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from compliance.models import ComplianceIssue
from projects.models import Project

CustomUser = get_user_model()


@pytest.fixture
def issue(db):
    """创建合规问题:项目经理 user 拥有该问题。

    ComplianceIssue 的"所有者"语义对应 issue.project.manager (无 reporter 字段)。
    """
    manager = CustomUser.objects.create_user(username='owner', password='p')
    project = Project.objects.create(name='合规测试项目', manager=manager)
    return ComplianceIssue.objects.create(
        project=project,
        issue_type='不规范',
        description='d',
        severity='中',
        status='待处理',
    )


@pytest.mark.django_db
class TestComplianceUpload:
    def test_owner_can_upload(self, issue, monkeypatch):
        from paperless_proxy.services.upload import PaperlessUploadService
        monkeypatch.setattr(
            PaperlessUploadService, 'queue_upload',
            staticmethod(lambda **kw: {'binding_id': 1, 'outbox_id': 1, 'status': 'pending'}),
        )
        owner = issue.project.manager
        client = APIClient()
        client.force_authenticate(owner)
        f = SimpleUploadedFile('r.pdf', b'x', content_type='application/pdf')
        resp = client.post(
            f'/api/compliance/{issue.id}/upload/',
            {'file': f, 'title': 'report'},
            format='multipart',
        )
        assert resp.status_code == 201

    def test_non_owner_non_admin_forbidden(self, issue):
        """非项目负责人非 admin 调用 upload:ComplianceIssueViewSet.get_queryset() 已
        按 'visible to user' 过滤,非授权用户对该 issue 拿到 404(资源隐藏),
        这与 projects 模块的权限语义一致。
        """
        other = CustomUser.objects.create_user(username='other', password='p')
        client = APIClient()
        client.force_authenticate(other)
        f = SimpleUploadedFile('r.pdf', b'x', content_type='application/pdf')
        resp = client.post(
            f'/api/compliance/{issue.id}/upload/',
            {'file': f, 'title': 'report'},
            format='multipart',
        )
        assert resp.status_code == 404

    def test_admin_can_upload(self, issue, monkeypatch):
        from paperless_proxy.services.upload import PaperlessUploadService
        monkeypatch.setattr(
            PaperlessUploadService, 'queue_upload',
            staticmethod(lambda **kw: {'binding_id': 1, 'outbox_id': 1, 'status': 'pending'}),
        )
        admin = CustomUser.objects.create_superuser(username='adm', password='a', email='a@a')
        client = APIClient()
        client.force_authenticate(admin)
        f = SimpleUploadedFile('r.pdf', b'x', content_type='application/pdf')
        resp = client.post(
            f'/api/compliance/{issue.id}/upload/',
            {'file': f, 'title': 'report'},
            format='multipart',
        )
        assert resp.status_code == 201
