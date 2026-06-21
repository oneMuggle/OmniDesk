"""SharedContext 跨 Agent 共享上下文

解决多 Agent 协作中的"信息孤岛"问题:
- 每个 Worker 能看到它**需要**的前置产物(通过 `to_context_for()` 构造精简上下文)
- 支持 `$subtask_id.field` 形式的变量引用(通过 `resolve_references()` 解析)
- 记录决策历史(`decisions`),避免后续 Agent 重复决策
- 记录错误历史(`error_log`),供 Supervisor 学习
- 追踪 Token 预算消耗(`token_budget_used` / `global_budget`)

Example:
    ctx = SharedContext(original_query="调研 RAG 并写报告")
    ctx.add_artifact("research", {"summary": "RAG 是...", "references": [...]})
    ctx.add_artifact("analysis", {"trends": ["趋势1", "趋势2"]})

    # 为 writer subtask 构造上下文
    writer_subtask = SubTask(
        id="writer",
        role=AgentRole.WRITER,
        objective="撰写报告",
        inputs={"summary": "$research.summary", "trends": "$analysis.trends"},
        depends_on=["research", "analysis"],
    )
    messages = ctx.to_context_for(writer_subtask)
    # messages 中包含:
    # {"role": "user", "content": "[前置任务 research 的 summary 字段]\\nRAG 是..."}
    # {"role": "user", "content": "[前置任务 analysis 的 trends 字段]\\n['趋势1', '趋势2']"}
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .task_packet import SubTask


# ---------------------------------------------------------------------------
# 辅助数据类
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Decision:
    """决策记录(避免后续 Agent 重复决策)

    Attributes:
        made_by: 决策者(subtask ID 或 'supervisor' 或 'user')
        decision: 决策内容(自然语言)
        rationale: 决策理由
        timestamp: 决策时间
    """

    made_by: str
    decision: str
    rationale: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass(frozen=True)
class ErrorRecord:
    """错误记录(供 Supervisor 学习)

    Attributes:
        subtask_id: 发生错误的 subtask ID
        error_type: 错误类型(异常类名)
        error_message: 错误消息
        recovery_action: 采取的恢复动作
        timestamp: 错误发生时间
    """

    subtask_id: str
    error_type: str
    error_message: str
    recovery_action: str
    timestamp: datetime = field(default_factory=datetime.now)


# ---------------------------------------------------------------------------
# SharedContext 主类
# ---------------------------------------------------------------------------


class SharedContext:
    """跨 Agent 的共享上下文

    在多 Agent 协作过程中,每个 Worker 通过 SharedContext 访问前置产物、
    记录决策、记录错误、追踪 Token 消耗。

    Attributes:
        original_query: 用户原始查询
        user_context: 用户上下文(部门/角色/权限等)
        artifacts: subtask_id → 产物(每个 subtask 的输出)
        decisions: 已做出的决策列表
        error_log: 错误记录列表
        token_budget_used: 已消耗的 Token 数
        global_budget: 全局 Token 预算
    """

    # 变量引用正则:匹配 $subtask_id 或 $subtask_id.field1.field2
    REFERENCE_PATTERN = re.compile(r"\$([a-zA-Z0-9_-]+(?:\.[a-zA-Z0-9_-]+)*)")

    def __init__(
        self,
        original_query: str,
        user_context: dict | None = None,
        global_budget: int = 20000,
    ):
        self.original_query = original_query
        self.user_context = user_context or {}
        self.artifacts: dict[str, dict] = {}
        self.decisions: list[Decision] = []
        self.error_log: list[ErrorRecord] = []
        self.token_budget_used: int = 0
        self.global_budget: int = global_budget

    # ------------------------------------------------------------------
    # Artifact 管理
    # ------------------------------------------------------------------

    def add_artifact(self, subtask_id: str, artifact: dict) -> None:
        """添加 subtask 产物

        Args:
            subtask_id: subtask 的 ID
            artifact: subtask 的输出(必须是 dict)

        Raises:
            ValueError: 如果 artifact 不是 dict
        """
        if not isinstance(artifact, dict):
            raise ValueError(
                f"artifact 必须是 dict,收到 {type(artifact).__name__}"
            )
        self.artifacts[subtask_id] = artifact

    def get_artifact(self, subtask_id: str) -> dict | None:
        """获取 subtask 产物

        Args:
            subtask_id: subtask 的 ID

        Returns:
            产物 dict,如果不存在返回 None
        """
        return self.artifacts.get(subtask_id)

    def has_artifact(self, subtask_id: str) -> bool:
        """检查是否存在指定 subtask 的产物"""
        return subtask_id in self.artifacts

    # ------------------------------------------------------------------
    # 决策与错误记录
    # ------------------------------------------------------------------

    def record_decision(
        self,
        made_by: str,
        decision: str,
        rationale: str = "",
    ) -> Decision:
        """记录一个决策

        Args:
            made_by: 决策者(subtask ID / 'supervisor' / 'user')
            decision: 决策内容
            rationale: 决策理由(可选)

        Returns:
            创建的 Decision 实例
        """
        decision_obj = Decision(
            made_by=made_by,
            decision=decision,
            rationale=rationale,
        )
        self.decisions.append(decision_obj)
        return decision_obj

    def record_error(
        self,
        subtask_id: str,
        error: Exception,
        recovery_action: str = "none",
    ) -> ErrorRecord:
        """记录一个错误

        Args:
            subtask_id: 发生错误的 subtask ID
            error: 抛出的异常
            recovery_action: 采取的恢复动作描述

        Returns:
            创建的 ErrorRecord 实例
        """
        error_record = ErrorRecord(
            subtask_id=subtask_id,
            error_type=type(error).__name__,
            error_message=str(error),
            recovery_action=recovery_action,
        )
        self.error_log.append(error_record)
        return error_record

    # ------------------------------------------------------------------
    # Token 预算追踪
    # ------------------------------------------------------------------

    def consume_tokens(self, count: int) -> None:
        """记录 Token 消耗

        Args:
            count: 消耗的 Token 数(正整数)
        """
        if count < 0:
            raise ValueError(f"Token 消耗数不能为负,收到 {count}")
        self.token_budget_used += count

    def remaining_budget(self) -> int:
        """返回剩余 Token 预算"""
        return max(0, self.global_budget - self.token_budget_used)

    def is_budget_exhausted(self) -> bool:
        """检查 Token 预算是否已耗尽"""
        return self.token_budget_used >= self.global_budget

    # ------------------------------------------------------------------
    # 变量引用解析
    # ------------------------------------------------------------------

    def resolve_references(self, template: Any) -> Any:
        """解析 `$subtask_id.field` 形式的变量引用

        支持的格式:
        - 字符串中的引用: `"Summary: $research.summary"` → `"Summary: RAG 是..."`
        - dict 中的引用: `{"query": "$research.summary"}` → `{"query": "RAG 是..."}`
        - list 中的引用: `["$research.summary"]` → `["RAG 是..."]`
        - 嵌套引用: `"$research.metadata.author"` → 从 artifact 中取嵌套字段
        - 直接引用 subtask 整体: `"$research"` → 整个 artifact dict
        - 非字符串类型原样返回:int / float / bool / None 不解析

        Args:
            template: 待解析的模板(可以是 str / dict / list / 其他类型)

        Returns:
            解析后的值

        Raises:
            KeyError: 如果引用的 subtask_id 不存在
            KeyError: 如果引用的 field 不存在
        """
        if isinstance(template, str):
            return self._resolve_string_reference(template)
        elif isinstance(template, dict):
            return {k: self.resolve_references(v) for k, v in template.items()}
        elif isinstance(template, list):
            return [self.resolve_references(item) for item in template]
        else:
            # int / float / bool / None 等原样返回
            return template

    def _resolve_string_reference(self, text: str) -> Any:
        """解析字符串中的变量引用

        如果整个字符串就是单个引用(如 "$research.summary"),返回引用值的原始类型(dict/list/...)。
        如果字符串包含多个引用或引用嵌入在文本中(如 "Summary: $research.summary"),返回字符串。
        """
        # 检查是否整个字符串就是单个引用
        match = re.fullmatch(r"\$([a-zA-Z0-9_-]+(?:\.[a-zA-Z0-9_-]+)*)", text)
        if match:
            # 整个字符串就是单个引用,返回原始类型
            return self._resolve_single_reference(match.group(1))

        # 否则,替换所有引用为字符串形式
        def replace_ref(m: re.Match) -> str:
            ref_path = m.group(1)
            try:
                value = self._resolve_single_reference(ref_path)
                # 转换为字符串表示
                if isinstance(value, (dict, list)):
                    return json.dumps(value, ensure_ascii=False)
                return str(value)
            except KeyError as e:
                return f"[未找到:{e}]"

        return self.REFERENCE_PATTERN.sub(replace_ref, text)

    def _resolve_single_reference(self, ref_path: str) -> Any:
        """解析单个引用路径

        Args:
            ref_path: 引用路径,如 "research.summary" 或 "research"

        Returns:
            解析后的值

        Raises:
            KeyError: 如果路径无效
        """
        parts = ref_path.split(".")
        subtask_id = parts[0]

        if subtask_id not in self.artifacts:
            raise KeyError(f"subtask_id '{subtask_id}' 的产物不存在")

        value: Any = self.artifacts[subtask_id]

        # 遍历嵌套字段
        for field_name in parts[1:]:
            if isinstance(value, dict):
                if field_name not in value:
                    raise KeyError(
                        f"subtask '{subtask_id}' 的产物中不存在字段 '{field_name}'"
                    )
                value = value[field_name]
            else:
                raise KeyError(
                    f"引用路径 '{ref_path}' 无效:中间值不是 dict"
                )

        return value

    # ------------------------------------------------------------------
    # 上下文构造
    # ------------------------------------------------------------------

    def to_context_for(self, subtask: SubTask) -> list[dict]:
        """为指定 subtask 构造上下文(messages 列表)

        构造逻辑:
        1. 用户消息:subtask 的 objective
        2. 为每个依赖 subtask 注入其产物(按 subtask.inputs 解析)
        3. 注入最近 5 条决策历史(让 subtask 知道已做出的决策)

        Args:
            subtask: 目标 subtask

        Returns:
            messages 列表(给 LLM 调用用)
        """
        messages: list[dict] = [
            {"role": "user", "content": subtask.objective},
        ]

        # 注入依赖 subtask 的产物
        for dep_id in subtask.depends_on:
            if dep_id not in self.artifacts:
                messages.append({
                    "role": "user",
                    "content": f"[前置任务 {dep_id} 未产出结果]",
                })
                continue

            # 如果 subtask.inputs 指定了具体字段,只注入这些字段
            if subtask.inputs:
                for key, value_template in subtask.inputs.items():
                    if isinstance(value_template, str) and value_template.startswith("$"):
                        # 解析引用
                        try:
                            resolved = self.resolve_references(value_template)
                            if isinstance(resolved, (dict, list)):
                                content = json.dumps(
                                    resolved, ensure_ascii=False, indent=2
                                )
                            else:
                                content = str(resolved)
                            messages.append({
                                "role": "user",
                                "content": (
                                    f"[前置任务 {dep_id} 的 {key} 字段]\n{content}"
                                ),
                            })
                        except KeyError as e:
                            messages.append({
                                "role": "user",
                                "content": (
                                    f"[前置任务 {dep_id} 的 {key} 字段解析失败: {e}]"
                                ),
                            })
                    else:
                        # 非引用,直接使用
                        messages.append({
                            "role": "user",
                            "content": f"[{key}]\n{value_template}",
                        })
            else:
                # 没指定 inputs,注入整个 artifact
                artifact = self.artifacts[dep_id]
                content = json.dumps(artifact, ensure_ascii=False, indent=2)
                messages.append({
                    "role": "user",
                    "content": f"[前置任务 {dep_id} 的完整产出]\n{content}",
                })

        # 注入决策历史(让 subtask 知道已做出的决策)
        if self.decisions:
            decisions_text = "\n".join(
                f"- [{d.made_by}] {d.decision}: {d.rationale}"
                for d in self.decisions[-5:]  # 只注入最近 5 条
            )
            messages.append({
                "role": "user",
                "content": f"[已做出的决策]\n{decisions_text}",
            })

        return messages

    # ------------------------------------------------------------------
    # 序列化(用于调试)
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        """序列化为 dict(用于调试和日志)"""
        return {
            "original_query": self.original_query,
            "user_context": self.user_context,
            "artifacts": self.artifacts,
            "decisions": [
                {
                    "made_by": d.made_by,
                    "decision": d.decision,
                    "rationale": d.rationale,
                    "timestamp": d.timestamp.isoformat(),
                }
                for d in self.decisions
            ],
            "error_log": [
                {
                    "subtask_id": e.subtask_id,
                    "error_type": e.error_type,
                    "error_message": e.error_message,
                    "recovery_action": e.recovery_action,
                    "timestamp": e.timestamp.isoformat(),
                }
                for e in self.error_log
            ],
            "token_budget_used": self.token_budget_used,
            "global_budget": self.global_budget,
            "remaining_budget": self.remaining_budget(),
        }
