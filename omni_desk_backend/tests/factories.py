"""项目级共享 factory。

供各 app 的 tests/factories.py 通过 SubFactory 引用。
"""
import factory
from factory.django import DjangoModelFactory

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
