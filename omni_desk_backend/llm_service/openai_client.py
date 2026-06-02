import os

import requests


class OpenAIClient:
    """OpenAI 兼容的 LLM 客户端，支持 gcli 等 OpenAI-compatible API 网关。"""

    def __init__(self, base_url=None, api_key=None, model_name=None):
        # 优先从数据库读取活跃配置
        db_config = self._load_config_from_db()
        if db_config:
            base_url = base_url or db_config.endpoint.api_endpoint
            api_key = api_key or db_config.endpoint.api_key
            model_name = model_name or db_config.model_name

        self.base_url = (base_url or os.environ.get("SMART_ASSISTANT_LLM_ENDPOINT", "https://gcli.ggchan.dev")).rstrip(
            "/"
        )
        self.api_key = api_key or os.environ.get("SMART_ASSISTANT_LLM_API_KEY", "")
        self.model_name = model_name or os.environ.get("SMART_ASSISTANT_LLM_MODEL", "gemini-2.5-pro")

    def _load_config_from_db(self):
        """尝试从数据库加载活跃的 LLM 应用配置"""
        try:
            from smart_assistant.models import LlmAppConfig

            config = LlmAppConfig.objects.select_related("endpoint").filter(is_active=True).first()
            if config:
                return config
        except Exception:
            pass
        return None

    def _make_request(self, data, stream=False):
        url = f"{self.base_url}/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        try:
            response = requests.post(url, headers=headers, json=data, timeout=120, stream=stream)
            response.raise_for_status()
            if stream:
                return response
            return response.json()
        except requests.exceptions.Timeout:
            raise Exception("LLM API 请求超时")
        except requests.exceptions.ConnectionError:
            raise Exception("无法连接 LLM API 服务")
        except requests.exceptions.HTTPError as e:
            raise Exception(f"LLM API 返回错误: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            raise Exception(f"LLM API 请求异常: {e}")

    def _stream_generate(self, response):
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

    def generate(self, prompt=None, system_message=None, stream=False, options=None, messages=None):
        """生成回答

        Args:
            prompt: 用户提示（与 messages 二选一）
            system_message: 可选的系统消息
            stream: 是否流式返回
            options: 模型选项（如 temperature, max_tokens）
            messages: 可选的完整 messages 数组（优先于 prompt）

        Returns:
            非流式时返回 (content, usage) 元组，流式时返回 generator
        """
        if messages is not None:
            final_messages = messages
        else:
            final_messages = []
            if system_message:
                final_messages.append({"role": "system", "content": system_message})
            final_messages.append({"role": "user", "content": prompt})

        data = {
            "model": self.model_name,
            "messages": final_messages,
            "stream": stream,
        }
        if options:
            data.update(options)

        if stream:
            response = self._make_request(data, stream=True)
            return self._stream_generate(response)
        else:
            response_data = self._make_request(data)
            choices = response_data.get("choices", [])
            usage = response_data.get("usage")
            if choices and "message" in choices[0]:
                return choices[0]["message"]["content"], usage
            else:
                raise Exception(f"LLM API 响应结构异常: {response_data}")
