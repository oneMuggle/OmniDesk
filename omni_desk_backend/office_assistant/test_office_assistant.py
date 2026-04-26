from rest_framework.test import APIClient, APITestCase
from django.urls import reverse
from rest_framework import status
from users.models import CustomUser
from unittest.mock import patch
import docx
from io import BytesIO

class OfficeAssistantProcessViewTests(APITestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(username='testuser', password='password123')
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.url = reverse('office-assistant-process')

    @patch('llm_service.ollama_client.OllamaClient.generate')
    def test_process_text_successfully(self, mock_generate):
        mock_generate.return_value = 'Processed text'

        data = {'action': 'proofread', 'text': 'Some text to process.'}
        response = self.client.post(self.url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['processed_text'], 'Processed text')

    def test_missing_action_or_text(self):
        response = self.client.post(self.url, {'action': 'proofread'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        response = self.client.post(self.url, {'text': 'Some text'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

class ProcessDocumentViewTests(APITestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(username='testuser', password='password123')
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.url = reverse('office-assistant-process-document')

    @patch('llm_service.ollama_client.OllamaClient.generate')
    def test_process_document_successfully(self, mock_generate):
        mock_generate.return_value = 'Processed document text.'

        document = docx.Document()
        document.add_paragraph('This is a test document.')
        file_stream = BytesIO()
        document.save(file_stream)
        file_stream.seek(0)
        file_stream.name = 'test.docx'

        data = {'file': file_stream, 'action': 'proofread', 'stream': 'false'}
        response = self.client.post(self.url, data, format='multipart')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data']['processed_text'], 'Processed document text.')

    def test_no_file_provided(self):
        response = self.client.post(self.url, {}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_file_type(self):
        file_stream = BytesIO(b"some text data")
        file_stream.name = 'test.invalid'
        data = {'file': file_stream, 'action': 'proofread'}
        response = self.client.post(self.url, data, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)