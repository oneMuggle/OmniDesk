from personnel.models import Personnel
from .base import BaseTool


def _mask_phone(phone: str) -> str:
    """最小脱敏:保留前 3 后 4,中间用 **** 替代;长度过短返回 ***。

    目的:在 ``PersonnelTool.execute`` 返回 ``tool_result`` 时,对 ``phone_number``
    做最基础字段级脱敏,避免原始手机号直接进入 SmartChat 响应体。Phase 2 兑现
    的 ``PIISanitizerHook`` 落地后,本函数可移除。
    """
    if not phone or len(phone) <= 4:
        return "***"
    return f"{phone[:3]}****{phone[-4:]}"


class PersonnelTool(BaseTool):
    name = "personnel_query"
    description = "查询人员信息（姓名、部门、职位、状态）"
    intent_type = "personnel_query"
    risk_level = "read"  # 显式声明:只读查询工具,无副作用

    def execute(self, query=None, context=None, params=None, scope=None, qs=None) -> dict:
        """搜索人员信息,仅返回脱敏字段(phone_number 已做最小字段级脱敏)。

        支持两种调用方式(向后兼容):
        - 旧:execute(query, context) — 由原生 tool_calls 旧签名/直调路径使用
        - 新:execute(params, scope, qs) — 由 scope-aware 执行分支使用
          (C-1 修复:复用 scoped queryset,确保 SELF/DEPARTMENT/GLOBAL 生效)。
        """
        # 新路径(scope-aware):用调用方注入的 scoped queryset 替代全量表查询
        if qs is not None and scope is not None:
            search_query = params.get("query") if isinstance(params, dict) and params.get("query") else (query or "")
            keywords = self._extract_keywords(search_query)
            personnel_list = qs.filter(name__icontains=keywords)[:10]
        else:
            keywords = self._extract_keywords(query or "")
            personnel_list = Personnel.objects.filter(name__icontains=keywords).select_related("position")[:10]

        if not personnel_list.exists():
            return {
                "found": False,
                "message": f'未找到与 "{keywords}" 匹配的人员',
            }

        results = []
        for p in personnel_list:
            results.append(
                {
                    "name": p.name,
                    "department": p.department or "未分配",
                    "position": p.position.name if p.position else "未设置",
                    "status": p.get_status_display(),
                    # 字段级最小脱敏:保留前 3 后 4(详见 _mask_phone docstring)
                    "phone_number": _mask_phone(p.phone_number) if p.phone_number else "未登记",
                }
            )

        return {
            "found": True,
            "count": len(results),
            "personnel": results,
        }

    @staticmethod
    def _extract_keywords(query: str) -> str:
        """从查询文本中剥离停用词(新旧路径共用,保证关键词口径一致)。"""
        return query.replace("谁", "").replace("是", "").replace("的", "").strip()

    @classmethod
    def get_openai_tool_schema(cls) -> dict:
        """OpenAI strict mode tool schema — 查询人员信息(姓名/部门/职位)。"""
        return {
            "type": "function",
            "function": {
                "name": cls.intent_type,
                "description": (
                    "查询人员信息(姓名、部门、职位、状态),仅返回脱敏后的手机号。"
                    "示例 query: '查张三'、'研发部有哪些人'、'谁在岗'。"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "自然语言查询,匹配姓名关键词",
                        },
                        "department": {
                            "type": "string",
                            "description": "按部门精确过滤(可选)",
                        },
                        "status": {
                            "type": "string",
                            "enum": ["在职", "离职", "休假", "未知"],
                            "description": "按状态过滤(可选)",
                        },
                    },
                    "required": ["query"],
                    "additionalProperties": False,
                },
                "strict": True,
            },
        }

    def get_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "intent_type": self.intent_type,
            # 与 BaseTool.get_schema 保持一致:暴露风险等级供执行器/前端门控
            "risk_level": self.risk_level,
        }

    def build_base_queryset(self):
        """返回未过滤的人员 QuerySet。"""
        return Personnel.objects.select_related("position").all()

    def _scope_self(self, qs, ctx):
        """本人范围:仅返回 ctx.user 自身关联的人员记录(经 CustomUser.personnel → Personnel.user_account 反向关系)。"""
        return qs.filter(user_account=ctx.user)
