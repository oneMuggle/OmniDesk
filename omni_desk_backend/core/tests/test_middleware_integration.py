# omni_desk_backend/core/tests/test_middleware_integration.py
import re
from django.http import HttpResponse
from django.test import Client
from django.urls import path


def view_echo(request):
    return HttpResponse(f"rid={request.request_id}")  # type: ignore[attr-defined]


urlpatterns = [path("__test_echo__/", view_echo)]


def test_middleware_is_first_in_chain(settings):
    # 测试模块自带 urlpatterns,必须显式让 Client 使用,否则 /__test_echo__/ 恒 404
    settings.ROOT_URLCONF = "core.tests.test_middleware_integration"
    client = Client()
    resp = client.get("/__test_echo__/", HTTP_X_REQUEST_ID="integration-1")
    assert resp.status_code == 200
    assert b"rid=integration-1" in resp.content
    assert resp["X-Request-ID"] == "integration-1"


def test_middleware_generates_uuid_when_no_header(settings):
    settings.ROOT_URLCONF = "core.tests.test_middleware_integration"
    client = Client()
    resp = client.get("/__test_echo__/")
    assert re.match(rb"rid=[0-9a-f]{32}", resp.content)
    assert re.match(r"^[0-9a-f]{32}$", resp["X-Request-ID"])
