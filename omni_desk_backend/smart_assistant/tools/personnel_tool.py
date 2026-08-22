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
    # R5-D2 收敛到 BaseTool.extract_keywords:旧链只剥 谁→是→的,
    # 不含通用指令词 搜索/查找,故显式置空 command_words 保证行为逐字等价。
    command_words = ()
    stopwords = ("谁", "是", "的")

    def execute(self, query=None, context=None, params=None, scope=None, qs=None) -> dict:
        """搜索人员信息,仅返回脱敏字段(phone_number 已做最小字段级脱敏)。

        支持两种调用方式(向后兼容):
        - 旧:execute(query, context) — 由原生 tool_calls 旧签名/直调路径使用
        - 新:execute(params, scope, qs) — 由 scope-aware 执行分支使用

        R5-D1 统一:两条路径都经 ``scoped_queryset`` 取数,SELF/DEPARTMENT/GLOBAL
        三级 scope 在两个入口下语义一致。
        """
        personnel_qs = self.scoped_queryset(context, qs=qs, scope=scope)
        search_query = query
        if isinstance(params, dict) and params.get("query"):
            search_query = params["query"]
        keywords = self.extract_keywords(search_query or "")
        if personnel_qs is None:
            # 非 scope-aware 兜底(不应发生:PersonnelTool 实现了 build_base_queryset)
            personnel_qs = Personnel.objects.select_related("position").all()
        personnel_list = personnel_qs.filter(name__icontains=keywords)
        if isinstance(params, dict):
            if params.get("department"):
                personnel_list = personnel_list.filter(department=params["department"])
            if params.get("status"):
                # schema 暴露中文枚举(在职/离职),模型存 code(active/inactive),
                # 先映射回 code 再过滤,否则中文值查不到任何记录
                label_to_code = {label: code for code, label in Personnel.STATUS_CHOICES}
                status_code = label_to_code.get(params["status"], params["status"])
                personnel_list = personnel_list.filter(status=status_code)
        personnel_list = personnel_list[:10]

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
