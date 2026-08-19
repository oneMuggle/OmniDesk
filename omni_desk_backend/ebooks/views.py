from rest_framework import viewsets
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated

from observability import get_logger

from .models import Ebook
from .serializers import EbookSerializer

logger = get_logger(__name__, "ebooks")


class EbookPagination(PageNumberPagination):
    page_size = 10


class EbookViewSet(viewsets.ModelViewSet):
    """电子书管理 ViewSet"""

    queryset = Ebook.objects.all()
    serializer_class = EbookSerializer
    pagination_class = EbookPagination
    permission_classes = [IsAuthenticated]

    def list(self, request, *args, **kwargs):
        logger.info("ebooks.view.entered", extra={"event": "ebooks.view.entered"})
        return super().list(request, *args, **kwargs)
