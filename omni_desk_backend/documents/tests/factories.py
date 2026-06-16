"""documents app 测试 factory。"""

import factory
from factory.django import DjangoModelFactory

from documents.models import DocumentTemplate, GeneratedDocument
from users.models import CustomUser


class UserFactory(DjangoModelFactory):
    """CustomUser factory — username/email 唯一,使用 Sequence 自增。"""

    class Meta:
        model = CustomUser
        django_get_or_create = ("username",)

    username = factory.Sequence(lambda n: f"user_{n}")
    email = factory.LazyAttribute(lambda obj: f"{obj.username}@example.com")
    is_active = True
    password = factory.PostGenerationMethodCall("set_password", "testpass123")


class DocumentTemplateFactory(DjangoModelFactory):
    class Meta:
        model = DocumentTemplate

    name = factory.Sequence(lambda n: f"Template {n}")
    template_type = "tech_design"
    content = "Template content"
    owner = factory.SubFactory(UserFactory)
    variables = factory.LazyFunction(dict)


class GeneratedDocumentFactory(DjangoModelFactory):
    class Meta:
        model = GeneratedDocument

    generated_by = factory.SubFactory(UserFactory)
    template = factory.SubFactory("documents.tests.factories.DocumentTemplateFactory")
    content = "Generated content"
    variables_used = factory.LazyFunction(dict)
    # 其他必填字段按模型默认填充
