"""RAGFlow API 客户端封装。

统一封装 RAGFlow 的 HTTP API 调用，提供类型安全的接口。
"""

import logging

import requests

logger = logging.getLogger(__name__)


class RagflowClientError(Exception):
    """RAGFlow API 调用异常。"""

    pass


class RagflowClient:
    """RAGFlow API 客户端。

    封装所有与 RAGFlow 服务器的 HTTP 交互。

    Usage:
        client = RagflowClient("http://ragflow:80", "your-api-key")
        datasets = client.list_datasets()
        client.chat_completion("chat-id", "question")
    """

    def __init__(self, api_endpoint: str, api_key: str, timeout: int = 30):
        """初始化 RAGFlow 客户端。

        Args:
            api_endpoint: RAGFlow API 端点（如 http://ragflow:80）
            api_key: RAGFlow API 密钥
            timeout: HTTP 请求超时时间（秒）
        """
        self.base_url = api_endpoint.rstrip("/")
        self.timeout = timeout
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        # 使用 requests.Session 复用 TCP 连接,降低多次请求的 TTFB
        self._session = requests.Session()
        self._session.headers.update(self.headers)

    def close(self):
        """关闭底层 HTTP session,释放连接资源。

        应在客户端不再使用时调用,特别是在长时间运行的应用中。
        也可使用 context manager (with statement) 自动管理。
        """
        if hasattr(self, "_session") and self._session is not None:
            self._session.close()
            self._session = None

    def __enter__(self):
        """支持 with statement 上下文管理器。"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出 with block 时自动关闭 session。"""
        self.close()
        return False  # 不抑制异常

    def _request(
        self,
        method: str,
        path: str,
        json: dict | None = None,
        files: dict | None = None,
        timeout: int | None = None,
    ) -> dict:
        """发送 HTTP 请求。

        Args:
            method: HTTP 方法（GET/POST/DELETE）
            path: API 路径（如 /api/v1/datasets）
            json: JSON 请求体
            files: 文件上传（multipart/form-data）
            timeout: 请求超时（覆盖默认值）

        Returns:
            RAGFlow API 响应（JSON 解析后的 dict）

        Raises:
            RagflowClientError: API 调用失败
        """
        url = f"{self.base_url}{path}"
        # 文件上传时临时移除 Content-Type,让 requests 自动设置 multipart boundary
        extra_headers = {}
        if files:
            extra_headers["Content-Type"] = None

        try:
            response = self._session.request(
                method=method,
                url=url,
                headers=extra_headers or None,
                json=json,
                files=files,
                timeout=timeout or self.timeout,
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            error_msg = f"RAGFlow API 错误: {e.response.status_code} - {e.response.text}"
            logger.error(error_msg)
            raise RagflowClientError(error_msg) from e
        except requests.exceptions.RequestException as e:
            error_msg = f"RAGFlow 请求失败: {e}"
            logger.error(error_msg)
            raise RagflowClientError(error_msg) from e

    # ── Dataset 管理 ──────────────────────────────────────────

    def list_datasets(self, page: int = 1, page_size: int = 30) -> list[dict]:
        """列出所有数据集。

        Args:
            page: 页码
            page_size: 每页数量

        Returns:
            数据集列表，每个元素包含 id、name 等字段
        """
        result = self._request("GET", f"/api/v1/datasets?page={page}&page_size={page_size}")
        return result.get("data", [])

    def create_dataset(self, name: str, **kwargs) -> dict:
        """创建新数据集。

        Args:
            name: 数据集名称
            **kwargs: 其他可选参数（如 description、parser_id 等）

        Returns:
            创建的数据集信息
        """
        payload = {"name": name, **kwargs}
        result = self._request("POST", "/api/v1/datasets", json=payload)
        return result.get("data", {})

    def delete_dataset(self, dataset_id: str) -> bool:
        """删除数据集。

        Args:
            dataset_id: 数据集 ID

        Returns:
            是否删除成功
        """
        self._request("DELETE", f"/api/v1/datasets/{dataset_id}")
        return True

    # ── 文档管理 ──────────────────────────────────────────────

    def list_documents(self, dataset_id: str, page: int = 1, page_size: int = 30) -> list[dict]:
        """列出数据集内的文档。

        Args:
            dataset_id: 数据集 ID
            page: 页码
            page_size: 每页数量

        Returns:
            文档列表
        """
        result = self._request("GET", f"/api/v1/datasets/{dataset_id}/documents?page={page}&page_size={page_size}")
        return result.get("data", {}).get("docs", [])

    def upload_document(self, dataset_id: str, file_name: str, file_content: bytes) -> dict:
        """上传文档到数据集。

        Args:
            dataset_id: 数据集 ID
            file_name: 文件名
            file_content: 文件内容（字节）

        Returns:
            上传结果，包含文档 ID
        """
        files = {"file": (file_name, file_content)}
        result = self._request("POST", f"/api/v1/datasets/{dataset_id}/documents", files=files)
        return result.get("data", {})

    def delete_document(self, dataset_id: str, document_ids: list[str]) -> bool:
        """删除文档。

        Args:
            dataset_id: 数据集 ID
            document_ids: 文档 ID 列表

        Returns:
            是否删除成功
        """
        self._request(
            "DELETE",
            f"/api/v1/datasets/{dataset_id}/documents",
            json={"ids": document_ids},
        )
        return True

    def parse_documents(self, dataset_id: str, document_ids: list[str]) -> bool:
        """触发文档解析（向量化）。

        Args:
            dataset_id: 数据集 ID
            document_ids: 文档 ID 列表

        Returns:
            是否触发成功
        """
        self._request(
            "POST",
            f"/api/v1/datasets/{dataset_id}/chunks",
            json={"document_ids": document_ids},
        )
        return True

    def stop_parsing(self, dataset_id: str, document_ids: list[str]) -> bool:
        """停止文档解析。

        Args:
            dataset_id: 数据集 ID
            document_ids: 文档 ID 列表

        Returns:
            是否停止成功
        """
        self._request(
            "POST",
            f"/api/v1/datasets/{dataset_id}/chunks",
            json={"document_ids": document_ids, "action": "cancel"},
        )
        return True

    # ── 检索 ──────────────────────────────────────────────────

    def retrieval(
        self,
        dataset_ids: list[str],
        question: str,
        top_k: int = 5,
        similarity_threshold: float = 0.2,
        vector_similarity_weight: float = 0.3,
    ) -> list[dict]:
        """从指定数据集检索文本块。

        Args:
            dataset_ids: 数据集 ID 列表
            question: 查询问题
            top_k: 返回的最相关文本块数量
            similarity_threshold: 相似度阈值
            vector_similarity_weight: 向量相似度权重（0-1，剩余为关键词权重）

        Returns:
            检索到的文本块列表，每个元素包含 content、document_name、similarity 等
        """
        payload = {
            "question": question,
            "dataset_ids": dataset_ids,
            "top_k": top_k,
            "similarity_threshold": similarity_threshold,
            "vector_similarity_weight": vector_similarity_weight,
        }
        result = self._request("POST", "/api/v1/retrieval", json=payload)
        chunks = result.get("data", {}).get("chunks", [])
        return chunks

    # ── Chat Assistant ────────────────────────────────────────

    def list_chats(self, page: int = 1, page_size: int = 30) -> list[dict]:
        """列出所有聊天助手。

        Args:
            page: 页码
            page_size: 每页数量

        Returns:
            聊天助手列表
        """
        result = self._request("GET", f"/api/v1/chats?page={page}&page_size={page_size}")
        return result.get("data", [])

    def create_chat(
        self,
        name: str,
        dataset_ids: list[str],
        llm_model: str | None = None,
        **kwargs,
    ) -> dict:
        """创建聊天助手。

        Args:
            name: 聊天助手名称
            dataset_ids: 绑定的数据集 ID 列表
            llm_model: LLM 模型名称（可选，使用 RAGFlow 默认）
            **kwargs: 其他可选参数（如 prompt、greeting 等）

        Returns:
            创建的聊天助手信息，包含 id
        """
        payload = {"name": name, "dataset_ids": dataset_ids, **kwargs}
        if llm_model:
            payload["llm"] = {"model_name": llm_model}
        result = self._request("POST", "/api/v1/chats", json=payload)
        return result.get("data", {})

    def chat_completion(
        self,
        chat_id: str,
        question: str,
        stream: bool = False,
        **kwargs,
    ) -> dict:
        """与聊天助手对话。

        Args:
            chat_id: 聊天助手 ID
            question: 用户问题
            stream: 是否流式返回（暂不支持，预留）
            **kwargs: 其他可选参数（如 conversation_id）

        Returns:
            对话结果，包含 answer 字段
        """
        payload = {"question": question, "stream": stream, **kwargs}
        result = self._request("POST", f"/api/v1/chats/{chat_id}/completions", json=payload)
        return result.get("data", {})

    # ── 健康检查 ──────────────────────────────────────────────

    def health_check(self) -> dict:
        """检查 RAGFlow 服务连接状态。

        Returns:
            {"status": "ok"|"error", "message": "..."}
        """
        try:
            self.list_datasets(page=1, page_size=1)
            return {"status": "ok", "message": "连接成功"}
        except RagflowClientError as e:
            return {"status": "error", "message": str(e)}
        except Exception as e:
            return {"status": "error", "message": f"未知错误: {e}"}
