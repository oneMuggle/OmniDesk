"""传感器模块的 AI 工具声明。

由 ``smart_assistant.capabilities`` 在启动时自动发现，见 ``docs/technical/46-ai-capability-catalog.md``。
"""

from smart_assistant.capabilities import DataScope, LOGIN_ONLY, PageContext, QuickPrompt, ToolSpec, toolset
from smart_assistant.capabilities.helpers import fmt_date, scoped_record


def load_sensor_context(user, record_id):
    """传感器详情页上下文：可见范围与 ``sensor_query`` 相同（三级 scope）。"""
    from smart_assistant.tools.sensor_tool import SensorTool

    sensor = scoped_record(SensorTool, user, record_id)
    if sensor is None:
        return None
    return {
        "label": sensor.name or sensor.sensor_number,
        "fields": {
            "名称": sensor.name,
            "编号": sensor.sensor_number,
            "类别": str(sensor.sensor_category) if sensor.sensor_category_id else None,
            "状态": sensor.get_status_display(),
            "存放位置": str(sensor.location) if sensor.location_id else None,
            "上次校准": fmt_date(sensor.last_calibration_date),
            "校准周期（天）": sensor.calibration_interval_days,
        },
    }


@toolset(
    "sensors",
    title="传感器",
    routes=(r"^/control-panel/sensors",),
    quick_prompts=(
        QuickPrompt("待校准", "哪些传感器快到校准日期了？"),
        QuickPrompt("校准记录", "这个传感器的校准记录是什么？", routes=(r"^/control-panel/sensors/\d+",)),
    ),
    page_contexts=(
        PageContext(
            record_type="sensor",
            title="传感器",
            route=r"^/control-panel/sensors/(?P<record_id>\d+)(/calibration/[a-z]+)?/?$",
            loader=load_sensor_context,
        ),
    ),
)
def sensor_tools():
    from smart_assistant.tools.sensor_tool import SensorTool

    return [
        ToolSpec(
            tool=SensorTool,
            title="查询传感器",
            required_permission=LOGIN_ONLY,
            data_scope=DataScope.SCOPE,
        ),
    ]
