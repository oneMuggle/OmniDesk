from news.models import NewsArticle
from .base import BaseTool


class NewsTool(BaseTool):
    name = "news_search"
    description = "搜索新闻/通知"
    intent_type = "news_search"
    risk_level = "read"  # 显式声明:只读查询工具,无副作用
    # 领域停用词(R5-D2 收敛到 BaseTool.extract_keywords;顺序与旧 replace 链一致)
    stopwords = ("新闻", "通知")

    def execute(self, query=None, context=None, params=None, scope=None, qs=None) -> dict:
        """搜索新闻文章。

        支持两种调用方式(向后兼容):
        - 旧:execute(query, context) — 由原生 tool_calls 旧签名/直调路径使用
        - 新:execute(params, scope, qs) — 由 scope-aware 执行分支使用

        R5-D1 统一:两条路径都经 ``scoped_queryset`` 取数,SELF/DEPARTMENT/GLOBAL
        三级 scope 在两个入口下语义一致(修复旧路径 SELF scope 泄露)。
        """
        articles = self.scoped_queryset(context, qs=qs, scope=scope)
        search_query = query
        if isinstance(params, dict) and params.get("query"):
            search_query = params["query"]
        keywords = self.extract_keywords(search_query or "")
        if articles is None:
            # 非 scope-aware 兜底(不应发生:NewsTool 实现了 build_base_queryset)
            articles = NewsArticle.objects.select_related("news_type", "personnel").all()
        # I-2:limit 结构化字段替换硬编码 [:10](缺失时保持 10)
        limit = params.get("limit") if isinstance(params, dict) and params.get("limit") else 10
        articles = articles.filter(title__icontains=keywords)[:limit]

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
                    "搜索新闻/通知文章,按标题模糊匹配。示例 query: '搜索关于春节的新闻'、'最近的培训通知'。"
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
