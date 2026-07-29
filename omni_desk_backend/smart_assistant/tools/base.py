from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from smart_assistant.scope import SmartAssistantScope

if TYPE_CHECKING:
    from .tool_context import ToolContext


class ValidationResult:
    """工具结果验证"""

    def __init__(self, is_valid: bool = True, reason: str = ""):
        self.is_valid = is_valid
        self.reason = reason


# ---------------------------------------------------------------------------
# 工具风险等级(借鉴 claw-code 的 PermissionMode 分层)
# ---------------------------------------------------------------------------

RISK_LEVEL_READ = "read"
RISK_LEVEL_WRITE = "write"
RISK_LEVEL_DESTRUCTIVE = "destructive"

#: 合法风险等级枚举。新工具声明 risk_level 时必须取其中之一
#: (见 test_tool_risk_level.py 的全量校验)。
VALID_RISK_LEVELS: frozenset = frozenset({RISK_LEVEL_READ, RISK_LEVEL_WRITE, RISK_LEVEL_DESTRUCTIVE})


class BaseTool(ABC):
    """工具基类"""

    name: str = ""
    description: str = ""
    intent_type: str = ""  # 用于意图匹配
    required_auth: bool = True
    """工具是否需要登录用户上下文。

    默认 ``True``(fail-closed):新工具默认需要认证,仅当工具确实无需用户身份
    (例如纯静态信息查询)时由子类显式覆盖为 ``False``。Registry 在分发时会据此
    拒绝未授权请求。
    """

    risk_level: str = RISK_LEVEL_READ
    """工具风险等级(权限分级,借鉴 claw-code 的 PermissionMode 分层)。

    三级语义与确认流程约定:

    - ``"read"``(只读):纯查询,无副作用。默认等级,直接执行,无需确认。
      当前已注册的 13 个工具均为该等级。
    - ``"write"``(写入):创建/修改数据(如新建日程、更新备忘录)。执行器
      应结合 ``require_confirmation`` 决定流程:``require_confirmation=True``
      时,先通过 pre_execute 钩子向前端返回"待确认"信号,用户确认后再放行;
      ``False`` 时可直接执行,但审计照常记录。
    - ``"destructive"``(破坏性):删除/批量覆盖等难以撤销的操作(如删除公文、
      清空备忘录)。**必须** ``require_confirmation=True``;执行器必须走二次
      确认流程,且 AuditLogHook 会以 WARNING 级别记录该类调用。

    子类必须显式声明该属性(哪怕值是默认的 "read"),便于审计与评审时一眼
    确认每个工具的副作用边界;test_tool_risk_level.py 会校验所有注册工具
    的取值合法性。
    """

    require_confirmation: bool = False
    """执行前是否需要用户二次确认。

    默认 ``False``。约定:``risk_level`` 为 ``"destructive"`` 的工具必须置
    ``True``;``"write"`` 工具按业务敏感度自行决定;``"read"`` 工具应保持
    ``False``。确认流程由执行器 + pre_execute 钩子实现(规划中):钩子返回
    Reject(error_code="confirmation_required") 挂起执行,待前端确认后重放。
    """

    @abstractmethod
    def execute(self, query: str, context: ToolContext) -> dict:
        """执行工具,返回结构化结果。

        参数:
            query: 用户的查询文本。
            context: 工具执行上下文(ToolContext),包含 user / request_id / history。
                必填 —— 调用方应在分发前从 DRF request 构造(参见
                ``ToolContext.from_request``)。``history`` 列表应视为只读,
                工具可读但不应原地修改;如需新历史请构造新 ToolContext 实例。
        """
        pass

    def get_schema(self) -> dict:
        """返回工具的描述 schema，用于意图识别

        包含 ``risk_level``,供执行器/前端在工具调用链中做权限门控与展示。
        """
        return {
            "name": self.name,
            "description": self.description,
            "intent_type": self.intent_type,
            "risk_level": self.risk_level,
        }

    def execute_with_guard(self, query: str, context: ToolContext) -> dict:
        """带超时熔断的执行包装层入口(旧路径:query + context)

        现有钩子契约的 post_execute 拿不到执行耗时,无法在钩子内计时,
        因此超时熔断在 BaseTool 执行包装层实现;``TimeoutGuardHook`` 作为
        配置入口(阈值读 settings ``SMART_ASSISTANT_TOOL_TIMEOUT``,默认 10s)。

        - 熔断关闭时:等价于直接调用 ``self.execute(query, context)``;
        - 超时时:立即返回 ``{"found": False, "timed_out": True, ...}``
          失败字典,调用方不挂起(详见 hooks/builtin/timeout_guard.py)。

        注:仅包装旧签名 ``execute(query, context)``;跨模块汇总新路径
        (``execute(params, scope, qs)``)的调用方可自行用
        ``TimeoutGuardHook.run_guarded_sync`` 包装。
        """
        # 延迟导入,避免 tools ↔ hooks 在应用加载期产生导入耦合
        from smart_assistant.hooks.builtin.timeout_guard import TimeoutGuardHook

        guard = TimeoutGuardHook()
        return guard.run_guarded_sync(self.execute, query, context, tool_name=self.name)

    def get_examples(self) -> list:
        """返回 few-shot 示例，帮助 LLM 理解工具用法。"""
        return []

    def validate_params(self, params: dict) -> ValidationResult:
        """校验工具参数。子类可覆盖。"""
        return ValidationResult(is_valid=True)

    def validate_result(self, result: dict) -> ValidationResult:
        """校验工具返回结果的有效性。子类可覆盖。

        当工具返回 found=False 或数据不完整时返回无效。
        """
        if not isinstance(result, dict):
            return ValidationResult(is_valid=False, reason="结果不是字典")
        if not result.get("found"):
            return ValidationResult(
                is_valid=False,
                reason=result.get("message", "未找到相关信息"),
            )
        return ValidationResult(is_valid=True)

    def extract_keywords(self, query: str) -> list:
        """从用户查询中提取关键词。默认去除停用词。"""
        stopwords = {"搜索", "查找", "查询", "请问", "帮我", "看看", "有没有", "的", "了", "吗", "呢"}
        keywords = []
        for word in query:
            if word not in stopwords:
                keywords.append(word)
        return keywords

    # === 新增:跨模块汇总权限抽象(2026-07-07) ===

    @property
    def supports_scope_filter(self) -> bool:
        """是否实现 scope 过滤。

        返回 True 当且仅当工具自身(而非仅从 BaseTool 继承)重写了
        build_base_queryset + _scope_self;ToolChainExecutor 据此判定
        是否走"跨模块汇总"新路径(否则走旧路径)。
        """
        return (
            type(self).build_base_queryset is not BaseTool.build_base_queryset
            and type(self)._scope_self is not BaseTool._scope_self
        )

    def build_base_queryset(self):
        """返回未过滤的 QuerySet(子类必须实现)。

        跨模块汇总路径使用:Executor 先调 build_base_queryset(),再调
        get_queryset_for_scope(),最后调 execute(params, scope, qs)。

        默认实现:raise NotImplementedError。注意这里不写 @abstractmethod
        以保证现有 13 个未实现该方法的旧工具仍可实例化(Task 3 仅添加方法,
        Task 4 才在子类中实现);调用本方法时才报错。
        """
        raise NotImplementedError(f"{self.__class__.__name__} must implement build_base_queryset()")

    def get_queryset_for_scope(self, base_qs, context: ToolContext):
        """根据 scope 过滤 QuerySet。默认实现:dispatch 到 _scope_self/_scope_department/GLOBAL 透传。

        子类通常不重写此方法;如需自定义分支逻辑可重写。
        """
        if context.scope == SmartAssistantScope.SELF:
            return self._scope_self(base_qs, context)
        if context.scope == SmartAssistantScope.DEPARTMENT:
            return self._scope_department(base_qs, context)
        return base_qs  # GLOBAL 不过滤

    def _scope_self(self, qs, ctx):
        """本人范围过滤(子类必须实现)。

        例:return qs.filter(user=ctx.user)

        默认实现:raise NotImplementedError。同 build_base_queryset,不写
        @abstractmethod 以保留向后兼容性。
        """
        raise NotImplementedError(f"{self.__class__.__name__} must implement _scope_self()")

    def _scope_department(self, qs, ctx):
        """部门范围过滤(默认 = 透传,子类可重写)。"""
        return qs
