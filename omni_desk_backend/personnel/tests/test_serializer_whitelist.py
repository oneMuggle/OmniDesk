"""personnel serializer 白名单化测试 (R3-B1 PR-2)。

契约(plan §3.2 PR-2):
- FamilyMemberSerializer 读响应**不得**返回 `id_card_number`(Fernet 加密,读取解密,前端未消费)
- ProfessionalQualificationSerializer 读响应**不得**返回 `certificate_id`(证件编号,前端未消费)
- 其余 4 个 serializer(Position/Contract/Education/WorkExperience)显式白名单字段,
  不随 `__all__` 暴露模型全部字段
"""

import pytest

from personnel.models import (
    Contract,
    Education,
    FamilyMember,
    Personnel,
    Position,
    ProfessionalQualification,
    WorkExperience,
)
from personnel.serializers import (
    ContractSerializer,
    EducationSerializer,
    FamilyMemberSerializer,
    PositionSerializer,
    ProfessionalQualificationSerializer,
    WorkExperienceSerializer,
)


@pytest.fixture
def personnel(db):
    return Personnel.objects.create(name="张三", department="研发部")


@pytest.mark.django_db
class TestFamilyMemberSerializerWhitelist:
    def test_read_response_does_not_expose_id_card_number(self, personnel):
        """🔴 身份证号(Fernet 加密,读取解密)不得在读响应中出现。"""
        member = FamilyMember.objects.create(
            personnel=personnel,
            name="李四",
            relationship="配偶",
            id_card_number="110101199001011234",
            contact_number="13800000000",
        )

        data = FamilyMemberSerializer(member).data

        assert "id_card_number" not in data

    def test_fields_whitelisted(self, personnel):
        member = FamilyMember.objects.create(
            personnel=personnel,
            name="李四",
            relationship="配偶",
            contact_number="13800000000",
        )

        data = FamilyMemberSerializer(member).data

        assert set(data.keys()) == {"id", "personnel", "name", "relationship", "contact_number"}

    def test_write_accepts_id_card_number(self, personnel):
        """写路径仍接受 id_card_number(保留 HR 经 API 录入能力,读侧不暴露)。"""
        serializer = FamilyMemberSerializer(
            data={
                "personnel": personnel.id,
                "name": "李四",
                "relationship": "配偶",
                "contact_number": "13800000000",
                "id_card_number": "110101199001011234",
            }
        )

        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data["id_card_number"] == "110101199001011234"


@pytest.mark.django_db
class TestProfessionalQualificationSerializerWhitelist:
    def test_read_response_does_not_expose_certificate_id(self, personnel):
        """🟠 证件编号(前端未消费)不得在读响应中出现。"""
        q = ProfessionalQualification.objects.create(
            personnel=personnel,
            qualification_name="电工证",
            issue_date="2024-01-01",
            expiry_date="2027-01-01",
            certificate_id="CERT-001",
        )

        data = ProfessionalQualificationSerializer(q).data

        assert "certificate_id" not in data

    def test_fields_whitelisted(self, personnel):
        q = ProfessionalQualification.objects.create(
            personnel=personnel,
            qualification_name="电工证",
            issue_date="2024-01-01",
        )

        data = ProfessionalQualificationSerializer(q).data

        assert set(data.keys()) == {"id", "personnel", "qualification_name", "issue_date", "expiry_date"}

    def test_write_accepts_certificate_id(self, personnel):
        """写路径仍接受 certificate_id(读侧不暴露)。"""
        serializer = ProfessionalQualificationSerializer(
            data={
                "personnel": personnel.id,
                "qualification_name": "电工证",
                "issue_date": "2024-01-01",
                "certificate_id": "CERT-001",
            }
        )

        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data["certificate_id"] == "CERT-001"


@pytest.mark.django_db
class TestPositionSerializerWhitelist:
    def test_fields_whitelisted(self):
        pos = Position.objects.create(name="工程师")

        data = PositionSerializer(pos).data

        assert set(data.keys()) == {"id", "name"}


@pytest.mark.django_db
class TestContractSerializerWhitelist:
    def test_fields_whitelisted(self, personnel):
        contract = Contract.objects.create(
            personnel=personnel,
            contract_number="HT-001",
            contract_type="fixed-term",
            start_date="2024-01-01",
            end_date="2026-12-31",
        )

        data = ContractSerializer(contract).data

        assert set(data.keys()) == {
            "id",
            "personnel",
            "contract_number",
            "contract_type",
            "start_date",
            "end_date",
        }


@pytest.mark.django_db
class TestEducationSerializerWhitelist:
    def test_fields_whitelisted(self, personnel):
        edu = Education.objects.create(
            personnel=personnel,
            school="清华大学",
            degree="本科",
            major="计算机科学",
            start_date="2015-09-01",
            end_date="2019-06-30",
        )

        data = EducationSerializer(edu).data

        assert set(data.keys()) == {
            "id",
            "personnel",
            "school",
            "degree",
            "major",
            "start_date",
            "end_date",
        }


@pytest.mark.django_db
class TestWorkExperienceSerializerWhitelist:
    def test_fields_whitelisted(self, personnel):
        work = WorkExperience.objects.create(
            personnel=personnel,
            company="某某科技公司",
            position="后端工程师",
            start_date="2019-07-01",
            end_date="2023-06-30",
            description="负责内部系统开发",
        )

        data = WorkExperienceSerializer(work).data

        assert set(data.keys()) == {
            "id",
            "personnel",
            "company",
            "position",
            "start_date",
            "end_date",
            "description",
        }
