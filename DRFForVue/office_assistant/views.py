import os
import requests
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

# 从环境变量中读取Dify配置
DIFY_API_KEY = os.environ.get('DIFY_API_KEY')
DIFY_BASE_URL = os.environ.get('DIFY_BASE_URL', 'https://api.dify.ai/v1')

# 预定义不同操作对应的Dify App ID
# 请确保已在Dify平台创建了这些应用，并在此处填入正确的ID
DIFY_APP_IDS = {
    'proofread': os.environ.get('DIFY_APP_ID_PROOFREAD', 'your-proofread-app-id'),
    'translate': os.environ.get('DIFY_APP_ID_TRANSLATE', 'your-translate-app-id'),
    'polish': os.environ.get('DIFY_APP_ID_POLISH', 'your-polish-app-id'),
}

class OfficeAssistantProcessView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        action = request.data.get('action')
        text = request.data.get('text')
        user = request.user

        if not action or not text:
            return Response({'error': 'Action and text are required.'}, status=status.HTTP_400_BAD_REQUEST)

        if action not in DIFY_APP_IDS:
            return Response({'error': 'Invalid action.'}, status=status.HTTP_400_BAD_REQUEST)

        if not DIFY_API_KEY:
            return Response({'error': 'Dify API key is not configured.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        app_id = DIFY_APP_IDS[action]
        dify_url = f"{DIFY_BASE_URL}/chat-messages"

        headers = {
            'Authorization': f'Bearer {DIFY_API_KEY}',
            'Content-Type': 'application/json'
        }

        data = {
            "inputs": {
                "text": text
            },
            "response_mode": "blocking",
            "user": str(user.id) # 使用用户ID作为Dify的会话标识
        }

        try:
            response = requests.post(dify_url, headers=headers, json=data, timeout=60)
            response.raise_for_status()  # 如果请求失败则抛出HTTPError
            
            dify_response_data = response.json()
            # 假设Dify返回的文本在 'answer' 字段中
            processed_text = dify_response_data.get('answer', '')

            return Response({'processed_text': processed_text}, status=status.HTTP_200_OK)

        except requests.exceptions.RequestException as e:
            return Response({'error': f'Failed to connect to Dify API: {e}'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception as e:
            return Response({'error': f'An unexpected error occurred: {e}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)