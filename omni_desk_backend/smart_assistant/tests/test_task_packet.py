"""TaskPacket 任务包单元测试

覆盖 agents/task_packet.py 的所有公开接口:
- ExecutionMode / FailureMode 枚举
- SubTask 字段校验(合法性 + 内部一致性)
- TaskPacket 字段校验(合法性 + 循环依赖检测 + 拓扑排序)
- TaskPacket.from_dict() 反序列化
- TaskPacket.to_dict() 序列化
- TaskPacketValidator 校验
"""

import pytest

from smart_assistant.agents.roles import AgentRole
from smart_assistant.agents.task_packet import (
    ExecutionMode,
    FailureMode,
    SubTask,
    TaskPacket,
    TaskPacketValidator,
)


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------


def make_subtask(
    id: str = "research",
    role: AgentRole = AgentRole.RESEARCHER,
    objective: str = "检索文献",
    **kwargs,
) -> SubTask:
    """快速构造 SubTask(用于测试)"""
    return SubTask(id=id, role=role, objective=objective, **kwargs)


def make_task_packet(
    task_id: str = "test-task-1",
    objective: str = "调研 RAG 技术并写报告",
    execution_mode: ExecutionMode = ExecutionMode.PIPELINE,
    subtasks: list[SubTask] | None = None,
    **kwargs,
) -> TaskPacket:
    """快速构造 TaskPacket(用于测试)"""
    if subtasks is None:
        subtasks = [
            make_subtask(id="research", role=AgentRole.RESEARCHER),
            make_subtask(id="write", role=AgentRole.WRITER, depends_on=["research"]),
        ]
    return TaskPacket(
        task_id=task_id,
        objective=objective,
        execution_mode=execution_mode,
        subtasks=subtasks,
        **kwargs,
    )


def make_valid_supervisor_output() -> dict:
    """构造一个合法的 Supervisor 输出(用于 from_dict / validate 测试)"""
    return {
        "objective": "调研 RAG 技术并写报告",
        "execution_mode": "pipeline",
        "subtasks": [
            {
                "id": "research",
                "role": "researcher",
                "objective": "检索文献",
                "inputs": {"query": "RAG 企业知识库"},
                "failure_mode": "retry",
                "depends_on": [],
                "quality_gate": ["引用数量 >= 5"],
            },
            {
                "id": "write",
                "role": "writer",
                "objective": "撰写报告",
                "inputs": {"summary": "$research.summary"},
                "failure_mode": "abort",
                "depends_on": ["research"],
                "quality_gate": ["字数 >= 2000"],
            },
        ],
        "user_context": {"department": "技术部"},
        "global_budget": 30000,
        "timeout_seconds": 900,
    }


# ---------------------------------------------------------------------------
# ExecutionMode / FailureMode 枚举测试
# ---------------------------------------------------------------------------


class TestEnums:
    def test_execution_mode_values(self):
        """验证 ExecutionMode 枚举值"""
        assert ExecutionMode.PIPELINE.value == "pipeline"
        assert ExecutionMode.FANOUT.value == "fanout"
        assert ExecutionMode.HIERARCHICAL.value == "hierarchical"

    def test_failure_mode_values(self):
        """验证 FailureMode 枚举值"""
        assert FailureMode.SKIP.value == "skip"
        assert FailureMode.RETRY.value == "retry"
        assert FailureMode.FALLBACK.value == "fallback"
        assert FailureMode.ABORT.value == "abort"


# ---------------------------------------------------------------------------
# SubTask 测试
# ---------------------------------------------------------------------------


class TestSubTask:
    def test_create_valid_subtask(self):
        """创建合法的 SubTask"""
        st = make_subtask()
        assert st.id == "research"
        assert st.role == AgentRole.RESEARCHER
        assert st.objective == "检索文献"
        assert st.failure_mode == FailureMode.RETRY
        assert st.depends_on == []
        assert st.quality_gate == []

    def test_subtask_with_all_fields(self):
        """SubTask 包含所有字段"""
        st = SubTask(
            id="analysis",
            role=AgentRole.ANALYST,
            objective="分析数据",
            inputs={"data": "$research.references"},
            failure_mode=FailureMode.ABORT,
            depends_on=["research"],
            quality_gate=["趋势数量 >= 3"],
        )
        assert st.inputs == {"data": "$research.references"}
        assert st.failure_mode == FailureMode.ABORT
        assert st.depends_on == ["research"]
        assert st.quality_gate == ["趋势数量 >= 3"]

    def test_subtask_frozen(self):
        """SubTask 是 frozen dataclass,不可修改"""
        st = make_subtask()
        with pytest.raises(AttributeError):
            st.id = "new_id"  # type: ignore[misc]

    def test_subtask_invalid_id_empty(self):
        """空 id 抛出 ValueError"""
        with pytest.raises(ValueError, match="非空字符串"):
            make_subtask(id="")

    def test_subtask_invalid_id_characters(self):
        """id 包含非法字符抛出 ValueError"""
        with pytest.raises(ValueError, match="字母/数字/下划线/短横线"):
            make_subtask(id="research.v2")  # 点号非法

    def test_subtask_invalid_role(self):
        """非法 role 抛出 ValueError"""
        with pytest.raises(ValueError, match="AgentRole 枚举"):
            SubTask(id="test", role="invalid", objective="test")  # type: ignore

    def test_subtask_invalid_objective(self):
        """空 objective 抛出 ValueError"""
        with pytest.raises(ValueError, match="非空字符串"):
            make_subtask(objective="")

    def test_subtask_invalid_inputs_type(self):
        """inputs 不是 dict 抛出 ValueError"""
        with pytest.raises(ValueError, match="必须是 dict"):
            make_subtask(inputs=["not", "a", "dict"])  # type: ignore

    def test_subtask_invalid_failure_mode(self):
        """非法 failure_mode 抛出 ValueError"""
        with pytest.raises(ValueError, match="FailureMode 枚举"):
            make_subtask(failure_mode="invalid")  # type: ignore

    def test_subtask_invalid_depends_on_type(self):
        """depends_on 不是 list 抛出 ValueError"""
        with pytest.raises(ValueError, match="必须是 list"):
            make_subtask(depends_on="research")  # type: ignore

    def test_subtask_invalid_depends_on_element(self):
        """depends_on 元素不是 str 抛出 ValueError"""
        with pytest.raises(ValueError, match="元素必须是字符串"):
            make_subtask(depends_on=[123])  # type: ignore

    def test_subtask_invalid_quality_gate_type(self):
        """quality_gate 不是 list 抛出 ValueError"""
        with pytest.raises(ValueError, match="必须是 list"):
            make_subtask(quality_gate="数量 >= 5")  # type: ignore

    def test_subtask_invalid_quality_gate_element(self):
        """quality_gate 元素不是 str 抛出 ValueError"""
        with pytest.raises(ValueError, match="元素必须是字符串"):
            make_subtask(quality_gate=[123])  # type: ignore


# ---------------------------------------------------------------------------
# TaskPacket 测试
# ---------------------------------------------------------------------------


class TestTaskPacket:
    def test_create_valid_task_packet(self):
        """创建合法的 TaskPacket"""
        tp = make_task_packet()
        assert tp.task_id == "test-task-1"
        assert tp.execution_mode == ExecutionMode.PIPELINE
        assert len(tp.subtasks) == 2
        assert tp.subtasks[0].id == "research"
        assert tp.subtasks[1].id == "write"

    def test_task_packet_frozen(self):
        """TaskPacket 是 frozen dataclass"""
        tp = make_task_packet()
        with pytest.raises(AttributeError):
            tp.task_id = "new_id"  # type: ignore[misc]

    def test_task_packet_invalid_task_id(self):
        """空 task_id 抛出 ValueError"""
        with pytest.raises(ValueError, match="非空字符串"):
            make_task_packet(task_id="")

    def test_task_packet_invalid_objective(self):
        """空 objective 抛出 ValueError"""
        with pytest.raises(ValueError, match="非空字符串"):
            make_task_packet(objective="")

    def test_task_packet_invalid_execution_mode(self):
        """非法 execution_mode 抛出 ValueError"""
        with pytest.raises(ValueError, match="ExecutionMode 枚举"):
            make_task_packet(execution_mode="invalid")  # type: ignore

    def test_task_packet_empty_subtasks(self):
        """空 subtasks 抛出 ValueError"""
        with pytest.raises(ValueError, match="非空 list"):
            make_task_packet(subtasks=[])

    def test_task_packet_invalid_global_budget(self):
        """非正整数 global_budget 抛出 ValueError"""
        with pytest.raises(ValueError, match="正整数"):
            make_task_packet(global_budget=0)

    def test_task_packet_invalid_timeout(self):
        """非正整数 timeout_seconds 抛出 ValueError"""
        with pytest.raises(ValueError, match="正整数"):
            make_task_packet(timeout_seconds=-1)

    def test_task_packet_duplicate_subtask_ids(self):
        """重复 subtask id 抛出 ValueError"""
        with pytest.raises(ValueError, match="重复的 id"):
            make_task_packet(
                subtasks=[
                    make_subtask(id="dup"),
                    make_subtask(id="dup"),
                ]
            )

    def test_task_packet_invalid_depends_on_reference(self):
        """depends_on 引用不存在的 id 抛出 ValueError"""
        with pytest.raises(ValueError, match="不存在的 id"):
            make_task_packet(
                subtasks=[
                    make_subtask(id="a", depends_on=["nonexistent"]),
                ]
            )

    def test_task_packet_self_dependency(self):
        """subtask 依赖自己抛出 ValueError"""
        with pytest.raises(ValueError, match="不能依赖自己"):
            make_task_packet(
                subtasks=[
                    make_subtask(id="a", depends_on=["a"]),
                ]
            )

    def test_task_packet_circular_dependency(self):
        """循环依赖抛出 ValueError"""
        with pytest.raises(ValueError, match="循环依赖"):
            make_task_packet(
                subtasks=[
                    make_subtask(id="a", depends_on=["b"]),
                    make_subtask(id="b", depends_on=["c"]),
                    make_subtask(id="c", depends_on=["a"]),
                ]
            )

    def test_get_subtask_found(self):
        """get_subtask 找到存在的 subtask"""
        tp = make_task_packet()
        st = tp.get_subtask("research")
        assert st is not None
        assert st.id == "research"

    def test_get_subtask_not_found(self):
        """get_subtask 找不到返回 None"""
        tp = make_task_packet()
        assert tp.get_subtask("nonexistent") is None

    def test_get_execution_order_simple(self):
        """简单依赖的执行顺序"""
        tp = make_task_packet(
            subtasks=[
                make_subtask(id="c", depends_on=["b"]),
                make_subtask(id="a"),
                make_subtask(id="b", depends_on=["a"]),
            ]
        )
        order = tp.get_execution_order()
        ids = [st.id for st in order]
        assert ids == ["a", "b", "c"]

    def test_get_execution_order_independent(self):
        """独立 subtask 按字典序"""
        tp = make_task_packet(
            subtasks=[
                make_subtask(id="z"),
                make_subtask(id="a"),
                make_subtask(id="m"),
            ]
        )
        order = tp.get_execution_order()
        ids = [st.id for st in order]
        assert ids == ["a", "m", "z"]


# ---------------------------------------------------------------------------
# TaskPacket.from_dict / to_dict 测试
# ---------------------------------------------------------------------------


class TestTaskPacketSerialization:
    def test_from_dict_valid(self):
        """从合法 dict 构造 TaskPacket"""
        data = make_valid_supervisor_output()
        tp = TaskPacket.from_dict(data)
        assert tp.objective == "调研 RAG 技术并写报告"
        assert tp.execution_mode == ExecutionMode.PIPELINE
        assert len(tp.subtasks) == 2
        assert tp.subtasks[0].role == AgentRole.RESEARCHER
        assert tp.subtasks[1].depends_on == ["research"]
        assert tp.user_context == {"department": "技术部"}
        assert tp.global_budget == 30000

    def test_from_dict_auto_task_id(self):
        """不指定 task_id 时自动生成 UUID"""
        data = make_valid_supervisor_output()
        tp = TaskPacket.from_dict(data)
        assert tp.task_id  # 非空
        assert len(tp.task_id) == 32  # UUID hex 长度

    def test_from_dict_explicit_task_id(self):
        """指定 task_id 时使用指定值"""
        data = make_valid_supervisor_output()
        tp = TaskPacket.from_dict(data, task_id="my-custom-id")
        assert tp.task_id == "my-custom-id"

    def test_from_dict_not_dict(self):
        """非 dict 抛出 ValueError"""
        with pytest.raises(ValueError, match="必须是 dict"):
            TaskPacket.from_dict("not a dict")  # type: ignore

    def test_from_dict_missing_required_field(self):
        """缺少必需字段抛出 ValueError"""
        data = make_valid_supervisor_output()
        del data["objective"]
        with pytest.raises(ValueError, match="缺少必需字段"):
            TaskPacket.from_dict(data)

    def test_from_dict_invalid_role(self):
        """非法 role 抛出 ValueError"""
        data = make_valid_supervisor_output()
        data["subtasks"][0]["role"] = "invalid_role"
        with pytest.raises(ValueError, match="不是合法的 AgentRole"):
            TaskPacket.from_dict(data)

    def test_from_dict_invalid_failure_mode(self):
        """非法 failure_mode 抛出 ValueError"""
        data = make_valid_supervisor_output()
        data["subtasks"][0]["failure_mode"] = "invalid_mode"
        with pytest.raises(ValueError, match="不是合法的 FailureMode"):
            TaskPacket.from_dict(data)

    def test_from_dict_with_final_synthesis(self):
        """包含 final_synthesis 的 dict"""
        data = make_valid_supervisor_output()
        data["final_synthesis"] = {
            "id": "synth",
            "role": "synthesizer",
            "objective": "综合产出",
        }
        tp = TaskPacket.from_dict(data)
        assert tp.final_synthesis is not None
        assert tp.final_synthesis.id == "synth"
        assert tp.final_synthesis.role == AgentRole.SYNTHESIZER

    def test_to_dict_roundtrip(self):
        """to_dict() 后 from_dict() 可恢复"""
        original = TaskPacket.from_dict(make_valid_supervisor_output())
        serialized = original.to_dict()
        restored = TaskPacket.from_dict(serialized)
        assert restored.task_id == original.task_id
        assert restored.objective == original.objective
        assert restored.execution_mode == original.execution_mode
        assert len(restored.subtasks) == len(original.subtasks)
        assert restored.global_budget == original.global_budget


# ---------------------------------------------------------------------------
# TaskPacketValidator 测试
# ---------------------------------------------------------------------------


class TestTaskPacketValidator:
    def setup_method(self):
        self.validator = TaskPacketValidator()

    def test_validate_valid(self):
        """合法 dict 校验通过"""
        data = make_valid_supervisor_output()
        errors = self.validator.validate(data)
        assert errors == []

    def test_validate_not_dict(self):
        """非 dict 返回错误"""
        errors = self.validator.validate("not a dict")
        assert len(errors) == 1
        assert "必须是 dict" in errors[0]

    def test_validate_missing_objective(self):
        """缺少 objective 返回错误"""
        data = make_valid_supervisor_output()
        del data["objective"]
        errors = self.validator.validate(data)
        assert any("objective" in e for e in errors)

    def test_validate_missing_execution_mode(self):
        """缺少 execution_mode 返回错误"""
        data = make_valid_supervisor_output()
        del data["execution_mode"]
        errors = self.validator.validate(data)
        assert any("execution_mode" in e for e in errors)

    def test_validate_missing_subtasks(self):
        """缺少 subtasks 返回错误"""
        data = make_valid_supervisor_output()
        del data["subtasks"]
        errors = self.validator.validate(data)
        assert any("subtasks" in e for e in errors)

    def test_validate_invalid_execution_mode(self):
        """非法 execution_mode 返回错误"""
        data = make_valid_supervisor_output()
        data["execution_mode"] = "invalid"
        errors = self.validator.validate(data)
        assert any("execution_mode" in e for e in errors)

    def test_validate_empty_subtasks(self):
        """空 subtasks 返回错误"""
        data = make_valid_supervisor_output()
        data["subtasks"] = []
        errors = self.validator.validate(data)
        assert any("非空数组" in e for e in errors)

    def test_validate_subtask_missing_required(self):
        """subtask 缺少必需字段返回错误"""
        data = make_valid_supervisor_output()
        del data["subtasks"][0]["id"]
        errors = self.validator.validate(data)
        assert any("subtasks[0]" in e and "id" in e for e in errors)

    def test_validate_subtask_invalid_id(self):
        """subtask id 包含非法字符返回错误"""
        data = make_valid_supervisor_output()
        data["subtasks"][0]["id"] = "invalid.id"
        errors = self.validator.validate(data)
        assert any("合法标识符" in e for e in errors)

    def test_validate_subtask_duplicate_id(self):
        """subtask id 重复返回错误"""
        data = make_valid_supervisor_output()
        data["subtasks"][1]["id"] = "research"  # 与 [0] 重复
        errors = self.validator.validate(data)
        assert any("重复" in e for e in errors)

    def test_validate_subtask_invalid_role(self):
        """subtask role 非法返回错误"""
        data = make_valid_supervisor_output()
        data["subtasks"][0]["role"] = "invalid_role"
        errors = self.validator.validate(data)
        assert any("不是合法的 AgentRole" in e for e in errors)

    def test_validate_subtask_invalid_failure_mode(self):
        """subtask failure_mode 非法返回错误"""
        data = make_valid_supervisor_output()
        data["subtasks"][0]["failure_mode"] = "invalid_mode"
        errors = self.validator.validate(data)
        assert any("不合法" in e for e in errors)

    def test_validate_invalid_depends_on_reference(self):
        """depends_on 引用不存在的 id 返回错误"""
        data = make_valid_supervisor_output()
        data["subtasks"][0]["depends_on"] = ["nonexistent"]
        errors = self.validator.validate(data)
        assert any("不存在" in e for e in errors)
