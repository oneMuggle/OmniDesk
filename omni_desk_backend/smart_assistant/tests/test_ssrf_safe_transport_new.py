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


def test_safe_request_does_not_follow_redirects():
    with patch("smart_assistant.ssrf.requests.Session.request") as request:
        request.return_value = requests.Response()
        request.return_value.status_code = 200
        safe_request("GET", "https://example.com")
        assert request.call_args.kwargs["allow_redirects"] is False
