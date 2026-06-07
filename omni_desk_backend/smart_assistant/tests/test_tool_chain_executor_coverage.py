"""Tests for smart_assistant.agent.tool_chain_executor — 覆盖率补齐.

目标:agent/tool_chain_executor.py 67% → 85%+。
覆盖:
- _resolve_variables 各种分支(变量替换 / 无字段 / 字段不存在 / 跨工具 / 非字符串)
- execute_tool_chain 工具不存在 + 工具异常路径
- synthesize_answer 综合多工具结果
"""

from unittest.mock import patch, MagicMock

import pytest

from smart_assistant.agent.tool_chain_executor import (
    execute_tool_chain,
    _resolve_variables,
    synthesize_answer,
)


# =============================================================================
# _resolve_variables
# =============================================================================


class TestResolveVariables:
    """_resolve_variables: 把 $tool_name.field 替换为前一个工具的实际值."""

    def test_simple_field_replacement(self):
        """$tool.field → 替换为 source_result[field]."""
        params = {"user_id": "$schedule.duty_person"}
        source = {"duty_person": "张三", "date": "2026-06-07"}
        result = _resolve_variables(params, "schedule", source)
        assert result == {"user_id": "张三"}

    def test_no_field_replaces_with_whole_result(self):
        """$tool(无 .field) → 替换为整个 source_result."""
        params = {"info": "$schedule"}
        source = {"duty_person": "张三"}
        result = _resolve_variables(params, "schedule", source)
        assert result == {"info": {"duty_person": "张三"}}

    def test_field_not_found_keeps_variable(self):
        """$tool.missing_field → 字段不存在,保留原始变量字符串."""
        params = {"user_id": "$schedule.nonexistent"}
        source = {"duty_person": "张三"}
        result = _resolve_variables(params, "schedule", source)
        assert result == {"user_id": "$schedule.nonexistent"}

    def test_cross_tool_reference_keeps_variable(self):
        """$other_tool.field (ref_tool != source_tool) → 保留原始变量."""
        params = {"user_id": "$other.field"}
        source = {"field": "value"}
        result = _resolve_variables(params, "schedule", source)
        # ref_tool 应该是 "other",source_tool 是 "schedule" → 不匹配 → 保留
        assert result == {"user_id": "$other.field"}

    def test_non_string_value_unchanged(self):
        """非字符串值(数字/列表/字典)不变."""
        params = {"a": 123, "b": [1, 2], "c": {"k": "v"}}
        source = {"x": "y"}
        result = _resolve_variables(params, "schedule", source)
        assert result == params

    def test_empty_source_result_keeps_variable(self):
        """source_result 为空字典时,变量不被替换(条件中 source_result falsy)."""
        params = {"x": "$tool.field"}
        # source={} → if ref_tool == source_tool and source_result: source_result 是空 dict → False
        result = _resolve_variables(params, "tool", {})
        assert result == {"x": "$tool.field"}

    def test_string_without_dollar_unchanged(self):
        """普通字符串(非 $ 开头)保持原样."""
        params = {"a": "normal_string"}
        source = {"var": "value"}
        result = _resolve_variables(params, "tool", source)
        assert result == {"a": "normal_string"}

    def test_multiple_params_mixed(self):
        """多个参数,部分有变量部分无."""
        params = {
            "query": "原始问题",
            "ref_id": "$tool1.user_id",
            "limit": 10,
            "info": "$tool2",
        }
        source1 = {"user_id": 42}
        # 同一函数只接受一个 source_tool
        result = _resolve_variables(params, "tool1", source1)
        assert result["query"] == "原始问题"
        assert result["ref_id"] == 42  # 替换
        assert result["limit"] == 10
        # info 的 ref_tool="tool2" ≠ source_tool="tool1" → 保留
        assert result["info"] == "$tool2"


# =============================================================================
# execute_tool_chain (补 execute 异常 / 不存在工具的覆盖)
# =============================================================================


class TestExecuteToolChain:
    """execute_tool_chain: 工具不存在 + 工具执行异常."""

    def test_tool_not_found_continues_to_next(self):
        """工具不存在时,记录失败结果并继续."""
        with patch("smart_assistant.agent.tool_chain_executor.ToolRegistry") as mock_registry:
            mock_registry.get_tool.return_value = None
            plan = [{"tool": "nonexistent_tool", "params": {}, "depends_on": None}]
            results = execute_tool_chain(plan, "test query")
            assert len(results) == 1
            assert results[0]["tool_name"] == "nonexistent_tool"
            assert results[0]["success"] is False
            assert "不存在" in results[0]["result"]["message"]

    def test_tool_execute_raises_exception(self):
        """工具 execute 抛异常时,记录错误结果."""
        with patch("smart_assistant.agent.tool_chain_executor.ToolRegistry") as mock_registry:
            mock_tool = MagicMock()
            mock_tool.execute.side_effect = RuntimeError("boom")
            mock_registry.get_tool.return_value = mock_tool
            plan = [{"tool": "bad_tool", "params": {}, "depends_on": None}]
            results = execute_tool_chain(plan, "test query")
            assert len(results) == 1
            assert results[0]["success"] is False
            assert "boom" in results[0]["result"]["message"]

    def test_tool_execute_returns_dict(self):
        """工具成功执行,result 包含 found 字段."""
        with patch("smart_assistant.agent.tool_chain_executor.ToolRegistry") as mock_registry:
            mock_tool = MagicMock()
            mock_tool.execute.return_value = {"found": True, "data": [1, 2, 3]}
            mock_registry.get_tool.return_value = mock_tool
            plan = [{"tool": "good_tool", "params": {}, "depends_on": None}]
            results = execute_tool_chain(plan, "test query")
            assert len(results) == 1
            assert results[0]["success"] is True
            assert results[0]["result"]["found"] is True

    def test_depends_on_injects_previous_output(self):
        """depends_on 引用前一个工具时,变量被注入 params."""
        with patch("smart_assistant.agent.tool_chain_executor.ToolRegistry") as mock_registry:
            # 第一个工具 schedule
            schedule_tool = MagicMock()
            schedule_tool.execute.return_value = {
                "found": True,
                "duty_person": "张三",
                "date": "2026-06-07",
            }
            # 第二个工具 personnel
            personnel_tool = MagicMock()
            personnel_tool.execute.return_value = {
                "found": True,
                "name": "张三",
                "dept": "研发",
            }
            # 第一次 get_tool 返回 schedule,第二次返回 personnel
            mock_registry.get_tool.side_effect = [schedule_tool, personnel_tool]
            plan = [
                {"tool": "schedule", "params": {}, "depends_on": None},
                {"tool": "personnel", "params": {"name": "$schedule.duty_person"}, "depends_on": "schedule"},
            ]
            results = execute_tool_chain(plan, "查张三")
            assert len(results) == 2
            assert results[0]["success"] is True
            assert results[1]["success"] is True
            # 第二个工具的 execute 至少被调用一次
            assert personnel_tool.execute.called


# =============================================================================
# synthesize_answer
# =============================================================================


class TestSynthesizeAnswer:
    """synthesize_answer: 综合多工具结果生成最终回答."""

    def test_basic_synthesis_success(self, mock_llm_router):
        """全部成功时,综合回答."""
        mock_llm_router.generate.return_value = ("综合回答", {"total_tokens": 30})
        plan = [{"tool": "a"}, {"tool": "b"}]
        tool_results = [
            {"tool_name": "a", "result": {"found": True, "data": "x"}, "success": True},
            {"tool_name": "b", "result": {"found": True, "data": "y"}, "success": True},
        ]
        answer = synthesize_answer(plan, tool_results, "用户问题")
        assert answer == "综合回答"
        # 检查 LLM 收到了工具结果
        call_args = mock_llm_router.generate.call_args
        prompt = call_args.kwargs.get("prompt", "")
        assert "[a]" in prompt
        assert "[b]" in prompt
        assert "(成功)" in prompt

    def test_synthesis_with_failure(self, mock_llm_router):
        """部分工具失败时,提示标记失败状态."""
        mock_llm_router.generate.return_value = ("部分失败", {})
        tool_results = [
            {"tool_name": "a", "result": {"found": True}, "success": True},
            {"tool_name": "b", "result": {"found": False}, "success": False},
        ]
        answer = synthesize_answer([], tool_results, "q")
        assert answer == "部分失败"
        call_args = mock_llm_router.generate.call_args
        prompt = call_args.kwargs.get("prompt", "")
        assert "(失败)" in prompt
        assert "[b]" in prompt

    def test_synthesis_exception_returns_error(self, mock_llm_router):
        """LLM 抛异常时,返回错误消息."""
        mock_llm_router.generate.side_effect = Exception("synth fail")
        answer = synthesize_answer([], [], "q")
        assert "回答生成失败" in answer
        assert "synth fail" in answer
