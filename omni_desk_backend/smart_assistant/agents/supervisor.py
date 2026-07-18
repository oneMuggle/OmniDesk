"""Supervisor LLM 任务分解

Supervisor 负责将用户的复杂查询分解为可执行的 TaskPacket:
1. 调用 LLMRouter 生成 TaskPacket JSON
2. 通过 TaskPacketValidator 校验 JSON 结构
3. 校验失败时重试(最多 max_retries 次,每次加强 prompt)
4. 通过 TaskPacket.from_dict() 构造 TaskPacket 实例

Example:
    supervisor = Supervisor(llm_router=LLMRouter())
    task_packet = supervisor.generate_task_packet(
        query="调研 RAG 技术并写报告",
        user_context={"department": "技术部"},
    )
    # task_packet 包含 3-5 个 subtask(Researcher → Analyst → Writer 等)
"""

from __future__ import annotations

import json
import re
from typing import Any

from .roles import ROLE_PROFILES, AgentRole
from .task_packet import TaskPacket, TaskPacketValidator


class Supervisor:
    """Supervisor LLM 任务分解

    Attributes:
        llm_router: LLMRouter 实例
        validator: TaskPacketValidator 实例
        max_retries: 最大重试次数(默认 3)
    """

    def __init__(
        self,
        llm_router: Any,  # LLMRouter 实例
        max_retries: int = 3,
    ):
        self.llm_router = llm_router
        self.validator = TaskPacketValidator()
        self.max_retries = max_retries

    def generate_task_packet(
        self,
        query: str,
        user_context: dict | None = None,
    ) -> TaskPacket:
        """根据用户查询生成 TaskPacket

        Args:
            query: 用户查询
            user_context: 用户上下文(部门/角色/权限等)

        Returns:
            TaskPacket 实例

        Raises:
            ValueError: 如果 max_retries 次后仍无法生成合法的 TaskPacket
        """
        last_error: str | None = None

        for attempt in range(self.max_retries):
            try:
                # 1. 调用 LLM 生成 JSON
                llm_output = self._invoke_llm(query, user_context, previous_errors=last_error)

                # 2. 解析 JSON
                data = self._parse_json(llm_output)

                # 3. 校验 JSON 结构
                errors = self.validator.validate(data)
                if errors:
                    last_error = f"JSON 校验失败: {'; '.join(errors)}"
                    continue

                # 4. 构造 TaskPacket
                task_packet = TaskPacket.from_dict(data)
                return task_packet

            except Exception as e:
                last_error = str(e)
                continue

        # 所有重试都失败
        raise ValueError(
            f"Supervisor 在 {self.max_retries} 次尝试后仍无法生成合法的 TaskPacket。最后错误: {last_error}"
        )

    def _invoke_llm(
        self,
        query: str,
        user_context: dict | None,
        previous_errors: str | None = None,
    ) -> str:
        """调用 LLM 生成 TaskPacket JSON

        Args:
            query: 用户查询
            user_context: 用户上下文
            previous_errors: 上一次尝试的错误信息(用于改进 prompt)

        Returns:
            LLM 生成的文本(应该是 JSON 格式)
        """
        # 构造 system prompt
        system_prompt = self._build_system_prompt()

        # 构造 user message
        user_message = self._build_user_message(query, user_context, previous_errors)

        # 调用 LLMRouter
        messages = [
            {"role": "user", "content": user_message},
        ]

        response = self.llm_router.generate(
            prompt=None,
            system_message=system_prompt,
            stream=False,
            options={
                "temperature": 0.3,  # 低温度,保证 JSON 结构稳定
                "top_p": 0.9,
                "max_tokens": 2000,
            },
            messages=messages,
        )

        # LLMRouter.generate 可能返回 (content, usage) 或纯 content
        if isinstance(response, tuple):
            content, _ = response
        else:
            content = response

        return content

    def _build_system_prompt(self) -> str:
        """构造 Supervisor 的 system prompt"""
        # 列出所有可用角色
        available_roles = ", ".join(
            f"{role.value}({profile.display_name})"
            for role, profile in ROLE_PROFILES.items()
            if role != AgentRole.SUPERVISOR  # Supervisor 自己不算
        )

        return f"""你是 OmniDesk 智能助手的任务监督者(Supervisor)。

你的职责是:
1. 理解用户的复杂查询,分解为多个可执行的子任务
2. 为每个子任务选择合适的专业角色
3. 确定子任务的执行顺序和依赖关系

可用的专业角色:
{available_roles}

你必须输出严格的 JSON 格式,包含以下字段:
{{
    "objective": "总目标(用户查询的提炼)",
    "execution_mode": "pipeline 或 fanout 或 hierarchical",
    "subtasks": [
        {{
            "id": "唯一标识(字母/数字/下划线/短横线)",
            "role": "角色名称(见上面列表)",
            "objective": "子任务目标(自然语言描述)",
            "inputs": {{"参数名": "$subtask_id.field 引用"}},
            "failure_mode": "retry 或 skip 或 fallback 或 abort",
            "depends_on": ["依赖的 subtask id 列表"],
            "quality_gate": ["质量检查点(自然语言)"]
        }}
    ],
    "final_synthesis": {{  // 可选,用于合并所有产物
        "id": "synth",
        "role": "synthesizer",
        "objective": "综合所有产出",
        "depends_on": ["需要综合的 subtask id"]
    }},
    "global_budget": 20000,  // 全局 Token 预算
    "timeout_seconds": 600  // 超时时间(秒)
}}

示例:用户问"分析本月传感器异常,生成根因报告"
{{
    "objective": "分析本月传感器异常并生成根因报告",
    "execution_mode": "pipeline",
    "subtasks": [
        {{
            "id": "researcher",
            "role": "researcher",
            "objective": "采集本月传感器异常数据",
            "inputs": {{"query": "本月传感器异常记录"}},
            "failure_mode": "retry",
            "depends_on": [],
            "quality_gate": ["anomalies 数量 >= 1"]
        }},
        {{
            "id": "analyst",
            "role": "analyst",
            "objective": "模式识别 + 异常归因",
            "inputs": {{"anomalies": "$researcher.anomalies"}},
            "failure_mode": "retry",
            "depends_on": ["researcher"],
            "quality_gate": ["root_causes 数量 >= 1"]
        }}
    ],
    "final_synthesis": {{
        "id": "writer",
        "role": "writer",
        "objective": "撰写根因报告 + 整改建议",
        "inputs": {{"anomalies": "$researcher.anomalies", "root_causes": "$analyst.root_causes"}},
        "depends_on": ["researcher", "analyst"]
    }},
    "global_budget": 20000,
    "timeout_seconds": 600
}}

不要输出任何解释,只输出 JSON。"""

    def _build_user_message(
        self,
        query: str,
        user_context: dict | None,
        previous_errors: str | None = None,
    ) -> str:
        """构造 user message"""
        parts = [f"用户查询: {query}"]

        if user_context:
            parts.append(f"用户上下文: {json.dumps(user_context, ensure_ascii=False)}")

        if previous_errors:
            parts.append(f"\n上一次尝试失败原因: {previous_errors}\n请仔细检查 JSON 格式,避免同样的错误。")

        return "\n".join(parts)

    def _parse_json(self, text: str) -> dict:
        """从 LLM 输出中解析 JSON

        支持:
        - 纯 JSON
        - Markdown 代码块包裹的 JSON
        - JSON 前后的额外文本(提取第一个 {} 块)

        Args:
            text: LLM 生成的文本

        Returns:
            解析后的 dict

        Raises:
            ValueError: 如果无法解析为 JSON
        """
        cleaned = text.strip()

        # 去除 markdown 代码块
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        # 尝试直接解析
        try:
            data = json.loads(cleaned)
            if isinstance(data, dict):
                return data
            raise ValueError(f"JSON 解析结果不是 dict,而是 {type(data).__name__}")
        except json.JSONDecodeError:
            pass

        # 尝试提取第一个 {} 块
        match = re.search(r"\{[\s\S]*\}", cleaned)
        if match:
            try:
                data = json.loads(match.group(0))
                if isinstance(data, dict):
                    return data
            except json.JSONDecodeError:
                pass

        raise ValueError(f"无法从 LLM 输出中解析 JSON:\n{text[:200]}...")
