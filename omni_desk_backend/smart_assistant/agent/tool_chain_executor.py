"""工具链执行器。

按依赖顺序执行工具列表，后一个工具可依赖前一个的输出。
支持变量替换（如 $tool_name.field 从前一个工具结果中提取值）。

新增 (Task 10):``ToolChainExecutor`` class —— 支持跨工具 scope 注入与
单工具失败降级。该 class 与原有 ``execute_tool_chain`` 函数并存,后者
继续服务于 orchestrator.py(契约不变)。

升级 (Task 2 of feat/sa-multi-tool-chain):
- 新增 ``Plan`` dataclass 路径(嵌套变量 + on_failure 三策略 + step-level AgentLog)
- 保留 dict 路径(向后兼容现有调用方)
"""

import logging
import re
import time
from typing import TYPE_CHECKING

from ..tools.registry import ToolRegistry
from .plan_serializer import Plan, PlanStep

if TYPE_CHECKING:
    from ..tools.tool_context import ToolContext

logger = logging.getLogger(__name__)

# {{step_name.output.path.to.value}} 占位符正则
NESTED_VAR_PATTERN = re.compile(r"\{\{([^}]+)\}\}")


def _resolve_nested_var(step_name: str, step_output: dict, path: str):
    """解析 ``{{step_name.output.path}}`` 中的 path 部分。

    支持 dict 嵌套 + list 索引(如 ``users[0].id``)。
    """
    data = step_output
    tokens = re.findall(r"\w+|\[\d+\]", path)
    for token in tokens:
        if token.startswith("[") and token.endswith("]"):
            idx = int(token[1:-1])
            data = data[idx]
        else:
            data = data[token]
    return data


def _replace_variables(params, step_results: dict):
    """递归替换 params 中所有 ``{{stepN.output.path}}`` 占位符。

    支持字符串/字典/列表嵌套;无法解析时保留原占位符(便于失败诊断)。
    """
    if isinstance(params, str):
        def repl(m):
            ref = m.group(1)
            parts = ref.split(".", 1)
            step_name = parts[0]
            path = parts[1] if len(parts) > 1 else ""
            if step_name not in step_results:
                return m.group(0)
            try:
                return str(_resolve_nested_var(step_name, step_results[step_name], path))
            except (KeyError, IndexError, TypeError):
                return m.group(0)

        return NESTED_VAR_PATTERN.sub(repl, params)
    if isinstance(params, dict):
        return {k: _replace_variables(v, step_results) for k, v in params.items()}
    if isinstance(params, list):
        return [_replace_variables(v, step_results) for v in params]
    return params


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

    新增 (Task 2 of feat/sa-multi-tool-chain):
    - 支持 ``Plan`` dataclass 输入(嵌套变量 + on_failure + AgentLog)
    - 保留 dict 路径向后兼容
    """

    def execute(self, plan, context: "ToolContext") -> list:
        """按顺序执行 plan 中每个步骤,收集结果。

        Args:
            plan: 两种格式之一:
                - dict: ``{"steps": [{"tool": ..., "params": ...}, ...]}``(旧)
                - ``Plan`` dataclass(新,支持嵌套变量与 on_failure)
            context: ``ToolContext`` 实例,含 user / scope 等。

        Returns:
            每步结果 dict 列表。
        """
        if isinstance(plan, Plan):
            return self._execute_advanced(plan, context)
        steps = (plan or {}).get("steps") or []
        results: list = []
        for step in steps:
            result = self._execute_single_tool(step, context)
            if result is not None:
                results.append(result)
        return results

    def _execute_advanced(self, plan: "Plan", context: "ToolContext") -> list:
        """新路径:执行 Plan dataclass,支持嵌套变量 + on_failure + AgentLog。"""
        step_results: dict = {}
        output: list = []
        for idx, step in enumerate(plan.steps):
            step_label = f"step{idx + 1}"
            start_time = time.time()
            result = self._execute_step_with_strategy(
                step, step_label, step_results, context,
            )
            result["latency_ms"] = int((time.time() - start_time) * 1000)
            step_results[step_label] = result
            output.append(result)

            self._write_agent_log(context.user, step, result, idx + 1)
        return output

    def _execute_step_with_strategy(
        self, step: "PlanStep", step_label: str, step_results: dict, context: "ToolContext",
    ) -> dict:
        """按 ``on_failure`` 策略执行单步,失败时根据策略返回不同 status。"""
        resolved_params = _replace_variables(step.params, step_results)
        attempts = step.retry_count if step.on_failure == "retry" else 1
        last_error: Exception | None = None

        for attempt in range(attempts):
            try:
                tool = ToolRegistry.get_tool_for_user(step.tool, context.user)
                if tool is None:
                    raise PermissionError(f"工具 {step.tool} 无权限或未注册")
                output = self._call_tool(tool, resolved_params, context)
                return {
                    "step": step_label,
                    "tool": step.tool,
                    "status": "success",
                    "output": output,
                    "attempts": attempt + 1,
                }
            except Exception as exc:
                last_error = exc
                if attempt + 1 < attempts:
                    continue

        return self._build_failure_result(step, step_label, attempts, last_error)

    def _call_tool(self, tool, params, context: "ToolContext"):
        """调用工具,优先支持新签名 ``execute(params, context)``。

        兼容旧签名 ``execute(query, context)``(取 params["query"] 作为 query)。
        """
        try:
            return tool.execute(params=params, context=context)
        except TypeError:
            query = params.get("query") if isinstance(params, dict) else None
            return tool.execute(query=query, context=context)

    def _build_failure_result(
        self, step: "PlanStep", step_label: str, attempts: int, last_error: Exception | None,
    ) -> dict:
        """根据 on_failure 构建失败结果 dict。"""
        error_str = str(last_error) if last_error else "未知错误"
        if step.on_failure == "skip":
            return {
                "step": step_label,
                "tool": step.tool,
                "status": "skipped",
                "output": None,
                "error": error_str,
                "attempts": attempts,
            }
        if step.on_failure == "fallback":
            return {
                "step": step_label,
                "tool": step.tool,
                "status": "fallback",
                "output": {"fallback_message": f"工具 {step.tool} 不可用,已跳过"},
                "error": error_str,
                "attempts": attempts,
            }
        return {
            "step": step_label,
            "tool": step.tool,
            "status": "failed",
            "output": None,
            "error": error_str,
            "attempts": attempts,
        }

    def _write_agent_log(self, user, step: "PlanStep", result: dict, step_index: int) -> None:
        """为每步执行写入 AgentLog(便于审计追踪)。

        ``user`` 参数保留以备将来扩展(目前 AgentLog 通过 ``session`` FK 关联用户)。
        """
        try:
            from ..models import AgentLog

            session = getattr(user, "_smart_assistant_session", None)
            AgentLog.objects.create(
                session=session,  # nullable: 测试场景无 session
                user_query=f"[chain step {step_index}] {step.tool}",
                intent=f"chain:{step.tool}",
                tool_used=step.tool,
                tool_input=step.params,
                tool_output=result.get("output") or {},
                llm_response="",  # 必填字段,工具链执行非 LLM 综合结果
                response_time_ms=result.get("latency_ms", 0),
                tool_success=result["status"] not in ("failed", "skipped"),
            )
        except Exception as exc:
            logger.warning("AgentLog 写入失败 (step %s): %s", step.tool, exc)

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
    """执行工具链计划(函数版,与 ToolChainExecutor class 并存)。

    Args:
        plan: 工具执行计划列表,每项包含 tool, params, depends_on
        query: 用户查询
        context: 对话上下文

    Returns:
        执行结果列表,每项包含 tool_name, result, success 字段
    """
    results = []
    tool_outputs = {}

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
            parts = value[1:].split(".", 1)
            ref_tool = parts[0]
            ref_field = parts[1] if len(parts) > 1 else None

            if ref_tool == source_tool and source_result:
                if ref_field and ref_field in source_result:
                    resolved[key] = source_result[ref_field]
                elif ref_field is None:
                    resolved[key] = source_result
                else:
                    resolved[key] = value
            else:
                resolved[key] = value
        else:
            resolved[key] = value

    return resolved


def synthesize_answer(plan: list, tool_results: list, query: str) -> str:
    """综合多工具结果,生成最终回答。"""
    from llm_service.router import get_router
    from .prompt_builder import TOOL_CHAIN_SYNTHESIS_PROMPT

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
