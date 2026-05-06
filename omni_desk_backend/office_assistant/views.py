import docx
import pypdf
from django.http import StreamingHttpResponse
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from llm_service.ollama_client import OllamaClient


class OfficeAssistantProcessView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        action = request.data.get('action')
        text = request.data.get('text')
        stream = request.data.get('stream', False)

        if not action or not text:
            return Response({'error': 'Action and text are required.'}, status=status.HTTP_400_BAD_REQUEST)

        system_prompts = {
            'proofread': "You are a proofreader. Find and correct any spelling or grammar mistakes in the following text.",
            'translate': "You are a translator. Translate the following text to Chinese.",
            'polish': "You are a writing assistant. Improve the style and clarity of the following text.",
        }

        if action not in system_prompts:
            return Response({'error': 'Invalid action.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            client = OllamaClient()
            system_message = system_prompts[action]

            if stream:
                response_stream = client.generate(prompt=text, system_message=system_message, stream=True)
                return StreamingHttpResponse(response_stream, content_type='text/event-stream')
            else:
                processed_text = client.generate(prompt=text, system_message=system_message, stream=False)
                return Response({'processed_text': processed_text}, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({'error': f'An unexpected error occurred: {e}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ProcessDocumentView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request, *args, **kwargs):
        if 'file' not in request.FILES:
            return Response({'status': 'error', 'message': 'No file provided.'}, status=status.HTTP_400_BAD_REQUEST)

        file_obj = request.FILES['file']
        action = request.data.get('action', 'proofread')
        stream = request.data.get('stream', 'true').lower() == 'true'

        file_name = file_obj.name
        original_text = ""

        try:
            if file_name.endswith('.docx'):
                document = docx.Document(file_obj)
                original_text = "\n".join([para.text for para in document.paragraphs])
            elif file_name.endswith('.pdf'):
                pdf_reader = pypdf.PdfReader(file_obj)
                for page in pdf_reader.pages:
                    original_text += page.extract_text() or ""
            elif file_name.endswith('.txt') or file_name.endswith('.md'):
                original_text = file_obj.read().decode('utf-8')
            else:
                return Response({'status': 'error', 'message': 'Invalid file type. Only .docx, .pdf, .txt and .md are supported.'}, status=status.HTTP_400_BAD_REQUEST)

            if not original_text.strip():
                return Response({'status': 'error', 'message': 'The document is empty or contains no text.'}, status=status.HTTP_400_BAD_REQUEST)

            client = OllamaClient()

            system_prompts = {
                'proofread': "You are a proofreader. Find and correct any spelling or grammar mistakes in the following text.",
                'improve': "You are a writing assistant. Improve the style and clarity of the following text.",
                'translate': "You are a translator. Translate the following text to Chinese.",
            }

            if action not in system_prompts:
                return Response({'status': 'error', 'message': 'Invalid action specified.'}, status=status.HTTP_400_BAD_REQUEST)

            system_message = system_prompts[action]

            if stream:
                response_stream = client.generate(prompt=original_text, system_message=system_message, stream=True)
                return StreamingHttpResponse(response_stream, content_type='text/event-stream')
            else:
                processed_text = client.generate(prompt=original_text, system_message=system_message, stream=False)
                response_data = {
                    'status': 'success',
                    'data': {
                        'original_text': original_text,
                        'processed_text': processed_text,
                    }
                }
                return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({'status': 'error', 'message': f'Failed to process document: {e!s}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
