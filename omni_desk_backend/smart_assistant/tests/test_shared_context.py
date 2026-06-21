"""SharedContext 跨 Agent 共享上下文单元测试

覆盖 agents/shared_context.py 的所有公开接口:
- Decision / ErrorRecord dataclass
- SharedContext artifact 管理(add/get/has)
- SharedContext 决策与错误记录
- SharedContext Token 预算追踪
- SharedContext.resolve_references() 变量解析
- SharedContext.to_context_for() 上下文构造
- SharedContext.to_dict() 序列化
"""

import pytest

from smart_assistant.agents.roles import AgentRole
from smart_assistant.agents.shared_context import (
    Decision,
    ErrorRecord,
    SharedContext,
)
from smart_assistant.agents.task_packet import SubTask


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------


def make_subtask(
    id: str = "writer",
    role: AgentRole = AgentRole.WRITER,
    objective: str = "撰写报告",
    **kwargs,
) -> SubTask:
    """快速构造 SubTask"""
    return SubTask(id=id, role=role, objective=objective, **kwargs)


def make_context_with_artifacts() -> SharedContext:
    """构造带 artifact 的 SharedContext"""
    ctx = SharedContext(original_query="调研 RAG 技术")
    ctx.add_artifact("research", {
        "summary": "RAG 是检索增强生成技术",
        "references": ["文献1", "文献2"],
        "metadata": {"author": "张三", "year": 2025},
    })
    ctx.add_artifact("analysis", {
        "trends": ["趋势1", "趋势2", "趋势3"],
        "trend_count": 3,
    })
    return ctx


# ---------------------------------------------------------------------------
# Decision / ErrorRecord 测试
# ---------------------------------------------------------------------------


class TestDataclasses:
    def test_decision_creation(self):
        """创建 Decision"""
        d = Decision(made_by="supervisor", decision="用 pipeline 模式", rationale="任务串行")
        assert d.made_by == "supervisor"
        assert d.decision == "用 pipeline 模式"
        assert d.rationale == "任务串行"
        assert d.timestamp  # 自动生成

    def test_decision_frozen(self):
        """Decision 是 frozen dataclass"""
        d = Decision(made_by="supervisor", decision="test", rationale="reason")
        with pytest.raises(AttributeError):
            d.made_by = "other"  # type: ignore[misc]

    def test_error_record_creation(self):
        """创建 ErrorRecord"""
        e = ErrorRecord(
            subtask_id="research",
            error_type="ValueError",
            error_message="参数错误",
            recovery_action="retry",
        )
        assert e.subtask_id == "research"
        assert e.error_type == "ValueError"
        assert e.recovery_action == "retry"


# ---------------------------------------------------------------------------
# SharedContext artifact 管理测试
# ---------------------------------------------------------------------------


class TestArtifactManagement:
    def setup_method(self):
        self.ctx = SharedContext(original_query="调研 RAG")

    def test_add_and_get_artifact(self):
        """添加和获取 artifact"""
        self.ctx.add_artifact("research", {"summary": "test"})
        assert self.ctx.get_artifact("research") == {"summary": "test"}

    def test_get_nonexistent_artifact(self):
        """获取不存在的 artifact 返回 None"""
        assert self.ctx.get_artifact("nonexistent") is None

    def test_has_artifact(self):
        """has_artifact 检查"""
        self.ctx.add_artifact("research", {"summary": "test"})
        assert self.ctx.has_artifact("research") is True
        assert self.ctx.has_artifact("nonexistent") is False

    def test_add_artifact_not_dict_raises(self):
        """添加非 dict 的 artifact 抛出 ValueError"""
        with pytest.raises(ValueError, match="必须是 dict"):
            self.ctx.add_artifact("test", "not a dict")  # type: ignore

    def test_add_artifact_overwrites(self):
        """重复添加同 subtask_id 的 artifact 覆盖"""
        self.ctx.add_artifact("research", {"v": 1})
        self.ctx.add_artifact("research", {"v": 2})
        assert self.ctx.get_artifact("research") == {"v": 2}


# ---------------------------------------------------------------------------
# SharedContext 决策与错误记录测试
# ---------------------------------------------------------------------------


class TestDecisionAndErrorLogging:
    def setup_method(self):
        self.ctx = SharedContext(original_query="调研 RAG")

    def test_record_decision(self):
        """记录决策"""
        d = self.ctx.record_decision(
            made_by="supervisor",
            decision="用 pipeline 模式",
            rationale="任务串行",
        )
        assert d.made_by == "supervisor"
        assert len(self.ctx.decisions) == 1
        assert self.ctx.decisions[0] is d

    def test_record_error(self):
        """记录错误"""
        error = ValueError("test error")
        e = self.ctx.record_error(
            subtask_id="research",
            error=error,
            recovery_action="retry",
        )
        assert e.subtask_id == "research"
        assert e.error_type == "ValueError"
        assert e.error_message == "test error"
        assert len(self.ctx.error_log) == 1
        assert self.ctx.error_log[0] is e


# ---------------------------------------------------------------------------
# SharedContext Token 预算测试
# ---------------------------------------------------------------------------


class TestTokenBudget:
    def setup_method(self):
        self.ctx = SharedContext(original_query="调研 RAG", global_budget=1000)

    def test_initial_budget(self):
        """初始预算状态"""
        assert self.ctx.token_budget_used == 0
        assert self.ctx.remaining_budget() == 1000
        assert self.ctx.is_budget_exhausted() is False

    def test_consume_tokens(self):
        """消耗 Token"""
        self.ctx.consume_tokens(300)
        assert self.ctx.token_budget_used == 300
        assert self.ctx.remaining_budget() == 700

    def test_consume_tokens_multiple(self):
        """多次消耗 Token"""
        self.ctx.consume_tokens(300)
        self.ctx.consume_tokens(400)
        assert self.ctx.token_budget_used == 700
        assert self.ctx.remaining_budget() == 300

    def test_consume_negative_raises(self):
        """消耗负数抛出 ValueError"""
        with pytest.raises(ValueError, match="不能为负"):
            self.ctx.consume_tokens(-10)

    def test_budget_exhausted(self):
        """预算耗尽"""
        self.ctx.consume_tokens(1000)
        assert self.ctx.remaining_budget() == 0
        assert self.ctx.is_budget_exhausted() is True

    def test_budget_over_consumed(self):
        """超额消耗"""
        self.ctx.consume_tokens(1500)
        assert self.ctx.remaining_budget() == 0  # max(0, ...) 不返回负数
        assert self.ctx.is_budget_exhausted() is True


# ---------------------------------------------------------------------------
# SharedContext.resolve_references() 测试
# ---------------------------------------------------------------------------


class TestResolveReferences:
    def setup_method(self):
        self.ctx = make_context_with_artifacts()

    def test_resolve_simple_field_reference(self):
        """解析简单字段引用 $subtask.field"""
        result = self.ctx.resolve_references("$research.summary")
        assert result == "RAG 是检索增强生成技术"

    def test_resolve_entire_artifact(self):
        """解析整个 artifact $subtask"""
        result = self.ctx.resolve_references("$research")
        assert isinstance(result, dict)
        assert "summary" in result
        assert "references" in result

    def test_resolve_nested_field_reference(self):
        """解析嵌套字段引用 $subtask.field1.field2"""
        result = self.ctx.resolve_references("$research.metadata.author")
        assert result == "张三"

    def test_resolve_reference_in_dict(self):
        """解析 dict 中的引用"""
        template = {"query": "$research.summary", "count": "$analysis.trend_count"}
        result = self.ctx.resolve_references(template)
        assert result == {
            "query": "RAG 是检索增强生成技术",
            "count": 3,
        }

    def test_resolve_reference_in_list(self):
        """解析 list 中的引用"""
        template = ["$research.summary", "$analysis.trend_count"]
        result = self.ctx.resolve_references(template)
        assert result == ["RAG 是检索增强生成技术", 3]

    def test_resolve_embedded_reference_in_string(self):
        """解析字符串中嵌入的引用"""
        result = self.ctx.resolve_references("Summary: $research.summary")
        assert result == "Summary: RAG 是检索增强生成技术"

    def test_resolve_multiple_references_in_string(self):
        """解析字符串中多个引用"""
        result = self.ctx.resolve_references(
            "RAG: $research.summary, 趋势数: $analysis.trend_count"
        )
        assert "RAG 是检索增强生成技术" in result
        assert "3" in result

    def test_resolve_dict_reference_to_json_string(self):
        """dict 引用在嵌入字符串时转为 JSON"""
        result = self.ctx.resolve_references("Refs: $research.references")
        # 嵌入字符串时 dict/list 转 JSON
        assert "文献1" in result
        assert "文献2" in result

    def test_resolve_non_string_passthrough(self):
        """非字符串类型原样返回"""
        assert self.ctx.resolve_references(42) == 42
        assert self.ctx.resolve_references(3.14) == 3.14
        assert self.ctx.resolve_references(True) is True
        assert self.ctx.resolve_references(None) is None

    def test_resolve_nonexistent_subtask_raises(self):
        """引用不存在的 subtask 抛出 KeyError"""
        with pytest.raises(KeyError, match="产物不存在"):
            self.ctx.resolve_references("$nonexistent.field")

    def test_resolve_nonexistent_field_raises(self):
        """引用不存在的字段抛出 KeyError"""
        with pytest.raises(KeyError, match="不存在字段"):
            self.ctx.resolve_references("$research.nonexistent")

    def test_resolve_embedded_nonexistent_shows_placeholder(self):
        """嵌入字符串中引用不存在显示占位符(不抛异常)"""
        result = self.ctx.resolve_references("Value: $nonexistent.field")
        assert "未找到" in result


# ---------------------------------------------------------------------------
# SharedContext.to_context_for() 测试
# ---------------------------------------------------------------------------


class TestToContextFor:
    def setup_method(self):
        self.ctx = make_context_with_artifacts()

    def test_to_context_for_includes_objective(self):
        """上下文包含 subtask 的 objective"""
        subtask = make_subtask(
            objective="撰写关于 RAG 的报告",
            depends_on=["research"],
        )
        messages = self.ctx.to_context_for(subtask)
        assert any(m["content"] == "撰写关于 RAG 的报告" for m in messages)

    def test_to_context_for_includes_dep_artifacts(self):
        """上下文包含依赖 subtask 的产物"""
        subtask = make_subtask(
            inputs={"summary": "$research.summary"},
            depends_on=["research"],
        )
        messages = self.ctx.to_context_for(subtask)
        # 应包含 research 的 summary 字段
        assert any("RAG 是检索增强生成技术" in m["content"] for m in messages)

    def test_to_context_for_missing_dep(self):
        """依赖 subtask 未产出时注入提示"""
        subtask = make_subtask(
            objective="撰写报告",
            depends_on=["nonexistent"],
        )
        messages = self.ctx.to_context_for(subtask)
        assert any("未产出结果" in m["content"] for m in messages)

    def test_to_context_for_no_inputs_uses_full_artifact(self):
        """未指定 inputs 时注入完整 artifact"""
        subtask = make_subtask(
            objective="分析数据",
            depends_on=["research"],
        )
        messages = self.ctx.to_context_for(subtask)
        # 应包含完整 artifact
        content = "\n".join(m["content"] for m in messages)
        assert "RAG 是检索增强生成技术" in content
        assert "文献1" in content

    def test_to_context_for_includes_decisions(self):
        """上下文包含最近 5 条决策"""
        for i in range(7):
            self.ctx.record_decision(
                made_by="supervisor",
                decision=f"决策{i}",
                rationale=f"理由{i}",
            )
        subtask = make_subtask(objective="撰写报告")
        messages = self.ctx.to_context_for(subtask)
        content = "\n".join(m["content"] for m in messages)
        # 只包含最近 5 条
        assert "决策6" in content  # 最新
        assert "决策2" in content  # 第 5 新
        assert "决策0" not in content  # 超出 5 条范围
        assert "决策1" not in content


# ---------------------------------------------------------------------------
# SharedContext.to_dict() 测试
# ---------------------------------------------------------------------------


class TestToDict:
    def test_to_dict_structure(self):
        """to_dict() 返回正确结构"""
        ctx = make_context_with_artifacts()
        ctx.record_decision("supervisor", "决策1")
        ctx.consume_tokens(100)

        d = ctx.to_dict()
        assert d["original_query"] == "调研 RAG 技术"
        assert "research" in d["artifacts"]
        assert len(d["decisions"]) == 1
        assert d["token_budget_used"] == 100
        assert d["global_budget"] == 20000
        assert d["remaining_budget"] == 19900

    def test_to_dict_decisions_have_iso_timestamp(self):
        """to_dict() 的决策包含 ISO 时间戳"""
        ctx = SharedContext(original_query="test")
        ctx.record_decision("supervisor", "决策")
        d = ctx.to_dict()
        assert "timestamp" in d["decisions"][0]
        # ISO 格式应该能解析
        from datetime import datetime
        datetime.fromisoformat(d["decisions"][0]["timestamp"])
