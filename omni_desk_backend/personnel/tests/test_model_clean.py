"""P2-4 Personnel.clean() L3 防护 — TDD 测试(RED 阶段)

L3 = Model.clean() 数据完整性校验。不依赖用户上下文,只校验数据本身。
- status 字段必须是有效值
- name 字段不能为空字符串
"""
import pytest
from django.core.exceptions import ValidationError

from personnel.models import Personnel


@pytest.mark.django_db
class TestPersonnelCleanStatus:
    def test_valid_status_passes(self):
        p = Personnel(name="测试", status="active")
        p.clean()  # 不抛异常

    def test_valid_status_inactive_passes(self):
        p = Personnel(name="测试", status="inactive")
        p.clean()

    def test_invalid_status_raises(self):
        p = Personnel(name="测试", status="unknown")
        with pytest.raises(ValidationError):
            p.clean()


@pytest.mark.django_db
class TestPersonnelCleanName:
    def test_empty_name_raises(self):
        p = Personnel(name="", status="active")
        with pytest.raises(ValidationError):
            p.clean()

    def test_whitespace_only_name_raises(self):
        p = Personnel(name="   ", status="active")
        with pytest.raises(ValidationError):
            p.clean()


@pytest.mark.django_db
class TestPersonnelFullCleanIntegration:
    """full_clean() 应调用 clean()。"""

    def test_full_clean_triggers_clean(self):
        p = Personnel(name="", status="active")
        with pytest.raises(ValidationError):
            p.full_clean()
