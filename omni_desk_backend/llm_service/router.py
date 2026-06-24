import logging

import requests

logger = logging.getLogger(__name__)


class LLMRouter:
    """多端点 LLM 路由器：按优先级尝试端点，自动降级。

    降级链路：数据库 LlmAppConfig（按 priority 排序）→ Ollama 本地。
    不再依赖环境变量。
    """

    OLLAMA_BASE = "http://localhost:11434"
    OLLAMA_MODEL = "qwen2.5:7b"
    REQUEST_TIMEOUT = 120

    def __init__(self):
        self._configs = []
        self._load_configs()

    def _load_configs(self):
        """从数据库加载所有活跃的 LlmAppConfig，按 priority 升序。"""
        try:
            from smart_assistant.models import LlmAppConfig

            self._configs = list(
                LlmAppConfig.objects.select_related("endpoint")
                .filter(
                    is_active=True,
                    app_name="smart_assistant",
                )
                .order_by("endpoint__priority", "endpoint__is_fallback")
            )
        except Exception as e:
            logger.warning("无法从数据库加载 LLM 应用配置: %s", e)
            self._configs = []

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
                model_name = self.OLLAMA_MODEL
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
                        return choices[0]["message"]["content"], usage
                    raise Exception("LLM API 响应结构异常")
            except Exception as e:
                last_error = e
                logger.warning("LLM 端点 %s 失败 (%s)，尝试下一个: %s", label, type(e).__name__, e)
                continue

        raise Exception(f"所有 LLM 端点均不可用，最后错误: {last_error}")

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


# 单例
_router = None


def get_router():
    global _router
    if _router is None:
        _router = LLMRouter()
    return _router
