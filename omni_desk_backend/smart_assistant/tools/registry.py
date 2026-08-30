from __future__ import annotations

from typing import TYPE_CHECKING, Any

from observability import get_logger

from .base import BaseTool

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractBaseUser


class ToolRegistry:
    """工具注册表"""

    _tools: dict = {}

    @classmethod
    def register(cls, tool: BaseTool) -> None:
        if not isinstance(tool, BaseTool):
            raise TypeError(f"{tool!r} is not a BaseTool instance (got {type(tool).__name__})")
        if not tool.intent_type:
            raise ValueError(
                f"Tool {tool.name or '<unnamed>'} must set non-empty intent_type (got {tool.intent_type!r})"
            )
        cls._tools[tool.intent_type] = tool

    @classmethod
    def get_tool(cls, intent_type: str) -> BaseTool | None:
        return cls._tools.get(intent_type)

    @classmethod
    def get_tool_for_user(
        cls,
        intent_type: str,
        user: AbstractBaseUser | Any | None,
    ) -> BaseTool | None:
        """按用户返回工具(权限校验)。

        若工具 ``required_auth=True`` 且用户未认证(``user`` 为 ``None`` 或
        ``user.is_authenticated`` 为 ``False``),返回 ``None``。该方法不抛异常
        —— 调用方应自行决定如何处理"用户未授权"这一信号(常见做法:返回
        401/403 或切换到 ``fallback`` 文本回答)。

        参数:
            intent_type: 工具的 intent_type 标识
            user: 当前请求用户(Django ``User`` 实例,或测试环境中的 mock
                对象)。允许 ``Any`` 是为支持测试中用 ``Mock(is_authenticated=...)``
                构造的对象。

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

    @classmethod
    def get_openai_tools(cls, user=None) -> list:
        """返回当前用户可用、按风险等级排序的 OpenAI tool schema 列表(Task 5)。

        用于 orchestrator 直接喂给 LLM 的 ``tools`` 参数。每个 schema 由
        BaseTool.get_openai_tool_schema() 生成,统一 OpenAI strict 模式规范。

        行为契约(Task 5 调整):

        - **用户过滤**:跳过 ``required_auth=True`` 且用户未认证的工具
          (``user`` 为 ``None`` 或 ``user.is_authenticated`` 为 ``False``)。
          认证用户能看到所有 ``required_auth=True`` 工具;``required_auth=False``
          工具对匿名用户也开放(若存在)。
        - **风险等级排序**: ``read`` → ``write`` → ``destructive`` 升序,
          降低 LLM 误调写/破坏性工具的概率(read 工具前置)。
        - **schema 结构校验**:非 dict 或缺少 OpenAI function 必需字段的 schema
          记录 warning 后跳过,避免非法 schema 静默进入 LLM payload。
        - **向后兼容**:未覆写 schema 的工具由 BaseTool 通用降级实现；只有
          真正抛出 NotImplementedError 的异常工具才记录 warning + skip。

        参数:
            user: 当前请求用户。可为 ``None`` / ``AnonymousUser`` /
              已认证的 Django ``User``。允许 ``Any`` 是为支持 mock 测试。

        返回:
            list[dict]: 已过滤 + 排序 + 校验后的 OpenAI tool schema 列表。
        """
        from .base import (
            RISK_LEVEL_DESTRUCTIVE,
            RISK_LEVEL_READ,
            RISK_LEVEL_WRITE,
        )

        log = get_logger(__name__, "smart_assistant")

        is_auth = user is not None and getattr(user, "is_authenticated", False)

        schemas: list = []
        for tool in cls._tools.values():
            # 1. 用户过滤:required_auth=True 且未登录 → 跳过
            if tool.required_auth and not is_auth:
                continue
            # 2. 收集 schema(NotImplementedError → warning + skip,向后兼容)
            try:
                schema = tool.get_openai_tool_schema()
            except NotImplementedError as exc:
                log.warning(
                    "工具 %s 未实现 get_openai_tool_schema(),已跳过(tool_calls 路径不可用): %s",
                    tool.intent_type,
                    exc,
                )
                continue
            # 3. schema 结构校验:非 dict 或缺关键字段 → warning + skip
            if not cls._is_valid_openai_schema(schema):
                log.warning(
                    "工具 %s 返回的 schema 结构不合法(非 dict 或缺 type/function 字段),已跳过: %s",
                    tool.intent_type,
                    type(schema).__name__,
                )
                continue
            schemas.append((tool, schema))

        # 4. 风险等级排序:read → write → destructive
        risk_order = {
            RISK_LEVEL_READ: 0,
            RISK_LEVEL_WRITE: 1,
            RISK_LEVEL_DESTRUCTIVE: 2,
        }
        schemas.sort(key=lambda item: risk_order.get(item[0].risk_level, 0))

        return [schema for _tool, schema in schemas]

    @classmethod
    def _is_valid_openai_schema(cls, schema) -> bool:
        """校验 OpenAI tool schema 的最小结构。

        OpenAI tool 调用协议要求 schema 形如::

            {"type": "function", "function": {"name": ..., "description": ..., "parameters": ...}}

        校验规则:
        - 必须是 dict
        - 必须有顶层 ``type`` 字段(值应为 ``"function"``)
        - 必须有 ``function`` 子字段(必须为 dict)
        - ``function.name`` 必须是非空字符串
        - ``function.description`` 必须是字符串
        - ``function.parameters`` 必须是 dict 且为 object schema
        不做 deep JSON Schema 校验(那是 BaseTool/测试层的职责)。
        """
        if not isinstance(schema, dict):
            return False
        if schema.get("type") != "function":
            return False
        function = schema.get("function")
        if not isinstance(function, dict):
            return False
        name = function.get("name")
        description = function.get("description")
        parameters = function.get("parameters")
        if not isinstance(name, str) or not name:
            return False
        if not isinstance(description, str):
            return False
        return isinstance(parameters, dict) and parameters.get("type") == "object"

    @classmethod
    def assert_all_have_openai_schema(cls) -> None:
        """CI lint:断言所有已注册工具都返回合法的 OpenAI schema。

        BaseTool 提供通用降级 schema，因此 lint 不再把 ``NotImplementedError``
        当作“未实现”检查，而是统一验证返回值结构。
        """
        invalid: list[str] = []
        for tool in cls._tools.values():
            try:
                schema = tool.get_openai_tool_schema()
            except Exception:
                invalid.append(tool.intent_type)
                continue
            if not cls._is_valid_openai_schema(schema):
                invalid.append(tool.intent_type)
        if invalid:
            raise AssertionError(f"以下工具返回的 OpenAI schema 结构不合法: {invalid}")
