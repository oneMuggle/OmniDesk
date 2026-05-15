import json
import tempfile

from rest_framework import parsers, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from compliance.models import ComplianceIssue
from compliance.serializers import ComplianceIssueSerializer
from llm_service.ollama_client import OllamaClient
from projects.models import Project

from .file_processing import process_uploaded_file
from .models import DocumentTemplate
from .serializers import DocumentTemplateSerializer


class DocumentTemplateViewSet(viewsets.ModelViewSet):
    queryset = DocumentTemplate.objects.all()
    serializer_class = DocumentTemplateSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [parsers.MultiPartParser]

    def get_queryset(self):
        queryset = self.queryset.filter(owner=self.request.user)
        project_id = self.request.query_params.get('project_id')
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        return queryset

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    @action(detail=False, methods=['post'], url_path='upload')
    def upload_template(self, request):
        file_obj = request.FILES.get('template')
        if not file_obj:
            return Response({'error': 'No file uploaded'}, status=status.HTTP_400_BAD_REQUEST)

        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                extracted_text = process_uploaded_file(file_obj, temp_dir)
                project_id = request.data.get('project')
                project_instance = None
                if project_id:
                    try:
                        project_instance = Project.objects.get(id=project_id)
                    except Project.DoesNotExist:
                        return Response({'error': 'Project not found'}, status=status.HTTP_404_NOT_FOUND)

                template = DocumentTemplate.objects.create(
                    name=file_obj.name,
                    file=file_obj,
                    owner=request.user,
                    extracted_text=extracted_text,
                    project=project_instance,
                )
                return Response(DocumentTemplateSerializer(template).data, status=status.HTTP_201_CREATED)
            except Exception as e:
                return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'], url_path='analyze')
    def analyze_file(self, request, pk=None):
        try:
            document_template = self.get_object()
            extracted_text = document_template.extracted_text
            project_instance = document_template.project

            if not project_instance:
                return Response(
                    {'error': 'Document not associated with a project. Cannot analyze compliance issues.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            ollama_client = OllamaClient()

            system_message = """你是一名专业的文档合规性审查员，专注于识别文档中的不规范、时间冲突、内容缺失或内容与规定不符的问题。
            你的输出必须是严格的 JSON 数组格式，每个元素代表一个发现的问题。
            每个问题对象应包含以下键值对：
            - "issue_type": 字符串，问题类型，必须是以下之一："不规范", "时间冲突", "内容缺失", "内容与规定不符", "其他"。
            - "description": 字符串，问题的详细描述。
            - "location": 字符串，问题在文档中的大致位置。
            - "severity": 字符串，严重程度，必须是以下之一："低", "中", "高", "紧急"。
            - "suggested_fix": 字符串，具体修改建议。
            如果文档完全合规，返回空数组 []。"""

            prompt = f"请严格按照系统消息的JSON格式要求，分析以下文档内容，识别其中存在的合规性问题：\n\n文档内容：\n{extracted_text}\n\n请输出JSON数组："

            ollama_response_json = ollama_client.generate(prompt=prompt, system_message=system_message)

            try:
                compliance_issues_data = json.loads(ollama_response_json)
                if not isinstance(compliance_issues_data, list):
                    raise ValueError(f"Ollama response is not a JSON array. Response: {ollama_response_json}")
            except json.JSONDecodeError as e:
                raise Exception(f"Ollama 返回的不是有效的 JSON 格式: {ollama_response_json}. 错误: {e}")
            except ValueError as ve:
                raise Exception(f"Ollama 返回数据结构不正确: {ve}")

            created_issues = []
            for issue_data in compliance_issues_data:
                required_fields = ['issue_type', 'description', 'location', 'severity', 'suggested_fix']
                if not all(field in issue_data and isinstance(issue_data[field], str) for field in required_fields):
                    continue

                issue_type = issue_data.get('issue_type', '其他')
                if issue_type not in [choice[0] for choice in ComplianceIssue.ISSUE_TYPES]:
                    issue_type = '其他'

                severity = issue_data.get('severity', '中')
                if severity not in [choice[0] for choice in ComplianceIssue.SEVERITY_CHOICES]:
                    severity = '中'

                issue = ComplianceIssue.objects.create(
                    project=project_instance,
                    document_template=document_template,
                    issue_type=issue_type,
                    description=issue_data['description'],
                    location=issue_data['location'],
                    severity=severity,
                )
                created_issues.append(ComplianceIssueSerializer(issue).data)

            return Response(
                {'message': f'Analysis complete. Found {len(created_issues)} compliance issues.', 'issues': created_issues},
                status=status.HTTP_200_OK,
            )
        except DocumentTemplate.DoesNotExist:
            return Response({'error': 'DocumentTemplate not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': f'文件分析失败: {e}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
