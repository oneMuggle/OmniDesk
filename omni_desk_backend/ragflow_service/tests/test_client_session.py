"""RAGFlow 客户端连接复用测试。

Task 2 of feat/sa-perf-ux: 用 requests.Session 长连接降低 TTFB。
"""
import pytest
import socket
import requests
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

        client = RagflowClient(api_endpoint="http://test", api_key="x", resolver=_public_resolver)

        # 验证初始化时创建了 Session
        assert hasattr(client, "_session")
        # 验证 _session 是 MagicMock(来自我们的 fixture)
        assert client._session is mock_session

    def test_repeated_calls_reuse_same_session(self, mock_session):
        """多次调用应复用同一 session,而不是每次新建。"""
        from ragflow_service.client import RagflowClient

        client = RagflowClient(api_endpoint="http://test", api_key="x", resolver=_public_resolver)
        client.list_datasets()
        client.list_datasets()

        # session.request 应被调用 2 次,但 session 对象始终是同一个
        assert mock_session.request.call_count == 2


class TestRagflowClientPerformance:
    def test_session_reduces_tcp_handshakes(self, mock_session):
        """50 个连续请求应在同一 Session 上,无需重新建连。"""
        from ragflow_service.client import RagflowClient

        client = RagflowClient(api_endpoint="http://test", api_key="x", resolver=_public_resolver)
        for _ in range(50):
            client.list_datasets()

        # Session 仍只有一个,请求 50 次
        assert mock_session.request.call_count == 50


class TestRagflowClientClose:
    def test_close_closes_session(self, mock_session):
        """close() 应关闭底层 session。"""
        from ragflow_service.client import RagflowClient

        client = RagflowClient(api_endpoint="http://test", api_key="x", resolver=_public_resolver)
        assert client._session is not None

        client.close()

        # session.close() 应被调用
        mock_session.close.assert_called_once()
        # _session 应被设置为 None
        assert client._session is None

    def test_close_idempotent(self, mock_session):
        """多次调用 close() 不应报错。"""
        from ragflow_service.client import RagflowClient

        client = RagflowClient(api_endpoint="http://test", api_key="x", resolver=_public_resolver)
        client.close()
        client.close()  # 第二次调用不应报错

        # session.close() 只应被调用一次
        assert mock_session.close.call_count == 1

    def test_context_manager_closes_session(self, mock_session):
        """with statement 应自动关闭 session。"""
        from ragflow_service.client import RagflowClient

        with RagflowClient(api_endpoint="http://test", api_key="x", resolver=_public_resolver) as client:
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
            with RagflowClient(api_endpoint="http://test", api_key="x", resolver=_public_resolver) as client:
                # 模拟一个会抛出异常的 API 调用(使用 requests 异常,会被 _request 捕获并转为 RagflowClientError)
                mock_session.request.side_effect = requests.exceptions.ConnectionError("Network error")
                client.list_datasets()
        except RagflowClientError:
            pass  # 预期会抛出 RagflowClientError

        # 即使发生异常,session 也应被关闭
        mock_session.close.assert_called_once()
        assert client._session is None


def _public_resolver(host, port, **kwargs):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port or 80))]


def test_client_rejects_restricted_endpoint_before_request():
    from ragflow_service.client import RagflowClient, RagflowClientError
    requester = MagicMock()
    with pytest.raises(RagflowClientError) as exc_info:
        RagflowClient("http://127.0.0.1:8080", "secret", requester=requester).list_datasets()
    assert exc_info.value.code == "unsafe_endpoint"
    assert "secret" not in str(exc_info.value)
    requester.assert_not_called()


def test_client_rejects_restricted_address_from_any_dns_result():
    from ragflow_service.client import RagflowClient, RagflowClientError
    def resolver(host, port, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port or 80)), (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.168.1.7", port or 80))]
    with pytest.raises(RagflowClientError) as exc_info:
        RagflowClient("http://rebind.example", "secret", resolver=resolver).list_datasets()
    assert exc_info.value.code == "unsafe_endpoint"


def test_client_disables_redirects_and_redacts_http_body():
    from ragflow_service.client import RagflowClient, RagflowClientError
    response = MagicMock()
    response.raise_for_status.side_effect = requests.HTTPError(response=response)
    response.status_code = 500
    response.text = "api_key=secret-body"
    requester = MagicMock(return_value=response)
    client = RagflowClient("https://example.com", "secret-header", resolver=_public_resolver, requester=requester)
    with pytest.raises(RagflowClientError) as exc_info:
        client.list_datasets()
    assert requester.call_args.kwargs["allow_redirects"] is False
    assert "secret-body" not in str(exc_info.value)
    assert "secret-header" not in str(exc_info.value)
    assert exc_info.value.code == "http_error"


def test_client_redacts_connection_exception():
    from ragflow_service.client import RagflowClient, RagflowClientError
    requester = MagicMock(side_effect=requests.ConnectionError("https://user:secret@example.com?q=token"))
    client = RagflowClient("https://example.com", "secret-header", resolver=_public_resolver, requester=requester)
    with pytest.raises(RagflowClientError) as exc_info:
        client.list_chats()
    assert exc_info.value.code == "request_error"
    assert "secret" not in str(exc_info.value)
    assert "example.com" not in str(exc_info.value)


def test_client_redacts_malformed_json_and_type_errors():
    from ragflow_service.client import RagflowClient, RagflowClientError
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.side_effect = ValueError("api_key=secret-body")
    requester = MagicMock(return_value=response)
    client = RagflowClient("https://example.com", "secret-header", resolver=_public_resolver, requester=requester)
    with pytest.raises(RagflowClientError) as exc_info:
        client.list_chats()
    assert exc_info.value.code == "response_error"
    assert str(exc_info.value) == "RAGFlow 响应格式错误。"
    assert "secret" not in str(exc_info.value)


def test_client_calls_shared_safe_request_for_health_chain():
    from ragflow_service.client import RagflowClient
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = {"data": []}
    requester = MagicMock(return_value=response)
    client = RagflowClient("https://example.com", "secret-header", resolver=_public_resolver, requester=requester)
    assert client.health_check() == {"status": "ok", "message": "连接成功"}
    requester.assert_called_once()


def test_safe_request_passes_method_to_session_request():
    from ragflow_service.client import RagflowClient
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = {"data": []}
    session = MagicMock()
    session.request.return_value = response
    with patch("ragflow_service.client.requests.Session", return_value=session):
        client = RagflowClient("https://example.com", "secret", resolver=_public_resolver)
        client.list_datasets()
    assert session.request.call_args.kwargs["method"] == "GET"
    assert session.request.call_args.kwargs["url"].startswith("https://example.com/")


def test_client_rejects_non_dict_json_response():
    from ragflow_service.client import RagflowClient, RagflowClientError
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = []
    requester = MagicMock(return_value=response)
    client = RagflowClient("https://example.com", "secret", resolver=_public_resolver, requester=requester)
    with pytest.raises(RagflowClientError) as exc_info:
        client.list_datasets()
    assert exc_info.value.code == "response_error"
