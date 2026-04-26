import json  # 确保已导入
import posixpath
import re
import shutil
import tempfile  # 导入 tempfile 来创建临时目录
from pathlib import Path

import markdown
from django.conf import settings
from django.db import transaction
from django.http import HttpResponse  # For file export
from rest_framework import parsers, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView  # For BookImportView

from compliance.models import ComplianceIssue  # 导入 ComplianceIssue 模型
from compliance.serializers import ComplianceIssueSerializer  # 导入 ComplianceIssue 序列化器
from llm_service.ollama_client import OllamaClient  # 导入 OllamaClient
from projects.models import Project

from .file_processing import process_uploaded_file  # 导入我们新创建的函数
from .models import Book, Chapter, DocumentTemplate, EBook, GeneratedDocument, Tag
from .serializers import (
    AnnotationSerializer,
    BookSerializer,
    ChapterSerializer,
    CommentSerializer,
    DocumentTemplateSerializer,
    EBookSerializer,
    GeneratedDocumentSerializer,
)


class DocumentTemplateViewSet(viewsets.ModelViewSet):
    queryset = DocumentTemplate.objects.all()
    serializer_class = DocumentTemplateSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [parsers.MultiPartParser]  # 添加文件上传支持

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

        # 使用临时目录处理文件
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                # 调用 file_processing.py 中的函数来处理文件并提取文本
                extracted_text = process_uploaded_file(file_obj, temp_dir)

                project_id = request.data.get('project') # 获取 project ID
                project_instance = None
                if project_id:
                    try:
                        project_instance = Project.objects.get(id=project_id)
                    except Project.DoesNotExist:
                        return Response({'error': 'Project not found'}, status=status.HTTP_404_NOT_FOUND)

                template = DocumentTemplate.objects.create(
                    name=file_obj.name,
                    file=file_obj, # 原始文件仍然保存
                    owner=request.user,
                    extracted_text=extracted_text, # 将提取的文本保存到模型字段
                    project=project_instance # 关联项目
                )
                return Response(DocumentTemplateSerializer(template).data, status=status.HTTP_201_CREATED)
            except Exception as e:
                return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'], url_path='analyze') # 将 detail 改为 True，以便通过 pk 获取 DocumentTemplate 实例
    def analyze_file(self, request, pk=None):
        try:
            document_template = self.get_object() # 获取 DocumentTemplate 实例
            extracted_text = document_template.extracted_text # 从模型中获取提取的文本
            project_instance = document_template.project # 获取关联的项目实例

            if not project_instance:
                return Response({'error': 'Document not associated with a project. Cannot analyze compliance issues.'}, status=status.HTTP_400_BAD_REQUEST)

            ollama_client = OllamaClient()

            # 优化后的系统消息和提示词
            system_message = """你是一名专业的文档合规性审查员，专注于识别文档中的不规范、时间冲突、内容缺失或内容与规定不符的问题。
            你的输出必须是严格的 JSON 数组格式，每个元素代表一个发现的问题。
            每个问题对象应包含以下键值对：
            - "issue_type": 字符串，问题类型，必须是以下之一："不规范", "时间冲突", "内容缺失", "内容与规定不符", "其他"。
            - "description": 字符串，问题的详细描述，清晰说明哪里不符合规定。
            - "location": 字符串，问题在文档中的大致位置，如“第3页第2段”、“章节标题：项目目标”、“图片描述缺失”。
            - "severity": 字符串，问题的严重程度，必须是以下之一："低", "中", "高", "紧急"。
            - "suggested_fix": 字符串，针对该问题提出的具体修改建议或改进措施。

            如果文档完全合规，没有发现任何问题，则返回一个空的 JSON 数组：[]。
            请严格遵守 JSON 格式要求，不要包含任何额外的文本或说明。"""

            # 考虑RAG辅助，这里可以加入从知识库检索到的相关规范内容
            # For now, let's keep it simple and assume `extracted_text` is sufficient.
            # 后续可以在这里加入 RAG 逻辑，将相关规范作为 prompt 的一部分。
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
                # 检查必要的字段是否存在，并进行类型校验
                required_fields = ['issue_type', 'description', 'location', 'severity', 'suggested_fix']
                if not all(field in issue_data and isinstance(issue_data[field], str) for field in required_fields):
                    print(f"Skipping malformed or incomplete issue data: {issue_data}")
                    continue

                # 确保 issue_type 和 severity 在允许的 choices 范围内
                issue_type = issue_data.get('issue_type', '其他')
                if issue_type not in [choice[0] for choice in ComplianceIssue.ISSUE_TYPES]:
                    issue_type = '其他' # 默认值

                severity = issue_data.get('severity', '中')
                if severity not in [choice[0] for choice in ComplianceIssue.SEVERITY_CHOICES]:
                    severity = '中' # 默认值

                # 创建 ComplianceIssue 实例
                issue = ComplianceIssue.objects.create(
                    project=project_instance,
                    document_template=document_template,
                    issue_type=issue_type,
                    description=issue_data['description'],
                    location=issue_data['location'],
                    severity=severity,
                    # suggested_fix 字段目前 ComplianceIssue 模型中没有，如果需要可以后续添加
                    # 如果需要保存 suggested_fix，需要先在 ComplianceIssue 模型中添加此字段
                )
                created_issues.append(ComplianceIssueSerializer(issue).data)

            return Response({'message': f'Analysis complete. Found {len(created_issues)} compliance issues.', 'issues': created_issues}, status=status.HTTP_200_OK)
        except DocumentTemplate.DoesNotExist:
            return Response({'error': 'DocumentTemplate not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': f'文件分析失败: {e}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class GeneratedDocumentViewSet(viewsets.ModelViewSet):
    queryset = GeneratedDocument.objects.select_related('generated_by')
    serializer_class = GeneratedDocumentSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None  # 禁用分页

    def get_queryset(self):
        return self.queryset.filter(generated_by=self.request.user)

    def perform_create(self, serializer):
        serializer.save(generated_by=self.request.user)

    @action(detail=True, methods=['post'])
    def finalize(self, request, pk=None):
        document = self.get_object()
        document.is_final = True
        document.save()
        return Response({'status': 'document finalized'})

class BookViewSet(viewsets.ModelViewSet):
    queryset = Book.objects.prefetch_related('tags', 'chapters')
    serializer_class = BookSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        project_id = self.request.query_params.get('project_id')
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        return queryset

    @action(detail=True, methods=['get'], url_path='export_markdown')
    def export_markdown(self, request, pk=None):
        book = self.get_object()
        chapters = book.chapters.order_by('order')

        full_markdown_content = f"# {book.title}\n\n"
        if book.author:
            full_markdown_content += f"- 作者：{book.author}\n"
        if book.description:
            full_markdown_content += f"- 简介：{book.description}\n"
        if book.cover_image:
            full_markdown_content += f"- 封面：{book.cover_image.name}\n" # Use .name to get relative path in MEDIA_ROOT
        if book.tags.exists():
            tags_str = ", ".join([tag.name for tag in book.tags.all()])
            full_markdown_content += f"- 标签：{tags_str}\n"
        full_markdown_content += "\n"

        for chapter in chapters:
            full_markdown_content += f"{chapter.content_md}\n\n"

        response = HttpResponse(full_markdown_content, content_type='text/markdown')
        response['Content-Disposition'] = f'attachment; filename="{book.title}.md"'
        return response

class ChapterViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Chapter.objects.prefetch_related('comments', 'annotations')
    serializer_class = ChapterSerializer
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def add_comment(self, request, pk=None):
        chapter = self.get_object()
        serializer = CommentSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save(chapter=chapter, user=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def add_annotation(self, request, pk=None):
        chapter = self.get_object()
        serializer = AnnotationSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(chapter=chapter, user=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['put'], permission_classes=[permissions.IsAuthenticated])
    def update_content(self, request, pk=None):
        chapter = self.get_object()
        new_content_md = request.data.get('content_md')

        if new_content_md is None:
            return Response({"error": "content_md field is required."}, status=status.HTTP_400_BAD_REQUEST)

        # Markdown extensions for better rendering, including math
        md_extensions = [
            'fenced_code', 'tables', 'nl2br',
            'pymdownx.arithmatex' # For math formulas
        ]
        md_extension_configs = {
            'pymdownx.arithmatex': {
                'generic': True # Allow generic math ($, $$)
            }
        }

        # Convert Markdown to HTML
        new_content_html = markdown.markdown(
            new_content_md,
            extensions=md_extensions,
            extension_configs=md_extension_configs
        )

        chapter.content_md = new_content_md
        chapter.content_html = new_content_html
        chapter.save()

        return Response(ChapterSerializer(chapter).data, status=status.HTTP_200_OK)


def extract_headings(markdown_content):
    """
    Extracts H1-H6 headings and builds a nested structure.
    """
    headings = []
    lines = markdown_content.split('\n')
    for line in lines:
        match = re.match(r'^(#+)\s+(.*)', line)
        if match:
            level = len(match.group(1))
            title = match.group(2).strip()
            slug = re.sub(r'[^\w\s-]', '', title).strip().lower()
            slug = re.sub(r'[-\s]+', '-', slug)
            headings.append({'level': level, 'title': title, 'id': slug, 'children': []})

    if not headings:
        return []

    root_nodes = []
    stack = []

    for heading in headings:
        level = heading['level']

        while stack and stack[-1]['level'] >= level:
            stack.pop()

        if not stack:
            root_nodes.append(heading)
        else:
            stack[-1]['children'].append(heading)

        stack.append(heading)

    return root_nodes

class BookImportView(APIView):
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]
    permission_classes = [permissions.IsAdminUser] # 只有管理员可以导入

    def post(self, request, format=None):
        import tempfile
        import zipfile
        from urllib.parse import unquote

        uploaded_file = request.FILES.get('file')
        cover_image_file = request.FILES.get('cover_image')
        title = request.data.get('title')
        author = request.data.get('author', '')
        description = request.data.get('description', '')
        publication_date = request.data.get('publication_date', None)
        tags_str = request.data.get('tags', '')

        if not uploaded_file:
            return Response({"error": "A markdown or zip file is required."}, status=status.HTTP_400_BAD_REQUEST)

        content = ""
        base_path_for_images = None
        temp_dir_obj = None
        book_obj = None

        try:
            if uploaded_file.name.endswith('.zip'):
                temp_dir_obj = tempfile.TemporaryDirectory()
                temp_dir = Path(temp_dir_obj.name)

                zip_path = temp_dir / uploaded_file.name
                with open(zip_path, 'wb+') as destination:
                    for chunk in uploaded_file.chunks():
                        destination.write(chunk)

                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(temp_dir)

                md_files = list(temp_dir.glob('**/*.md'))
                if not md_files:
                    return Response({"error": "No markdown file found in the zip archive."}, status=status.HTTP_400_BAD_REQUEST)

                markdown_file_path = md_files[0]
                base_path_for_images = markdown_file_path.parent
                content = markdown_file_path.read_text(encoding='utf-8')

            elif uploaded_file.name.endswith('.md'):
                content = uploaded_file.read().decode('utf-8')
            else:
                return Response({"error": "Unsupported file type. Please upload a .md or .zip file."}, status=status.HTTP_400_BAD_REQUEST)

            if not title:
                title_match = re.search(r'^#\s*(.+)', content, re.MULTILINE)
                if title_match:
                    title = title_match.group(1).strip()
                else:
                    title = Path(uploaded_file.name).stem

            if not title:
                return Response({"error": "Book title is required."}, status=status.HTTP_400_BAD_REQUEST)

            with transaction.atomic():
                cover_image_path = None
                if cover_image_file:
                    media_root = Path(settings.MEDIA_ROOT)
                    cover_dest_dir = media_root / 'covers'
                    cover_dest_dir.mkdir(parents=True, exist_ok=True)

                    cover_filename = cover_image_file.name
                    dest_path = cover_dest_dir / cover_filename

                    with open(dest_path, 'wb+') as destination:
                        for chunk in cover_image_file.chunks():
                            destination.write(chunk)
                    cover_image_path = f"covers/{cover_filename}"

                book_obj, created = Book.objects.update_or_create(
                    title=title,
                    defaults={
                        'author': author,
                        'description': description,
                        'cover_image': cover_image_path,
                        'publication_date': publication_date,
                    }
                )

                tags_list = [t.strip() for t in tags_str.split(',') if t.strip()]
                book_obj.tags.clear()
                for tag_name in tags_list:
                    tag, _ = Tag.objects.get_or_create(name=tag_name)
                    book_obj.tags.add(tag)

                if base_path_for_images:
                    def replace_image_path(match):
                        alt_text = match.group(1)
                        original_path_str = unquote(match.group(2))

                        if original_path_str.startswith(('http://', 'https://', 'data:')):
                            return match.group(0)

                        try:
                            # Resolve path and ensure it's a file within the temp directory
                            original_path_str = original_path_str.replace('\\', '/')
                            src_image_path = (base_path_for_images / original_path_str).resolve(strict=True)

                            if not str(src_image_path).startswith(str(base_path_for_images.resolve())):
                                return match.group(0)

                            sanitized_title = re.sub(r'[^\w\-_\.]', '_', book_obj.title)
                            image_filename = src_image_path.name
                            image_dest_dir = Path(settings.MEDIA_ROOT) / 'book_images' / sanitized_title
                            image_dest_dir.mkdir(parents=True, exist_ok=True)
                            dest_image_path = image_dest_dir / image_filename

                            shutil.move(str(src_image_path), str(dest_image_path))

                            new_path = posixpath.join(settings.MEDIA_URL, 'book_images', sanitized_title, image_filename)
                            return f'![{alt_text}]({new_path})'
                        except (FileNotFoundError, ValueError):
                            # This will catch resolution errors or if the file doesn't exist
                            return match.group(0)
                        except Exception:
                            # Catch any other error during file move or path creation
                            return match.group(0)

                    content = re.sub(r'!\[(.*?)\]\((.*?)\)', replace_image_path, content)

                book_obj.chapters.all().delete()

                chapters_md = re.split(r'(?m)^# (?!#)', content)

                md_extensions = ['fenced_code', 'tables', 'nl2br', 'pymdownx.arithmatex']
                md_extension_configs = {'pymdownx.arithmatex': {'generic': True}}

                chapter_order = 0
                preamble = chapters_md[0].strip()
                if preamble and not re.fullmatch(r'\s*', preamble):
                    Chapter.objects.create(
                        book=book_obj,
                        title="前言",
                        content_md=preamble,
                        content_html=markdown.markdown(preamble, extensions=md_extensions, extension_configs=md_extension_configs),
                        order=chapter_order
                    )
                    chapter_order += 1

                for i in range(1, len(chapters_md)):
                    chapter_full_content = chapters_md[i]
                    if not chapter_full_content.strip():
                        continue
                    parts = chapter_full_content.split('\n', 1)
                    chapter_title = parts[0].strip()
                    chapter_content_md = "# " + chapter_full_content.strip()

                    Chapter.objects.create(
                        book=book_obj,
                        title=chapter_title,
                        content_md=chapter_content_md,
                        content_html=markdown.markdown(chapter_content_md, extensions=md_extensions, extension_configs=md_extension_configs),
                        heading_structure=extract_headings(chapter_content_md),
                        order=chapter_order
                    )
                    chapter_order += 1

            serializer = BookSerializer(book_obj)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({"error": f"An unexpected error occurred: {e!s}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        finally:
            if temp_dir_obj:
                temp_dir_obj.cleanup()

class EBookViewSet(viewsets.ModelViewSet):
    queryset = EBook.objects.all()
    serializer_class = EBookSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]

    @action(detail=False, methods=['post'])
    def upload(self, request, *args, **kwargs):
        file = request.FILES.get('file')
        if not file:
            return Response({'error': 'No file provided'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            content = file.read().decode('utf-8')
            # Simple parsing for title and author from markdown
            title_match = re.search(r'^#\s+(.*)', content, re.MULTILINE)
            title = title_match.group(1).strip() if title_match else file.name

            author_match = re.search(r'author:\s*(.*)', content, re.IGNORECASE)
            author = author_match.group(1).strip() if author_match else ''

            ebook = EBook.objects.create(
                title=title,
                author=author,
                content=content
            )
            serializer = self.get_serializer(ebook)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
