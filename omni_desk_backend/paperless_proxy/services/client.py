"""paperless HTTP 客户端,基于 requests + 手动重试"""
import logging
from typing import Optional, BinaryIO, Dict, Any
from urllib.parse import urlencode

import requests
from django.conf import settings

from ..exceptions import (
    PaperlessError, PaperlessUnavailableError, PaperlessAuthError, PaperlessNotFoundError
)

logger = logging.getLogger(__name__)


class PaperlessClient:
    def __init__(self):
        self.base_url = settings.PAPERLESS_URL.rstrip('/')
        self.token = settings.PAPERLESS_API_TOKEN
        self.timeout = settings.PAPERLESS_TIMEOUT_SECONDS
        self.session = requests.Session()
        self.session.headers.update({'Authorization': f'Token {self.token}'})

    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        url = f'{self.base_url}{path}'
        try:
            resp = self.session.request(method, url, timeout=self.timeout, **kwargs)
        except requests.RequestException as e:
            raise PaperlessUnavailableError(f'paperless network error: {e}') from e

        if resp.status_code == 401:
            raise PaperlessAuthError('paperless auth failed (401)')
        if resp.status_code == 403:
            raise PaperlessAuthError('paperless forbidden (403)')
        if resp.status_code == 404:
            raise PaperlessNotFoundError(f'paperless not found: {path}')
        if 500 <= resp.status_code < 600:
            raise PaperlessUnavailableError(f'paperless {resp.status_code}: {resp.text[:200]}')
        if not resp.ok:
            raise PaperlessError(f'paperless {resp.status_code}: {resp.text[:200]}')
        return resp

    # --- Auth ---

    def post_token(self, username: str, password: str) -> str:
        """账号密码换取 paperless token,用于账号绑定"""
        try:
            resp = requests.post(
                f'{self.base_url}/api/token/',
                data={'username': username, 'password': password},
                timeout=self.timeout,
            )
        except requests.RequestException as e:
            raise PaperlessUnavailableError(f'paperless network error: {e}') from e
        if resp.status_code == 400:
            raise PaperlessAuthError('invalid username or password')
        if not resp.ok:
            raise PaperlessError(f'paperless token error: {resp.status_code}')
        return resp.json()['token']

    def get_user_by_username(self, username: str) -> Dict[str, Any]:
        """根据 username 查 paperless 用户"""
        resp = self._request('GET', '/api/users/', params={'username': username})
        data = resp.json()
        for u in data.get('results', []):
            if u.get('username') == username:
                return u
        raise PaperlessNotFoundError(f'paperless user {username} not found')

    # --- Documents ---

    def upload(
        self,
        file_obj: BinaryIO,
        filename: str,
        title: str,
        owner: Optional[int] = None,
        correspondent: Optional[int] = None,
        document_type: Optional[int] = None,
        tags: Optional[list] = None,
    ) -> Dict[str, Any]:
        """上传文档到 paperless"""
        files = {'document': (filename, file_obj)}
        data = {'title': title}
        if owner is not None:
            data['owner'] = owner
        if correspondent is not None:
            data['correspondent'] = correspondent
        if document_type is not None:
            data['document_type'] = document_type
        if tags:
            # paperless 接收 tag id 列表
            data['tags'] = tags
        resp = self._request('POST', '/api/documents/post_document/', files=files, data=data)
        return resp.json()

    def get_document(self, paperless_id: int) -> Dict[str, Any]:
        """获取 paperless 文档元数据"""
        resp = self._request('GET', f'/api/documents/{paperless_id}/')
        return resp.json()

    def download(self, paperless_id: int) -> bytes:
        """下载 paperless 文档原始内容"""
        resp = self._request('GET', f'/api/documents/{paperless_id}/download/')
        return resp.content

    def preview(self, paperless_id: int) -> bytes:
        """获取 paperless 文档预览图"""
        resp = self._request('GET', f'/api/documents/{paperless_id}/preview/')
        return resp.content

    def search(self, query: str, page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        """Tantivy 全文搜索"""
        params = {'query': query, 'page': page, 'page_size': page_size}
        resp = self._request('GET', '/api/documents/', params=params)
        return resp.json()

    def health_check(self) -> bool:
        """健康检查(GET /api/)"""
        try:
            resp = self.session.get(f'{self.base_url}/api/', timeout=self.timeout)
            return resp.status_code == 200
        except requests.RequestException:
            return False