"""news serializer 白名单化测试 (R3-B1 PR-4)。

契约(plan §3.2 PR-4):
- NewsTypeSerializer 白名单 `("id","name")`(嵌套于 NewsArticleSerializer)
"""

import pytest

from news.models import NewsType
from news.serializers import NewsTypeSerializer


@pytest.mark.django_db
class TestNewsTypeSerializerWhitelist:
    def test_fields_whitelisted(self):
        news_type = NewsType.objects.create(name="通知")

        data = NewsTypeSerializer(news_type).data

        assert set(data.keys()) == {"id", "name"}
