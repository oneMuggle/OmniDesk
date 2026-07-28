"""确定性 mock LLM 服务（OpenAI 兼容，仅标准库实现）。

为智能助手端到端测试提供一个线程内可启停的本地 HTTP 服务，
模拟 ``POST /v1/chat/completions``，使 CI 无需依赖真实 LLM
即可跑通「DB 端点配置 → LLMRouter 真实 HTTP 往返 → 对话视图」全链路。

确定性路由规则（按请求体中**最后一条 user message** 的文本关键词，
不使用任何随机行为）：

- 含 ``错误`` 或 ``fail``   → 返回 HTTP 500（模拟端点故障）
- 含 ``超时`` 或 ``timeout`` → 先 sleep ``timeout_delay`` 秒再响应
  （默认 121s，比 ``LLMRouter.REQUEST_TIMEOUT`` 默认值 120s 多 1s；
  单测中应配合 monkeypatch 缩小 router 超时并传入更小的 delay）
- 其他 → HTTP 200，固定回答 ``FIXED_ANSWER`` +
  固定 usage ``{prompt_tokens: 100, completion_tokens: 50, total_tokens: 150}``

请求体携带 ``"stream": true`` 时以 SSE 格式返回同一固定文本
（按 ~3 段切分 delta chunk，以 ``data: [DONE]`` 收尾）。

用法::

    with running_server() as llm:
        # llm.url          → http://127.0.0.1:<自动分配端口>
        # llm.request_count → 已收到的请求数（供断言重试次数）
        # llm.reset()       → 清零计数与请求记录
        ...

端口使用 0 由操作系统自动分配，避免并行测试冲突；服务线程为
daemon 线程，teardown 时先 ``shutdown()`` 再 ``server_close()``
并 join 线程，保证不泄漏。
"""

import json
import sys
import threading
import time
import uuid
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

__all__ = [
    "FIXED_ANSWER",
    "DEFAULT_USAGE",
    "DEFAULT_TIMEOUT_DELAY",
    "MockLLMHandler",
    "MockLLMService",
    "running_server",
]

# 固定回答文本：纯中文、不含工具名（ASCII snake_case），
# 保证意图分类结果不会误命中 ToolRegistry 中的任何工具。
FIXED_ANSWER = "这是来自模拟LLM服务的确定性回答"

# 固定 token 用量（供成本核算断言：150 tokens × 单价 / 1000）
DEFAULT_USAGE = {
    "prompt_tokens": 100,
    "completion_tokens": 50,
    "total_tokens": 150,
}

# 关键词路由表：中文按原文匹配，英文按小写匹配
ERROR_KEYWORDS = ("错误", "fail")
TIMEOUT_KEYWORDS = ("超时", "timeout")

# 超时场景默认睡眠秒数：比 LLMRouter.REQUEST_TIMEOUT 默认值（120s）多 1s。
# 测试中通常会 monkeypatch 缩小 router 超时，并显式传入更小的 delay。
DEFAULT_TIMEOUT_DELAY = 121.0

_COMPLETIONS_PATH = "/v1/chat/completions"


def _matches_keywords(content: str, keywords) -> bool:
    """关键词命中判断：中文原文匹配，英文小写匹配。"""
    lowered = content.lower()
    return any(kw in content for kw in keywords if not kw.isascii()) or any(
        kw in lowered for kw in keywords if kw.isascii()
    )


def _last_user_content(body: dict) -> str:
    """提取请求体 messages 数组中最后一条 user 消息的文本。"""
    for msg in reversed(body.get("messages") or []):
        if isinstance(msg, dict) and msg.get("role") == "user":
            return str(msg.get("content") or "")
    return ""


def _split_chunks(text: str, parts: int = 3):
    """把固定文本切成约 parts 段，用于 SSE delta chunk。"""
    size = max(1, -(-len(text) // parts))  # 向上取整的分段长度
    for i in range(0, len(text), size):
        yield text[i : i + size]


class MockLLMHandler(BaseHTTPRequestHandler):
    """OpenAI 兼容的确定性请求处理器。"""

    # HTTP/1.0：每请求结束后关闭连接，避免残留 keep-alive 线程
    protocol_version = "HTTP/1.0"

    # ------------------------------------------------------------------
    # 静音默认日志，保持测试输出干净
    # ------------------------------------------------------------------
    def log_message(self, format, *args):  # noqa: A002（签名沿用父类）
        pass

    # ------------------------------------------------------------------
    # 路由入口
    # ------------------------------------------------------------------
    def do_POST(self):  # noqa: N802（http.server 约定）
        state = self.server.mock_state
        try:
            if self.path != _COMPLETIONS_PATH:
                self._send_json(404, {"error": {"message": f"未知路径: {self.path}"}})
                return

            body = self._read_json_body()
            if body is None:
                self._send_json(400, {"error": {"message": "请求体不是合法 JSON"}})
                return

            content = _last_user_content(body)

            # 先登记请求（失败/超时请求同样计数，供重试次数断言）
            with state.lock:
                state.request_count += 1
                state.requests.append(
                    {
                        "path": self.path,
                        "model": body.get("model"),
                        "stream": bool(body.get("stream")),
                        "last_user_content": content,
                        "authorization": self.headers.get("Authorization"),
                    }
                )

            # 确定性关键词路由
            if _matches_keywords(content, ERROR_KEYWORDS):
                self._send_json(
                    500,
                    {
                        "error": {
                            "message": "mock LLM 内部错误（确定性触发）",
                            "type": "mock_error",
                            "code": "internal_error",
                        }
                    },
                )
                return

            if _matches_keywords(content, TIMEOUT_KEYWORDS):
                # 睡过 router 超时阈值后再响应；此时客户端多半已断开，
                # 后续写入异常会被外层 except 静默吞掉。
                time.sleep(state.timeout_delay)

            if body.get("stream"):
                self._send_sse(body)
            else:
                self._send_json(200, self._completion_body(body))
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            # 客户端因超时提前断开属预期行为
            pass
        except Exception as exc:  # 兜底：记录但不向测试输出打印栈
            with state.lock:
                state.last_error = repr(exc)

    # ------------------------------------------------------------------
    # 响应构造
    # ------------------------------------------------------------------
    def _read_json_body(self):
        """读取并解析 JSON 请求体；非法 JSON 返回 None。"""
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return None
        raw = self.rfile.read(length) if length > 0 else b""
        if not raw:
            return {}
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None

    @staticmethod
    def _completion_body(body: dict) -> dict:
        """构造非流式的 OpenAI 兼容完成响应（固定文本 + 固定 usage）。"""
        return {
            "id": f"chatcmpl-mock-{uuid.uuid4().hex[:8]}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": body.get("model") or "mock-model",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": FIXED_ANSWER},
                    "finish_reason": "stop",
                }
            ],
            "usage": dict(DEFAULT_USAGE),
        }

    def _send_sse(self, body: dict):
        """以 SSE 格式返回固定文本：若干 delta chunk + [DONE]。"""
        lines = []
        for piece in _split_chunks(FIXED_ANSWER):
            chunk = {
                "id": f"chatcmpl-mock-{uuid.uuid4().hex[:8]}",
                "object": "chat.completion.chunk",
                "model": body.get("model") or "mock-model",
                "choices": [{"index": 0, "delta": {"content": piece}, "finish_reason": None}],
            }
            lines.append(f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n")
        lines.append("data: [DONE]\n\n")
        payload = "".join(lines).encode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _send_json(self, status_code: int, payload: dict):
        """发送 JSON 响应。"""
        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


class _MockLLMHTTPServer(ThreadingHTTPServer):
    """每请求一个 daemon 线程；静默客户端断开导致的套接字异常。"""

    daemon_threads = True
    allow_reuse_address = True

    def handle_error(self, request, client_address):
        exc = sys.exc_info()[1]
        if isinstance(exc, (BrokenPipeError, ConnectionResetError, TimeoutError)):
            return  # 客户端超时断开属预期行为，不打印栈
        super().handle_error(request, client_address)


class MockLLMService:
    """线程内 mock LLM 服务的生命周期封装。

    属性：
        url:           服务根地址（如 ``http://127.0.0.1:54321``）
        request_count: 已收到的请求数（线程安全）
        requests:      请求明细列表（含 model/stream/last_user_content）
        last_error:    处理器兜底捕获的异常 repr（调试用）
        timeout_delay: 超时关键词命中后的睡眠秒数
    """

    def __init__(self, host: str = "127.0.0.1", timeout_delay: float = DEFAULT_TIMEOUT_DELAY):
        self.host = host
        self.timeout_delay = timeout_delay
        self.lock = threading.Lock()
        self.requests = []
        self.request_count = 0
        self.last_error = None
        # 端口 0：由操作系统自动分配空闲端口，避免并行测试冲突
        self._httpd = _MockLLMHTTPServer((host, 0), MockLLMHandler)
        self._httpd.mock_state = self
        self._thread = None

    # ------------------------------------------------------------------
    # 基础信息
    # ------------------------------------------------------------------
    @property
    def port(self) -> int:
        return self._httpd.server_address[1]

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}"

    @property
    def last_request(self):
        """最近一条请求明细（无请求时为 None）。"""
        with self.lock:
            return self.requests[-1] if self.requests else None

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------
    def start(self) -> "MockLLMService":
        """在 daemon 线程中启动服务（监听套接字在构造时已绑定）。"""
        self._thread = threading.Thread(
            target=self._httpd.serve_forever,
            name=f"mock-llm-{self.port}",
            daemon=True,
        )
        self._thread.start()
        return self

    def stop(self):
        """停止服务：shutdown 退出 serve_forever，关闭套接字并 join 线程。"""
        self._httpd.shutdown()
        self._httpd.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None

    def reset(self):
        """清零计数与请求记录（同一服务跨多个断言阶段复用）。"""
        with self.lock:
            self.requests.clear()
            self.request_count = 0
            self.last_error = None


@contextmanager
def running_server(host: str = "127.0.0.1", timeout_delay: float = DEFAULT_TIMEOUT_DELAY):
    """上下文管理器：启动 mock LLM 服务，退出时确保线程与端口释放。

    产出 ``MockLLMService`` 实例：``svc.url`` 为服务根地址，
    ``svc.request_count`` 可用于断言 router 的重试/降级次数。
    """
    service = MockLLMService(host=host, timeout_delay=timeout_delay).start()
    try:
        yield service
    finally:
        service.stop()
