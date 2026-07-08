"""工具链执行器。

按依赖顺序执行工具列表，后一个工具可依赖前一个的输出。
支持变量替换（如 $tool_name.field 从前一个工具结果中提取值）。

新增 (Task 10):``ToolChainExecutor`` class —— 支持跨工具 scope 注入与
单工具失败降级。该 class 与原有 ``execute_tool_chain`` 函数并存,后者
继续服务于 orchestrator.py(契约不变)。
"""

import logging
from typing import TYPE_CHECKING

from ..tools.registry import ToolRegistry

if TYPE_CHECKING:
    from ..tools.tool_context import ToolContext

logger = logging.getLogger(__name__)


class ToolChainExecutor:
    """工具链执行器(class 版)。

    与函数版 ``execute_tool_chain`` 的区别:
    - 接收 ``ToolContext`` 实例(而非裸 dict),从中读取 ``scope`` / ``user``;
    - 调度逻辑拆为 ``execute`` 与 ``_execute_single_tool``,便于测试时
      子类化 ``_execute_single_tool`` 进行捕获;
    - 单工具抛异常被捕获,标记 ``reason="exception"`` 后继续执行后续步骤,
      而不是中断整个 plan;
    - 工具未注册或用户未认证时,标记 ``reason="permission_denied"``;
    - 空 plan(``{"steps": []}`` 或缺失 ``steps``)返回空列表。
    """

    def execute(self, plan, context: "ToolContext") -> list:
        """按顺序执行 plan 中每个步骤,收集结果。

        Args:
            plan: ``{"steps": [{"tool": ..., "params": ...}, ...]}`` 格式。
                缺失或空 ``steps`` 视为空 plan。
            context: ``ToolContext`` 实例,含 user / scope 等。

        Returns:
            每步结果 dict 列表。每个 dict 至少含 ``tool`` 字段;成功时含
            ``found`` / ``module_label``;失败时含 ``reason``(取值:
            ``permission_denied`` / ``exception``)。
        """
        steps = (plan or {}).get("steps") or []
        results: list = []
        for step in steps:
            result = self._execute_single_tool(step, context)
            if result is not None:
                results.append(result)
        return results

    def _execute_single_tool(self, step: dict, context: "ToolContext") -> dict:
        """执行单个步骤。子类可重写以注入捕获/桩逻辑。

        流程:
        1. ``ToolRegistry.get_tool_for_user(tool_name, user)`` 校验权限;
           返回 ``None`` → ``permission_denied``。
        2. 工具支持 ``scope`` 过滤 → 走 ``build_base_queryset`` →
           ``get_queryset_for_scope`` → ``execute(params, scope, qs)`` 新路径。
        3. 否则 → 走旧路径 ``execute(query, context)``。
        4. 任意异常 → 标记 ``reason="exception"`` 并返回。
        """
        tool_name = step.get("tool") if isinstance(step, dict) else None
        tool = ToolRegistry.get_tool_for_user(tool_name, context.user)
        if tool is None:
            return {
                "tool": tool_name,
                "found": False,
                "reason": "permission_denied",
                "module_label": tool_name or "",
            }

        params = (step.get("params") or {}) if isinstance(step, dict) else {}

        try:
            if getattr(tool, "supports_scope_filter", False):
                base_qs = tool.build_base_queryset()
                scoped_qs = tool.get_queryset_for_scope(base_qs, context)
                return tool.execute(params=params, scope=context.scope, qs=scoped_qs)
            return tool.execute(query=params.get("query") if isinstance(params, dict) else None, context=context)
        except Exception as exc:
            logger.exception("工具执行失败: %s — %s", tool_name, exc)
            return {
                "tool": tool_name,
                "found": False,
                "reason": "exception",
                "error": str(exc),
                "module_label": tool_name or "",
            }


def execute_tool_chain(plan: list, query: str, context: dict = None) -> list:
    """执行工具链计划。

    Args:
        plan: 工具执行计划列表，每项包含 tool, params, depends_on
        query: 用户查询
        context: 对话上下文

    Returns:
        执行结果列表，每项包含 tool_name, result, success 字段
    """
    results = []
    tool_outputs = {}  # 存储每个工具的输出，供后续工具引用

    for step in plan:
        tool_name = step.get("tool")
        params = step.get("params", {})
        depends_on = step.get("depends_on")

        tool = ToolRegistry.get_tool(tool_name)
        if not tool:
            logger.warning("工具不存在: %s", tool_name)
            results.append(
                {
                    "tool_name": tool_name,
                    "result": {"found": False, "message": f"工具 {tool_name} 不存在"},
                    "success": False,
                }
            )
            continue

        # 如果有依赖，注入前一个工具的结果到参数中
        if depends_on and depends_on in tool_outputs:
            dep_result = tool_outputs[depends_on]
            params = _resolve_variables(params, depends_on, dep_result)

        try:
            result = tool.execute(query, context=context)
            success = result.get("found", False)
        except Exception as e:
            logger.error("工具执行失败: %s — %s", tool_name, e)
            result = {"found": False, "message": f"工具执行失败: {str(e)}"}
            success = False

        tool_outputs[tool_name] = result
        results.append(
            {
                "tool_name": tool_name,
                "result": result,
                "success": success,
            }
        )

    return results


def _resolve_variables(params: dict, source_tool: str, source_result: dict) -> dict:
    """将参数中的 $tool_name.xxx 变量替换为实际值。"""
    resolved = {}
    for key, value in params.items():
        if isinstance(value, str) and value.startswith("$"):
            # 变量引用格式: $tool_name.field
            parts = value[1:].split(".", 1)
            ref_tool = parts[0]
            ref_field = parts[1] if len(parts) > 1 else None

            if ref_tool == source_tool and source_result:
                if ref_field and ref_field in source_result:
                    resolved[key] = source_result[ref_field]
                elif ref_field is None:
                    resolved[key] = source_result
                else:
                    # 字段不存在，保留原始变量
                    resolved[key] = value
            else:
                resolved[key] = value
        else:
            resolved[key] = value

    return resolved


def synthesize_answer(plan: list, tool_results: list, query: str) -> str:
    """综合多工具结果，生成最终回答。"""
    from llm_service.router import get_router
    from .prompt_builder import TOOL_CHAIN_SYNTHESIS_PROMPT

    # 收集所有结果
    all_results_text = []
    for r in tool_results:
        tool_name = r["tool_name"]
        result = r["result"]
        status = "成功" if r["success"] else "失败"
        all_results_text.append(f"[{tool_name}] ({status}): {result}")

    synthesis_prompt = TOOL_CHAIN_SYNTHESIS_PROMPT.format(
        user_query=query,
        tool_results="\n".join(all_results_text),
    )

    client = get_router()
    try:
        answer, _ = client.generate(prompt=synthesis_prompt)
        return answer.strip()
    except Exception as e:
        return f"回答生成失败: {str(e)}"
