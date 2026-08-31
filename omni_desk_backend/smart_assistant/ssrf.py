"""用于所有 LLM 出站请求的 SSRF 安全校验与受控传输。"""
import ipaddress
import socket
from urllib.parse import urlsplit, urlunsplit

import requests


class UnsafeEndpointError(ValueError):
    """端点地址不允许用于服务端出站请求。"""


_SAFE_SCHEMES = {"http", "https"}


def _forbidden(ip):
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_unspecified
        or ip.is_multicast
        or ip in ipaddress.ip_network("100.64.0.0/10")
    )


def validate_endpoint_url(value, *, resolve_dns=True, resolver=None):
    """校验 URL，并返回规范化 URL；DNS 的任一结果受限即拒绝。"""
    if not isinstance(value, str):
        raise UnsafeEndpointError("端点地址格式不正确。")
    try:
        parsed = urlsplit(value)
        scheme = parsed.scheme.lower()
        hostname = parsed.hostname
        port = parsed.port
    except (ValueError, UnicodeError):
        raise UnsafeEndpointError("端点地址格式不正确。")
    if scheme not in _SAFE_SCHEMES or not hostname:
        raise UnsafeEndpointError("端点地址必须使用 http 或 https 协议。")
    if parsed.username is not None or parsed.password is not None:
        raise UnsafeEndpointError("端点地址不能包含用户名或密码。")
    try:
        literal_ip = ipaddress.ip_address(hostname.strip("[]"))
    except ValueError:
        literal_ip = None
    if literal_ip is not None and resolver is None:
        if _forbidden(literal_ip) and resolver is None:
            raise UnsafeEndpointError("端点地址指向受限网络。")
        return urlunsplit((scheme, parsed.netloc, parsed.path, parsed.query, parsed.fragment))
    if not resolve_dns and resolver is None:
        return urlunsplit((scheme, parsed.netloc, parsed.path, parsed.query, parsed.fragment))
    try:
        infos = (resolver or socket.getaddrinfo)(hostname, port, type=socket.SOCK_STREAM)
    except (OSError, ValueError, UnicodeError):
        raise UnsafeEndpointError("端点地址无法解析。")
    if not infos:
        raise UnsafeEndpointError("端点地址无法解析。")
    addresses = []
    for info in infos:
        raw = info[4][0].split("%", 1)[0]
        try:
            ip = ipaddress.ip_address(raw)
        except ValueError:
            raise UnsafeEndpointError("端点地址无法解析。")
        if _forbidden(ip):
            raise UnsafeEndpointError("端点地址指向受限网络。")
        if raw not in addresses:
            addresses.append(raw)
    return urlunsplit((scheme, parsed.netloc, parsed.path, parsed.query, parsed.fragment))


def safe_request(method, url, *, requester=None, resolver=None, **kwargs):
    """校验端点后通过显式 requester 发起不可重定向请求。"""
    request_method = requester or getattr(requests, method.lower())
    checked = validate_endpoint_url(url, resolver=resolver)
    request_kwargs = dict(kwargs)
    request_kwargs["allow_redirects"] = False
    return request_method(checked, **request_kwargs)
