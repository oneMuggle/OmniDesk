"""Supervisor 任务分解专项测试(Plan 3 新增)

聚焦传感器异常分析报告场景(Plan 3 demo 任务):
- 标准分解:传感器异常任务 → ≥ 3 SubTask(researcher + analyst + writer)
- JSON 校验通过(所有字段合法)
- 重试机制(第 1 次失败,第 2 次成功)
- max_retries 耗尽抛 ValueError

与 test_supervisor.py 的区别:
- test_supervisor.py 覆盖通用 Supervisor 行为
- 本文件覆盖 Plan 3 特定的传感器异常场景分解质量
"""

import json

import pytest

from smart_assistant.agents.supervisor import Supervisor
from smart_assistant.agents.task_packet import (
    ExecutionMode,
    FailureMode,
    TaskPacket,
    TaskPacketValidator,
)
from smart_assistant.agents.roles import AgentRole


# ---------------------------------------------------------------------------
# Mock LLMRouter(复用 test_supervisor.py 的模式)
# ---------------------------------------------------------------------------


class MockLLMRouter:
    """Mock LLMRouter(返回预设的 LLM 输出)"""

    def __init__(self, responses: list[str] | None = None):
        self.responses = responses or []
        self.call_count = 0

    def generate(self, prompt=None, system_message=None, stream=False, options=None, messages=None):
        if self.call_count >= len(self.responses):
            raise RuntimeError("MockLLMRouter: 没有更多预设响应")
        response = self.responses[self.call_count]
        self.call_count += 1
        return response, {"total_tokens": 100}


def make_sensor_anomaly_task_packet_json() -> str:
    """生成传感器异常分析的合法 TaskPacket JSON

    这是 Plan 3 demo 任务的标准分解:
    - researcher: 采集传感器异常数据
    - analyst: 模式识别 + 异常归因
    - writer(final_synthesis): 撰写根因报告 + 整改建议
    """
    return json.dumps({
        "objective": "分析本月传感器异常并生成根因报告",
        "execution_mode": "pipeline",
        "subtasks": [
            {
                "id": "researcher",
                "role": "researcher",
                "objective": "采集本月传感器异常数据",
                "inputs": {"query": "本月传感器异常记录"},
                "failure_mode": "retry",
                "depends_on": [],
                "quality_gate": ["anomalies 数量 >= 1"],
            },
            {
                "id": "analyst",
                "role": "analyst",
                "objective": "模式识别 + 异常归因",
                "inputs": {"anomalies": "$researcher.anomalies"},
                "failure_mode": "retry",
                "depends_on": ["researcher"],
                "quality_gate": ["root_causes 数量 >= 1"],
            },
        ],
        "final_synthesis": {
            "id": "writer",
            "role": "writer",
            "objective": "撰写根因报告 + 整改建议",
            "inputs": {
                "anomalies": "$researcher.anomalies",
                "root_causes": "$analyst.root_causes",
            },
            "failure_mode": "retry",
            "depends_on": ["researcher", "analyst"],
            "quality_gate": ["报告字数 >= 1000"],
        },
        "global_budget": 20000,
        "timeout_seconds": 600,
    })


# ---------------------------------------------------------------------------
# Plan 3 传感器异常场景分解测试
# ---------------------------------------------------------------------------


class TestSupervisorSensorDecomposition:
    """Plan 3: 传感器异常分析报告场景的 Supervisor 分解测试"""

    def test_sensor_anomaly_decomposition_yields_at_least_3_subtasks(self):
        """测试 1: 标准分解 — 传感器异常任务应分解为 ≥ 3 SubTask

        Plan 3 demo 任务: "分析本月所有传感器异常,生成根因报告 + 整改建议"
        预期分解:
        - researcher: 采集异常数据
        - analyst: 模式识别 + 归因
        - writer(final_synthesis): 撰写报告

        验证点:
        - subtasks 数量 ≥ 2(不含 final_synthesis)
        - 加上 final_synthesis 总 Step 数 ≥ 3
        - 角色包含 researcher / analyst / writer
        """
        llm_router = MockLLMRouter(responses=[make_sensor_anomaly_task_packet_json()])
        supervisor = Supervisor(llm_router=llm_router)

        task_packet = supervisor.generate_task_packet(
            query="分析本月所有传感器异常,生成根因报告 + 整改建议"
        )

        # 验证 subtasks 数量(不含 final_synthesis)
        assert len(task_packet.subtasks) >= 2, (
            f"传感器异常任务应分解为至少 2 个 subtask,实际 {len(task_packet.subtasks)} 个"
        )

        # 验证加上 final_synthesis 总 Step 数 ≥ 3
        total_steps = len(task_packet.subtasks) + (1 if task_packet.final_synthesis else 0)
        assert total_steps >= 3, (
            f"传感器异常任务总 Step 数应 ≥ 3(含 final_synthesis),实际 {total_steps} 个"
        )

        # 验证角色分布
        roles_used = {st.role for st in task_packet.subtasks}
        if task_packet.final_synthesis:
            roles_used.add(task_packet.final_synthesis.role)

        assert AgentRole.RESEARCHER in roles_used, "应包含 researcher 角色(采集数据)"
        assert AgentRole.ANALYST in roles_used, "应包含 analyst 角色(模式识别)"
        assert AgentRole.WRITER in roles_used, "应包含 writer 角色(撰写报告)"

        # 验证 LLM 只被调用 1 次(无重试)
        assert llm_router.call_count == 1

    def test_sensor_anomaly_json_validation_passes(self):
        """测试 2: JSON 校验通过 — 所有字段合法

        验证 TaskPacketValidator 对传感器异常场景的 JSON 校验通过:
        - objective 非空
        - execution_mode 合法(pipeline)
        - subtasks 每个都有 id/role/objective
        - depends_on 引用的 id 都存在
        - role 都是合法的 AgentRole
        - failure_mode 合法
        """
        json_str = make_sensor_anomaly_task_packet_json()
        data = json.loads(json_str)

        # 用 TaskPacketValidator 校验
        validator = TaskPacketValidator()
        errors = validator.validate(data)

        assert errors == [], f"传感器异常场景的 JSON 校验应通过,实际错误: {errors}"

        # 进一步验证 TaskPacket.from_dict() 能成功构造
        task_packet = TaskPacket.from_dict(data)
        assert isinstance(task_packet, TaskPacket)
        assert task_packet.execution_mode == ExecutionMode.PIPELINE
        assert task_packet.objective == "分析本月传感器异常并生成根因报告"

        # 验证 final_synthesis 构造正确
        assert task_packet.final_synthesis is not None
        assert task_packet.final_synthesis.id == "writer"
        assert task_packet.final_synthesis.role == AgentRole.WRITER

        # 验证 depends_on 引用完整性
        subtask_ids = {st.id for st in task_packet.subtasks}
        for st in task_packet.subtasks:
            for dep_id in st.depends_on:
                assert dep_id in subtask_ids, (
                    f"subtask '{st.id}' 的 depends_on 引用了不存在的 id '{dep_id}'"
                )

        # 验证 final_synthesis 的 depends_on 也完整
        for dep_id in task_packet.final_synthesis.depends_on:
            assert dep_id in subtask_ids, (
                f"final_synthesis 的 depends_on 引用了不存在的 id '{dep_id}'"
            )

    def test_sensor_anomaly_retry_on_first_failure(self):
        """测试 3: 重试机制 — 第 1 次失败,第 2 次成功

        模拟 LLM 第 1 次输出非法 JSON(缺少 subtasks),第 2 次输出合法 JSON。
        验证 Supervisor 能成功重试并返回正确的 TaskPacket。
        """
        # 第 1 次返回非法 JSON(缺少 subtasks 字段)
        invalid_json = json.dumps({
            "objective": "分析传感器异常",
            "execution_mode": "pipeline",
            # 缺少 subtasks
        })
        # 第 2 次返回合法 JSON
        valid_json = make_sensor_anomaly_task_packet_json()

        llm_router = MockLLMRouter(responses=[invalid_json, valid_json])
        supervisor = Supervisor(llm_router=llm_router, max_retries=3)

        task_packet = supervisor.generate_task_packet(
            query="分析本月所有传感器异常,生成根因报告"
        )

        # 验证成功返回
        assert isinstance(task_packet, TaskPacket)
        assert task_packet.objective == "分析本月传感器异常并生成根因报告"
        assert len(task_packet.subtasks) >= 2

        # 验证 LLM 被调用 2 次(第 1 次失败,第 2 次成功)
        assert llm_router.call_count == 2

    def test_sensor_anomaly_max_retries_exceeded_raises_value_error(self):
        """测试 4: max_retries 耗尽抛 ValueError

        模拟 LLM 所有响应都非法,验证 Supervisor 在 max_retries 次后抛出 ValueError。
        """
        # 所有响应都非法
        invalid_responses = [
            "这不是 JSON",
            json.dumps({"objective": "test"}),  # 缺少必需字段
            "```json\n{invalid}\n```",  # 非法 JSON
        ]

        llm_router = MockLLMRouter(responses=invalid_responses)
        supervisor = Supervisor(llm_router=llm_router, max_retries=3)

        # 验证抛出 ValueError
        with pytest.raises(ValueError, match="仍无法生成合法的 TaskPacket"):
            supervisor.generate_task_packet(
                query="分析本月所有传感器异常,生成根因报告"
            )

        # 验证 LLM 被调用 3 次(max_retries)
        assert llm_router.call_count == 3


# ---------------------------------------------------------------------------
# 额外测试: 验证 few-shot 示例不影响现有功能
# ---------------------------------------------------------------------------


class TestSupervisorFewShotCompatibility:
    """验证 few-shot 示例添加后不破坏现有功能"""

    def test_existing_rag_research_scenario_still_works(self):
        """原有的 RAG 调研场景仍然可以正常分解

        确保 few-shot 示例(传感器异常)不会影响其他场景的分解。
        """
        # 使用 test_supervisor.py 中的标准 RAG 调研 JSON
        rag_json = json.dumps({
            "objective": "调研 RAG 技术并写报告",
            "execution_mode": "pipeline",
            "subtasks": [
                {
                    "id": "research",
                    "role": "researcher",
                    "objective": "检索 RAG 相关文献",
                    "inputs": {},
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
            "global_budget": 30000,
            "timeout_seconds": 900,
        })

        llm_router = MockLLMRouter(responses=[rag_json])
        supervisor = Supervisor(llm_router=llm_router)

        task_packet = supervisor.generate_task_packet(query="调研 RAG 技术")

        assert isinstance(task_packet, TaskPacket)
        assert task_packet.objective == "调研 RAG 技术并写报告"
        assert len(task_packet.subtasks) == 2
        assert task_packet.subtasks[0].id == "research"
        assert task_packet.subtasks[1].id == "write"
