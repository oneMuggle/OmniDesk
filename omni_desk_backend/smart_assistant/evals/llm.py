"""LLM 拦截点：所有 LLM 请求都经过 ``llm_service.router`` 里的 ``safe_request`` /
``safe_internal_request``，评估期间替换这两个函数。

- 剧本模式：``ScriptedLLM`` 按当前用例的剧本作答（不发任何网络请求）；
- 真模型模式：``passthrough`` 原样转发给真实端点（SSRF 校验照旧），同时记录。

两种模式都把每次请求记进 ``LlmRecorder``，供安全判定（发给模型的数据里有没有越权标记）
与性能统计（调用次数、耗时、token）使用。
"""

from __future__ import annotations

import json
import re
import time
from contextlib import contextmanager
from dataclasses import dataclass, field

INTENT_MARK = "你是一个意图分类器"
PLAN_MARK = "你是一个工具链规划器"
# 写工具的参数提取器（memo_extractor / swap_request_extractor / 通用参数提取器）
EXTRACT_MARKS = ("_extractor,负责", "你是参数提取器")
SCRIPTED_PREFIX = "【剧本回答】"
_PLACEHOLDER_RE = re.compile(r"^\{(\w+)\}$")
_INLINE_PLACEHOLDER_RE = re.compile(r"\{(\w+)\}")


@dataclass
class LlmCall:
    url: str
    body: dict
    elapsed_ms: int = 0
    status: int | None = None
    usage: dict = field(default_factory=dict)
    error: str = ""
    kind: str = ""  # tools / intent / plan / extract / answer

    @property
    def is_fallback(self) -> bool:
        return "localhost:11434" in self.url

    def request_text(self) -> str:
        try:
            return json.dumps(self.body, ensure_ascii=False, default=str)
        except (TypeError, ValueError):
            return str(self.body)


class LlmRecorder:
    """记录一条用例期间的全部 LLM 请求。"""

    def __init__(self):
        self.calls: list[LlmCall] = []

    def reset(self):
        self.calls = []

    def total_tokens(self) -> int:
        return sum(int((c.usage or {}).get("total_tokens") or 0) for c in self.calls)


class FakeResponse:
    """最小化的 ``requests.Response`` 替身：router 只用到下面这些成员。"""

    def __init__(self, payload: dict | None = None, *, status_code: int = 200, lines: list | None = None):
        self._payload = payload or {}
        self.status_code = status_code
        self._lines = lines

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests

            raise requests.HTTPError(f"{self.status_code} 评估模拟错误", response=self)

    def json(self):
        return self._payload

    @property
    def text(self):
        return json.dumps(self._payload, ensure_ascii=False)

    def iter_lines(self):
        yield from self._lines or []

    def close(self):
        return None


def _usage_for(body: dict, content: str) -> dict:
    prompt = len(json.dumps(body.get("messages") or [], ensure_ascii=False))
    prompt_tokens = max(1, prompt // 2)
    completion_tokens = max(1, len(content or "") // 2)
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
    }


def _completion(body: dict, content: str = "", tool_calls: list | None = None) -> dict:
    message = {"role": "assistant", "content": content}
    if tool_calls:
        message["tool_calls"] = tool_calls
    return {
        "id": "eval-scripted",
        "object": "chat.completion",
        "model": body.get("model") or "scripted-model",
        "choices": [
            {"index": 0, "message": message, "finish_reason": "tool_calls" if tool_calls else "stop"},
        ],
        "usage": _usage_for(body, content or json.dumps(tool_calls or [], ensure_ascii=False)),
    }


def _sse_lines(body: dict, content: str) -> list:
    lines = []
    step = max(1, len(content) // 3) if content else 1
    for i in range(0, len(content), step):
        chunk = {"choices": [{"index": 0, "delta": {"content": content[i : i + step]}}]}
        lines.append(("data: " + json.dumps(chunk, ensure_ascii=False)).encode("utf-8"))
    usage = {"choices": [], "usage": _usage_for(body, content)}
    lines.append(("data: " + json.dumps(usage, ensure_ascii=False)).encode("utf-8"))
    lines.append(b"data: [DONE]")
    return lines


def _message_texts(body: dict) -> list:
    texts = []
    for msg in body.get("messages") or []:
        if isinstance(msg, dict) and isinstance(msg.get("content"), str):
            texts.append(msg["content"])
    if isinstance(body.get("prompt"), str):
        texts.append(body["prompt"])
    return texts


def classify_request(body: dict) -> str:
    """判断 router 发出的是哪类请求：tools / intent / plan / extract / answer。"""
    if body.get("tools"):
        return "tools"
    joined = "\n".join(_message_texts(body))
    if INTENT_MARK in joined:
        return "intent"
    if PLAN_MARK in joined:
        return "plan"
    if any(mark in joined for mark in EXTRACT_MARKS):
        return "extract"
    return "answer"


class ScriptedLLM:
    """按当前用例剧本作答的模拟 LLM。

    - 带 ``tools`` 的请求：按剧本逐轮返回 ``tool_calls``；剧本用完后给最终回答。
    - 意图分类：返回 ``script.intent``；工具链规划：返回 ``script.plan``（默认 ``[]``）；
      写工具的参数提取：返回 ``script.extract``（JSON 对象）。
    - 其他请求（回答生成、汇总）：把收到的全部内容原样回显——即「最坏的模型」：
      工具交给模型的任何数据都会被原样说给用户。
    """

    def __init__(self, objects: dict | None = None):
        self.case = None
        self.objects = objects or {}

    def set_case(self, case):
        self.case = case

    def _resolve_value(self, value):
        """``{key}`` 替换为种子对象（整串占位保留原类型，如 id；嵌在文字里时按字符串替换）。"""
        if isinstance(value, str):
            m = _PLACEHOLDER_RE.match(value)
            if m and m.group(1) in self.objects:
                return self.objects[m.group(1)]
            return _INLINE_PLACEHOLDER_RE.sub(
                lambda mm: str(self.objects[mm.group(1)]) if mm.group(1) in self.objects else mm.group(0), value
            )
        if isinstance(value, list):
            return [self._resolve_value(v) for v in value]
        if isinstance(value, dict):
            return {k: self._resolve_value(v) for k, v in value.items()}
        return value

    def _resolve_args(self, args: dict) -> dict:
        resolved = {key: self._resolve_value(value) for key, value in (args or {}).items()}
        if "query" not in resolved and self.case is not None:
            resolved["query"] = self.case.question
        return resolved

    @staticmethod
    def _tool_rounds_done(body: dict) -> int:
        return sum(
            1
            for m in body.get("messages") or []
            if isinstance(m, dict) and m.get("role") == "assistant" and m.get("tool_calls")
        )

    def _echo(self, body: dict) -> str:
        script_answer = self.case.script.answer if self.case is not None else ""
        parts = [SCRIPTED_PREFIX + (script_answer or "以下是根据工具结果整理的回答。")]
        for msg in body.get("messages") or []:
            if not isinstance(msg, dict):
                continue
            # 最坏情况：模型把收到的一切（系统提示、工具结果、合成提示）原样复述给用户
            if msg.get("role") != "assistant" and isinstance(msg.get("content"), str):
                parts.append(msg["content"])
        if isinstance(body.get("prompt"), str):
            parts.append(body["prompt"])
        return "\n".join(parts)

    def content_for(self, body: dict) -> tuple[str, list | None, str]:
        """返回 ``(content, tool_calls, kind)``。"""
        kind = classify_request(body)
        script = self.case.script if self.case is not None else None
        if kind == "tools":
            done = self._tool_rounds_done(body)
            rounds = script.rounds if script else ()
            if done < len(rounds):
                calls = [
                    {
                        "id": f"call_{done}_{i}",
                        "type": "function",
                        "function": {
                            "name": step.name,
                            "arguments": json.dumps(self._resolve_args(step.args), ensure_ascii=False),
                        },
                    }
                    for i, step in enumerate(rounds[done])
                ]
                return "", calls, kind
            return self._echo(body), None, kind
        if kind == "intent":
            return (script.intent if script else "general_chat"), None, kind
        if kind == "extract":
            extract = self._resolve_value(dict(script.extract)) if script else {}
            return json.dumps(extract, ensure_ascii=False), None, kind
        if kind == "plan":
            plan = [dict(step) for step in (script.plan if script else ())]
            return json.dumps(plan, ensure_ascii=False), None, kind
        return self._echo(body), None, kind

    def respond(self, body: dict, *, stream: bool = False) -> tuple[FakeResponse, str]:
        content, tool_calls, kind = self.content_for(body)
        if stream:
            return FakeResponse(status_code=200, lines=_sse_lines(body, content)), kind
        return FakeResponse(_completion(body, content, tool_calls)), kind


class _RecordingStream:
    """真模型流式响应的包装：透传 ``iter_lines`` 并从中取 usage。"""

    def __init__(self, response, call: LlmCall):
        self._response = response
        self._call = call

    def __getattr__(self, name):
        return getattr(self._response, name)

    def iter_lines(self):
        for line in self._response.iter_lines():
            try:
                text = line.decode("utf-8") if isinstance(line, bytes) else str(line)
                if text.startswith("data: ") and '"usage"' in text:
                    data = json.loads(text[6:])
                    if isinstance(data.get("usage"), dict):
                        self._call.usage = data["usage"]
            except (ValueError, UnicodeDecodeError):
                pass
            yield line


@contextmanager
def intercept_llm(recorder: LlmRecorder, *, scripted: ScriptedLLM | None = None):
    """替换 router 的出站函数；``scripted`` 为 None 时原样转发（真模型模式）。"""
    from llm_service import router as router_module

    original_safe = router_module.safe_request
    original_internal = router_module.safe_internal_request

    def _handle(original, method, url, **kwargs):
        body = kwargs.get("json") or {}
        stream = bool(kwargs.get("stream"))
        call = LlmCall(url=str(url), body=body)
        recorder.calls.append(call)
        started = time.perf_counter()
        try:
            if scripted is not None:
                if call.is_fallback:
                    # 剧本模式下兜底端点一律不可用，避免掩盖主端点的问题
                    call.status = 503
                    call.kind = "fallback"
                    return FakeResponse({"error": "fallback disabled"}, status_code=503)
                response, call.kind = scripted.respond(body, stream=stream)
                call.status = response.status_code
                if not stream:
                    call.usage = dict(response.json().get("usage") or {})
                else:
                    call.usage = _usage_for(body, "")
                return response
            call.kind = classify_request(body)
            response = original(method, url, **kwargs)
            call.status = getattr(response, "status_code", None)
            if stream:
                return _RecordingStream(response, call)
            try:
                call.usage = dict((response.json() or {}).get("usage") or {})
            except (ValueError, AttributeError, TypeError):
                call.usage = {}
            return response
        except Exception as exc:
            call.error = f"{type(exc).__name__}: {exc}"[:300]
            raise
        finally:
            call.elapsed_ms = int((time.perf_counter() - started) * 1000)

    def safe_request(method, url, **kwargs):
        return _handle(original_safe, method, url, **kwargs)

    def safe_internal_request(method, url, **kwargs):
        return _handle(original_internal, method, url, **kwargs)

    router_module.safe_request = safe_request
    router_module.safe_internal_request = safe_internal_request
    try:
        yield recorder
    finally:
        router_module.safe_request = original_safe
        router_module.safe_internal_request = original_internal
