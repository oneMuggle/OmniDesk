"""传感器模块的 AI 工具声明。

由 ``smart_assistant.capabilities`` 在启动时自动发现，见 ``docs/technical/46-ai-capability-catalog.md``。
"""

from smart_assistant.capabilities import DataScope, LOGIN_ONLY, ToolSpec, toolset


@toolset("sensors", title="传感器")
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
