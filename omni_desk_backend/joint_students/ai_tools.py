"""联培生模块的 AI 工具声明。

由 ``smart_assistant.capabilities`` 在启动时自动发现，见 ``docs/technical/46-ai-capability-catalog.md``。
"""

from smart_assistant.capabilities import DataScope, LOGIN_ONLY, PageContext, QuickPrompt, ToolSpec, toolset
from smart_assistant.capabilities.helpers import clamp_limit, context_user, tool_params
from smart_assistant.tools.base import BaseTool


class JointStudentQueryTool(BaseTool):
    """查询联培生及其最近一次月报状态（只读）。

    可见范围与 ``/api/joint-students/students/`` 完全一致，调用
    ``joint_students.services.access.visible_joint_students``：管理员组 / superuser
    看全部，导师看名下，本人看自己。智能助手的 DEPARTMENT / GLOBAL scope 不会扩大
    这一范围，因此不实现 scope 三件套。
    """

    name = "joint_student_query"
    description = "查询联培生（姓名、学号、导师、在读状态、最近一次月报状态），按联培生模块的可见范围返回"
    intent_type = "joint_student_query"
    risk_level = "read"
    required_auth = True

    def execute(self, query=None, context=None, params=None, **_kwargs) -> dict:
        from django.db.models import Q

        from joint_students.models import JointStudent
        from joint_students.services.access import visible_joint_students

        user = context_user(context)
        if user is None:
            return {"found": False, "message": "未识别到当前用户，无法查询联培生", "module_label": "联培生"}

        params = tool_params(params)
        qs = visible_joint_students(user, JointStudent.objects.select_related("personnel", "mentor"))

        if params.get("active_only", True) is not False:
            qs = qs.filter(is_active=True)
        student_type = params.get("student_type")
        if student_type in {code for code, _ in JointStudent.STUDENT_TYPE_CHOICES}:
            qs = qs.filter(student_type=student_type)
        keyword = str(params.get("keyword") or "").strip()
        if keyword:
            qs = qs.filter(
                Q(personnel__name__icontains=keyword)
                | Q(student_id__icontains=keyword)
                | Q(mentor__name__icontains=keyword)
            )

        limit = clamp_limit(params.get("limit"))
        students = []
        for js in qs.order_by("id")[:limit]:
            latest = js.monthly_reports.order_by("-year", "-month").first()
            students.append(
                {
                    "id": js.id,
                    "name": js.personnel.name if js.personnel_id else "",
                    "student_type": js.get_student_type_display(),
                    "student_id": js.student_id,
                    "mentor": js.mentor.name if js.mentor_id else None,
                    "enrollment_date": js.enrollment_date.isoformat() if js.enrollment_date else None,
                    "graduation_date": js.graduation_date.isoformat() if js.graduation_date else None,
                    "is_active": js.is_active,
                    "latest_report": (
                        {
                            "period": f"{latest.year}-{latest.month:02d}",
                            "status": latest.get_status_display(),
                        }
                        if latest
                        else None
                    ),
                }
            )

        if not students:
            return {"found": False, "message": "没有你可以查看的联培生记录", "module_label": "联培生"}
        return {"found": True, "count": len(students), "students": students, "module_label": "联培生"}

    @classmethod
    def get_openai_tool_schema(cls) -> dict:
        return {
            "type": "function",
            "function": {
                "name": cls.intent_type,
                "description": (
                    "查询联培生信息与最近一次月报状态。管理员可查全部，导师只能查名下学生，"
                    "学生只能查自己。示例：'我带的联培生有哪些'、'张三这个月的月报交了吗'。"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "用户的原始问题（用于理解意图，不直接作为筛选词）"},
                        "keyword": {"type": "string", "description": "按姓名、学号或导师姓名筛选（可选）"},
                        "student_type": {
                            "type": "string",
                            "enum": ["master", "phd"],
                            "description": "学生类型：master 硕士 / phd 博士（可选）",
                        },
                        "active_only": {"type": "boolean", "description": "是否只看在读学生，默认是"},
                        "limit": {"type": "integer", "description": "返回条数，默认 10，最多 20"},
                    },
                    "required": ["query"],
                    "additionalProperties": False,
                },
                "strict": True,
            },
        }


def load_joint_student_context(user, record_id):
    """联培生详情页上下文：可见范围与 ``/api/joint-students/students/`` 相同。"""
    from joint_students.models import JointStudent
    from joint_students.services.access import visible_joint_students

    js = (
        visible_joint_students(user, JointStudent.objects.select_related("personnel", "mentor"))
        .filter(pk=record_id)
        .first()
    )
    if js is None:
        return None
    name = js.personnel.name if js.personnel_id else js.student_id
    latest = js.monthly_reports.order_by("-year", "-month").first()
    return {
        "label": name,
        "fields": {
            "姓名": name,
            "类型": js.get_student_type_display(),
            "学号": js.student_id,
            "导师": js.mentor.name if js.mentor_id else None,
            "在读": "是" if js.is_active else "否",
            "入学日期": js.enrollment_date.isoformat() if js.enrollment_date else None,
            "最近月报": f"{latest.year}-{latest.month:02d} {latest.get_status_display()}" if latest else "暂无",
        },
    }


@toolset(
    "joint_students",
    title="联培生",
    routes=(r"^/joint-students",),
    quick_prompts=(
        QuickPrompt("联培生概况", "列出我可以查看的联培生及最近月报状态"),
        QuickPrompt(
            "月报情况",
            "这个联培生最近的月报情况怎么样？",
            routes=(r"^/joint-students/admin/students/\d+",),
        ),
    ),
    page_contexts=(
        PageContext(
            record_type="joint_student",
            title="联培生",
            route=r"^/joint-students/admin/students/(?P<record_id>\d+)(/edit)?/?$",
            loader=load_joint_student_context,
        ),
    ),
)
def joint_student_tools():
    return [
        ToolSpec(
            tool=JointStudentQueryTool,
            title="查询联培生",
            required_permission=LOGIN_ONLY,
            data_scope=DataScope.MODULE,
        ),
    ]
