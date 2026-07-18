"""RAGFlow 客户端连接复用测试。

Task 2 of feat/sa-perf-ux: 用 requests.Session 长连接降低 TTFB。
"""
import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture
def mock_session():
    """Mock requests.Session 验证连接复用。"""
    with patch("ragflow_service.client.requests.Session") as MockSession:
        session_instance = MagicMock()
        # 让 session.request() 返回一个可用的 mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": []}
        session_instance.request.return_value = mock_response
        MockSession.return_value = session_instance
        yield session_instance


class TestRagflowClientSessionReuse:
    def test_client_uses_session_not_requests(self, mock_session):
        """RagflowClient 内部应使用 requests.Session,不是直接 requests.get/post。"""
        from ragflow_service.client import RagflowClient

        client = RagflowClient(api_endpoint="http://test", api_key="x")

        # 验证初始化时创建了 Session
        assert hasattr(client, "_session")
        # 验证 _session 是 MagicMock(来自我们的 fixture)
        assert client._session is mock_session

    def test_repeated_calls_reuse_same_session(self, mock_session):
        """多次调用应复用同一 session,而不是每次新建。"""
        from ragflow_service.client import RagflowClient

        client = RagflowClient(api_endpoint="http://test", api_key="x")
        client.list_datasets()
        client.list_datasets()

        # session.request 应被调用 2 次,但 session 对象始终是同一个
        assert mock_session.request.call_count == 2


class TestRagflowClientPerformance:
    def test_session_reduces_tcp_handshakes(self, mock_session):
        """50 个连续请求应在同一 Session 上,无需重新建连。"""
        from ragflow_service.client import RagflowClient

        client = RagflowClient(api_endpoint="http://test", api_key="x")
        for _ in range(50):
            client.list_datasets()

        # Session 仍只有一个,请求 50 次
        assert mock_session.request.call_count == 50


class TestRagflowClientClose:
    def test_close_closes_session(self, mock_session):
        """close() 应关闭底层 session。"""
        from ragflow_service.client import RagflowClient

        client = RagflowClient(api_endpoint="http://test", api_key="x")
        assert client._session is not None

        client.close()

        # session.close() 应被调用
        mock_session.close.assert_called_once()
        # _session 应被设置为 None
        assert client._session is None

    def test_close_idempotent(self, mock_session):
        """多次调用 close() 不应报错。"""
        from ragflow_service.client import RagflowClient

        client = RagflowClient(api_endpoint="http://test", api_key="x")
        client.close()
        client.close()  # 第二次调用不应报错

        # session.close() 只应被调用一次
        assert mock_session.close.call_count == 1

    def test_context_manager_closes_session(self, mock_session):
        """with statement 应自动关闭 session。"""
        from ragflow_service.client import RagflowClient

        with RagflowClient(api_endpoint="http://test", api_key="x") as client:
            assert client._session is not None
            client.list_datasets()

        # 退出 with block 后,session 应被关闭
        mock_session.close.assert_called_once()
        assert client._session is None

    def test_context_manager_with_exception(self, mock_session):
        """with statement 中发生异常时,session 仍应被关闭。"""
        from ragflow_service.client import RagflowClient, RagflowClientError
        import requests

        try:
            with RagflowClient(api_endpoint="http://test", api_key="x") as client:
                # 模拟一个会抛出异常的 API 调用(使用 requests 异常,会被 _request 捕获并转为 RagflowClientError)
                mock_session.request.side_effect = requests.exceptions.ConnectionError("Network error")
                client.list_datasets()
        except RagflowClientError:
            pass  # 预期会抛出 RagflowClientError

        # 即使发生异常,session 也应被关闭
        mock_session.close.assert_called_once()
        assert client._session is None
