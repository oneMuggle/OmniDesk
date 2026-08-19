"""config serializer 白名单化测试 (R3-B1 PR-4)。

契约(plan §3.2 PR-4):
- PageSerializer 白名单 `("id","name","path")`
- PageVisibilitySerializer 白名单 `("id","page","group","is_visible")`,保留嵌套 page/group
  (后端未使用——裸 ViewSet 手工组装——收敛即可)
"""

import pytest
from django.contrib.auth.models import Group

from config.models import Page, PageVisibility
from config.serializers import PageSerializer, PageVisibilitySerializer


@pytest.mark.django_db
class TestPageSerializerWhitelist:
    def test_fields_whitelisted(self):
        page = Page.objects.create(name="首页", path="/home")

        data = PageSerializer(page).data

        assert set(data.keys()) == {"id", "name", "path"}


@pytest.mark.django_db
class TestPageVisibilitySerializerWhitelist:
    def test_fields_whitelisted(self):
        page = Page.objects.create(name="首页", path="/home")
        group = Group.objects.create(name="User")
        vis = PageVisibility.objects.create(page=page, group=group, is_visible=True)

        data = PageVisibilitySerializer(vis).data

        assert set(data.keys()) == {"id", "page", "group", "is_visible"}
        assert data["page"]["name"] == "首页"
        assert data["group"]["name"] == "User"
