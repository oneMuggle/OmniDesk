"""documents serializer 白名单化测试 (R3-B1 PR-4)。

契约(plan §3.2 PR-4):
- DocumentTemplateSerializer 剔除 `variables`(前端零消费),保留 project_name/template_type_display 之外的消费字段
- GeneratedDocumentSerializer 剔除 `variables_used`
- TagSerializer / EBookSerializer 显式白名单字段
"""

import pytest

from documents.models import EBook, Tag
from documents.serializers import (
    DocumentTemplateSerializer,
    EBookSerializer,
    GeneratedDocumentSerializer,
    TagSerializer,
)
from documents.tests.factories import DocumentTemplateFactory, GeneratedDocumentFactory
from projects.models import Project


@pytest.fixture
def project(db):
    return Project.objects.create(name="项目X")


@pytest.mark.django_db
class TestDocumentTemplateSerializerWhitelist:
    def test_fields_whitelisted(self, regular_user_obj, project):
        template = DocumentTemplateFactory(
            owner=regular_user_obj,
            project=project,
            variables={"k": "v"},
        )

        data = DocumentTemplateSerializer(template).data

        assert set(data.keys()) == {
            "id",
            "project",
            "name",
            "template_type",
            "content",
            "extracted_text",
            "created_at",
            "updated_at",
            "owner",
            "project_name",
        }
        # variables(前端零消费)被剔除
        assert "variables" not in data

    def test_write_accepts_fields(self, regular_user_obj, project):
        serializer = DocumentTemplateSerializer(
            data={
                "project": project.id,
                "name": "测试模板",
                "template_type": "tech_design",
                "content": "模板内容",
                "owner": regular_user_obj.id,
            }
        )

        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data["name"] == "测试模板"

    def test_write_ignores_removed_variables(self, regular_user_obj, project):
        """variables 不在白名单:提交被 DRF 静默忽略,不写入 validated_data。"""
        serializer = DocumentTemplateSerializer(
            data={
                "project": project.id,
                "name": "测试模板",
                "template_type": "tech_design",
                "content": "模板内容",
                "owner": regular_user_obj.id,
                "variables": {"custom": 1},
            }
        )

        assert serializer.is_valid(), serializer.errors
        assert "variables" not in serializer.validated_data


@pytest.mark.django_db
class TestGeneratedDocumentSerializerWhitelist:
    def test_fields_whitelisted(self, regular_user_obj):
        template = DocumentTemplateFactory(owner=regular_user_obj)
        doc = GeneratedDocumentFactory(
            template=template,
            generated_by=regular_user_obj,
            variables_used={"k": "v"},
        )

        data = GeneratedDocumentSerializer(doc).data

        assert set(data.keys()) == {
            "id",
            "template",
            "content",
            "generated_by",
            "generated_at",
            "is_final",
            "content_preview",
        }
        # variables_used(前端零消费)被剔除
        assert "variables_used" not in data

    def test_write_accepts_fields(self, regular_user_obj):
        template = DocumentTemplateFactory(owner=regular_user_obj)
        serializer = GeneratedDocumentSerializer(
            data={
                "template": template.id,
                "content": "生成内容",
                "is_final": False,
            }
        )

        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data["template"] == template


@pytest.mark.django_db
class TestTagSerializerWhitelist:
    def test_fields_whitelisted(self):
        tag = Tag.objects.create(name="技术")

        data = TagSerializer(tag).data

        assert set(data.keys()) == {"id", "name"}


@pytest.mark.django_db
class TestEBookSerializerWhitelist:
    def test_fields_whitelisted(self):
        book = EBook.objects.create(title="测试书", author="作者", content="# md")

        data = EBookSerializer(book).data

        assert set(data.keys()) == {"id", "title", "author", "content", "created_at"}
