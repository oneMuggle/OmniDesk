from news.models import NewsArticle
from .base import BaseTool


class NewsTool(BaseTool):
    name = "news_search"
    description = "搜索新闻/通知"
    intent_type = "news_search"

    def execute(self, query: str, context: dict | None = None) -> dict:
        """搜索新闻文章"""
        keywords = query.replace("搜索", "").replace("查找", "").replace("新闻", "").replace("通知", "").strip()

        articles = NewsArticle.objects.filter(title__icontains=keywords).select_related("news_type", "personnel")[:10]

        if not articles.exists():
            return {
                "found": False,
                "message": f'未找到与 "{keywords}" 相关的新闻',
            }

        results = []
        for a in articles:
            results.append(
                {
                    "title": a.title,
                    "link": a.link,
                    "publication_date": str(a.publication_date),
                    "news_type": a.news_type.name if a.news_type else "未分类",
                    "personnel": a.personnel.username if a.personnel else "未知",
                }
            )

        return {
            "found": True,
            "count": len(results),
            "articles": results,
        }
