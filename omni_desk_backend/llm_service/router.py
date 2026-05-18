import logging
import os

import requests

logger = logging.getLogger(__name__)


class LLMRouter:
    """多端点 LLM 路由器：按优先级尝试端点，自动降级。

    降级链路：数据库活跃端点 → 环境变量端点 → Ollama 本地
    """

    OLLAMA_BASE = 'http://localhost:11434'
    OLLAMA_MODEL = os.environ.get('SMART_ASSISTANT_OLLAMA_MODEL', 'qwen2.5:7b')
    REQUEST_TIMEOUT = 120

    def __init__(self):
        self._endpoints = []
        self._load_endpoints()

    def _load_endpoints(self):
        """从数据库加载所有活跃端点，按 created_at 降序（最新的优先）。"""
        try:
            from smart_assistant.models import LlmEndpoint
            self._endpoints = list(
                LlmEndpoint.objects.filter(is_active=True).order_by('-created_at')
            )
        except Exception as e:
            logger.warning('无法从数据库加载 LLM 端点: %s', e)
            self._endpoints = []

    def generate(self, prompt, system_message=None, stream=False, options=None):
        """生成回答，自动在多个端点间降级。

        非流式返回完整文本，流式返回 generator。
        """
        messages = []
        if system_message:
            messages.append({'role': 'system', 'content': system_message})
        messages.append({'role': 'user', 'content': prompt})

        # 构建降级链路
        candidates = list(self._endpoints)

        # 环境变量端点
        env_url = os.environ.get('SMART_ASSISTANT_LLM_ENDPOINT')
        env_key = os.environ.get('SMART_ASSISTANT_LLM_API_KEY', '')
        env_model = os.environ.get('SMART_ASSISTANT_LLM_MODEL', 'gemini-2.5-pro')
        if env_url:
            candidates.append({
                'api_endpoint': env_url,
                'api_key': env_key,
                'model_name': env_model,
                '_is_env': True,
            })

        # Ollama 本地兜底
        candidates.append({
            'api_endpoint': self.OLLAMA_BASE,
            'api_key': '',
            'model_name': self.OLLAMA_MODEL,
            '_is_ollama': True,
        })

        data = {
            'model': None,
            'messages': messages,
            'stream': stream,
        }
        if options:
            data.update(options)

        last_error = None
        for i, candidate in enumerate(candidates):
            is_ollama = candidate.get('_is_ollama', False)
            is_env = candidate.get('_is_env', False)

            if is_ollama:
                base_url = candidate['api_endpoint']
                api_key = ''
                model_name = candidate['model_name']
                label = f'Ollama ({model_name})'
            elif is_env:
                base_url = candidate['api_endpoint']
                api_key = candidate['api_key']
                model_name = candidate['model_name']
                label = f'Env ({model_name})'
            else:
                base_url = candidate.api_endpoint
                api_key = candidate.api_key
                try:
                    from smart_assistant.models import LlmAppConfig
                    config = LlmAppConfig.objects.select_related('endpoint').filter(
                        endpoint=candidate, is_active=True
                    ).first()
                    model_name = config.model_name if config else 'gemini-2.5-pro'
                except Exception:
                    model_name = 'gemini-2.5-pro'
                label = f'DB:{candidate.name} ({model_name})'

            data['model'] = model_name
            url = f"{base_url.rstrip('/')}/v1/chat/completions"
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f"Bearer {api_key}",
            }

            try:
                response = requests.post(
                    url, headers=headers, json=data, timeout=self.REQUEST_TIMEOUT, stream=stream
                )
                response.raise_for_status()

                if stream:
                    return self._stream_generate(response)
                else:
                    resp_data = response.json()
                    choices = resp_data.get('choices', [])
                    if choices and 'message' in choices[0]:
                        if i > 0:
                            logger.info('LLM 降级成功: 切换到 %s', label)
                        return choices[0]['message']['content']
                    raise Exception('LLM API 响应结构异常')
            except Exception as e:
                last_error = e
                logger.warning('LLM 端点 %s 失败 (%s)，尝试下一个: %s', label, type(e).__name__, e)
                continue

        raise Exception(f'所有 LLM 端点均不可用，最后错误: {last_error}')

    def _stream_generate(self, response):
        """流式解析 SSE 响应。"""
        import json

        for line in response.iter_lines():
            if not line:
                continue
            text = line.decode('utf-8')
            if text.startswith('data: '):
                text = text[6:]
            if text == '[DONE]':
                break
            try:
                chunk = json.loads(text)
                choices = chunk.get('choices', [])
                if choices:
                    delta = choices[0].get('delta', {})
                    content = delta.get('content')
                    if content:
                        yield content
            except Exception:
                continue

    def refresh(self):
        """重新加载数据库端点配置。"""
        self._load_endpoints()


# 单例
_router = None


def get_router():
    global _router
    if _router is None:
        _router = LLMRouter()
    return _router
