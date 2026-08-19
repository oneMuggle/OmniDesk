import ipaddress
import socket
from urllib.parse import urlparse

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from .models import ExternalLink, IntegrationService, Plugin, PluginVersion


def _is_cgnat(ip):
    """CGNAT 段(100.64.0.0/10)单独判断。

    Python 3.10 的 ``IPv4Address.is_private`` 不覆盖该段；CGNAT 在部分 ISP / 企业网
    中作为内部地址使用,为 SSRF 防护严密起见显式拒绝。
    """
    try:
        return ip in ipaddress.ip_network("100.64.0.0/10")
    except (TypeError, ValueError):
        return False


def _is_forbidden_ip(ip):
    """判断 IP 是否落在回环 / 私有 / 链路本地（含云元数据）/ CGNAT 等禁止网段。"""
    return (
        ip.is_loopback  # 127.0.0.0/8、::1
        or ip.is_private  # 10.0.0.0/8、172.16.0.0/12、192.168.0.0/16、fc00::/7
        or ip.is_link_local  # 169.254.0.0/16（云元数据地址）、fe80::/10
        or ip.is_unspecified  # 0.0.0.0、::
        or ip.is_multicast
        or ip.is_reserved
        or _is_cgnat(ip)  # 100.64.0.0/10
    )


def is_forbidden_host(host):
    """SSRF 防护：判断 host 是否指向内网 / 本机 / 元数据等禁止地址。

    字面 IP 直接判断；主机名经 DNS 解析后逐一判断，解析失败同样视为禁止。
    """
    if not host:
        return True

    host = host.strip("[]").strip().lower()
    if not host or host == "localhost":
        return True

    # 字面 IP：直接判断
    try:
        return _is_forbidden_ip(ipaddress.ip_address(host))
    except ValueError:
        pass

    # 主机名：任一解析地址落在禁止网段即拒绝
    try:
        addr_info_list = socket.getaddrinfo(host, None)
    except (OSError, UnicodeError):  # 含 socket.gaierror，解析失败一律拒绝
        return True

    if not addr_info_list:
        return True

    for _family, _socktype, _proto, _canonname, sockaddr in addr_info_list:
        ip_str = sockaddr[0].split("%")[0]  # 去掉 IPv6 zone 后缀
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            return True
        if _is_forbidden_ip(ip):
            return True
    return False


def validate_endpoint_url(value):
    """SSRF 校验：禁止非 http/https 协议 + 回环/内网/元数据/CGNAT 主机。

    模块级函数,可在 DRF serializer、模型 ``save()`` 与服务层 ``forward_post`` 三处复用,
    保证 Django Admin 与直接 ORM 写入路径也受 SSRF 校验保护(否则 Admin 路径会绕过
    DRF serializer 的字段校验)。
    """
    parsed = urlparse(value)
    if parsed.scheme not in ("http", "https"):
        raise DjangoValidationError("仅允许 http/https 协议")
    if is_forbidden_host(parsed.hostname):
        raise DjangoValidationError("endpoint_url 禁止指向回环、内网或元数据地址")
    return value


class ExternalLinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExternalLink
        fields = [
            "id",
            "name",
            "url",
            "icon",
            "description",
            "category",
            "sso_enabled",
            "sso_token_endpoint",
            "sort_order",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ("created_at", "updated_at")


class IntegrationServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = IntegrationService
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "integration_type",
            "endpoint_url",
            "api_key",
            "embed_path",
            "config_schema",
            "metadata",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ("created_at", "updated_at")
        # R3-B1: api_key 加密存储,不得在读响应中返回明文密钥;仅允许写入
        extra_kwargs = {"api_key": {"write_only": True}}

    def validate_endpoint_url(self, value):
        """SSRF 防护：委托给模块级 ``validate_endpoint_url`` 以保证 Admin/ORM 路径也能复用。"""
        return validate_endpoint_url(value)


class PluginVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PluginVersion
        fields = ("id", "version", "file_hash", "manifest", "is_active", "uploaded_by", "uploaded_at", "review_notes")
        read_only_fields = ("id", "uploaded_at")


class PluginSerializer(serializers.ModelSerializer):
    versions = PluginVersionSerializer(many=True, read_only=True)

    class Meta:
        model = Plugin
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "author",
            "category",
            "icon",
            "status",
            "interface_version",
            "versions",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ("created_at", "updated_at")


class PluginUploadSerializer(serializers.Serializer):
    """插件上传文件序列化器"""

    file = serializers.FileField()
