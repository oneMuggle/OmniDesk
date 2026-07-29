"""P0-B Fernet 加密字段测试

- 静态加密:DB 中存储的不是明文,Python 层透明读回
- 数据迁移:旧 XOR 密文经 RunPython 后能以 Fernet 读回
"""
import base64
import hashlib
import importlib

import pytest
from django.conf import settings
from django.db import connection

from personnel.models import FamilyMember, Personnel

# 数字开头的迁移模块无法用常规 import 语法
_migration = importlib.import_module("personnel.migrations.0007_alter_familymember_id_card_number_and_more")
xor_to_fernet = _migration.xor_to_fernet

ID_CARD = "110101199003078888"


def _raw_id_card(table, pk):
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT id_card_number FROM {table} WHERE id = %s", [pk])
        row = cursor.fetchone()
    return row[0] if row else None


@pytest.mark.django_db
class TestEncryptedAtRest:
    def test_id_card_number_is_encrypted_at_rest(self):
        """DB 层不是明文,Python 层能读回。"""
        personnel = Personnel.objects.create(name="加密测试", id_card_number=ID_CARD)

        raw = _raw_id_card("personnel_personnel", personnel.id)
        assert raw is not None
        assert raw != ID_CARD
        assert "110101" not in raw  # 明文任何片段都不应出现在密文中

        refreshed = Personnel.objects.get(pk=personnel.id)
        assert refreshed.id_card_number == ID_CARD

    def test_family_member_id_card_encrypted_at_rest(self):
        personnel = Personnel.objects.create(name="家属测试")
        member = FamilyMember.objects.create(
            personnel=personnel, name="家属甲", relationship="配偶", id_card_number=ID_CARD
        )

        raw = _raw_id_card("personnel_familymember", member.id)
        assert raw != ID_CARD
        assert FamilyMember.objects.get(pk=member.id).id_card_number == ID_CARD

    def test_blank_and_none_passthrough(self):
        """空值透传:不加密、读回原值。"""
        p_none = Personnel.objects.create(name="空值A", id_card_number=None)
        p_blank = Personnel.objects.create(name="空值B")
        member = FamilyMember.objects.create(personnel=p_blank, name="家属乙", relationship="子女", id_card_number="")

        assert _raw_id_card("personnel_personnel", p_none.id) is None
        assert _raw_id_card("personnel_familymember", member.id) == ""
        assert Personnel.objects.get(pk=p_none.id).id_card_number is None
        assert Personnel.objects.get(pk=p_blank.id).id_card_number in (None, "")

    def test_ciphertext_differs_per_write(self):
        """Fernet 含随机 IV:相同明文两次写入密文不同(防频率分析)。"""
        p1 = Personnel.objects.create(name="随机IV-A", id_card_number=ID_CARD)
        p2 = Personnel.objects.create(name="随机IV-B", id_card_number=ID_CARD)
        assert _raw_id_card("personnel_personnel", p1.id) != _raw_id_card("personnel_personnel", p2.id)


@pytest.mark.django_db
class TestLegacyDataMigration:
    def test_xor_legacy_rows_reencrypted_as_fernet(self):
        """模拟旧 XOR 存量数据,RunPython 后可透明读回明文。"""
        key_bytes = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
        value_bytes = ID_CARD.encode("utf-8")
        legacy = base64.b64encode(
            bytes(v ^ key_bytes[i % len(key_bytes)] for i, v in enumerate(value_bytes))
        ).decode()

        personnel = Personnel.objects.create(name="存量迁移")
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE personnel_personnel SET id_card_number = %s WHERE id = %s",
                [legacy, personnel.id],
            )

        # 迁移前:ORM 读回的是无法解密的旧密文(容错返回原值,不等于明文)
        assert Personnel.objects.get(pk=personnel.id).id_card_number != ID_CARD

        xor_to_fernet(apps=None, schema_editor=None)

        assert Personnel.objects.get(pk=personnel.id).id_card_number == ID_CARD

    def test_migration_is_idempotent(self):
        """已是 Fernet 格式的行再次运行迁移保持不变。"""
        personnel = Personnel.objects.create(name="幂等测试", id_card_number=ID_CARD)
        before = _raw_id_card("personnel_personnel", personnel.id)

        xor_to_fernet(apps=None, schema_editor=None)

        assert _raw_id_card("personnel_personnel", personnel.id) == before
        assert Personnel.objects.get(pk=personnel.id).id_card_number == ID_CARD
