from rest_framework import viewsets, permissions, parsers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView # For BookImportView
import tempfile # 导入 tempfile 来创建临时目录

from .file_processing import process_uploaded_file # 导入我们新创建的函数

from .models import DocumentTemplate, GeneratedDocument, Book, Chapter, Comment, Annotation, Tag
from .serializers import DocumentTemplateSerializer, GeneratedDocumentSerializer, BookSerializer, ChapterSerializer, CommentSerializer, AnnotationSerializer, TagSerializer
from compliance.models import ComplianceIssue # 导入 ComplianceIssue 模型
from compliance.serializers import ComplianceIssueSerializer # 导入 ComplianceIssue 序列化器
from llm_service.ollama_client import OllamaClient # 导入 OllamaClient

import re
import os
import shutil
from pathlib import Path
from django.conf import settings
from django.db import transaction
from django.http import HttpResponse # For file export


class DocumentTemplateViewSet(viewsets.ModelViewSet):
    queryset = DocumentTemplate.objects.all()
    serializer_class = DocumentTemplateSerializer
    permission_classes = []
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

            ollama_client = OllamaClient()
            
            # 构建提示词
            system_message = """你是一名专业的文档合规性审查员。你的任务是分析提供的文档文本，识别其中的不规范、时间冲突、内容缺失或内容与规定不符的问题。
            请以 JSON 数组的格式返回发现的所有问题，每个问题对象包含以下字段：
            - "issue_type": 问题类型，可选值为 "不规范", "时间冲突", "内容缺失", "内容与规定不符", "其他"。
            - "description": 问题的详细描述。
            - "location": 问题在文档中的大致位置（例如，页码、段落、章节）。
            - "severity": 严重程度，可选值为 "低", "中", "高", "紧急"。
            - "suggested_fix": 建议的修改方案。
            如果未发现任何问题，请返回一个空的 JSON 数组。"""

            prompt = f"请分析以下文档内容，并识别其中存在的合规性问题：\n\n{extracted_text}"

            # 调用 Ollama 进行分析
            ollama_response_json = ollama_client.generate(prompt=prompt, system_message=system_message)
            
            try:
                compliance_issues_data = json.loads(ollama_response_json)
                if not isinstance(compliance_issues_data, list):
                    raise ValueError("Ollama response is not a JSON array.")
            except json.JSONDecodeError:
                raise Exception(f"Ollama 返回的不是有效的 JSON 格式: {ollama_response_json}")
            except ValueError as ve:
                raise Exception(f"Ollama 返回数据结构不正确: {ve}")

            created_issues = []
            for issue_data in compliance_issues_data:
                # 检查必要的字段是否存在
                required_fields = ['issue_type', 'description', 'location', 'severity', 'suggested_fix']
                if not all(field in issue_data for field in required_fields):
                    print(f"Skipping malformed issue data: {issue_data}")
                    continue

                # 创建 ComplianceIssue 实例
                issue = ComplianceIssue.objects.create(
                    project=document_template.project, # 假设 DocumentTemplate 已经关联了 Project
                    document_template=document_template,
                    issue_type=issue_data.get('issue_type', '其他'),
                    description=issue_data['description'],
                    location=issue_data['location'],
                    severity=issue_data.get('severity', '中'),
                    # suggested_fix 字段目前 ComplianceIssue 模型中没有，如果需要可以后续添加
                )
                created_issues.append(ComplianceIssueSerializer(issue).data)
            
            return Response({'message': 'Analysis complete', 'issues': created_issues}, status=status.HTTP_200_OK)
        except DocumentTemplate.DoesNotExist:
            return Response({'error': 'DocumentTemplate not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': f'文件分析失败: {e}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class GeneratedDocumentViewSet(viewsets.ModelViewSet):
    queryset = GeneratedDocument.objects.all()
    serializer_class = GeneratedDocumentSerializer
    permission_classes = []
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
    queryset = Book.objects.all()
    serializer_class = BookSerializer
    permission_classes = []

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
    queryset = Chapter.objects.all()
    serializer_class = ChapterSerializer
    permission_classes = []

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def add_comment(self, request, pk=None):
        chapter = self.get_object()
        serializer = CommentSerializer(data=request.data)
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
        import zipfile
        import tempfile

        uploaded_file = request.FILES.get('file') # Accepting a single file (md or zip)
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

        if uploaded_file.name.endswith('.zip'):
            with tempfile.TemporaryDirectory() as temp_dir:
                zip_path = os.path.join(temp_dir, uploaded_file.name)
                with open(zip_path, 'wb+') as destination:
                    for chunk in uploaded_file.chunks():
                        destination.write(chunk)
                
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(temp_dir)
                
                # Find the main markdown file in the zip
                md_files = list(Path(temp_dir).glob('**/*.md'))
                if not md_files:
                    return Response({"error": "No markdown file found in the zip archive."}, status=status.HTTP_400_BAD_REQUEST)
                
                # Using the first md file found as the main one
                markdown_file_path = md_files[0]
                base_path_for_images = markdown_file_path.parent
                content = markdown_file_path.read_text(encoding='utf-8')

        elif uploaded_file.name.endswith('.md'):
            content = uploaded_file.read().decode('utf-8')
            # For single md file upload, relative images are not supported directly
            # unless we have a convention. For now, we assume they are absolute URLs.
            base_path_for_images = None # Or handle it differently if needed
        else:
            return Response({"error": "Unsupported file type. Please upload a .md or .zip file."}, status=status.HTTP_400_BAD_REQUEST)

        # Extract tags
        tags_list = [t.strip() for t in tags_str.split(',') if t.strip()]

        # Process cover image
        cover_image_path = None
        if cover_image_file:
            try:
                media_root = Path(settings.MEDIA_ROOT)
                cover_dest_dir = media_root / 'covers'
                cover_dest_dir.mkdir(parents=True, exist_ok=True)
                
                cover_filename = cover_image_file.name
                dest_path = cover_dest_dir / cover_filename
                
                with open(dest_path, 'wb+') as destination:
                    for chunk in cover_image_file.chunks():
                        destination.write(chunk)
                cover_image_path = f"covers/{cover_filename}"
            except Exception as e:
                return Response({"error": f"Error saving cover image: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Ensure title is present
        if not title:
            title_match = re.search(r'^#\s*(.+)', content, re.MULTILINE)
            if title_match:
                title = title_match.group(1).strip()
            else:
                return Response({"error": "Book title is required or must be present as H1 in markdown."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            with transaction.atomic():
                # Create/Update Book
                book_obj, created = Book.objects.update_or_create(
                    title=title,
                    defaults={
                        'author': author,
                        'description': description,
                        'cover_image': cover_image_path,
                        'publication_date': publication_date,
                    }
                )

                # Add tags
                book_obj.tags.clear()
                for tag_name in tags_list:
                    tag, _ = Tag.objects.get_or_create(name=tag_name)
                    book_obj.tags.add(tag)

                # Clear existing chapters
                book_obj.chapters.all().delete()

                # Split and Process Chapters (similar to import_book command)
                chapters_md = re.split(r'(?m)^# (?!#)', content)
                
                md_extensions = [
                    'fenced_code', 'tables', 'nl2br',
                    'pymdownx.arithmatex'
                ]
                md_extension_configs = {
                    'pymdownx.arithmatex': {
                        'generic': True
                    }
                }

                chapter_order = 0
                preamble = chapters_md[0].strip()
                if preamble and not re.fullmatch(r'\s*', preamble):
                    chapter_title = "前言"
                    chapter_content_md = preamble
                    chapter_content_html = markdown.markdown(
                        chapter_content_md,
                        extensions=md_extensions,
                        extension_configs=md_extension_configs
                    )
                    Chapter.objects.create(
                        book=book_obj,
                        title=chapter_title,
                        content_md=chapter_content_md,
                        content_html=chapter_content_html,
                        order=chapter_order
                    )
                    chapter_order += 1

                for i in range(1, len(chapters_md)):
                    chapter_full_content = chapters_md[i]
                    title_line_match = re.match(r'^#\s*(.+)', chapter_full_content)
                    if title_line_match:
                        chapter_title = title_line_match.group(1).strip()
                    else:
                        chapter_title = f"Untitled Chapter {chapter_order}"
                    
                    chapter_content_md = "# " + chapter_full_content.strip()

                    # Image Path Correction within Chapter Content
                    def replace_image_path(match):
                        alt_text = match.group(1)
                        original_path_str = match.group(2)

                        if not original_path_str or original_path_str.startswith(('http://', 'https://', 'data:')):
                            return match.group(0)
                        
                        if not base_path_for_images:
                            # Cannot resolve relative paths if not from a zip
                            return match.group(0)

                        src_image_path = base_path_for_images / original_path_str
                        if not src_image_path.is_file():
                            return match.group(0) # Keep if image not found

                        try:
                            sanitized_title = re.sub(r'[^\w\-_\. ]', '_', book_obj.title)
                            image_dest_dir = Path(settings.MEDIA_ROOT) / 'book_images' / sanitized_title
                            image_dest_dir.mkdir(parents=True, exist_ok=True)
                            
                            dest_image_path = image_dest_dir / src_image_path.name
                            shutil.copy(src_image_path, dest_image_path)
                            
                            new_path = f"{settings.MEDIA_URL}book_images/{sanitized_title}/{src_image_path.name}"
                            return f'![{alt_text}]({new_path})'
                        except Exception:
                            return match.group(0) # Keep original on error

                    chapter_content_md = re.sub(r'!\[(.*?)\]\((.*?)\)', replace_image_path, chapter_content_md)

                    chapter_content_html = markdown.markdown(
                        chapter_content_md,
                        extensions=md_extensions,
                        extension_configs=md_extension_configs
                    )

                    headings = extract_headings(chapter_content_md)

                    Chapter.objects.create(
                        book=book_obj,
                        title=chapter_title,
                        content_md=chapter_content_md,
                        content_html=chapter_content_html,
                        heading_structure=headings,
                        order=chapter_order
                    )
                    chapter_order += 1
            
            return Response({"message": f"Book '{book_obj.title}' imported successfully with {chapter_order} chapters."}, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({"error": f"Error importing book: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
