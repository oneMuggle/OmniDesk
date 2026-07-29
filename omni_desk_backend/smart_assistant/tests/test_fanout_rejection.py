"""P0-J 未实现执行模式显式拒绝测试

- executor:FANOUT / HIERARCHICAL 模式返回 status='rejected'
  (而非抛 NotImplementedError 混入 failed 异常路径)
- supervisor:LLM 产出 fanout/hierarchical 的 TaskPacket 时直接
  抛 ValidationError,不进入重试循环
"""
from unittest.mock import MagicMock

import pytest
from django.core.exceptions import ValidationError

from smart_assistant.agents.executor import MultiAgentExecutor
from smart_assistant.agents.supervisor import Supervisor
from smart_assistant.agents.task_packet import ExecutionMode, TaskPacket


def _make_packet(mode: str) -> TaskPacket:
    return TaskPacket.from_dict(
        {
            "objective": "测试目标",
            "execution_mode": mode,
            "subtasks": [
                {
                    "id": "t1",
                    "role": "researcher",
                    "objective": "调研 X",
                    "failure_mode": "skip",
                    "depends_on": [],
                }
            ],
        }
    )


def _make_executor(packet: TaskPacket) -> MultiAgentExecutor:
    """FANOUT/HIERARCHICAL 分支在触碰 registry 前即返回,桩对象即可。"""
    return MultiAgentExecutor(
        task_packet=packet,
        llm_router=MagicMock(),
        tool_registry=MagicMock(),
    )


class TestExecutorModeRejection:
    def test_fanout_returns_rejected(self):
        result = _make_executor(_make_packet("fanout")).execute()

        assert result.status == "rejected"
        assert "fanout" in result.error_message
        assert "pipeline" in result.error_message
        assert result.subtask_results == []

    def test_hierarchical_returns_rejected(self):
        result = _make_executor(_make_packet("hierarchical")).execute()

        assert result.status == "rejected"
        assert "hierarchical" in result.error_message

    def test_rejected_is_not_failed(self):
        """rejected 与真实执行失败 failed 语义区分(运维告警面不同)。"""
        result = _make_executor(_make_packet("fanout")).execute()
        assert result.status != "failed"


class TestSupervisorModeValidation:
    def _supervisor_returning(self, mode: str) -> Supervisor:
        llm_router = MagicMock()
        llm_router.generate.return_value = (
            '{"objective": "目标", "execution_mode": "%s", '
            '"subtasks": [{"id": "t1", "role": "researcher", "objective": "调研"}]}' % mode
        )
        return Supervisor(llm_router=llm_router)

    def test_fanout_packet_raises_validation_error(self):
        supervisor = self._supervisor_returning("fanout")
        with pytest.raises(ValidationError, match="fanout mode not yet implemented"):
            supervisor.generate_task_packet(query="测试")

    def test_pipeline_packet_accepted(self):
        supervisor = self._supervisor_returning("pipeline")
        packet = supervisor.generate_task_packet(query="测试")
        assert packet.execution_mode == ExecutionMode.PIPELINE
