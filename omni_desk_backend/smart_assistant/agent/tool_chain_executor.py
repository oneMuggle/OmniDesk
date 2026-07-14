"""工具链执行器。

按依赖顺序执行工具列表，后一个工具可依赖前一个的输出。
支持变量替换（如 $tool_name.field 从前一个工具结果中提取值）。
"""

import logging
from typing import Any, cast

from ..tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


def execute_tool_chain(plan: list, query: str, context: dict | None = None) -> list:
    """执行工具链计划。

    Args:
        plan: 工具执行计划列表，每项包含 tool, params, depends_on
        query: 用户查询
        context: 对话上下文

    Returns:
        执行结果列表，每项包含 tool_name, result, success 字段
    """
    results = []
    tool_outputs: dict[str, Any] = {}  # 存储每个工具的输出，供后续工具引用

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
        # client.generate() 无返回类型注解 → tuple[Any, ...]；answer 为 Any
        answer, _ = client.generate(prompt=synthesis_prompt)
        return cast(str, answer.strip())
    except Exception as e:
        return f"回答生成失败: {str(e)}"
