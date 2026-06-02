import re

from rest_framework import parsers, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from ..models import EBook
from ..serializers import EBookSerializer


class EBookViewSet(viewsets.ModelViewSet):
    queryset = EBook.objects.all()
    serializer_class = EBookSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]

    @action(detail=False, methods=["post"])
    def upload(self, request, *args, **kwargs):
        file = request.FILES.get("file")
        if not file:
            return Response({"error": "No file provided"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            content = file.read().decode("utf-8")
            title_match = re.search(r"^#\s+(.*)", content, re.MULTILINE)
            title = title_match.group(1).strip() if title_match else file.name

            author_match = re.search(r"author:\s*(.*)", content, re.IGNORECASE)
            author = author_match.group(1).strip() if author_match else ""

            ebook = EBook.objects.create(
                title=title,
                author=author,
                content=content,
            )
            serializer = self.get_serializer(ebook)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
