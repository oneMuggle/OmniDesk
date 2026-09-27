"""能力声明：``ToolSpec`` / ``Toolset`` / ``toolset`` 装饰器。

各业务 app 在自己的 ``ai_tools.py`` 里声明工具集::

    from smart_assistant.capabilities import LOGIN_ONLY, DataScope, ToolSpec, toolset

    @toolset("memos", title="备忘录")
    def memo_tools():
        from smart_assistant.tools.memo_tool import MemoTool

        return [
            ToolSpec(
                tool=MemoTool,
                title="查询备忘录",
                required_permission=LOGIN_ONLY,
                data_scope=DataScope.SCOPE,
            ),
        ]

工具类在函数体内导入，避免 app 加载期的循环依赖。``smart_assistant`` 在
``ready()`` 中按 ``INSTALLED_APPS`` 顺序发现这些函数（见 ``registry.discover``）。
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass, field
from typing import Any
from collections.abc import Callable

#: 登录即可调用；数据范围由 ``data_scope`` 约束。必须显式声明，不能省略。
LOGIN_ONLY = "login"


class DataScope:
    """数据范围策略（能力目录与自检使用）。"""

    #: SELF / DEPARTMENT / GLOBAL 三级 scope（``build_base_queryset`` + ``_scope_self``）
    SCOPE = "scope"
    #: 只返回当前用户本人的数据，任何 scope 都不扩大
    OWNER = "owner"
    #: 复用模块自身 HTTP 接口的可见性规则（与接口共用同一段代码）
    MODULE = "module"
    #: 不直接查模型，委托给其他工具的 scoped_queryset（如 global_search）
    DELEGATED = "delegated"
    #: 只读取本次请求携带的附件
    ATTACHMENT = "attachment"
    #: 知识库 / 公共资料检索，不涉及用户私有数据
    KNOWLEDGE = "knowledge"
    #: 写给他人的工具（如发通知）：按发起人 scope 限定可选收件人
    RECIPIENT = "recipient"

    ALL = frozenset({SCOPE, OWNER, MODULE, DELEGATED, ATTACHMENT, KNOWLEDGE, RECIPIENT})

    LABELS = {
        SCOPE: "三级 scope",
        OWNER: "仅本人",
        MODULE: "同模块接口",
        DELEGATED: "委托其他工具",
        ATTACHMENT: "仅本次附件",
        KNOWLEDGE: "知识库",
        RECIPIENT: "按 scope 限定收件人",
    }


class ConfirmPolicy:
    """执行前确认策略。"""

    NONE = "none"
    #: 单人确认：走 confirm-replay，由发起人本人确认后执行
    USER = "user"

    ALL = frozenset({NONE, USER})

    LABELS = {NONE: "—", USER: "本人确认"}


@dataclass(frozen=True)
class ToolSpec:
    """单个 AI 工具的能力声明。

    ``read_only`` / ``destructive`` 不在此重复声明，由工具类的 ``risk_level``
    推导（见 ``ResolvedToolSpec``），避免两处不一致。
    """

    #: ``BaseTool`` 子类，或其点分路径（``"pkg.module.ClassName"``）
    tool: Any
    #: 中文短名（能力目录展示）
    title: str
    #: ``LOGIN_ONLY`` 或 Django 权限码 ``app_label.codename``
    required_permission: str
    #: 数据范围策略，取值见 ``DataScope``
    data_scope: str
    #: 执行前确认策略，取值见 ``ConfirmPolicy``；写 / 删除工具必须为 ``USER``
    confirm: str = ConfirmPolicy.NONE
    #: 是否幂等；``None`` 表示按风险等级推导（只读 True，写入 False）
    idempotent: bool | None = None
    #: 是否访问外部系统（RAGFlow、第三方 API 等）
    open_world: bool = False
    #: 预留（S3）：回滚方式，如 ``"agent_write_log"``；只读工具不得声明
    rollback: str | None = None
    #: 预留（S3）：settings 开关名；为假时不注册该工具
    feature_flag: str | None = None
    version: str = "1"


@dataclass(frozen=True)
class Toolset:
    """一个 app 声明的一组工具。"""

    name: str
    title: str
    app_label: str
    module: str
    specs: tuple[ToolSpec, ...] = field(default_factory=tuple)
    description: str = ""


#: 被 ``@toolset`` 装饰的函数上挂的标记属性名
TOOLSET_MARKER = "__ai_toolset__"


def toolset(name: str, *, title: str, description: str = "") -> Callable:
    """把一个"返回 ToolSpec 列表"的函数标记为工具集。

    装饰器本身不做全局注册（导入模块不产生副作用），由发现流程扫描模块中带
    标记的函数并调用。
    """

    def decorator(func: Callable[[], list[ToolSpec]]) -> Callable[[], list[ToolSpec]]:
        setattr(func, TOOLSET_MARKER, {"name": name, "title": title, "description": description})
        return func

    return decorator


def import_tool_class(ref: Any) -> type:
    """把 ``ToolSpec.tool`` 解析为类；支持类对象或点分路径。"""
    if isinstance(ref, str):
        module_path, _, attr = ref.rpartition(".")
        if not module_path:
            raise ImportError(f"工具路径必须是 'pkg.module.ClassName' 形式: {ref!r}")
        return getattr(importlib.import_module(module_path), attr)
    return ref
