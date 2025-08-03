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


class BookImportView(APIView):
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]
    permission_classes = [permissions.IsAdminUser] # 只有管理员可以导入

    def post(self, request, format=None):
        markdown_file = request.FILES.get('markdown_file')
        cover_image_file = request.FILES.get('cover_image')
        title = request.data.get('title')
        author = request.data.get('author', '')
        description = request.data.get('description', '')
        publication_date = request.data.get('publication_date', None)
        tags_str = request.data.get('tags', '')

        if not markdown_file:
            return Response({"error": "Markdown file is required."}, status=status.HTTP_400_BAD_REQUEST)
        
        # Read markdown content
        try:
            content = markdown_file.read().decode('utf-8')
        except Exception as e:
            return Response({"error": f"Error reading markdown file: {e}"}, status=status.HTTP_400_BAD_REQUEST)

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
                        original_path = match.group(2) if match.group(2) else match.group(4)
                        if original_path.startswith(('http://', 'https://', 'data:')):
                            return match.group(0)

                        # For web import, assume image path is relative to the markdown file in the upload
                        # For simplicity, we'll just copy it to a generic book_images folder
                        # In a real scenario, you might want to associate it with the book ID
                        image_filename = Path(original_path).name
                        media_root_path = Path(settings.MEDIA_ROOT)
                        
                        # Sanitize title for directory name
                        sanitized_title = re.sub(r'[^\w\-_\. ]', '_', book_obj.title)
                        book_images_dir = media_root_path / 'book_images' / sanitized_title
                        book_images_dir.mkdir(parents=True, exist_ok=True)
                        dest_path = book_images_dir / image_filename

                        # This part of image handling is simplified for web upload.
                        # A robust solution would involve accepting a zip file with images,
                        # or having a separate image upload process.
                        # For now, we assume images are either external URLs or pre-uploaded.
                        # If a local path is referenced, it will remain as is, and the user
                        # would need to ensure the image is accessible via media URL or external.
                        return match.group(0) # Keep original path for now

                    chapter_content_md = re.sub(
                        r'(!\[.*?\]\((.+?)\))|(<img\s+src="([^"]+)"[^>]*>)',
                        replace_image_path,
                        chapter_content_md,
                        flags=re.IGNORECASE
                    )

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
            
            return Response({"message": f"Book '{book_obj.title}' imported successfully with {chapter_order} chapters."}, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({"error": f"Error importing book: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
