# omni_desk_backend/llm_service/test_ollama_client.py

import unittest
from unittest.mock import patch, MagicMock
import json
import os
from omni_desk_backend.llm_service.ollama_client import OllamaClient

class TestOllamaClient(unittest.TestCase):

    def setUp(self):
        self.base_url = "http://test-ollama:11434"
        self.model_name = "test-model"
        self.client = OllamaClient(base_url=self.base_url, model_name=self.model_name)

    def test_initialization_with_params(self):
        """Test client initialization with specific parameters."""
        self.assertEqual(self.client.base_url, self.base_url)
        self.assertEqual(self.client.model_name, self.model_name)

    @patch.dict(os.environ, {"OLLAMA_BASE_URL": "http://env-url:11434", "OLLAMA_MODEL_NAME": "env-model"})
    def test_initialization_with_env_vars(self):
        """Test client initialization with environment variables."""
        client = OllamaClient()
        self.assertEqual(client.base_url, "http://env-url:11434")
        self.assertEqual(client.model_name, "env-model")

    def test_initialization_with_defaults(self):
        """Test client initialization with default values."""
        with patch.dict(os.environ, {}, clear=True):
            client = OllamaClient()
            self.assertEqual(client.base_url, "http://localhost:11434")
            self.assertEqual(client.model_name, "llama2")

    @patch('requests.get')
    def test_list_models_success(self, mock_get):
        """Test successful listing of available models."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "models": [
                {"name": "model1:latest", "size": 1024},
                {"name": "model2:latest", "size": 2048}
            ]
        }
        mock_get.return_value = mock_response

        models = self.client.list_models()

        self.assertEqual(len(models), 2)
        self.assertEqual(models[0]['name'], 'model1:latest')
        mock_get.assert_called_once_with(f"{self.base_url}/api/tags", timeout=30)

    @patch('requests.get')
    def test_list_models_failure(self, mock_get):
        """Test failure in listing models."""
        mock_get.side_effect = requests.exceptions.ConnectionError("Test connection error")
        with self.assertRaisesRegex(Exception, "Failed to list Ollama models"):
            self.client.list_models()

    @patch('requests.post')
    def test_generate_completion_success(self, mock_post):
        """Test successful non-streaming generation."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": {"content": "The capital of France is Paris."}
        }
        mock_post.return_value = mock_response

        prompt = "What is the capital of France?"
        response_text = self.client.generate(prompt)

        self.assertEqual(response_text, "The capital of France is Paris.")
        
        expected_data = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {}
        }
        mock_post.assert_called_once()
        called_args, called_kwargs = mock_post.call_args
        self.assertEqual(called_args[0], f"{self.base_url}/api/chat")
        self.assertEqual(json.loads(called_kwargs['data']), expected_data)


    @patch('requests.post')
    def test_stream_completion_success(self, mock_post):
        """Test successful streaming generation."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        stream_content = [
            json.dumps({"message": {"content": "The capital "}}).encode('utf-8'),
            json.dumps({"message": {"content": "of France "}}).encode('utf-8'),
            json.dumps({"message": {"content": "is Paris."}}).encode('utf-8'),
        ]
        mock_response.iter_lines.return_value = stream_content
        mock_post.return_value = mock_response

        prompt = "What is the capital of France?"
        response_generator = self.client.generate(prompt, stream=True)
        
        result = "".join(list(response_generator))
        self.assertEqual(result, "The capital of France is Paris.")

        expected_data = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": prompt}],
            "stream": True,
            "options": {}
        }
        mock_post.assert_called_once()
        called_args, called_kwargs = mock_post.call_args
        self.assertEqual(called_args[0], f"{self.base_url}/api/chat")
        self.assertEqual(json.loads(called_kwargs['data']), expected_data)
        self.assertTrue(called_kwargs['stream'])

    @patch('requests.post')
    def test_generate_with_system_message(self, mock_post):
        """Test generation with a system message."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"message": {"content": "Oui."}}
        mock_post.return_value = mock_response

        prompt = "Is Paris in France?"
        system_message = "Respond in French."
        self.client.generate(prompt, system_message=system_message)

        expected_messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": prompt}
        ]
        
        called_args, called_kwargs = mock_post.call_args
        self.assertEqual(json.loads(called_kwargs['data'])['messages'], expected_messages)

    @patch('requests.post')
    def test_generate_http_error(self, mock_post):
        """Test handling of HTTP errors during generation."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        http_error = requests.exceptions.HTTPError(response=mock_response)
        mock_response.raise_for_status.side_effect = http_error
        mock_post.return_value = mock_response

        with self.assertRaisesRegex(Exception, "Ollama API returned an error: 500 - Internal Server Error"):
            self.client.generate("test prompt")

if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)