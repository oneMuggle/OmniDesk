from news.models import NewsArticle
from .base import BaseTool


class NewsTool(BaseTool):
    name = "news_search"
    description = "搜索新闻/通知"
    intent_type = "news_search"
    risk_level = "read"  # 显式声明:只读查询工具,无副作用

    def execute(self, query=None, context=None, params=None, scope=None, qs=None) -> dict:
        """搜索新闻文章。

        支持两种调用方式(向后兼容):
        - 旧:execute(query, context) — 由原生 tool_calls 旧签名/直调路径使用
        - 新:execute(params, scope, qs) — 由 scope-aware 执行分支使用
          (C-1 修复:复用 build_base_queryset + get_queryset_for_scope 的
          scoped queryset,确保 SELF/DEPARTMENT/GLOBAL 三级 scope 生效)。
        """
        # 新路径(scope-aware):用调用方注入的 scoped queryset 替代全量表查询
        if qs is not None and scope is not None:
            search_query = params.get("query") if isinstance(params, dict) and params.get("query") else (query or "")
            keywords = self._extract_keywords(search_query)
            # I-2:limit 结构化字段替换硬编码 [:10](缺失时保持 10)
            limit = params.get("limit") if isinstance(params, dict) and params.get("limit") else 10
            articles = qs.filter(title__icontains=keywords)[:limit]
        else:
            keywords = self._extract_keywords(query or "")
            articles = NewsArticle.objects.filter(title__icontains=keywords).select_related("news_type", "personnel")[
                :10
            ]

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

    @staticmethod
    def _extract_keywords(query: str) -> str:
        """从查询文本中剥离停用词(新旧路径共用,保证关键词口径一致)。"""
        return query.replace("搜索", "").replace("查找", "").replace("新闻", "").replace("通知", "").strip()

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
