"""Fernet 对称加密模型字段(P0-B)

替换旧的 XOR + base64 假加密(personnel/models.py 中的 EncryptedCharField)。
XOR 流密码不具备抗已知明文攻击能力,任何能读到源码 + SECRET_KEY 的人都可以
平凡还原身份证号等敏感数据。Fernet(cryptography 库,AES-128-CBC + HMAC-SHA256)
是经审计的认证加密方案,密文不可伪造、不可重放。

密钥派生:sha256(settings.SECRET_KEY) → urlsafe base64(32 字节),
与旧实现共用同一 SECRET_KEY 来源,部署无需额外配置密钥。
"""

import base64
import hashlib

from observability import get_logger
from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.db import models

logger = get_logger(__name__, "personnel.fields")


class EncryptedCharField(models.CharField):
    """基于 Fernet 透明加解密的 CharField。

    - 空值(None / "")透传,不加密(保持与旧字段一致的 blank 语义)
    - 解密失败(旧格式残留 / 数据损坏)返回原始值而非崩溃,与旧实现容错策略一致
    """

    @staticmethod
    def _fernet_key() -> bytes:
        """由 SECRET_KEY 派生 32 字节 urlsafe-base64 Fernet 密钥。"""
        return base64.urlsafe_b64encode(hashlib.sha256(settings.SECRET_KEY.encode()).digest())

    def get_prep_value(self, value):
        if value is None or value == "":
            return value
        return Fernet(self._fernet_key()).encrypt(value.encode()).decode()

    def from_db_value(self, value, expression, connection):
        if value is None or value == "":
            return value
        try:
            return Fernet(self._fernet_key()).decrypt(value.encode()).decode()
        except InvalidToken:
            logger.debug("Fernet 解密失败,返回原始值(可能为未迁移的旧数据或数据损坏)")
            return value
