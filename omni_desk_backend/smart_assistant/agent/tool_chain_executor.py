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

    def execute_parallel(self, plan: "Plan", context: "ToolContext") -> list:
        """执行 plan,无依赖步骤并行,有依赖步骤串行。

        Task 1 of feat/sa-perf-ux:降低 P95 延迟的核心方法。

        算法:
        1. 解析每步的依赖(扫描 params 中的 ``{{stepN.output...}}`` 引用)
        2. 拓扑排序分组:同层步骤可并行,跨层串行
        3. 单步组串行执行,多步组用 ``asyncio.gather`` + ``asyncio.to_thread``
           并行(绕过 GIL,真正利用多核/并发 I/O 阻塞)

        与 ``execute(plan)`` 的区别:
        - ``execute`` 永远串行(保留兼容性)
        - ``execute_parallel`` 分析依赖图,同层步骤并行

        Args:
            plan: ``Plan`` dataclass(不支持旧 dict 格式,旧格式请用 ``execute``)
            context: ``ToolContext`` 实例

        Returns:
            每步结果 dict 列表(顺序与 plan.steps 一致)。
        """
        import asyncio

        steps = plan.steps
        dep_graph = self._build_dependency_graph(steps)
        groups = self._topological_groups(steps, dep_graph)

        step_results: dict = {}
        output: list = []

        for group in groups:
            # 预解析每步的标签和参数(避免在闭包/线程中重复计算)
            group_data = []
            for idx, step in group:
                step_label = f"step{idx + 1}"
                resolved_params = _replace_variables(step.params, step_results)
                group_data.append((idx, step, step_label, resolved_params))

            if len(group_data) == 1:
                # 单步:串行(避免 asyncio 调度开销)
                idx, step, step_label, resolved_params = group_data[0]
                result = self._execute_and_time(step, step_label, resolved_params, context)
                step_results[step_label] = result
                output.append(result)
                self._write_agent_log(context.user, step, result, idx + 1, resolved_params)
            else:
                # 多步:并行(asyncio + 线程池,绕过 GIL 对 time.sleep/DB 阻塞的序列化)
                async def _run_group(data=group_data):
                    coros = [
                        asyncio.to_thread(
                            self._execute_and_time,
                            step,
                            step_label,
                            resolved_params,
                            context,
                        )
                        for (_, step, step_label, resolved_params) in data
                    ]
                    return await asyncio.gather(*coros)

                group_results = asyncio.run(_run_group())

                for (idx, step, step_label, resolved_params), result in zip(
                    group_data, group_results, strict=True
                ):
                    step_results[step_label] = result
                    output.append(result)
                    self._write_agent_log(
                        context.user, step, result, idx + 1, resolved_params
                    )

        return output

    def _execute_and_time(
        self,
        step: "PlanStep",
        step_label: str,
        resolved_params: dict,
        context: "ToolContext",
    ) -> dict:
        """执行单步并记录耗时(供串行/并行路径复用)。

        从 ``_execute_advanced`` 抽取出来,便于 ``execute_parallel`` 在
        ``asyncio.to_thread`` 中调用(避免 lambda 捕获 + 重复 latency 计算)。
        """
        start_time = time.time()
        result = self._execute_step_with_strategy(step, step_label, resolved_params, context)
        result["latency_ms"] = int((time.time() - start_time) * 1000)
        return result

    def _build_dependency_graph(self, steps: list) -> dict:
        """扫描每个 step 的 params,提取 ``{{stepN.output...}}`` 引用作为依赖。

        Returns:
            ``{step_index: set(dependency_indices)}`` 的邻接表。
            依赖方向:``graph[i]`` 包含 i 依赖的所有前序步骤索引。
            只允许前向依赖(``dep_step < i``),反向/自引用被忽略。
        """
        dep_pattern = re.compile(r"\{\{step(\d+)\.")
        graph = {i: set() for i in range(len(steps))}
        for i, step in enumerate(steps):
            params_str = str(step.params)
            for m in dep_pattern.finditer(params_str):
                dep_step = int(m.group(1)) - 1  # {{step1...}} → index 0
                if 0 <= dep_step < i:  # 只能依赖前序步骤
                    graph[i].add(dep_step)
        return graph

    def _topological_groups(self, steps: list, dep_graph: dict) -> list:
        """拓扑排序分组:同一层的步骤可并行执行。

        Kahn 算法变体:每次取所有入度为 0 的步骤作为一层,
        移除后更新后续步骤入度,循环直到所有步骤分组完毕。

        Returns:
            ``list[list[tuple[int, PlanStep]]]`` — 每组是 (index, step) 元组列表。
            组间顺序保证依赖先执行;组内步骤可并行。
        """
        in_degree = {i: len(dep_graph[i]) for i in range(len(steps))}
        groups: list = []
        remaining = set(range(len(steps)))

        while remaining:
            # 当前层:所有依赖已满足的步骤
            current = sorted([i for i in remaining if in_degree[i] == 0])
            if not current:
                # 存在环(不应发生,LLM planner 应保证 DAG),降级为串行全部打包
                current = sorted(remaining)
            groups.append([(i, steps[i]) for i in current])

            # 移除已分组步骤,更新后续步骤的入度
            for i in current:
                remaining.discard(i)
                for j in remaining:
                    if i in dep_graph[j]:
                        in_degree[j] -= 1

        return groups

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
            resolved_params = _replace_variables(step.params, step_results)
            result = self._execute_step_with_strategy(
                step,
                step_label,
                resolved_params,
                context,
            )
            result["latency_ms"] = int((time.time() - start_time) * 1000)
            step_results[step_label] = result
            output.append(result)

            self._write_agent_log(context.user, step, result, idx + 1, resolved_params)
        return output

    def _execute_step_with_strategy(
        self,
        step: "PlanStep",
        step_label: str,
        resolved_params: dict,
        context: "ToolContext",
    ) -> dict:
        """按 ``on_failure`` 策略执行单步,失败时根据策略返回不同 status。

        ``resolved_params`` 由调用方解析(避免重试时重复解析变量)。
        """
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
        """调用工具,与 ``_execute_single_tool`` 签名处理一致。

        分支:
        1. ``supports_scope_filter`` 工具 → 走 ``build_base_queryset`` + ``execute(params, scope, qs)``
        2. 旧工具 → 走 ``execute(query=params.get("query"), context=context)``

        旧工具签名 ``execute(self, query: str, context: dict = None)``(13 个工具)
        仅支持 ``query`` 位置参数 — 把整个 ``params`` dict 透传会触发 TypeError 后
        退化为 ``query=None``,丢失所有数据。修复方式:显式按签名分发,不依赖
        TypeError 兜底。
        """
        if getattr(tool, "supports_scope_filter", False):
            base_qs = tool.build_base_queryset()
            scoped_qs = tool.get_queryset_for_scope(base_qs, context)
            return tool.execute(params=params, scope=context.scope, qs=scoped_qs)
        query = params.get("query") if isinstance(params, dict) else None
        return tool.execute(query=query, context=context)

    def _build_failure_result(
        self,
        step: "PlanStep",
        step_label: str,
        attempts: int,
        last_error: Exception | None,
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

    def _write_agent_log(
        self,
        user,
        step: "PlanStep",
        result: dict,
        step_index: int,
        resolved_params: dict,
    ) -> None:
        """为每步执行写入 AgentLog(便于审计追踪)。

        Args:
            user: ToolContext.user(目前 AgentLog 通过 ``session`` FK 关联用户)
            step: 当前 PlanStep
            result: ``_execute_step_with_strategy`` 返回的 dict
            step_index: 1-based step 编号
            resolved_params: 已解析 ``{{stepN.output.x}}`` 的最终参数(避免审计看到占位符)
        """
        try:
            from ..models import AgentLog

            session = getattr(user, "_smart_assistant_session", None)
            AgentLog.objects.create(
                session=session,  # nullable: 测试场景无 session
                user_query=f"[chain step {step_index}] {step.tool}",
                intent=f"chain:{step.tool}",
                tool_used=step.tool,
                tool_input=resolved_params,  # 已解析,审计可读
                tool_output=result.get("output") or {},
                llm_response="",  # 必填字段,工具链执行非 LLM 综合结果
                response_time_ms=result.get("latency_ms", 0),
                # 仅 success=True;fallback/skip/failed 均为 False(更准确反映工具可用性)
                tool_success=result["status"] == "success",
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
