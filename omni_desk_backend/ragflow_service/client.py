"""RAGFlow API 客户端封装。"""

import requests
from observability import get_logger
from smart_assistant.ssrf import UnsafeEndpointError, safe_request

logger = get_logger(__name__, "ragflow_service.client")


class RagflowClientError(Exception):
    """RAGFlow API 调用异常，消息只包含稳定的安全文案。"""

    MESSAGES = {
        "unsafe_endpoint": "RAGFlow 端点不安全。",
        "http_error": "RAGFlow 服务返回错误。",
        "request_error": "RAGFlow 服务暂时不可用。",
        "response_error": "RAGFlow 响应格式错误。",
    }

    def __init__(self, code: str):
        self.code = code if code in self.MESSAGES else "request_error"
        super().__init__(self.MESSAGES[self.code])


class RagflowClient:
    """RAGFlow API 客户端，复用 Session 并通过 SSRF 安全传输。"""

    def __init__(self, api_endpoint: str, api_key: str, timeout: int = 30, *, requester=None, resolver=None):
        self.base_url = api_endpoint.rstrip("/")
        self.timeout = timeout
        self.headers = {"Authorization": f"Bearer {api_key}"}
        self._session = requests.Session()
        self._session.headers.update(self.headers)
        self._requester = requester
        self._resolver = resolver

    def close(self):
        if hasattr(self, "_session") and self._session is not None:
            self._session.close()
            self._session = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    def _transport(self, url, method=None, **kwargs):
        if self._requester is not None:
            return self._requester(url, method=method, **kwargs)
        return self._session.request(method=method, url=url, **kwargs)

    def _request(self, method, path, json=None, files=None, timeout=None):
        url = f"{self.base_url}{path}"
        request_headers = dict(self.headers)
        if not files:
            request_headers["Content-Type"] = "application/json"
        try:
            response = safe_request(
                method,
                url,
                requester=lambda checked_url, **request_kwargs: self._transport(
                    checked_url, method=method, **request_kwargs
                ),
                resolver=self._resolver,
                headers=request_headers,
                json=json,
                files=files,
                timeout=timeout or self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise TypeError("RAGFlow response must be an object")
            return payload
        except UnsafeEndpointError as exc:
            logger.warning("RAGFlow 请求端点校验失败: type=%s", type(exc).__name__)
            raise RagflowClientError("unsafe_endpoint") from exc
        except requests.exceptions.HTTPError as exc:
            status_code = getattr(getattr(exc, "response", None), "status_code", None)
            logger.error("RAGFlow HTTP 请求失败: type=%s status=%s", type(exc).__name__, status_code)
            raise RagflowClientError("http_error") from exc
        except requests.exceptions.RequestException as exc:
            logger.error("RAGFlow 网络请求失败: type=%s", type(exc).__name__)
            raise RagflowClientError("request_error") from exc
        except (ValueError, TypeError, AttributeError) as exc:
            logger.error("RAGFlow 响应解析失败: type=%s", type(exc).__name__)
            raise RagflowClientError("response_error") from exc

    def list_datasets(self, page=1, page_size=30):
        return self._request("GET", f"/api/v1/datasets?page={page}&page_size={page_size}").get("data", [])

    def create_dataset(self, name, **kwargs):
        return self._request("POST", "/api/v1/datasets", json={"name": name, **kwargs}).get("data", {})

    def delete_dataset(self, dataset_id):
        self._request("DELETE", f"/api/v1/datasets/{dataset_id}")
        return True

    def list_documents(self, dataset_id, page=1, page_size=30):
        result = self._request("GET", f"/api/v1/datasets/{dataset_id}/documents?page={page}&page_size={page_size}")
        return result.get("data", {}).get("docs", [])

    def upload_document(self, dataset_id, file_name, file_content):
        return self._request(
            "POST", f"/api/v1/datasets/{dataset_id}/documents", files={"file": (file_name, file_content)}
        ).get("data", {})

    def delete_document(self, dataset_id, document_ids):
        self._request("DELETE", f"/api/v1/datasets/{dataset_id}/documents", json={"ids": document_ids})
        return True

    def parse_documents(self, dataset_id, document_ids):
        self._request("POST", f"/api/v1/datasets/{dataset_id}/chunks", json={"document_ids": document_ids})
        return True

    def stop_parsing(self, dataset_id, document_ids):
        self._request(
            "POST", f"/api/v1/datasets/{dataset_id}/chunks", json={"document_ids": document_ids, "action": "cancel"}
        )
        return True

    def retrieval(self, dataset_ids, question, top_k=5, similarity_threshold=0.2, vector_similarity_weight=0.3):
        result = self._request(
            "POST",
            "/api/v1/retrieval",
            json={
                "question": question,
                "dataset_ids": dataset_ids,
                "top_k": top_k,
                "similarity_threshold": similarity_threshold,
                "vector_similarity_weight": vector_similarity_weight,
            },
        )
        return result.get("data", {}).get("chunks", [])

    def list_chats(self, page=1, page_size=30):
        return self._request("GET", f"/api/v1/chats?page={page}&page_size={page_size}").get("data", [])

    def create_chat(self, name, dataset_ids, llm_model=None, **kwargs):
        payload = {"name": name, "dataset_ids": dataset_ids, **kwargs}
        if llm_model:
            payload["llm"] = {"model_name": llm_model}
        return self._request("POST", "/api/v1/chats", json=payload).get("data", {})

    def chat_completion(self, chat_id, question, stream=False, **kwargs):
        return self._request(
            "POST", f"/api/v1/chats/{chat_id}/completions", json={"question": question, "stream": stream, **kwargs}
        ).get("data", {})

    def health_check(self):
        try:
            self.list_datasets(page=1, page_size=1)
            return {"status": "ok", "message": "连接成功"}
        except RagflowClientError as exc:
            logger.warning("RAGFlow 健康检查失败: code=%s", exc.code)
            return {"status": "error", "message": "RAGFlow 服务暂时不可用。"}
        except Exception as exc:
            logger.error("RAGFlow 健康检查失败: type=%s", type(exc).__name__)
            return {"status": "error", "message": "RAGFlow 服务暂时不可用。"}
