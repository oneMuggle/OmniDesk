"""P0-C 权限类清理测试

- IsAdminOrManagerOrReadOnly 在 users/permissions.py 中只有一个定义
  (旧版基于 groups 的实现与 P2-5 HR-aware 版重名,Python 后者覆盖前者,属隐蔽缺陷)
- HR-aware 版语义保留:admin/hr 可写,普通用户只读
- has_object_permission 对 admin/hr 入口放行
"""
import ast
from pathlib import Path

import pytest
from rest_framework.test import APIRequestFactory
from rest_framework.views import APIView

from users.permissions import IsAdminOrManagerOrReadOnly

_PERMISSIONS_FILE = Path(__file__).resolve().parents[1] / "permissions.py"


def _make_request(method, user):
    factory = APIRequestFactory()
    request = getattr(factory, method)("/")
    request.user = user
    return request


class TestSingleDefinition:
    def test_is_admin_or_manager_or_readonly_defined_once(self):
        """AST 级别确认同名 class 只定义一次。"""
        tree = ast.parse(_PERMISSIONS_FILE.read_text(encoding="utf-8"))
        definitions = [
            node.name for node in tree.body if isinstance(node, ast.ClassDef)
        ]
        assert definitions.count("IsAdminOrManagerOrReadOnly") == 1


@pytest.mark.django_db
class TestHRAwareSemantics:
    def test_admin_can_write(self, admin_user_obj):
        perm = IsAdminOrManagerOrReadOnly()
        request = _make_request("post", admin_user_obj)
        assert perm.has_permission(request, APIView()) is True
        assert perm.has_object_permission(request, APIView(), object()) is True

    def test_manager_can_write(self, manager_user_obj):
        perm = IsAdminOrManagerOrReadOnly()
        request = _make_request("put", manager_user_obj)
        assert perm.has_permission(request, APIView()) is True
        assert perm.has_object_permission(request, APIView(), object()) is True

    def test_regular_user_read_only(self, regular_user_obj):
        perm = IsAdminOrManagerOrReadOnly()
        view = APIView()

        read_request = _make_request("get", regular_user_obj)
        assert perm.has_permission(read_request, view) is True
        assert perm.has_object_permission(read_request, view, object()) is True

        write_request = _make_request("delete", regular_user_obj)
        assert perm.has_permission(write_request, view) is False
        assert perm.has_object_permission(write_request, view, object()) is False

    def test_anonymous_denied(self):
        from django.contrib.auth.models import AnonymousUser

        perm = IsAdminOrManagerOrReadOnly()
        request = _make_request("get", AnonymousUser())
        assert perm.has_permission(request, APIView()) is False
