"""Supervisor LLM 任务分解单元测试

覆盖 agents/supervisor.py 的核心功能:
- Supervisor.generate_task_packet() 完整流程
- JSON 解析(纯 JSON / markdown 代码块 / 提取第一个 {} 块)
- 校验失败重试(最多 max_retries 次)
- 错误处理
"""

import json

import pytest

from smart_assistant.agents.supervisor import Supervisor
from smart_assistant.agents.task_packet import ExecutionMode, TaskPacket


# ---------------------------------------------------------------------------
# Mock LLMRouter
# ---------------------------------------------------------------------------


class MockLLMRouter:
    """Mock LLMRouter(返回预设的 LLM 输出)"""

    def __init__(self, responses: list[str] | None = None):
        """
        Args:
            responses: 按顺序返回的 LLM 输出列表
                      如果 responses 用尽,抛出异常
        """
        self.responses = responses or []
        self.call_count = 0

    def generate(self, prompt=None, system_message=None, stream=False, options=None, messages=None):
        """模拟 LLMRouter.generate()"""
        if self.call_count >= len(self.responses):
            raise RuntimeError("MockLLMRouter: 没有更多预设响应")
        response = self.responses[self.call_count]
        self.call_count += 1
        return response, {"total_tokens": 100}


def make_valid_task_packet_json() -> str:
    """生成一个合法的 TaskPacket JSON 字符串"""
    return json.dumps({
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


# ---------------------------------------------------------------------------
# Supervisor 测试
# ---------------------------------------------------------------------------


class TestSupervisor:
    def test_generate_task_packet_success(self):
        """成功生成 TaskPacket"""
        llm_router = MockLLMRouter(responses=[make_valid_task_packet_json()])
        supervisor = Supervisor(llm_router=llm_router)

        task_packet = supervisor.generate_task_packet(query="调研 RAG 技术")

        assert isinstance(task_packet, TaskPacket)
        assert task_packet.objective == "调研 RAG 技术并写报告"
        assert task_packet.execution_mode == ExecutionMode.PIPELINE
        assert len(task_packet.subtasks) == 2
        assert task_packet.subtasks[0].id == "research"
        assert task_packet.subtasks[1].id == "write"
        assert llm_router.call_count == 1

    def test_generate_task_packet_with_markdown(self):
        """解析 markdown 代码块包裹的 JSON"""
        json_str = make_valid_task_packet_json()
        llm_router = MockLLMRouter(responses=[f"```json\n{json_str}\n```"])
        supervisor = Supervisor(llm_router=llm_router)

        task_packet = supervisor.generate_task_packet(query="test")
        assert task_packet.objective == "调研 RAG 技术并写报告"

    def test_generate_task_packet_with_extra_text(self):
        """解析 JSON 前后的额外文本"""
        json_str = make_valid_task_packet_json()
        llm_router = MockLLMRouter(responses=[f"这是您的任务计划:\n{json_str}\n希望这能帮到您!"])
        supervisor = Supervisor(llm_router=llm_router)

        task_packet = supervisor.generate_task_packet(query="test")
        assert task_packet.objective == "调研 RAG 技术并写报告"

    def test_generate_task_packet_retry_on_invalid_json(self):
        """JSON 解析失败时重试"""
        # 第一次返回非法 JSON,第二次返回合法 JSON
        llm_router = MockLLMRouter(responses=[
            "这不是 JSON",
            make_valid_task_packet_json(),
        ])
        supervisor = Supervisor(llm_router=llm_router, max_retries=3)

        task_packet = supervisor.generate_task_packet(query="test")
        assert task_packet.objective == "调研 RAG 技术并写报告"
        assert llm_router.call_count == 2  # 重试了 1 次

    def test_generate_task_packet_retry_on_validation_error(self):
        """JSON 校验失败时重试"""
        # 第一次返回缺少必需字段的 JSON,第二次返回合法 JSON
        invalid_json = json.dumps({"objective": "test"})  # 缺少 execution_mode / subtasks
        llm_router = MockLLMRouter(responses=[
            invalid_json,
            make_valid_task_packet_json(),
        ])
        supervisor = Supervisor(llm_router=llm_router, max_retries=3)

        task_packet = supervisor.generate_task_packet(query="test")
        assert task_packet.objective == "调研 RAG 技术并写报告"
        assert llm_router.call_count == 2

    def test_generate_task_packet_max_retries_exceeded(self):
        """超过最大重试次数后抛出 ValueError"""
        # 所有响应都非法
        llm_router = MockLLMRouter(responses=[
            "invalid 1",
            "invalid 2",
            "invalid 3",
        ])
        supervisor = Supervisor(llm_router=llm_router, max_retries=3)

        with pytest.raises(ValueError, match="仍无法生成合法的 TaskPacket"):
            supervisor.generate_task_packet(query="test")

        assert llm_router.call_count == 3

    def test_generate_task_packet_with_user_context(self):
        """带用户上下文的 TaskPacket 生成"""
        llm_router = MockLLMRouter(responses=[make_valid_task_packet_json()])
        supervisor = Supervisor(llm_router=llm_router)

        task_packet = supervisor.generate_task_packet(
            query="调研 RAG 技术",
            user_context={"department": "技术部", "role": "工程师"},
        )

        assert isinstance(task_packet, TaskPacket)
        # user_context 不直接影响 task_packet,但会被传递给 LLM

    def test_parse_json_pure_json(self):
        """解析纯 JSON"""
        supervisor = Supervisor(llm_router=MockLLMRouter())
        json_str = make_valid_task_packet_json()
        data = supervisor._parse_json(json_str)
        assert isinstance(data, dict)
        assert data["objective"] == "调研 RAG 技术并写报告"

    def test_parse_json_with_markdown_json(self):
        """解析 ```json ... ``` 代码块"""
        supervisor = Supervisor(llm_router=MockLLMRouter())
        json_str = make_valid_task_packet_json()
        data = supervisor._parse_json(f"```json\n{json_str}\n```")
        assert isinstance(data, dict)

    def test_parse_json_with_markdown_plain(self):
        """解析 ``` ... ``` 代码块"""
        supervisor = Supervisor(llm_router=MockLLMRouter())
        json_str = make_valid_task_packet_json()
        data = supervisor._parse_json(f"```\n{json_str}\n```")
        assert isinstance(data, dict)

    def test_parse_json_with_surrounding_text(self):
        """解析带前后文本的 JSON"""
        supervisor = Supervisor(llm_router=MockLLMRouter())
        json_str = make_valid_task_packet_json()
        data = supervisor._parse_json(f"Here is the plan:\n{json_str}\nGood luck!")
        assert isinstance(data, dict)

    def test_parse_json_invalid_raises(self):
        """无法解析的 JSON 抛出 ValueError"""
        supervisor = Supervisor(llm_router=MockLLMRouter())
        with pytest.raises(ValueError, match="无法从 LLM 输出中解析 JSON"):
            supervisor._parse_json("this is not json at all")

    def test_parse_json_non_dict_raises(self):
        """解析为 list 而不是 dict 抛出 ValueError"""
        supervisor = Supervisor(llm_router=MockLLMRouter())
        with pytest.raises(ValueError, match="JSON 解析结果不是 dict"):
            supervisor._parse_json("[1, 2, 3]")
