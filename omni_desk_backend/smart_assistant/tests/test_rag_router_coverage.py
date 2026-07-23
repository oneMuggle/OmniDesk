"""Tests for smart_assistant.agent.rag_router — 覆盖率补齐.

目标:agent/rag_router.py 13% → 60%+。
覆盖:RAGRouter.route_query / search_dataset / search_multi / get_active_datasets
+ get_ragflow_config / get_rag_router 单例。
"""

from unittest.mock import MagicMock, patch

import pytest
from django.test import override_settings

from smart_assistant.agent.rag_router import (
    RAGRouter,
    get_ragflow_config,
    get_rag_router,
)


# =============================================================================
# get_ragflow_config
# =============================================================================


class TestGetRagflowConfig:
    """get_ragflow_config: 兼容旧版单配置模式."""

    @patch("ragflow_service.models.RagflowConfig")
    def test_returns_active_config(self, mock_config_cls):
        """存在 active 配置时返回它."""
        fake_config = MagicMock()
        fake_config.is_active = True
        mock_config_cls.objects.filter.return_value.first.return_value = fake_config

        result = get_ragflow_config()

        assert result is fake_config
        mock_config_cls.objects.filter.assert_called_once_with(is_active=True)

    @patch("ragflow_service.models.RagflowConfig")
    def test_returns_none_when_no_active_config(self, mock_config_cls):
        """无 active 配置时返回 None."""
        mock_config_cls.objects.filter.return_value.first.return_value = None

        result = get_ragflow_config()

        assert result is None

    @patch("ragflow_service.models.RagflowConfig")
    def test_returns_none_on_exception(self, mock_config_cls):
        """异常时(例如 model 表不存在)返回 None,不传播异常."""
        mock_config_cls.objects.filter.side_effect = Exception("table missing")

        result = get_ragflow_config()

        assert result is None


# =============================================================================
# RAGRouter.get_active_datasets
# =============================================================================


class TestGetActiveDatasets:
    """RAGRouter.get_active_datasets: 列出所有活跃数据集."""

    @patch("smart_assistant.models.KnowledgeDataset")
    def test_returns_active_datasets(self, mock_kd_cls):
        fake_ds1 = MagicMock(name="ds1")
        fake_ds2 = MagicMock(name="ds2")
        mock_kd_cls.objects.filter.return_value.order_by.return_value = [fake_ds1, fake_ds2]

        router = RAGRouter()
        result = router.get_active_datasets()

        assert result == [fake_ds1, fake_ds2]
        mock_kd_cls.objects.filter.assert_called_once_with(is_active=True)

    @patch("smart_assistant.models.KnowledgeDataset")
    def test_returns_empty_list_on_exception(self, mock_kd_cls):
        mock_kd_cls.objects.filter.side_effect = Exception("db error")

        router = RAGRouter()
        result = router.get_active_datasets()

        assert result == []


# =============================================================================
# RAGRouter.route_query
# =============================================================================


class TestRouteQuery:
    """RAGRouter.route_query: 基于标签匹配最相关的数据集."""

    def _make_dataset(self, name="测试集", priority=1, tags=None, ds_id="ds-001"):
        ds = MagicMock()
        ds.name = name
        ds.priority = priority
        ds.tags = tags or []
        ds.ragflow_dataset_id = ds_id
        return ds

    @patch("smart_assistant.agent.rag_router.get_ragflow_config")
    @patch("smart_assistant.models.KnowledgeDataset")
    def test_fallback_to_default_config_when_no_datasets(
        self, mock_kd_cls, mock_get_config
    ):
        """无 datasets 时,fallback 到 SMART_ASSISTANT_DATASET_ID + config."""
        mock_kd_cls.objects.filter.return_value.order_by.return_value = []
        fake_config = MagicMock()
        fake_config.api_endpoint = "http://ragflow.local"
        fake_config.api_key = "key-abc"
        mock_get_config.return_value = fake_config

        router = RAGRouter()
        with override_settings(SMART_ASSISTANT_DATASET_ID="default-ds-id"):
            result = router.route_query("任意查询")

        assert len(result) == 1
        assert result[0]["name"] == "默认知识库"
        assert result[0]["ragflow_dataset_id"] == "default-ds-id"
        assert result[0]["api_endpoint"] == "http://ragflow.local"
        assert result[0]["api_key"] == "key-abc"

    @patch("smart_assistant.agent.rag_router.get_ragflow_config")
    @patch("smart_assistant.models.KnowledgeDataset")
    def test_returns_empty_when_no_datasets_and_no_config(
        self, mock_kd_cls, mock_get_config
    ):
        """无 datasets 且无 fallback config 时返回 []."""
        mock_kd_cls.objects.filter.return_value.order_by.return_value = []
        mock_get_config.return_value = None

        router = RAGRouter()
        result = router.route_query("任意查询")

        assert result == []

    @patch("smart_assistant.agent.rag_router.get_ragflow_config")
    @patch("smart_assistant.models.KnowledgeDataset")
    def test_returns_empty_when_no_datasets_and_empty_dataset_id(
        self, mock_kd_cls, mock_get_config
    ):
        """无 datasets + 有 config 但 SMART_ASSISTANT_DATASET_ID 为空时返回 []."""
        mock_kd_cls.objects.filter.return_value.order_by.return_value = []
        mock_get_config.return_value = MagicMock()

        router = RAGRouter()
        with override_settings(SMART_ASSISTANT_DATASET_ID=""):
            result = router.route_query("任意查询")

        assert result == []

    @patch("smart_assistant.agent.rag_router.get_ragflow_config")
    @patch("smart_assistant.models.KnowledgeDataset")
    def test_routes_by_tag_match(self, mock_kd_cls, mock_get_config):
        """标签匹配按分数排序,取前 2."""
        ds_schedule = self._make_dataset(name="排班库", priority=1, tags=["排班", "值班"])
        ds_personnel = self._make_dataset(name="人员库", priority=1, tags=["人员", "联系方式"])
        ds_unrelated = self._make_dataset(name="无关库", priority=1, tags=["财务"])
        mock_kd_cls.objects.filter.return_value.order_by.return_value = [
            ds_schedule, ds_personnel, ds_unrelated
        ]
        fake_config = MagicMock()
        fake_config.api_endpoint = "http://rag.local"
        fake_config.api_key = "k1"
        mock_get_config.return_value = fake_config

        router = RAGRouter()
        result = router.route_query("查排班和值班")

        # ds_schedule 匹配 2 个标签,ds_personnel 匹配 0,ds_unrelated 匹配 0
        # 应只返回 ds_schedule
        assert len(result) == 1
        assert result[0]["name"] == "排班库"

    @patch("smart_assistant.agent.rag_router.get_ragflow_config")
    @patch("smart_assistant.models.KnowledgeDataset")
    def test_no_tag_match_returns_top_three_datasets(
        self, mock_kd_cls, mock_get_config
    ):
        """无标签匹配时,返回前 3 个数据集(按 priority+name 排序)."""
        datasets = [
            self._make_dataset(name=f"ds{i}", priority=i + 1, tags=[f"tag{i}"])
            for i in range(5)
        ]
        mock_kd_cls.objects.filter.return_value.order_by.return_value = datasets
        fake_config = MagicMock()
        fake_config.api_endpoint = "http://rag.local"
        fake_config.api_key = "k1"
        mock_get_config.return_value = fake_config

        router = RAGRouter()
        result = router.route_query("完全无关的查询XYZ")

        # 应返回前 3 个
        assert len(result) == 3
        assert result[0]["name"] == "ds0"
        assert result[2]["name"] == "ds2"

    @patch("smart_assistant.agent.rag_router.get_ragflow_config")
    @patch("smart_assistant.models.KnowledgeDataset")
    def test_no_tag_match_handles_missing_config(
        self, mock_kd_cls, mock_get_config
    ):
        """无标签匹配 + 无 config 时,api_endpoint 和 api_key 应为空字符串."""
        datasets = [
            self._make_dataset(name="ds1", priority=1, tags=["tag1"]),
        ]
        mock_kd_cls.objects.filter.return_value.order_by.return_value = datasets
        mock_get_config.return_value = None

        router = RAGRouter()
        result = router.route_query("无关查询")

        assert len(result) == 1
        assert result[0]["api_endpoint"] == ""
        assert result[0]["api_key"] == ""


# =============================================================================
# RAGRouter.search_dataset
# =============================================================================


class TestSearchDataset:
    """RAGRouter.search_dataset: 搜索单个数据集."""

    def _make_dataset_dict(self, **overrides):
        defaults = {
            "name": "测试集",
            "ragflow_dataset_id": "ds-001",
            "api_endpoint": "http://rag.local",
            "api_key": "key-abc",
        }
        defaults.update(overrides)
        return defaults

    def test_returns_empty_when_config_incomplete(self):
        """api_endpoint 为空时返回 [],不调用网络."""
        router = RAGRouter()
        dataset = self._make_dataset_dict(api_endpoint="")
        with patch("smart_assistant.agent.rag_router.RagflowClient") as mock_client_cls:
            result = router.search_dataset("query", dataset)
        assert result == []
        mock_client_cls.assert_not_called()

    def test_returns_empty_when_api_key_missing(self):
        router = RAGRouter()
        dataset = self._make_dataset_dict(api_key="")
        with patch("smart_assistant.agent.rag_router.RagflowClient") as mock_client_cls:
            result = router.search_dataset("query", dataset)
        assert result == []
        mock_client_cls.assert_not_called()

    def test_returns_empty_when_dataset_id_missing(self):
        router = RAGRouter()
        dataset = self._make_dataset_dict(ragflow_dataset_id="")
        with patch("smart_assistant.agent.rag_router.RagflowClient") as mock_client_cls:
            result = router.search_dataset("query", dataset)
        assert result == []
        mock_client_cls.assert_not_called()

    def test_search_success_adds_source_marker(self):
        """成功时给每个 chunk 加 _source 字段."""
        router = RAGRouter()
        dataset = self._make_dataset_dict(name="人事库")

        mock_client = MagicMock()
        mock_client.retrieval.return_value = [
            {"content": "chunk1", "score": 0.9},
            {"content": "chunk2", "score": 0.8},
        ]

        with patch("smart_assistant.agent.rag_router.RagflowClient", return_value=mock_client) as mock_client_cls:
            result = router.search_dataset("问题", dataset, top_k=3)

        assert len(result) == 2
        assert result[0]["_source"] == "人事库"
        assert result[1]["_source"] == "人事库"
        # 验证 RagflowClient.retrieval 调用参数
        call_args = mock_client.retrieval.call_args
        assert call_args.kwargs["dataset_ids"] == ["ds-001"]
        assert call_args.kwargs["question"] == "问题"
        assert call_args.kwargs["top_k"] == 3

    def test_search_returns_empty_on_network_exception(self):
        """网络异常时返回 [],不传播异常."""
        from ragflow_service.client import RagflowClientError

        router = RAGRouter()
        dataset = self._make_dataset_dict()

        mock_client = MagicMock()
        mock_client.retrieval.side_effect = RagflowClientError("connection refused")

        with patch("smart_assistant.agent.rag_router.RagflowClient", return_value=mock_client):
            result = router.search_dataset("问题", dataset)

        assert result == []


# =============================================================================
# RAGRouter.search_multi
# =============================================================================


class TestSearchMulti:
    """RAGRouter.search_multi: 并行搜索多个数据集,合并去重."""

    @patch.object(RAGRouter, "route_query")
    def test_returns_empty_when_no_datasets(self, mock_route):
        """route_query 返回 [] 时,search_multi 返回 []."""
        mock_route.return_value = []

        router = RAGRouter()
        result = router.search_multi("query")

        assert result == []

    @patch.object(RAGRouter, "route_query")
    @patch.object(RAGRouter, "search_dataset")
    def test_deduplicates_by_content(self, mock_search, mock_route):
        """多个数据集的相同 content 应去重."""
        mock_route.return_value = [
            {"name": "ds1", "ragflow_dataset_id": "id1", "api_endpoint": "http://a", "api_key": "k"},
            {"name": "ds2", "ragflow_dataset_id": "id2", "api_endpoint": "http://b", "api_key": "k"},
        ]
        # ds1 返回 2 个 chunk,ds2 返回 1 个 chunk(其中 1 个 content 与 ds1 重复)
        mock_search.side_effect = [
            [
                {"content": "重复内容", "_source": "ds1"},
                {"content": "ds1独有", "_source": "ds1"},
            ],
            [
                {"content": "重复内容", "_source": "ds2"},
                {"content": "ds2独有", "_source": "ds2"},
            ],
        ]

        router = RAGRouter()
        result = router.search_multi("query", top_k=10)

        # 3 个唯一内容
        assert len(result) == 3
        contents = [r["content"] for r in result]
        assert contents.count("重复内容") == 1

    @patch.object(RAGRouter, "route_query")
    @patch.object(RAGRouter, "search_dataset")
    def test_truncates_to_top_k(self, mock_search, mock_route):
        """结果超 top_k 时截断."""
        mock_route.return_value = [
            {"name": "ds1", "ragflow_dataset_id": "id1", "api_endpoint": "http://a", "api_key": "k"},
        ]
        mock_search.return_value = [
            {"content": f"chunk{i}", "_source": "ds1"} for i in range(10)
        ]

        router = RAGRouter()
        result = router.search_multi("query", top_k=3)

        assert len(result) == 3

    @patch.object(RAGRouter, "route_query")
    @patch.object(RAGRouter, "search_dataset")
    def test_uses_text_field_as_fallback_for_dedup(self, mock_search, mock_route):
        """去重时若 content 字段缺失,使用 text 字段."""
        mock_route.return_value = [
            {"name": "ds1", "ragflow_dataset_id": "id1", "api_endpoint": "http://a", "api_key": "k"},
        ]
        # chunk 用 text 字段而非 content
        mock_search.return_value = [
            {"text": "用text字段", "_source": "ds1"},
            {"text": "用text字段", "_source": "ds1"},  # 重复
        ]

        router = RAGRouter()
        result = router.search_multi("query", top_k=10)

        assert len(result) == 1


# =============================================================================
# get_rag_router
# =============================================================================


class TestGetRagRouter:
    """get_rag_router: 全局单例."""

    def test_returns_rag_router_instance(self):
        # 重置全局单例
        import smart_assistant.agent.rag_router as router_module
        router_module._router = None

        router = get_rag_router()

        assert isinstance(router, RAGRouter)

    def test_returns_same_instance_on_subsequent_calls(self):
        import smart_assistant.agent.rag_router as router_module
        router_module._router = None

        router1 = get_rag_router()
        router2 = get_rag_router()

        assert router1 is router2
