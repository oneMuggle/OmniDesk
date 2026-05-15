import re

import markdown
from django.http import HttpResponse
from rest_framework import parsers, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Book, Chapter
from .serializers import AnnotationSerializer, BookSerializer, ChapterSerializer, CommentSerializer


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
            full_markdown_content += f"- 封面：{book.cover_image.name}\n"
        if book.tags.exists():
            tags_str = ", ".join([tag.name for tag in book.tags.all()])
            full_markdown_content += f"- 标签：{tags_str}\n"
        full_markdown_content += "\n"

        for chapter in chapters:
            full_markdown_content += f"{chapter.content_md}\n\n"

        response = HttpResponse(full_markdown_content, content_type='text/markdown')
        response['Content-Disposition'] = f'attachment; filename="{book.title}.md"'
        return response


def extract_headings(markdown_content):
    """Extracts H1-H6 headings and builds a nested structure."""
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


class ChapterViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Chapter.objects.prefetch_related('comments', 'annotations')
    serializer_class = ChapterSerializer
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=True, methods=['post'])
    def add_comment(self, request, pk=None):
        chapter = self.get_object()
        serializer = CommentSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save(chapter=chapter, user=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def add_annotation(self, request, pk=None):
        chapter = self.get_object()
        serializer = AnnotationSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(chapter=chapter, user=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['put'])
    def update_content(self, request, pk=None):
        chapter = self.get_object()
        new_content_md = request.data.get('content_md')

        if new_content_md is None:
            return Response({"error": "content_md field is required."}, status=status.HTTP_400_BAD_REQUEST)

        md_extensions = ['fenced_code', 'tables', 'nl2br', 'pymdownx.arithmatex']
        md_extension_configs = {'pymdownx.arithmatex': {'generic': True}}

        new_content_html = markdown.markdown(
            new_content_md,
            extensions=md_extensions,
            extension_configs=md_extension_configs,
        )

        chapter.content_md = new_content_md
        chapter.content_html = new_content_html
        chapter.save()

        return Response(ChapterSerializer(chapter).data, status=status.HTTP_200_OK)


class BookImportView(APIView):
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]
    permission_classes = [permissions.IsAdminUser]

    def post(self, request, format=None):
        from .book_import import import_book_from_file

        uploaded_file = request.FILES.get('file')
        cover_image_file = request.FILES.get('cover_image')
        title = request.data.get('title')
        author = request.data.get('author', '')
        description = request.data.get('description', '')
        publication_date = request.data.get('publication_date', None)
        tags_str = request.data.get('tags', '')

        if not uploaded_file:
            return Response({"error": "A markdown or zip file is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            book_obj = import_book_from_file(
                uploaded_file, cover_image_file, title,
                author, description, publication_date, tags_str,
            )
            serializer = BookSerializer(book_obj)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": f"An unexpected error occurred: {e!s}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
