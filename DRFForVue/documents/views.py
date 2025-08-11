from rest_framework import viewsets, permissions, parsers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView # For BookImportView

from .models import DocumentTemplate, GeneratedDocument, Book, Chapter, Comment, Annotation, Tag
from .serializers import DocumentTemplateSerializer, GeneratedDocumentSerializer, BookSerializer, ChapterSerializer, CommentSerializer, AnnotationSerializer, TagSerializer

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
        return self.queryset.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    @action(detail=False, methods=['post'], url_path='upload')
    def upload_template(self, request):
        file_obj = request.FILES.get('template')
        if not file_obj:
            return Response({'error': 'No file uploaded'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            template = DocumentTemplate.objects.create(
                name=file_obj.name,
                file=file_obj,
                owner=request.user
            )
            return Response(DocumentTemplateSerializer(template).data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'], url_path='analyze')
    def analyze_file(self, request):
        file_obj = request.FILES.get('file')
        if not file_obj:
            return Response({'error': 'No file uploaded'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # TODO: 实现实际的文件解析逻辑
            # 这里模拟解析结果
            result = {
                'fileName': file_obj.name,
                'people': [
                    {'name': '张三', 'origin': '北京', 'age': 30},
                    {'name': '李四', 'origin': '上海', 'age': 25}
                ]
            }
            return Response(result, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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

class BookViewSet(viewsets.ReadOnlyModelViewSet):
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
