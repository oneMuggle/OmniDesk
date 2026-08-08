"""工具上下文解析器(Task 6 新增)。

设计目标:把 "user → 可用工具 schema 列表" 这一查询封装为单一入口,
避免 orchestrator 与 ToolRegistry.get_openai_tools() 之间出现
重复的"user/scope 过滤逻辑"。

当前实现薄包装:`resolve_tools_for_user(user)` 直接调用
``ToolRegistry.get_openai_tools(user)``(已包含 required_auth /
risk_level 排序 / schema 结构校验)。

后续若引入"按 user 组裁剪工具"等策略,只需在本文件内实现,
orchestrator 不感知。
"""
from __future__ import annotations

from typing import Any


def resolve_tools_for_user(user: Any) -> list:
    """返回当前 user 可用的 OpenAI tool schema 列表。

    参数:
        user: 当前请求用户(已认证 Django User / 未认证 None / mock)。
            透传给 ToolRegistry.get_openai_tools(),后者负责
            ``required_auth`` 过滤与风险等级排序。

    返回:
        list[dict]: OpenAI 格式 tool schema 列表(已排序 + 校验)。
        未登录用户返回空列表(所有 19 个工具 required_auth=True)。
    """
    from smart_assistant.tools.registry import ToolRegistry

    return ToolRegistry.get_openai_tools(user)
