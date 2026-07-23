"""Personnel ViewSet tests for paperless upload action.

Adapts brief for Personnel model:
- Personnel has `id_card_number` (not `id_card`); no `employee_id` / `created_by` fields.
- Personnel URL prefix is `personnel/` (singular, no extra segment).
"""
import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from personnel.models import Personnel

CustomUser = get_user_model()


@pytest.fixture
def personnel(db):
    """创建人员记录:Personnel 模型无 employee_id / created_by 字段,
    与 brief 中假设的字段名不同,故仅使用实际模型字段。"""
    return Personnel.objects.create(
        name='Test Person',
        id_card_number='110101199001011234',
    )


@pytest.mark.django_db
class TestPersonnelUpload:
    def test_admin_can_upload(self, personnel, monkeypatch):
        from paperless_proxy.services.upload import PaperlessUploadService
        monkeypatch.setattr(
            PaperlessUploadService, 'queue_upload',
            staticmethod(lambda **kw: {'binding_id': 1, 'outbox_id': 1, 'status': 'pending'}),
        )
        admin = CustomUser.objects.create_superuser(username='adm2', password='a', email='a2@a')
        client = APIClient()
        client.force_authenticate(admin)
        f = SimpleUploadedFile('p.pdf', b'x', content_type='application/pdf')
        resp = client.post(
            f'/api/personnel/personnel/{personnel.id}/upload/',
            {'file': f, 'title': '档案'},
            format='multipart',
        )
        assert resp.status_code == 201

    def test_unauthenticated_forbidden(self, personnel):
        client = APIClient()
        f = SimpleUploadedFile('p.pdf', b'x', content_type='application/pdf')
        resp = client.post(
            f'/api/personnel/personnel/{personnel.id}/upload/',
            {'file': f, 'title': '档案'},
            format='multipart',
        )
        assert resp.status_code in (401, 403)
