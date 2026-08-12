import re
import pytest
from django.test import RequestFactory
from core.middleware import RequestIdMiddleware


@pytest.fixture
def mw():
    return RequestIdMiddleware(get_response=lambda r: _echo(r))


def _echo(request):
    from django.http import HttpResponse
    resp = HttpResponse("ok")
    resp.request_id_echo = request.request_id  # type: ignore[attr-defined]
    return resp


def test_request_id_from_header(mw):
    rf = RequestFactory()
    req = rf.get("/any/path/", HTTP_X_REQUEST_ID="deadbeef")
    resp = mw(req)
    assert resp["X-Request-ID"] == "deadbeef"
    assert resp.request_id_echo == "deadbeef"


def test_request_id_generated_when_missing(mw):
    rf = RequestFactory()
    req = rf.get("/any/path/")
    resp = mw(req)
    assert re.match(r"^[0-9a-f]{32}$", resp["X-Request-ID"])
    assert resp.request_id_echo == resp["X-Request-ID"]


def test_request_id_unique_per_request(mw):
    rf = RequestFactory()
    r1 = mw(rf.get("/"))
    r2 = mw(rf.get("/"))
    assert r1["X-Request-ID"] != r2["X-Request-ID"]
