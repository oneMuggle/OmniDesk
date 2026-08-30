from observability import get_logger
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

import requests
from django.conf import settings
from django.core.cache import cache

logger = get_logger(__name__, "llm_service.router")

# R5-B4: 配置加载缓存。所有 LLM 调用路径都构造 router,每次 chat/embedding
# 省 1 条 LlmAppConfig 查询;LlmAppConfig/LlmEndpoint 变更由 signals 即时失效
ROUTER_CACHE_TIMEOUT = 60


def _router_cache_key(app_name):
    return f"llm_router_configs_{app_name}"


class LLMRouter:
    """多端点 LLM 路由器：按优先级尝试端点，自动降级。

    降级链路：数据库 LlmAppConfig（按 priority 排序，按 app_name 隔离）
    → Ollama 本地全局兜底。不再依赖环境变量。

    各业务模块（smart_assistant、office_assistant 等）通过 ``app_name``
    获取各自的端点配置；无专属配置时自动落到 Ollama 全局兜底链。
    """

    OLLAMA_BASE = "http://localhost:11434"
    # Ollama 兜底模型的最终回退值；运行时优先读 settings.OLLAMA_MODEL_NAME
    OLLAMA_MODEL = "qwen2.5:7b"
    REQUEST_TIMEOUT = 120

    def __init__(self, app_name="smart_assistant"):
        # 按应用隔离 DB 端点配置，默认兼容既有 smart_assistant 调用方
        self.app_name = app_name
        try:
            self.REQUEST_TIMEOUT = max(1, int(getattr(settings, "LLM_REQUEST_TIMEOUT_SECONDS", 120)))
        except Exception:
            # 允许在 Django settings 尚未配置时导入模块；运行时使用默认值。
            self.REQUEST_TIMEOUT = 120
        self._configs = []
        self._load_configs()

    def _load_configs(self):
        """从数据库加载当前应用所有活跃的 LlmAppConfig，按 priority 升序。

        结果缓存 60s(R5-B4);LlmAppConfig/LlmEndpoint 变更由 signals 失效。
        直接缓存配置对象列表(模型实例可 pickle,LocMemCache/Redis 兼容)。
        """
        cache_key = _router_cache_key(self.app_name)
        try:
            from smart_assistant.models import LlmAppConfig

            cached = cache.get(cache_key)
            if cached is not None:
                self._configs = cached
                return

            self._configs = list(
                LlmAppConfig.objects.select_related("endpoint")
                .filter(
                    is_active=True,
                    app_name=self.app_name,
                )
                .order_by("endpoint__priority", "endpoint__is_fallback")
            )
            cache.set(cache_key, self._configs, ROUTER_CACHE_TIMEOUT)
        except Exception as e:
            logger.warning("无法从数据库加载 LLM 应用配置: %s", e)
            self._configs = []

    @classmethod
    def _resolve_ollama_model(cls) -> str:
        """解析 Ollama 兜底模型：优先 settings.OLLAMA_MODEL_NAME，缺失时回退类常量。"""
        return getattr(settings, "OLLAMA_MODEL_NAME", None) or cls.OLLAMA_MODEL

    def generate(self, prompt=None, system_message=None, stream=False, options=None, messages=None):
        """生成回答，自动在多个端点间降级。

        降级链路：数据库 LlmAppConfig（按 priority 排序，is_fallback 兜底）
        → Ollama 本地兜底。

        Args:
            prompt: 用户提示（与 messages 二选一）
            system_message: 可选的系统消息
            stream: 是否流式返回
            options: 模型选项（如 temperature, max_tokens）
            messages: 可选的完整 messages 数组（优先于 prompt）

        非流式返回 (content, usage) 元组，流式返回 generator。
        """
        if messages is not None:
            final_messages = messages
        else:
            final_messages = []
            if system_message:
                final_messages.append({"role": "system", "content": system_message})
            final_messages.append({"role": "user", "content": prompt})

        # 构建降级链路：按 LlmAppConfig 顺序（主端点 → 备用端点）
        candidates = list(self._configs)

        # Ollama 本地兜底
        candidates.append(
            {
                "_is_ollama": True,
            }
        )

        data = {
            "model": None,
            "messages": final_messages,
            "stream": stream,
        }
        if options:
            data.update(options)

        last_error = None
        for i, candidate in enumerate(candidates):
            # 检查是否是 Ollama 兜底配置（字典）
            is_ollama = isinstance(candidate, dict) and candidate.get("_is_ollama", False)

            if is_ollama:
                base_url = self.OLLAMA_BASE
                api_key = ""
                model_name = self._resolve_ollama_model()
                label = f"Ollama ({model_name})"
            else:
                # LlmAppConfig 对象
                config = candidate
                endpoint = config.endpoint
                base_url = endpoint.api_endpoint
                api_key = endpoint.api_key
                model_name = config.model_name
                label = f"{endpoint.name} ({model_name})"

            data["model"] = model_name
            url = f"{base_url.rstrip('/')}/v1/chat/completions"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            }

            try:
                response = requests.post(url, headers=headers, json=data, timeout=self.REQUEST_TIMEOUT, stream=stream)
                response.raise_for_status()

                if stream:
                    return self._stream_generate(response)
                else:
                    resp_data = response.json()
                    choices = resp_data.get("choices", [])
                    usage = resp_data.get("usage")
                    if choices and "message" in choices[0]:
                        if i > 0:
                            logger.info("LLM 降级成功: 切换到 %s", label)
                        # 补充成本核算字段：命中的端点 ID + 预估费用
                        usage = self._enrich_usage(
                            usage,
                            endpoint=None if is_ollama else endpoint,
                            model_name=model_name,
                        )
                        return choices[0]["message"]["content"], usage
                    raise Exception("LLM API 响应结构异常")
            except Exception as e:
                last_error = e
                if i == len(candidates) - 1:
                    # P0-W:最后一个端点仍失败 → 抛出原始异常保留类型与完整堆栈,
                    # 不再吞掉后替换成通用 Exception 文案
                    logger.warning("最后 LLM 端点 %s 失败 (%s)，抛出原始异常: %s", label, type(e).__name__, e)
                    raise
                logger.warning("LLM 端点 %s 失败 (%s)，尝试下一个: %s", label, type(e).__name__, e)
                continue

        # 理论上不可达(循环末尾已抛原始异常),保留兜底并链接原始异常
        raise Exception(f"所有 LLM 端点均不可用，最后错误: {last_error}") from last_error

    def generate_with_tools(
        self,
        messages,
        *,
        tools=None,
        tool_choice=None,
        endpoint_url=None,
        options=None,
    ):
        """透传 ``tools``/``tool_choice`` 给 OpenAI 兼容端点,并返回 tool_calls 三元组。

        与 ``generate()`` 的差异:
        - 接受 ``tools``/``tool_choice`` 参数,原样写入请求体;
        - 返回 ``(content, usage, tool_calls)`` 三元组,``tool_calls`` 是
          ``[{"id", "type", "function": {"name", "arguments"}}]`` 列表;
          未触发工具调用时为空列表。
        - 接受 ``endpoint_url`` 覆盖参数,主要用于测试场景(直接命中 mock
          服务)。未提供时自动走 DB ``LlmAppConfig`` 候选链路(与 ``generate()``
          一致:按 priority 依次尝试,最后 Ollama 本地兜底),满足真实业务
          通过 DB 端点配置调用原生 tool_calls 的需求。

        Args:
            messages: 完整 messages 数组
            tools: OpenAI 格式 tool schema 列表(可选)
            tool_choice: "auto"/"none"/"required"/具体 tool dict(可选)
            endpoint_url: 覆盖 DB 端点 URL,直接指向特定 OpenAI 兼容端点
            options: 透传的额外参数(如 temperature、max_tokens)

        Returns:
            ``(content, usage, tool_calls)`` 三元组。
        """
        # 显式 endpoint_url 覆盖(测试场景):直接命中,不降级
        if endpoint_url:
            model_name = self._resolve_model_name_for_tools()
            content, usage, tool_calls = self._generate_with_tools_single(
                messages=messages,
                tools=tools,
                tool_choice=tool_choice,
                base_url=endpoint_url,
                api_key="",
                model_name=model_name,
                options=options,
            )
            return content, usage, tool_calls

        # DB 配置链路:按 LlmAppConfig 顺序(主端点 → 备用端点),最后 Ollama 兜底
        candidates = list(self._configs)
        candidates.append({"_is_ollama": True})

        last_error = None
        for i, candidate in enumerate(candidates):
            is_ollama = isinstance(candidate, dict) and candidate.get("_is_ollama", False)
            if is_ollama:
                base_url = self.OLLAMA_BASE
                api_key = ""
                model_name = self._resolve_ollama_model()
                endpoint = None
                label = f"Ollama ({model_name})"
            else:
                endpoint = candidate.endpoint
                base_url = endpoint.api_endpoint
                api_key = endpoint.api_key
                model_name = candidate.model_name
                label = f"{endpoint.name} ({model_name})"

            try:
                content, usage, tool_calls = self._generate_with_tools_single(
                    messages=messages,
                    tools=tools,
                    tool_choice=tool_choice,
                    base_url=base_url,
                    api_key=api_key,
                    model_name=model_name,
                    options=options,
                )
                # 补充成本核算字段(命中的端点 ID + 预估费用)
                usage = self._enrich_usage(usage, endpoint, model_name)
                if i > 0:
                    logger.info("LLM 工具调用降级成功: 切换到 %s", label)
                return content, usage, tool_calls
            except Exception as exc:
                last_error = exc
                if i == len(candidates) - 1:
                    logger.warning("最后 LLM 工具调用端点 %s 失败 (%s),抛出原始异常", label, type(exc).__name__)
                    raise
                logger.warning("LLM 工具调用端点 %s 失败 (%s),尝试下一个", label, type(exc).__name__)
                continue

        # 理论上不可达(循环末尾已抛原始异常),保留兜底并链接原始异常
        raise Exception(f"所有 LLM 端点均不可用,最后错误: {last_error}") from last_error

    def _resolve_model_name_for_tools(self) -> str:
        """工具调用路径的默认模型名:优先首个活跃 DB 配置,缺失时回退类常量。"""
        if self._configs:
            return self._configs[0].model_name
        return self.OLLAMA_MODEL

    def _generate_with_tools_single(
        self,
        messages,
        *,
        tools,
        tool_choice,
        base_url,
        api_key,
        model_name,
        options=None,
    ):
        """向单个端点发起 tool_calls 请求并解析为三元组。

        返回 ``(content, usage, tool_calls)``;``tool_calls`` 是标准
        OpenAI 结构 ``[{"id", "type", "function": {"name", "arguments"}}]``。
        该助手同时服务 ``endpoint_url`` 覆盖路径与 DB 候选链路,避免重复。
        """
        body = {
            "model": model_name,
            "messages": messages,
            "stream": False,
        }
        if options:
            body.update(options)
        if tools is not None:
            body["tools"] = tools
        if tool_choice is not None:
            body["tool_choice"] = tool_choice

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }

        url = f"{base_url.rstrip('/')}/v1/chat/completions"
        response = requests.post(url, headers=headers, json=body, timeout=self.REQUEST_TIMEOUT)
        response.raise_for_status()
        resp_data = response.json()

        choices = resp_data.get("choices", [])
        if not choices or "message" not in choices[0]:
            raise Exception("LLM API 响应结构异常")

        message = choices[0]["message"]
        content = message.get("content") or ""
        usage_raw = resp_data.get("usage") or {}

        # 解析 tool_calls 为标准 OpenAI 结构
        tool_calls_raw = message.get("tool_calls") or []
        tool_calls = []
        for tc in tool_calls_raw:
            if not isinstance(tc, dict):
                continue
            function_payload = tc.get("function") or {}
            tool_calls.append(
                {
                    "id": tc.get("id", ""),
                    "type": tc.get("type", "function"),
                    "function": {
                        "name": function_payload.get("name", ""),
                        "arguments": function_payload.get("arguments", ""),
                    },
                }
            )

        usage = dict(usage_raw) if isinstance(usage_raw, dict) else {}
        usage.setdefault("model_name", model_name)
        usage.setdefault("estimated_cost", 0.0)
        usage.setdefault("endpoint_id", None)

        return content, usage, tool_calls

    @staticmethod
    def _compute_estimated_cost(endpoint, total_tokens) -> float:
        """根据命中端点的单价配置计算本次调用的预估费用（元）。

        无端点、无 ``cost_per_1k_tokens`` 配置或无 token 用量时返回 0.0，
        保证调用方任何情况下都不会因成本计算报错。
        """
        cost_per_1k = getattr(endpoint, "cost_per_1k_tokens", None) if endpoint is not None else None
        if cost_per_1k is None or not total_tokens:
            return 0.0
        try:
            cost = Decimal(str(total_tokens)) * Decimal(str(cost_per_1k)) / Decimal("1000")
            return float(cost.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP))
        except (InvalidOperation, ValueError, TypeError):
            logger.warning("成本计算失败: total_tokens=%s, cost_per_1k=%s", total_tokens, cost_per_1k)
            return 0.0

    def _enrich_usage(self, usage, endpoint, model_name: str) -> dict:
        """在 usage 字典中补充成本核算字段（向后兼容，不改动原有 token 字段）。

        新增字段：
        - ``estimated_cost``: 本次调用预估费用（元），无配置时为 0.0
        - ``endpoint_id``: 实际命中的 LlmEndpoint 主键（Ollama 兜底为 None）
        - ``model_name``: 实际命中的模型名（调用方未提供时才写入）
        """
        enriched = dict(usage) if isinstance(usage, dict) else {}
        total_tokens = enriched.get("total_tokens")
        if total_tokens is None:
            total_tokens = (enriched.get("prompt_tokens") or 0) + (enriched.get("completion_tokens") or 0)
        enriched["estimated_cost"] = self._compute_estimated_cost(endpoint, total_tokens)
        enriched["endpoint_id"] = getattr(endpoint, "id", None)
        enriched.setdefault("model_name", model_name)
        return enriched

    def _stream_generate(self, response):
        """流式解析 SSE 响应。"""
        import json

        for line in response.iter_lines():
            if not line:
                continue
            text = line.decode("utf-8")
            if text.startswith("data: "):
                text = text[6:]
            if text == "[DONE]":
                break
            try:
                chunk = json.loads(text)
                choices = chunk.get("choices", [])
                if choices:
                    delta = choices[0].get("delta", {})
                    content = delta.get("content")
                    if content:
                        yield content
            except Exception:
                continue

    def refresh(self):
        """重新加载数据库 LlmAppConfig。"""
        self._load_configs()


# 按 app_name 缓存的单例（各应用独立持有自己的端点配置）
_routers = {}


def get_router(app_name="smart_assistant"):
    """获取指定应用的 LLMRouter 单例。

    Args:
        app_name: 应用标识（对应 LlmAppConfig.app_name），默认
            ``smart_assistant`` 以兼容既有调用方。无专属配置的应用
            （如 office_assistant）会自动落到 Ollama 全局兜底链。
    """
    if app_name not in _routers:
        _routers[app_name] = LLMRouter(app_name=app_name)
    return _routers[app_name]
