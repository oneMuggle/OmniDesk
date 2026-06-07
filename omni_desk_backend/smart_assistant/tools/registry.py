from .base import BaseTool


class ToolRegistry:
    """工具注册表"""

    _tools: dict = {}

    @classmethod
    def register(cls, tool: BaseTool) -> None:
        if not isinstance(tool, BaseTool):
            raise TypeError(
                f"{tool!r} is not a BaseTool instance (got {type(tool).__name__})"
            )
        if not tool.intent_type:
            raise ValueError(
                f"Tool {tool.name or '<unnamed>'} missing intent_type"
            )
        cls._tools[tool.intent_type] = tool

    @classmethod
    def get_tool(cls, intent_type: str) -> BaseTool | None:
        return cls._tools.get(intent_type)

    @classmethod
    def get_tool_for_user(cls, intent_type: str, user) -> BaseTool | None:
        """按用户返回工具(权限校验)。

        若工具 ``required_auth=True`` 且用户未认证(``user`` 为 ``None`` 或
        ``user.is_authenticated`` 为 ``False``),返回 ``None``。该方法不抛异常
        —— 调用方应自行决定如何处理"用户未授权"这一信号(常见做法:返回
        401/403 或切换到 ``fallback`` 文本回答)。

        参数:
            intent_type: 工具的 intent_type 标识
            user: 当前请求用户(Django ``User`` 实例)或 ``None``

        返回:
            对应工具实例,或当未找到 / 未授权时返回 ``None``。
        """
        tool = cls._tools.get(intent_type)
        if tool is None:
            return None
        if tool.required_auth and not (user and user.is_authenticated):
            return None
        return tool

    @classmethod
    def get_all_schemas(cls) -> list:
        return [tool.get_schema() for tool in cls._tools.values()]
