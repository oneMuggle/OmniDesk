"""人员模块的 AI 工具声明。

由 ``smart_assistant.capabilities`` 在启动时自动发现，见 ``docs/technical/46-ai-capability-catalog.md``。
"""

from smart_assistant.capabilities import DataScope, LOGIN_ONLY, PageContext, QuickPrompt, ToolSpec, toolset
from smart_assistant.capabilities.helpers import fmt_date, scoped_record


def load_personnel_context(user, record_id):
    """人员详情页上下文：可见范围与 ``personnel_query`` 相同（三级 scope）。

    不带手机号、住址、生日、身份证号等敏感字段。
    """
    from smart_assistant.tools.personnel_tool import PersonnelTool

    person = scoped_record(PersonnelTool, user, record_id)
    if person is None:
        return None
    return {
        "label": person.name,
        "fields": {
            "姓名": person.name,
            "部门": person.department,
            "职位": str(person.position) if person.position_id else None,
            "状态": person.get_status_display(),
            "入职日期": fmt_date(person.hire_date),
        },
    }


@toolset(
    "personnel",
    title="人员",
    routes=(r"^/control-panel/personnel", r"^/me/personnel"),
    quick_prompts=(QuickPrompt("我的信息", "查一下我的人员信息"),),
    page_contexts=(
        PageContext(
            record_type="personnel",
            title="人员",
            route=r"^/control-panel/personnel/(?P<record_id>\d+)(/edit)?/?$",
            loader=load_personnel_context,
        ),
    ),
)
def personnel_tools():
    from smart_assistant.tools.personnel_tool import PersonnelTool

    return [
        ToolSpec(
            tool=PersonnelTool,
            title="查询人员",
            required_permission=LOGIN_ONLY,
            data_scope=DataScope.SCOPE,
        ),
    ]
