"""RagflowConfig.api_key 加密存储测试。

覆盖:
- 加密往返：保存 → 从 DB 刷新 → 读回原始明文
- 落库密文：DB 原始值不等于明文（绕过 ORM 字段解密直接查库验证）
- 空值处理：空字符串 / None 密钥原样存取，不触发加解密异常
"""

import pytest
from django.db import connection

from personnel.models import _encrypt_field
from ragflow_service.models import RagflowConfig


def _read_raw_api_key(config_id):
    """绕过 ORM 字段层解密，用原生 SQL 读取 DB 中的原始存储值。"""
    table = RagflowConfig._meta.db_table
    with connection.cursor() as cursor:
        cursor.execute(  # nosec B608 - table from model _meta
            f"SELECT api_key FROM {table} WHERE id = %s", [config_id]
        )
        row = cursor.fetchone()
    return row[0] if row else None


@pytest.mark.django_db
class TestApiKeyEncryption:
    def test_roundtrip_returns_original_plaintext(self):
        """保存后重新从数据库加载，应读回原始明文。"""
        config = RagflowConfig.objects.create(
            name="enc-roundtrip",
            api_endpoint="https://ragflow.example.com/api",
            api_key="secret-key-123",
        )

        refreshed = RagflowConfig.objects.get(pk=config.pk)
        assert refreshed.api_key == "secret-key-123"

    def test_db_raw_value_is_ciphertext(self):
        """数据库中的原始值必须是密文：不等于明文，且等于加密函数的输出。"""
        from django.conf import settings

        config = RagflowConfig.objects.create(
            name="enc-raw",
            api_endpoint="https://ragflow.example.com/api",
            api_key="secret-key-123",
        )

        raw = _read_raw_api_key(config.pk)
        assert raw is not None
        assert raw != "secret-key-123"
        # 与 EncryptedCharField 使用的加密函数输出一致
        assert raw == _encrypt_field("secret-key-123", settings.SECRET_KEY)

    def test_base64_like_plaintext_survives_roundtrip(self):
        """形似 base64 的明文密钥也能无损往返（防止误解密路径回归）。"""
        tricky_key = "YWJjZGVmZzEyMzQ1Njc4OQ=="  # 合法 base64 字符串
        config = RagflowConfig.objects.create(
            name="enc-base64-like",
            api_endpoint="https://ragflow.example.com/api",
            api_key=tricky_key,
        )

        refreshed = RagflowConfig.objects.get(pk=config.pk)
        assert refreshed.api_key == tricky_key
        assert _read_raw_api_key(config.pk) != tricky_key

    def test_empty_and_null_key_untouched(self):
        """空字符串 / None 密钥原样存取，不报错。"""
        empty = RagflowConfig.objects.create(
            name="enc-empty",
            api_endpoint="https://ragflow.example.com/api",
            api_key="",
        )
        null = RagflowConfig.objects.create(
            name="enc-null",
            api_endpoint="https://ragflow.example.com/api",
            api_key=None,
        )

        assert RagflowConfig.objects.get(pk=empty.pk).api_key == ""
        assert RagflowConfig.objects.get(pk=null.pk).api_key is None
        assert _read_raw_api_key(empty.pk) == ""
        assert _read_raw_api_key(null.pk) is None
