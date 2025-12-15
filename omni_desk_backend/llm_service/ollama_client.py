# omni_desk_backend/llm_service/ollama_client.py

import requests
import json
import os

class OllamaClient:
    def __init__(self, base_url=None, model_name=None):
        self.base_url = base_url or os.environ.get('OLLAMA_BASE_URL', 'http://localhost:11434')
        self.model_name = model_name or os.environ.get('OLLAMA_MODEL_NAME', 'llama2') # 默认使用llama2模型

    def _make_request(self, endpoint, data, stream=False):
        url = f"{self.base_url}/{endpoint}"
        headers = {'Content-Type': 'application/json'}
        try:
            response = requests.post(url, headers=headers, data=json.dumps(data), timeout=120, stream=stream)
            response.raise_for_status()
            if stream:
                return response
            return response.json()
        except requests.exceptions.Timeout:
            raise Exception("Ollama API request timed out.")
        except requests.exceptions.ConnectionError:
            raise Exception("Could not connect to Ollama API. Is the server running?")
        except requests.exceptions.HTTPError as e:
            raise Exception(f"Ollama API returned an error: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            raise Exception(f"An unexpected error occurred during Ollama API request: {e}")

    def _stream_generate(self, response):
        for line in response.iter_lines():
            if line:
                chunk = json.loads(line)
                if 'message' in chunk and 'content' in chunk['message']:
                    yield chunk['message']['content']

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
            "options": options if options is not None else {}
        }

        if stream:
            response = self._make_request("api/chat", data, stream=True)
            return self._stream_generate(response)
        else:
            response_data = self._make_request("api/chat", data)
            if 'message' in response_data and 'content' in response_data['message']:
                return response_data['message']['content']
            else:
                raise Exception(f"Unexpected Ollama API response structure: {response_data}")

    def pull_model(self, model_name):
        """
        Pulls a model from Ollama.
        :param model_name: The name of the model to pull.
        """
        data = {
            "name": model_name,
            "stream": False # Pulling usually doesn't stream progress in this simple client
        }
        print(f"Attempting to pull Ollama model: {model_name}. This may take some time.")
        try:
            response = self._make_request("api/pull", data)
            print(f"Ollama model pull response: {response}")
            return response
        except Exception as e:
            print(f"Failed to pull Ollama model {model_name}: {e}")
            raise

    def list_models(self):
        """
        Lists available Ollama models.
        """
        url = f"{self.base_url}/api/tags"
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            return response.json().get('models', [])
        except Exception as e:
            raise Exception(f"Failed to list Ollama models: {e}")

# Example Usage (can be used for testing)
if __name__ == "__main__":
    client = OllamaClient()
    try:
        # Example: List models
        print("Listing available Ollama models:")
        models = client.list_models()
        for model in models:
            print(f"- {model['name']} ({model['size'] / (1024*1024*1024):.2f} GB)")

        # Example: Generate text (ensure llama2 is available or pull it first)
        # print("\nGenerating text with llama2:")
        # response_text = client.generate(prompt="What is the capital of France?", model_name="llama2")
        # print(response_text)

        # Example: Pull a model (uncomment to run)
        # client.pull_model("llama2")

    except Exception as e:
        print(f"Error: {e}")