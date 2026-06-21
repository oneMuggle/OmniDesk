"""TaskPacket 任务包定义

定义多 Agent 协作中的结构化任务:
- ExecutionMode: 执行模式(顺序 / 并行 / 层级)
- FailureMode: 失败处理策略
- SubTask: 单个子任务
- TaskPacket: 完整任务包(含多个 subtask)
- TaskPacketValidator: JSON Schema 校验(验证 Supervisor 生成的 JSON)

Supervisor LLM 生成的 JSON 经过 TaskPacketValidator 校验后,
通过 TaskPacket.from_dict() 构造 TaskPacket 实例。
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .roles import AgentRole, get_role_by_name


# ---------------------------------------------------------------------------
# 枚举
# ---------------------------------------------------------------------------


class ExecutionMode(str, Enum):  # noqa: UP042
    """任务执行模式"""

    PIPELINE = "pipeline"  # 顺序执行(前一个输出是后一个输入)
    FANOUT = "fanout"  # 并行执行(多个 subtask 同时进行)
    HIERARCHICAL = "hierarchical"  # 层级执行(Supervisor 动态调度)


class FailureMode(str, Enum):  # noqa: UP042
    """子任务失败处理策略"""

    SKIP = "skip"  # 失败跳过,继续下一步
    RETRY = "retry"  # 失败重试(最多 3 次)
    FALLBACK = "fallback"  # 失败用兜底方案
    ABORT = "abort"  # 失败终止整个任务


# ---------------------------------------------------------------------------
# SubTask 数据类
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SubTask:
    """子任务定义

    Attributes:
        id: 唯一标识(在 TaskPacket 内唯一,用于依赖引用)
        role: 执行角色(AgentRole 枚举)
        objective: 子任务目标(自然语言描述)
        inputs: 输入参数,支持 `$subtask_id.field` 形式的引用
                例: {"query": "$research.summary"} 表示引用 research 子任务的 summary 字段
        failure_mode: 失败处理策略
        depends_on: 依赖的子任务 ID 列表(必须先执行)
        quality_gate: 质量检查点(自然语言列表,由 Reviewer 验证)
    """

    id: str
    role: AgentRole
    objective: str
    inputs: dict[str, Any] = field(default_factory=dict)
    failure_mode: FailureMode = FailureMode.RETRY
    depends_on: list[str] = field(default_factory=list)
    quality_gate: list[str] = field(default_factory=list)

    def __post_init__(self):
        """验证字段合法性(frozen dataclass 的 post_init 在 __new__ 后调用)"""
        # id 必须是非空字符串
        if not self.id or not isinstance(self.id, str):
            raise ValueError(f"SubTask.id 必须是非空字符串,收到 {self.id!r}")

        # id 必须是合法的标识符(字母/数字/下划线/短横线)
        if not re.match(r"^[a-zA-Z0-9_-]+$", self.id):
            raise ValueError(
                f"SubTask.id 只能包含字母/数字/下划线/短横线,收到 {self.id!r}"
            )

        # role 必须是 AgentRole 枚举
        if not isinstance(self.role, AgentRole):
            raise ValueError(f"SubTask.role 必须是 AgentRole 枚举,收到 {self.role!r}")

        # objective 必须是非空字符串
        if not self.objective or not isinstance(self.objective, str):
            raise ValueError(
                f"SubTask.objective 必须是非空字符串,收到 {self.objective!r}"
            )

        # inputs 必须是 dict
        if not isinstance(self.inputs, dict):
            raise ValueError(f"SubTask.inputs 必须是 dict,收到 {type(self.inputs)}")

        # failure_mode 必须是 FailureMode 枚举
        if not isinstance(self.failure_mode, FailureMode):
            raise ValueError(
                f"SubTask.failure_mode 必须是 FailureMode 枚举,收到 {self.failure_mode!r}"
            )

        # depends_on 必须是 list[str]
        if not isinstance(self.depends_on, list):
            raise ValueError(
                f"SubTask.depends_on 必须是 list,收到 {type(self.depends_on)}"
            )
        for dep in self.depends_on:
            if not isinstance(dep, str):
                raise ValueError(
                    f"SubTask.depends_on 元素必须是字符串,收到 {type(dep)}"
                )

        # quality_gate 必须是 list[str]
        if not isinstance(self.quality_gate, list):
            raise ValueError(
                f"SubTask.quality_gate 必须是 list,收到 {type(self.quality_gate)}"
            )
        for criterion in self.quality_gate:
            if not isinstance(criterion, str):
                raise ValueError(
                    f"SubTask.quality_gate 元素必须是字符串,收到 {type(criterion)}"
                )


# ---------------------------------------------------------------------------
# TaskPacket 数据类
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TaskPacket:
    """任务包定义

    由 Supervisor LLM 生成,经过 TaskPacketValidator 校验后构造。
    多 Agent 执行器(MultiAgentExecutor)根据 TaskPacket 驱动任务执行。

    Attributes:
        task_id: 任务唯一 ID(自动生成 UUID)
        objective: 总目标(用户原始查询或 Supervisor 提炼)
        execution_mode: 执行模式
        subtasks: 子任务列表
        final_synthesis: 最终合成步骤(可选,用于合并所有产物)
        user_context: 用户上下文(部门/角色/权限等)
        global_budget: 全局 Token 预算
        timeout_seconds: 全局超时时间(秒)
    """

    task_id: str
    objective: str
    execution_mode: ExecutionMode
    subtasks: list[SubTask]
    final_synthesis: SubTask | None = None
    user_context: dict = field(default_factory=dict)
    global_budget: int = 20000
    timeout_seconds: int = 600

    def __post_init__(self):
        """验证字段合法性 + 内部一致性"""
        # 基础字段校验
        if not self.task_id or not isinstance(self.task_id, str):
            raise ValueError("TaskPacket.task_id 必须是非空字符串")
        if not self.objective or not isinstance(self.objective, str):
            raise ValueError("TaskPacket.objective 必须是非空字符串")
        if not isinstance(self.execution_mode, ExecutionMode):
            raise ValueError("TaskPacket.execution_mode 必须是 ExecutionMode 枚举")
        if not isinstance(self.subtasks, list) or len(self.subtasks) == 0:
            raise ValueError("TaskPacket.subtasks 必须是非空 list")
        if not isinstance(self.global_budget, int) or self.global_budget <= 0:
            raise ValueError("TaskPacket.global_budget 必须是正整数")
        if not isinstance(self.timeout_seconds, int) or self.timeout_seconds <= 0:
            raise ValueError("TaskPacket.timeout_seconds 必须是正整数")

        # 内部一致性校验
        subtask_ids = {st.id for st in self.subtasks}

        # subtask id 必须唯一
        if len(subtask_ids) != len(self.subtasks):
            raise ValueError("TaskPacket.subtasks 中存在重复的 id")

        # depends_on 引用的 id 必须存在
        for st in self.subtasks:
            for dep_id in st.depends_on:
                if dep_id not in subtask_ids:
                    raise ValueError(
                        f"SubTask '{st.id}' 的 depends_on 引用了不存在的 id '{dep_id}'"
                    )
            # 不能依赖自己
            if st.id in st.depends_on:
                raise ValueError(f"SubTask '{st.id}' 不能依赖自己")

        # 检测循环依赖(简单 DFS)
        self._check_circular_dependencies()

        # final_synthesis 校验(如果存在)
        if self.final_synthesis is not None and not isinstance(self.final_synthesis, SubTask):
            raise ValueError("TaskPacket.final_synthesis 必须是 SubTask 或 None")

    def _check_circular_dependencies(self) -> None:
        """检测循环依赖(DFS)"""
        visited: set[str] = set()
        rec_stack: set[str] = set()

        def dfs(node_id: str) -> bool:
            visited.add(node_id)
            rec_stack.add(node_id)

            current = next((st for st in self.subtasks if st.id == node_id), None)
            if current is None:
                rec_stack.remove(node_id)
                return False

            for dep_id in current.depends_on:
                if dep_id not in visited:
                    if dfs(dep_id):
                        return True
                elif dep_id in rec_stack:
                    return True  # 发现环

            rec_stack.remove(node_id)
            return False

        for st in self.subtasks:
            if st.id not in visited:
                if dfs(st.id):
                    raise ValueError(
                        f"TaskPacket.subtasks 中存在循环依赖,涉及节点 '{st.id}'"
                    )

    def get_subtask(self, subtask_id: str) -> SubTask | None:
        """根据 ID 获取子任务"""
        for st in self.subtasks:
            if st.id == subtask_id:
                return st
        return None

    def get_execution_order(self) -> list[SubTask]:
        """获取拓扑排序后的执行顺序(仅对 PIPELINE 模式有效)

        Returns:
            按依赖关系排序的 SubTask 列表

        Raises:
            ValueError: 如果无法完成拓扑排序
        """
        in_degree: dict[str, int] = {st.id: 0 for st in self.subtasks}
        adjacency: dict[str, list[str]] = {st.id: [] for st in self.subtasks}

        for st in self.subtasks:
            for dep_id in st.depends_on:
                adjacency[dep_id].append(st.id)
                in_degree[st.id] += 1

        # Kahn 算法
        queue = sorted([sid for sid, deg in in_degree.items() if deg == 0])
        order: list[str] = []

        while queue:
            node_id = queue.pop(0)
            order.append(node_id)
            for neighbor in sorted(adjacency[node_id]):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
            queue.sort()  # 保证确定性

        if len(order) != len(self.subtasks):
            raise ValueError("无法拓扑排序,可能存在循环依赖")

        return [self.get_subtask(sid) for sid in order]  # type: ignore[return-value]

    @classmethod
    def from_dict(
        cls,
        data: dict,
        task_id: str | None = None,
    ) -> TaskPacket:
        """从 dict 构造 TaskPacket(由 Supervisor LLM 生成的 JSON 反序列化)

        Args:
            data: Supervisor 生成的 dict,结构见 TaskPacketValidator
            task_id: 可选的 task_id(不指定则自动生成 UUID)

        Returns:
            TaskPacket 实例

        Raises:
            ValueError: 如果 data 结构不合法或缺少必需字段
        """
        if not isinstance(data, dict):
            raise ValueError(f"data 必须是 dict,收到 {type(data)}")

        # 提取必需字段
        try:
            objective = data["objective"]
            execution_mode = ExecutionMode(data["execution_mode"])
            subtasks_data = data["subtasks"]
        except KeyError as e:
            raise ValueError(f"data 缺少必需字段: {e}")
        except ValueError as e:
            raise ValueError(f"data 字段值不合法: {e}")

        # 解析 subtasks
        subtasks = []
        for i, st_data in enumerate(subtasks_data):
            if not isinstance(st_data, dict):
                raise ValueError(f"subtasks[{i}] 必须是 dict")

            # 解析 role(支持字符串或 AgentRole 枚举)
            role_raw = st_data.get("role")
            if isinstance(role_raw, str):
                role = get_role_by_name(role_raw)
                if role is None:
                    raise ValueError(
                        f"subtasks[{i}].role='{role_raw}' 不是合法的 AgentRole"
                    )
            elif isinstance(role_raw, AgentRole):
                role = role_raw
            else:
                raise ValueError(
                    f"subtasks[{i}].role 必须是字符串或 AgentRole,收到 {type(role_raw)}"
                )

            # 解析 failure_mode
            failure_mode_raw = st_data.get("failure_mode", "retry")
            try:
                failure_mode = FailureMode(failure_mode_raw)
            except ValueError:
                raise ValueError(
                    f"subtasks[{i}].failure_mode='{failure_mode_raw}' 不是合法的 FailureMode"
                )

            subtask = SubTask(
                id=st_data["id"],
                role=role,
                objective=st_data["objective"],
                inputs=st_data.get("inputs", {}),
                failure_mode=failure_mode,
                depends_on=st_data.get("depends_on", []),
                quality_gate=st_data.get("quality_gate", []),
            )
            subtasks.append(subtask)

        # 解析 final_synthesis(可选)
        final_synthesis_data = data.get("final_synthesis")
        final_synthesis = None
        if final_synthesis_data is not None:
            if not isinstance(final_synthesis_data, dict):
                raise ValueError("final_synthesis 必须是 dict 或 None")
            role_raw = final_synthesis_data.get("role")
            if isinstance(role_raw, str):
                role = get_role_by_name(role_raw)
                if role is None:
                    raise ValueError(
                        f"final_synthesis.role='{role_raw}' 不是合法的 AgentRole"
                    )
            elif isinstance(role_raw, AgentRole):
                role = role_raw
            else:
                raise ValueError("final_synthesis.role 必须是字符串或 AgentRole")
            final_synthesis = SubTask(
                id=final_synthesis_data.get("id", "final_synthesis"),
                role=role,
                objective=final_synthesis_data["objective"],
                inputs=final_synthesis_data.get("inputs", {}),
                failure_mode=FailureMode(
                    final_synthesis_data.get("failure_mode", "retry")
                ),
                depends_on=final_synthesis_data.get("depends_on", []),
                quality_gate=final_synthesis_data.get("quality_gate", []),
            )

        return cls(
            task_id=task_id or data.get("task_id") or uuid.uuid4().hex,
            objective=objective,
            execution_mode=execution_mode,
            subtasks=subtasks,
            final_synthesis=final_synthesis,
            user_context=data.get("user_context", {}),
            global_budget=data.get("global_budget", 20000),
            timeout_seconds=data.get("timeout_seconds", 600),
        )

    def to_dict(self) -> dict:
        """序列化为 dict(用于存储到数据库 task_packet 字段)"""
        return {
            "task_id": self.task_id,
            "objective": self.objective,
            "execution_mode": self.execution_mode.value,
            "subtasks": [
                {
                    "id": st.id,
                    "role": st.role.value,
                    "objective": st.objective,
                    "inputs": st.inputs,
                    "failure_mode": st.failure_mode.value,
                    "depends_on": st.depends_on,
                    "quality_gate": st.quality_gate,
                }
                for st in self.subtasks
            ],
            "final_synthesis": {
                "id": self.final_synthesis.id,
                "role": self.final_synthesis.role.value,
                "objective": self.final_synthesis.objective,
                "inputs": self.final_synthesis.inputs,
                "failure_mode": self.final_synthesis.failure_mode.value,
                "depends_on": self.final_synthesis.depends_on,
                "quality_gate": self.final_synthesis.quality_gate,
            } if self.final_synthesis else None,
            "user_context": self.user_context,
            "global_budget": self.global_budget,
            "timeout_seconds": self.timeout_seconds,
        }


# ---------------------------------------------------------------------------
# TaskPacket 校验器(给 Supervisor LLM 输出用)
# ---------------------------------------------------------------------------


class TaskPacketValidator:
    """TaskPacket JSON Schema 校验器

    Supervisor LLM 生成的 JSON 先经过此校验器校验,
    通过后才能用 TaskPacket.from_dict() 构造实例。

    Example:
        validator = TaskPacketValidator()
        errors = validator.validate(supervisor_output)
        if errors:
            # 让 Supervisor 重新生成
            ...
        else:
            task_packet = TaskPacket.from_dict(supervisor_output)
    """

    # 简化的 JSON Schema(给 Supervisor 参考,不强制依赖 jsonschema 库)
    SCHEMA = {
        "type": "object",
        "required": ["objective", "execution_mode", "subtasks"],
        "properties": {
            "objective": {"type": "string", "minLength": 1},
            "execution_mode": {"enum": ["pipeline", "fanout", "hierarchical"]},
            "subtasks": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "required": ["id", "role", "objective"],
                    "properties": {
                        "id": {"type": "string", "pattern": "^[a-zA-Z0-9_-]+$"},
                        "role": {"type": "string"},
                        "objective": {"type": "string", "minLength": 1},
                        "inputs": {"type": "object"},
                        "failure_mode": {
                            "enum": ["skip", "retry", "fallback", "abort"]
                        },
                        "depends_on": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "quality_gate": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                },
            },
            "final_synthesis": {
                "type": ["object", "null"],
                "required": ["id", "role", "objective"],
            },
            "user_context": {"type": "object"},
            "global_budget": {"type": "integer", "minimum": 1},
            "timeout_seconds": {"type": "integer", "minimum": 1},
        },
    }

    def validate(self, data: Any) -> list[str]:
        """校验 Supervisor 生成的 dict

        Args:
            data: Supervisor 生成的 dict

        Returns:
            错误消息列表(空列表表示校验通过)
        """
        errors: list[str] = []

        # 基础类型检查
        if not isinstance(data, dict):
            return [f"data 必须是 dict,收到 {type(data).__name__}"]

        # 必需字段检查
        for required_field in ["objective", "execution_mode", "subtasks"]:
            if required_field not in data:
                errors.append(f"缺少必需字段: {required_field}")

        if errors:
            return errors  # 缺少必需字段,直接返回

        # objective 检查
        if not isinstance(data["objective"], str) or not data["objective"].strip():
            errors.append("objective 必须是非空字符串")

        # execution_mode 检查
        valid_modes = {"pipeline", "fanout", "hierarchical"}
        if data["execution_mode"] not in valid_modes:
            errors.append(
                f"execution_mode 必须是 {valid_modes} 之一,收到 {data['execution_mode']!r}"
            )

        # subtasks 检查
        if not isinstance(data["subtasks"], list) or len(data["subtasks"]) == 0:
            errors.append("subtasks 必须是非空数组")
            return errors

        subtask_ids: set[str] = set()
        for i, st_data in enumerate(data["subtasks"]):
            if not isinstance(st_data, dict):
                errors.append(f"subtasks[{i}] 必须是对象")
                continue

            # 必需字段
            for required_field in ["id", "role", "objective"]:
                if required_field not in st_data:
                    errors.append(f"subtasks[{i}] 缺少必需字段: {required_field}")

            if "id" in st_data:
                st_id = st_data["id"]
                if not isinstance(st_id, str) or not re.match(
                    r"^[a-zA-Z0-9_-]+$", st_id
                ):
                    errors.append(
                        f"subtasks[{i}].id 必须是合法标识符(字母/数字/下划线/短横线)"
                    )
                elif st_id in subtask_ids:
                    errors.append(f"subtasks[{i}].id='{st_id}' 重复")
                else:
                    subtask_ids.add(st_id)

            if "role" in st_data:
                role_name = get_role_by_name(st_data["role"])
                if role_name is None:
                    errors.append(
                        f"subtasks[{i}].role='{st_data['role']}' 不是合法的 AgentRole"
                    )

            if "failure_mode" in st_data:
                if st_data["failure_mode"] not in {
                    "skip", "retry", "fallback", "abort"
                }:
                    errors.append(
                        f"subtasks[{i}].failure_mode='{st_data['failure_mode']}' 不合法"
                    )

            if "depends_on" in st_data:
                if not isinstance(st_data["depends_on"], list):
                    errors.append(f"subtasks[{i}].depends_on 必须是数组")

        # depends_on 引用检查
        for i, st_data in enumerate(data["subtasks"]):
            if not isinstance(st_data, dict):
                continue
            for dep_id in st_data.get("depends_on", []):
                if dep_id not in subtask_ids:
                    errors.append(
                        f"subtasks[{i}].depends_on 引用了不存在的 id '{dep_id}'"
                    )

        return errors
