from news.models import NewsArticle
from .base import BaseTool


class NewsTool(BaseTool):
    name = "news_search"
    description = "搜索新闻/通知"
    intent_type = "news_search"
    risk_level = "read"  # 显式声明:只读查询工具,无副作用

    def execute(self, query: str, context: dict = None) -> dict:
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

    @classmethod
    def get_openai_tool_schema(cls) -> dict:
        """OpenAI strict mode tool schema — 搜索新闻/通知。"""
        return {
            "type": "function",
            "function": {
                "name": cls.intent_type,
                "description": (
                    "搜索新闻/通知文章,按标题模糊匹配。"
                    "示例 query: '搜索关于春节的新闻'、'最近的培训通知'。"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "搜索关键词,按标题 icontains 匹配",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "返回条目数上限,默认 10",
                        },
                    },
                    "required": ["query"],
                    "additionalProperties": False,
                },
                "strict": True,
            },
        }

    def build_base_queryset(self):
        """返回未过滤的新闻 QuerySet。"""
        return NewsArticle.objects.select_related("news_type", "personnel").all()

    def _scope_self(self, qs, ctx):
        """本人范围:仅返回 ctx.user 名下发布的新闻(按 personnel 字段 = CustomUser FK)。"""
        return qs.filter(personnel=ctx.user)
