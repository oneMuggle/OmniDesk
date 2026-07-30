import ipaddress
import socket
from urllib.parse import urlparse

from rest_framework import serializers
from .models import ExternalLink, IntegrationService, Plugin, PluginVersion


def _is_forbidden_ip(ip):
    """判断 IP 是否落在回环 / 私有 / 链路本地（含云元数据）等禁止网段。"""
    return (
        ip.is_loopback  # 127.0.0.0/8、::1
        or ip.is_private  # 10.0.0.0/8、172.16.0.0/12、192.168.0.0/16、fc00::/7
        or ip.is_link_local  # 169.254.0.0/16（云元数据地址）、fe80::/10
        or ip.is_unspecified  # 0.0.0.0、::
        or ip.is_multicast
        or ip.is_reserved
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


class ExternalLinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExternalLink
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at")


class IntegrationServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = IntegrationService
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at")

    def validate_endpoint_url(self, value):
        """SSRF 防护：禁止 endpoint_url 指向回环 / 内网 / 元数据地址。"""
        parsed = urlparse(value)
        if parsed.scheme not in ("http", "https"):
            raise serializers.ValidationError("仅允许 http/https 协议")
        if is_forbidden_host(parsed.hostname):
            raise serializers.ValidationError("endpoint_url 禁止指向回环、内网或元数据地址")
        return value


class PluginVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PluginVersion
        fields = ("id", "version", "file_hash", "manifest", "is_active", "uploaded_by", "uploaded_at", "review_notes")
        read_only_fields = ("id", "uploaded_at")


class PluginSerializer(serializers.ModelSerializer):
    versions = PluginVersionSerializer(many=True, read_only=True)

    class Meta:
        model = Plugin
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at")


class PluginUploadSerializer(serializers.Serializer):
    """插件上传文件序列化器"""

    file = serializers.FileField()
