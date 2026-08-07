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
    "TOOL_CALL_SCENARIOS",
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

# ---------------------------------------------------------------------------
# Tool Calling 场景字典(Task 10)
# ---------------------------------------------------------------------------
# 当请求体携带 ``tools`` 且最后一条 user message 文本命中下面任一关键字时,
# 按 ``call_count`` 取预设场景的第 N 段响应(让 orchestrator 端到端跑通
# "工具调用决策 -> tool_calls -> 工具执行 -> 自然语言回复" 链路)。
#
# 每个场景至少含 1 段响应(``finish_reason="tool_calls"``);
# 可选追加第 2 段(``finish_reason="stop"``,纯文本回复),
# 模拟"工具结果回灌给 LLM 后,模型基于结果生成自然语言"的多轮流程。
#
# 覆盖工具维度:**至少 5 个**(schedule / personnel / rag / memo / news),
# 与 ToolRegistry 真实工具集对齐,便于 E2E 验证 router + orchestrator 链路。
# ---------------------------------------------------------------------------
TOOL_CALL_SCENARIOS = {
    "明天排班": [
        {
            "id": "chatcmpl-mock-tool-001",
            "choices": [{
                "index": 0,
                "finish_reason": "tool_calls",
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{
                        "id": "call_mock_schedule_001",
                        "type": "function",
                        "function": {
                            "name": "schedule_query",
                            "arguments": json.dumps({"query": "明天"}),
                        },
                    }],
                },
            }],
            "usage": dict(DEFAULT_USAGE),
        },
        {
            "id": "chatcmpl-mock-tool-002",
            "choices": [{
                "index": 0,
                "finish_reason": "stop",
                "message": {
                    "role": "assistant",
                    "content": "明天是张三早班(08:00-16:00)。",
                    "tool_calls": None,
                },
            }],
            "usage": dict(DEFAULT_USAGE),
        },
    ],
    "张三": [
        {
            "id": "chatcmpl-mock-tool-003",
            "choices": [{
                "index": 0,
                "finish_reason": "tool_calls",
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{
                        "id": "call_mock_personnel_001",
                        "type": "function",
                        "function": {
                            "name": "personnel_query",
                            "arguments": json.dumps({"name": "张三"}),
                        },
                    }],
                },
            }],
            "usage": dict(DEFAULT_USAGE),
        },
        {
            "id": "chatcmpl-mock-tool-004",
            "choices": [{
                "index": 0,
                "finish_reason": "stop",
                "message": {
                    "role": "assistant",
                    "content": "张三属于研发部,岗位为高级工程师。",
                    "tool_calls": None,
                },
            }],
            "usage": dict(DEFAULT_USAGE),
        },
    ],
    "哪个部门": [
        {
            "id": "chatcmpl-mock-tool-005",
            "choices": [{
                "index": 0,
                "finish_reason": "tool_calls",
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{
                        "id": "call_mock_personnel_002",
                        "type": "function",
                        "function": {
                            "name": "personnel_query",
                            "arguments": json.dumps({"name": "李四"}),
                        },
                    }],
                },
            }],
            "usage": dict(DEFAULT_USAGE),
        },
    ],
    "报销制度": [
        {
            "id": "chatcmpl-mock-tool-006",
            "choices": [{
                "index": 0,
                "finish_reason": "tool_calls",
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{
                        "id": "call_mock_rag_001",
                        "type": "function",
                        "function": {
                            "name": "rag_query",
                            "arguments": json.dumps({"query": "公司报销制度流程"}),
                        },
                    }],
                },
            }],
            "usage": dict(DEFAULT_USAGE),
        },
        {
            "id": "chatcmpl-mock-tool-007",
            "choices": [{
                "index": 0,
                "finish_reason": "stop",
                "message": {
                    "role": "assistant",
                    "content": "根据公司手册,差旅需事前申请,事后凭票据在 5 个工作日内提交报销。",
                    "tool_calls": None,
                },
            }],
            "usage": dict(DEFAULT_USAGE),
        },
    ],
    "备忘录": [
        {
            "id": "chatcmpl-mock-tool-008",
            "choices": [{
                "index": 0,
                "finish_reason": "tool_calls",
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{
                        "id": "call_mock_memo_001",
                        "type": "function",
                        "function": {
                            "name": "memo_query",
                            "arguments": json.dumps({"query": "上周待办"}),
                        },
                    }],
                },
            }],
            "usage": dict(DEFAULT_USAGE),
        },
    ],
    "新闻": [
        {
            "id": "chatcmpl-mock-tool-009",
            "choices": [{
                "index": 0,
                "finish_reason": "tool_calls",
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{
                        "id": "call_mock_news_001",
                        "type": "function",
                        "function": {
                            "name": "news_query",
                            "arguments": json.dumps({"query": "今天公司新闻"}),
                        },
                    }],
                },
            }],
            "usage": dict(DEFAULT_USAGE),
        },
        {
            "id": "chatcmpl-mock-tool-010",
            "choices": [{
                "index": 0,
                "finish_reason": "stop",
                "message": {
                    "role": "assistant",
                    "content": "今天的头条:公司年会定档下月 15 日。",
                    "tool_calls": None,
                },
            }],
            "usage": dict(DEFAULT_USAGE),
        },
    ],
    # --- Task 11 E2E 新增场景(仅追加,不破坏现有场景) ---
    # 两工具并行:第一轮同时调 schedule_query + memo_query,第二轮自然语言总结
    "本周安排": [
        {
            "id": "chatcmpl-mock-tool-011",
            "choices": [{
                "index": 0,
                "finish_reason": "tool_calls",
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_mock_schedule_002",
                            "type": "function",
                            "function": {
                                "name": "schedule_query",
                                "arguments": json.dumps({"query": "本周"}),
                            },
                        },
                        {
                            "id": "call_mock_memo_002",
                            "type": "function",
                            "function": {
                                "name": "memo_query",
                                "arguments": json.dumps({"query": "本周待办"}),
                            },
                        },
                    ],
                },
            }],
            "usage": dict(DEFAULT_USAGE),
        },
        {
            "id": "chatcmpl-mock-tool-012",
            "choices": [{
                "index": 0,
                "finish_reason": "stop",
                "message": {
                    "role": "assistant",
                    "content": "本周安排:排班 3 人次,待办备忘录 2 条,详见汇总卡片。",
                    "tool_calls": None,
                },
            }],
            "usage": dict(DEFAULT_USAGE),
        },
    ],
    # 参数非法:第一轮 arguments 不是合法 JSON → orchestrator 注入 invalid_arguments
    # 第二轮 LLM 修正为合法参数 → 第三轮自然语言回答
    "乱码参数": [
        {
            "id": "chatcmpl-mock-tool-013",
            "choices": [{
                "index": 0,
                "finish_reason": "tool_calls",
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{
                        "id": "call_mock_bad_args_001",
                        "type": "function",
                        "function": {
                            "name": "schedule_query",
                            "arguments": "这不是合法JSON",
                        },
                    }],
                },
            }],
            "usage": dict(DEFAULT_USAGE),
        },
        {
            "id": "chatcmpl-mock-tool-014",
            "choices": [{
                "index": 0,
                "finish_reason": "tool_calls",
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{
                        "id": "call_mock_bad_args_002",
                        "type": "function",
                        "function": {
                            "name": "schedule_query",
                            "arguments": json.dumps({"query": "明天"}),
                        },
                    }],
                },
            }],
            "usage": dict(DEFAULT_USAGE),
        },
        {
            "id": "chatcmpl-mock-tool-015",
            "choices": [{
                "index": 0,
                "finish_reason": "stop",
                "message": {
                    "role": "assistant",
                    "content": "参数已修正,排班查询完成。",
                    "tool_calls": None,
                },
            }],
            "usage": dict(DEFAULT_USAGE),
        },
    ],
    # 越权工具:第一轮调到未注册的 admin_only_tool → orchestrator 注入 unavailable
    # 第二轮 LLM 换用已注册的 schedule_query → 第三轮自然语言回答
    "管理员操作": [
        {
            "id": "chatcmpl-mock-tool-016",
            "choices": [{
                "index": 0,
                "finish_reason": "tool_calls",
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{
                        "id": "call_mock_admin_001",
                        "type": "function",
                        "function": {
                            "name": "admin_only_tool",
                            "arguments": json.dumps({"action": "delete"}),
                        },
                    }],
                },
            }],
            "usage": dict(DEFAULT_USAGE),
        },
        {
            "id": "chatcmpl-mock-tool-017",
            "choices": [{
                "index": 0,
                "finish_reason": "tool_calls",
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{
                        "id": "call_mock_admin_002",
                        "type": "function",
                        "function": {
                            "name": "schedule_query",
                            "arguments": json.dumps({"query": "明天"}),
                        },
                    }],
                },
            }],
            "usage": dict(DEFAULT_USAGE),
        },
        {
            "id": "chatcmpl-mock-tool-018",
            "choices": [{
                "index": 0,
                "finish_reason": "stop",
                "message": {
                    "role": "assistant",
                    "content": "已改用排班查询完成。",
                    "tool_calls": None,
                },
            }],
            "usage": dict(DEFAULT_USAGE),
        },
    ],
    # 死循环:每一轮都返回 tool_calls(共 3 段),超出后回退固定文本
    # 供 orchestrator 的 MAX_TOOL_CALLS_ROUNDS=3 兜底(强制 tool_choice="none")使用
    "永远查询": [
        {
            "id": "chatcmpl-mock-tool-019",
            "choices": [{
                "index": 0,
                "finish_reason": "tool_calls",
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{
                        "id": "call_mock_loop_001",
                        "type": "function",
                        "function": {
                            "name": "schedule_query",
                            "arguments": json.dumps({"query": "loop"}),
                        },
                    }],
                },
            }],
            "usage": dict(DEFAULT_USAGE),
        },
        {
            "id": "chatcmpl-mock-tool-020",
            "choices": [{
                "index": 0,
                "finish_reason": "tool_calls",
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{
                        "id": "call_mock_loop_002",
                        "type": "function",
                        "function": {
                            "name": "schedule_query",
                            "arguments": json.dumps({"query": "loop"}),
                        },
                    }],
                },
            }],
            "usage": dict(DEFAULT_USAGE),
        },
        {
            "id": "chatcmpl-mock-tool-021",
            "choices": [{
                "index": 0,
                "finish_reason": "tool_calls",
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{
                        "id": "call_mock_loop_003",
                        "type": "function",
                        "function": {
                            "name": "schedule_query",
                            "arguments": json.dumps({"query": "loop"}),
                        },
                    }],
                },
            }],
            "usage": dict(DEFAULT_USAGE),
        },
    ],
}


def _assistant_tool_calls_round(body: dict) -> int:
    """根据请求体推断当前是第几轮 tool_calls 调用(从 0 开始)。

    orchestrator 每执行完一轮,会向 ``messages`` 追加一条携带
    ``tool_calls`` 的 assistant 消息 + 若干 tool 结果消息。因此
    "已出现的 assistant tool_calls 消息条数"即当前请求应命中的轮次:
    首轮请求 0 条 → 返回场景第 0 段;第二轮请求 1 条 → 场景第 1 段。
    """
    rounds = 0
    for msg in body.get("messages") or []:
        if isinstance(msg, dict) and msg.get("role") == "assistant" and msg.get("tool_calls"):
            rounds += 1
    return rounds


def _select_scenario(body: dict, call_count: int = 0):
    """根据 query 关键字与请求轮次选择预设 tool_calls 场景。

    仅当请求体携带 ``tools`` 且最后一条 user message 文本命中
    :data:`TOOL_CALL_SCENARIOS` 任一关键字时,返回该场景第 ``call_count``
    段响应;否则返回 ``None``(交给调用方走原有 keyword 路由)。

    ``call_count`` 由调用方传入;默认 0 保持单轮语义。orchestrator 的
    多轮请求会携带已出现的 assistant tool_calls 消息,调用方应通过
    :func:`_assistant_tool_calls_round` 计算真实轮次,让场景按
    tool_calls → ... → 自然语言逐段推进。

    Args:
        body:  OpenAI 风格 chat completion 请求体(含 ``messages`` / ``tools``)
        call_count: 当前会话中针对该关键字的累计请求次数(从 0 开始),
            用于在多轮调用中依次返回 tool_calls → 自然语言等不同段。
            当 ``call_count`` 超出场景长度时返回 ``None``(回到兜底)。

    Returns:
        OpenAI 兼容的 completion 响应 dict,或在无匹配场景时返回 ``None``。
    """
    # 未带 tools 参数 -> 不命中场景(让下游走标准文本回复路径)
    if not body.get("tools"):
        return None

    content = _last_user_content(body)
    for keyword, scenario in TOOL_CALL_SCENARIOS.items():
        if keyword in content and 0 <= call_count < len(scenario):
            return scenario[call_count]
    return None


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

            # Task 10/11: 优先看 tool_calls 场景。call_count 由请求体中
            # 已出现的 assistant tool_calls 消息条数推断(每执行完一轮,
            # orchestrator 会追加一条 assistant tool_calls 消息),让场景
            # 按 tool_calls → ... → 自然语言逐段推进,而非永远命中第 0 段。
            call_count = _assistant_tool_calls_round(body)
            scenario_response = _select_scenario(body, call_count=call_count)
            if scenario_response is not None:
                if body.get("stream"):
                    # 工具调用场景暂不提供流式返回 -> 退回标准文本回复
                    # (与 `_completion_body` 行为保持一致)
                    self._send_json(200, self._completion_body(body))
                else:
                    self._send_json(200, scenario_response)
                return

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
