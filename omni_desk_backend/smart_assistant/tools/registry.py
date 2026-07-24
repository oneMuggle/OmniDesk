from .base import BaseTool


class ToolRegistry:
    """工具注册表"""

    _tools: dict = {}

    @classmethod
    def register(cls, tool: BaseTool) -> None:
        cls._tools[tool.intent_type] = tool

    @classmethod
    def get_tool(cls, intent_type: str) -> BaseTool | None:
        return cls._tools.get(intent_type)

    @classmethod
    def get_all_schemas(cls) -> list:
        return [tool.get_schema() for tool in cls._tools.values()]
