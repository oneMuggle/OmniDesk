import os
from urllib.parse import unquote

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from smart_assistant.tools_io import create_download_token, save_tmp_office_file


@pytest.fixture(autouse=True)
def _media_root(tmp_path):
    old = settings.MEDIA_ROOT
    settings.MEDIA_ROOT = str(tmp_path)
    yield
    settings.MEDIA_ROOT = old


@pytest.fixture
def user(db):
    User = get_user_model()
    return User.objects.create_user(username="dluser", password="x")


@pytest.fixture
def client(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


class TestOfficeDownload:
    def test_valid_token_returns_blob(self, client, user):
        rel = save_tmp_office_file("请假单.docx", b"docx-content")
        token = create_download_token(rel, user_id=user.pk)
        resp = client.get(f"/api/smart-assistant/office-download/{token}/")
        assert resp.status_code == 200
        assert b"docx-content" in b"".join(resp.streaming_content)
        assert unquote(resp["Content-Disposition"]).endswith("请假单.docx")

    def test_reused_token_rejected(self, client, user):
        rel = save_tmp_office_file("测试.docx", b"x")
        token = create_download_token(rel, user_id=user.pk)
        client.get(f"/api/smart-assistant/office-download/{token}/")
        resp2 = client.get(f"/api/smart-assistant/office-download/{token}/")
        assert resp2.status_code == 403

    def test_forged_token_rejected(self, client):
        resp = client.get("/api/smart-assistant/office-download/forged.token/")
        assert resp.status_code == 403

    def test_requires_auth(self):
        c = APIClient()
        resp = c.get("/api/smart-assistant/office-download/anything/")
        assert resp.status_code == 401