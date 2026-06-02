from rest_framework import viewsets
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated

from .models import Ebook
from .serializers import EbookSerializer


class EbookPagination(PageNumberPagination):
    page_size = 10


class EbookViewSet(viewsets.ModelViewSet):
    """电子书管理 ViewSet"""

    queryset = Ebook.objects.all()
    serializer_class = EbookSerializer
    pagination_class = EbookPagination
    permission_classes = [IsAuthenticated]
