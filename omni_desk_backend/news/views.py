from django.db.models import Count
from django.db.models.functions import TruncMonth
from rest_framework import viewsets
from rest_framework.permissions import IsAdminOrReadOnly
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import NewsArticle, NewsType
from .serializers import NewsArticleSerializer, NewsTypeSerializer


class NewsTypeViewSet(viewsets.ModelViewSet):
    queryset = NewsType.objects.all()
    serializer_class = NewsTypeSerializer
    permission_classes = [IsAdminOrReadOnly]

class NewsArticleViewSet(viewsets.ModelViewSet):
    queryset = NewsArticle.objects.select_related('personnel', 'news_type').all()
    serializer_class = NewsArticleSerializer
    permission_classes = [IsAdminOrReadOnly]

    def get_queryset(self):
        queryset = NewsArticle.objects.select_related('personnel', 'news_type')
        personnel_id = self.request.query_params.get('personnel_id')
        month = self.request.query_params.get('month')
        type_id = self.request.query_params.get('type_id')

        if personnel_id:
            queryset = queryset.filter(personnel_id=personnel_id)
        if month:
            queryset = queryset.filter(publication_date__year=month.split('-')[0], publication_date__month=month.split('-')[1])
        if type_id:
            queryset = queryset.filter(news_type_id=type_id)

        return queryset

    def perform_create(self, serializer):
        serializer.save(personnel_id=self.request.data.get('personnel_id'), news_type_id=self.request.data.get('news_type_id'))

class NewsStatsView(APIView):
    def get(self, request, *args, **kwargs):
        total_articles = NewsArticle.objects.count()

        by_person_monthly = (
            NewsArticle.objects
            .annotate(month=TruncMonth('publication_date'))
            .values('personnel__username', 'month')
            .annotate(count=Count('id'))
            .order_by('personnel__username', 'month')
        )

        stats = {
            'total_articles': total_articles,
            'by_person': {}
        }

        # Process monthly data and calculate totals simultaneously
        for item in by_person_monthly:
            person = item['personnel__username']
            month_str = item['month'].strftime('%Y-%m')
            count = item['count']

            if person not in stats['by_person']:
                stats['by_person'][person] = {
                    'total': 0,
                    'monthly': {}
                }

            stats['by_person'][person]['monthly'][month_str] = count
            stats['by_person'][person]['total'] += count

        return Response(stats)
