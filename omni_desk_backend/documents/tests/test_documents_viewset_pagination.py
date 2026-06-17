"""GeneratedDocumentViewSet 分页行为测试。

对应 PR-1 任务:验证移除 pagination_class = None 后,API 返回标准分页响应。
"""
import pytest
from rest_framework import status

from documents.tests.factories import GeneratedDocumentFactory


@pytest.fixture
def regular_user(regular_user_obj):
    """Local alias to match project naming preference; reuses global regular_user_obj."""
    return regular_user_obj


@pytest.mark.django_db
class TestGeneratedDocumentPagination:
    """验证 GeneratedDocumentViewSet 已启用分页。"""

    def test_list_returns_paginated_envelope(self, api_client, regular_user):
        """列表端点应返回 count/next/previous/results 字段(不是裸 list)。"""
        GeneratedDocumentFactory.create_batch(
            12, generated_by=regular_user  # 超过 PAGE_SIZE=10
        )
        api_client.force_authenticate(regular_user)
        response = api_client.get("/api/documents/generated/")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        # 分页 envelope 必有字段
        assert "count" in data
        assert "next" in data
        assert "previous" in data
        assert "results" in data
        assert data["count"] == 12
        assert len(data["results"]) == 10  # PAGE_SIZE=10

    def test_list_second_page(self, api_client, regular_user):
        """第二页应返回剩余 2 条。"""
        GeneratedDocumentFactory.create_batch(12, generated_by=regular_user)
        api_client.force_authenticate(regular_user)
        response = api_client.get("/api/documents/generated/?page=2")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["results"]) == 2
        assert data["previous"] is not None
