"""知识库数据集 CRUD API 测试。

契约：/api/smart-assistant/knowledge-base/datasets/
    - GET    列表（分页，count/results）
    - POST   创建（必填：name、ragflow_dataset_id；document_count 只读）
    - GET    详情 /{id}/
    - PATCH  部分更新 /{id}/
    - PUT    全量更新 /{id}/
    - DELETE 删除 /{id}/ → 204
    - 未认证 → 401
"""

import pytest
from rest_framework import status

from smart_assistant.models import KnowledgeDataset

LIST_URL = "/api/smart-assistant/knowledge-base/datasets/"


def _detail_url(dataset_id):
    return f"{LIST_URL}{dataset_id}/"


def _create_dataset(**kwargs):
    """创建数据集的辅助工厂。"""
    defaults = {
        "name": "默认数据集",
        "ragflow_dataset_id": "ragflow-ds-001",
    }
    defaults.update(kwargs)
    return KnowledgeDataset.objects.create(**defaults)


class TestDatasetCreate:
    """POST /api/smart-assistant/knowledge-base/datasets/"""

    def test_create_dataset(self, authenticated_client):
        """完整字段创建 → 201，返回持久化后的字段。"""
        payload = {
            "name": "技术文档库",
            "description": "存放技术类知识库文档",
            "ragflow_dataset_id": "ragflow-tech-001",
            "is_active": True,
            "tags": ["tech", "backend"],
            "priority": 2,
        }

        resp = authenticated_client.post(LIST_URL, payload, format="json")

        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.data["name"] == "技术文档库"
        assert resp.data["description"] == "存放技术类知识库文档"
        assert resp.data["ragflow_dataset_id"] == "ragflow-tech-001"
        assert resp.data["tags"] == ["tech", "backend"]
        assert resp.data["priority"] == 2
        assert KnowledgeDataset.objects.filter(name="技术文档库").exists()

    def test_create_dataset_minimal_fields_use_defaults(self, authenticated_client):
        """仅必填字段创建 → 201，其余字段取模型默认值。"""
        resp = authenticated_client.post(
            LIST_URL,
            {"name": "最小数据集", "ragflow_dataset_id": "ragflow-min-001"},
            format="json",
        )

        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.data["is_active"] is True
        assert resp.data["tags"] == []
        assert resp.data["priority"] == 1
        assert resp.data["document_count"] == 0

    def test_create_dataset_document_count_is_read_only(self, authenticated_client):
        """document_count 为只读统计字段：客户端传值被忽略，落库仍为 0。"""
        resp = authenticated_client.post(
            LIST_URL,
            {
                "name": "只读计数字段",
                "ragflow_dataset_id": "ragflow-ro-001",
                "document_count": 999,
            },
            format="json",
        )

        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.data["document_count"] == 0
        assert KnowledgeDataset.objects.get(name="只读计数字段").document_count == 0

    def test_create_dataset_missing_name_returns_400(self, authenticated_client):
        """缺必填 name → 400。"""
        resp = authenticated_client.post(
            LIST_URL,
            {"ragflow_dataset_id": "ragflow-x"},
            format="json",
        )

        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "name" in resp.data

    def test_create_dataset_missing_ragflow_dataset_id_returns_400(self, authenticated_client):
        """缺必填 ragflow_dataset_id → 400。"""
        resp = authenticated_client.post(
            LIST_URL,
            {"name": "缺少 ragflow id"},
            format="json",
        )

        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "ragflow_dataset_id" in resp.data

    def test_create_dataset_duplicate_name_returns_400(self, authenticated_client):
        """name 唯一约束：重名创建 → 400。"""
        _create_dataset(name="重名数据集", ragflow_dataset_id="ragflow-dup-1")

        resp = authenticated_client.post(
            LIST_URL,
            {"name": "重名数据集", "ragflow_dataset_id": "ragflow-dup-2"},
            format="json",
        )

        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "name" in resp.data


class TestDatasetListRetrieve:
    """GET 列表与详情"""

    def test_list_datasets(self, authenticated_client):
        """列表返回全部数据集（分页结构 count/results）。"""
        _create_dataset(name="数据集A", ragflow_dataset_id="ragflow-a")
        _create_dataset(name="数据集B", ragflow_dataset_id="ragflow-b")

        resp = authenticated_client.get(LIST_URL)

        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["count"] == 2
        names = {item["name"] for item in resp.data["results"]}
        assert names == {"数据集A", "数据集B"}

    def test_retrieve_dataset(self, authenticated_client):
        """详情返回单个数据集字段。"""
        dataset = _create_dataset(name="详情数据集", ragflow_dataset_id="ragflow-detail")

        resp = authenticated_client.get(_detail_url(dataset.id))

        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["id"] == dataset.id
        assert resp.data["name"] == "详情数据集"
        assert resp.data["ragflow_dataset_id"] == "ragflow-detail"


class TestDatasetUpdateDelete:
    """PATCH / PUT / DELETE"""

    def test_partial_update_dataset(self, authenticated_client):
        """PATCH 部分更新：仅改 name，其余字段不变。"""
        dataset = _create_dataset(
            name="原名",
            ragflow_dataset_id="ragflow-patch",
            description="原描述",
            priority=1,
        )

        resp = authenticated_client.patch(
            _detail_url(dataset.id),
            {"name": "新名"},
            format="json",
        )

        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["name"] == "新名"
        dataset.refresh_from_db()
        assert dataset.name == "新名"
        assert dataset.description == "原描述"
        assert dataset.priority == 1

    def test_full_update_dataset(self, authenticated_client):
        """PUT 全量更新：覆盖所有可写字段。"""
        dataset = _create_dataset(name="PUT前", ragflow_dataset_id="ragflow-put")

        resp = authenticated_client.put(
            _detail_url(dataset.id),
            {
                "name": "PUT后",
                "description": "新描述",
                "ragflow_dataset_id": "ragflow-put-new",
                "is_active": False,
                "tags": ["policy"],
                "priority": 5,
            },
            format="json",
        )

        assert resp.status_code == status.HTTP_200_OK
        dataset.refresh_from_db()
        assert dataset.name == "PUT后"
        assert dataset.description == "新描述"
        assert dataset.ragflow_dataset_id == "ragflow-put-new"
        assert dataset.is_active is False
        assert dataset.tags == ["policy"]
        assert dataset.priority == 5

    def test_update_dataset_missing_required_returns_400(self, authenticated_client):
        """PUT 缺必填字段 → 400。"""
        dataset = _create_dataset(name="更新校验", ragflow_dataset_id="ragflow-val")

        resp = authenticated_client.put(
            _detail_url(dataset.id),
            {"name": "只有名字"},
            format="json",
        )

        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "ragflow_dataset_id" in resp.data

    def test_delete_dataset(self, authenticated_client):
        """DELETE → 204，数据库中不再存在。"""
        dataset = _create_dataset(name="待删除", ragflow_dataset_id="ragflow-del")

        resp = authenticated_client.delete(_detail_url(dataset.id))

        assert resp.status_code == status.HTTP_204_NO_CONTENT
        assert not KnowledgeDataset.objects.filter(id=dataset.id).exists()


class TestDatasetAuth:
    """认证校验"""

    def test_unauthenticated_returns_401(self, api_client):
        """未认证访问列表 → 401。"""
        resp = api_client.get(LIST_URL)
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_unauthenticated_create_returns_401(self, api_client):
        """未认证创建 → 401。"""
        resp = api_client.post(
            LIST_URL,
            {"name": "匿名", "ragflow_dataset_id": "ragflow-anon"},
            format="json",
        )
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED
