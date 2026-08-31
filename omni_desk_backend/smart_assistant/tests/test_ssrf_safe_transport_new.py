import socket
from unittest.mock import patch

import pytest
import requests

from smart_assistant.ssrf import UnsafeEndpointError, validate_endpoint_url, safe_request


def test_rejects_malformed_port_without_leaking_details():
    with pytest.raises(UnsafeEndpointError):
        validate_endpoint_url("http://example.com:bad")


def test_rejects_any_restricted_dns_address(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *args, **kwargs: [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 80)),
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.168.1.4", 80)),
    ])
    with pytest.raises(UnsafeEndpointError):
        validate_endpoint_url("http://rebinding.example")


def test_custom_resolver_cannot_allow_literal_restricted_addresses():
    resolver = lambda *args, **kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 80))]
    for host in ("127.0.0.1", "10.0.0.1", "169.254.169.254", "::1"):
        url = f"http://[{host}]/" if ":" in host else f"http://{host}/"
        with pytest.raises(UnsafeEndpointError):
            validate_endpoint_url(url, resolver=resolver)


    with patch("smart_assistant.ssrf.requests.Session.request") as request:
        request.return_value = requests.Response()
        request.return_value.status_code = 200
        safe_request("GET", "https://example.com")
        assert request.call_args.kwargs["allow_redirects"] is False


def test_safe_request_revalidates_dns_before_transport(monkeypatch):
    calls = []

    def resolver(host, port, **kwargs):
        calls.append(host)
        address = "93.184.216.34" if len(calls) == 1 else "127.0.0.1"
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, port or 80))]

    requester = patch("smart_assistant.ssrf.requests.Session.request").start()
    requester.return_value = requests.Response()
    requester.return_value.status_code = 200
    try:
        with pytest.raises(UnsafeEndpointError):
            safe_request("GET", "http://rebind.example/", resolver=resolver)
    finally:
        patch.stopall()
    assert len(calls) >= 2


def test_safe_request_rejects_redirects_even_with_injected_requester():
    requester = patch("smart_assistant.ssrf.requests.get").start()
    requester.return_value = requests.Response()
    requester.return_value.status_code = 200
    try:
        safe_request("GET", "https://example.com/", requester=requester)
        assert requester.call_args.kwargs["allow_redirects"] is False
    finally:
        patch.stopall()
