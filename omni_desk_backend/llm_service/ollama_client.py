# omni_desk_backend/llm_service/ollama_client.py

import json
import os

import requests
from observability import get_logger

from smart_assistant.ssrf import UnsafeEndpointError, safe_request

logger = get_logger(__name__, "llm_service.ollama_client")


class OllamaClient:
    def __init__(self, base_url=None, model_name=None, *, requester=None, resolver=None):
        self.base_url = base_url or os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
        self._requester = requester
        self._resolver = resolver
        # 默认模型与 LLMRouter / settings.OLLAMA_MODEL_NAME 统一为 qwen2.5:7b
        self.model_name = model_name or os.environ.get("OLLAMA_MODEL_NAME", "qwen2.5:7b")

    def _make_request(self, endpoint, data, stream=False):
        url = f"{self.base_url}/{endpoint}"
        headers = {"Content-Type": "application/json"}
        try:
            response = safe_request(
                "POST", url, headers=headers, data=json.dumps(data),
                timeout=120, stream=stream,
                requester=self._requester, resolver=self._resolver,
            )
            response.raise_for_status()
            if stream:
                return response
            return response.json()
        except requests.exceptions.HTTPError:
            raise Exception("Ollama API 返回 HTTP 错误。")
        except UnsafeEndpointError:
            raise Exception("Ollama 端点地址不允许。")
        except requests.exceptions.RequestException:
            raise Exception("Ollama API 请求失败。")
        except (ValueError, TypeError):
            raise Exception("Ollama API 响应格式无效。")
        except Exception:
            raise Exception("Ollama API 请求失败。")

    def _stream_generate(self, response):
        for line in response.iter_lines():
            if line:
                chunk = json.loads(line)
                if "message" in chunk and "content" in chunk["message"]:
                    yield chunk["message"]["content"]

    def generate(self, prompt, system_message=None, stream=False, options=None):
        """
        Generates a response from the Ollama model.
        :param prompt: The user prompt.
        :param system_message: An optional system message to guide the model.
        :param stream: Whether to stream the response.
        :param options: A dictionary of model options (e.g., {'temperature': 0.7}).
        :return: The generated text or a generator if streaming.
        """
        messages = []
        if system_message:
            messages.append({"role": "system", "content": system_message})
        messages.append({"role": "user", "content": prompt})

        data = {
            "model": self.model_name,
            "messages": messages,
            "stream": stream,
            "options": options if options is not None else {},
        }

        if stream:
            response = self._make_request("api/chat", data, stream=True)
            return self._stream_generate(response)
        else:
            response_data = self._make_request("api/chat", data)
            if "message" in response_data and "content" in response_data["message"]:
                return response_data["message"]["content"]
            else:
                raise Exception(f"Unexpected Ollama API response structure: {response_data}")

    def pull_model(self, model_name):
        """
        Pulls a model from Ollama.
        :param model_name: The name of the model to pull.
        """
        data = {
            "name": model_name,
            "stream": False,  # Pulling usually doesn't stream progress in this simple client
        }
        logger.info("Attempting to pull Ollama model: %s. This may take some time.", model_name)
        try:
            response = self._make_request("api/pull", data)
            logger.info("Ollama model pull response: %s", response)
            return response
        except Exception as e:
            logger.error("Failed to pull Ollama model %s: %s", model_name, e, exc_info=True)
            raise

    def list_models(self):
        """
        Lists available Ollama models.
        """
        url = f"{self.base_url}/api/tags"
        try:
            response = safe_request("GET", url, timeout=30, requester=self._requester, resolver=self._resolver)
            response.raise_for_status()
            return response.json().get("models", [])
        except UnsafeEndpointError:
            raise Exception("Ollama 端点地址不允许。")
        except requests.exceptions.RequestException:
            raise Exception("Ollama 模型列表请求失败。")
        except (ValueError, TypeError):
            raise Exception("Ollama 模型列表响应格式无效。")
        except Exception:
            raise Exception("Ollama 模型列表请求失败。")


# Example Usage (can be used for testing)
if __name__ == "__main__":
    client = OllamaClient()
    try:
        # Example: List models
        logger.info("Listing available Ollama models:")
        models = client.list_models()
        for model in models:
            logger.info("- %s (%.2f GB)", model["name"], model["size"] / (1024 * 1024 * 1024))

        # Example: Generate text (ensure the default model is available or pull it first)
        # logger.info("\nGenerating text with the default model:")
        # response_text = client.generate(prompt="What is the capital of France?")
        # logger.info(response_text)

        # Example: Pull a model (uncomment to run)
        # client.pull_model("qwen2.5:7b")

    except Exception as e:
        logger.error("Error: %s", e, exc_info=True)
