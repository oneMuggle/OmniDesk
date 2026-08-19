"""TaskPacket JSON Schema 校验器

定义 Supervisor LLM 输出 JSON 的结构校验:
- SCHEMA: 简化的 JSON Schema(给 Supervisor 参考)
- TaskPacketValidator: 校验器,返回错误消息列表

Supervisor LLM 生成的 JSON 先经过 TaskPacketValidator 校验,
通过后才能用 TaskPacket.from_dict() 构造实例。
"""

from __future__ import annotations

import re
from typing import Any

from .roles import get_role_by_name


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
                        "failure_mode": {"enum": ["skip", "retry", "fallback", "abort"]},
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

        # 必需字段检查(缺少则直接返回)
        if self._check_required_fields(data, errors):
            return errors

        # objective 检查
        self._check_objective(data, errors)

        # execution_mode 检查
        self._check_execution_mode(data, errors)

        # subtasks 检查(非法则直接返回,跳过 depends_on 引用检查)
        if self._check_subtasks(data, errors):
            return errors

        # subtask 逐项检查(收集合法 id,供 depends_on 引用检查)
        subtask_ids = self._check_subtask_items(data, errors)

        # depends_on 引用检查
        self._check_depends_on_refs(data, subtask_ids, errors)

        return errors

    # ------------------------------------------------------------------
    # 校验辅助方法
    # ------------------------------------------------------------------

    def _check_required_fields(self, data: dict, errors: list[str]) -> bool:
        """检查顶层必需字段,返回是否存在缺失"""
        missing = False
        for required_field in ["objective", "execution_mode", "subtasks"]:
            if required_field not in data:
                errors.append(f"缺少必需字段: {required_field}")
                missing = True
        return missing

    def _check_objective(self, data: dict, errors: list[str]) -> None:
        """校验 objective 必须是非空字符串"""
        if not isinstance(data["objective"], str) or not data["objective"].strip():
            errors.append("objective 必须是非空字符串")

    def _check_execution_mode(self, data: dict, errors: list[str]) -> None:
        """校验 execution_mode 必须是合法枚举值"""
        valid_modes = {"pipeline", "fanout", "hierarchical"}
        if data["execution_mode"] not in valid_modes:
            errors.append(f"execution_mode 必须是 {valid_modes} 之一,收到 {data['execution_mode']!r}")

    def _check_subtasks(self, data: dict, errors: list[str]) -> bool:
        """校验 subtasks 必须是非空数组,返回是否非法"""
        if not isinstance(data["subtasks"], list) or len(data["subtasks"]) == 0:
            errors.append("subtasks 必须是非空数组")
            return True
        return False

    def _check_subtask_items(self, data: dict, errors: list[str]) -> set[str]:
        """逐项校验 subtask,返回收集到的合法 id 集合"""
        subtask_ids: set[str] = set()
        for index, st_data in enumerate(data["subtasks"]):
            self._check_subtask_item(st_data, index, subtask_ids, errors)
        return subtask_ids

    def _check_subtask_item(
        self,
        st_data: Any,
        index: int,
        subtask_ids: set[str],
        errors: list[str],
    ) -> None:
        """校验单个 subtask dict"""
        if not isinstance(st_data, dict):
            errors.append(f"subtasks[{index}] 必须是对象")
            return

        self._check_subtask_required_fields(st_data, index, errors)
        self._check_subtask_id(st_data, index, subtask_ids, errors)
        self._check_subtask_role(st_data, index, errors)
        self._check_subtask_failure_mode(st_data, index, errors)
        self._check_subtask_depends_on(st_data, index, errors)

    def _check_subtask_required_fields(
        self,
        st_data: dict,
        index: int,
        errors: list[str],
    ) -> None:
        """检查 subtask 必需字段(id / role / objective)"""
        for required_field in ["id", "role", "objective"]:
            if required_field not in st_data:
                errors.append(f"subtasks[{index}] 缺少必需字段: {required_field}")

    def _check_subtask_id(
        self,
        st_data: dict,
        index: int,
        subtask_ids: set[str],
        errors: list[str],
    ) -> None:
        """校验 subtask id 合法性 + 唯一性"""
        if "id" not in st_data:
            return
        st_id = st_data["id"]
        if not isinstance(st_id, str) or not re.match(r"^[a-zA-Z0-9_-]+$", st_id):
            errors.append(f"subtasks[{index}].id 必须是合法标识符(字母/数字/下划线/短横线)")
        elif st_id in subtask_ids:
            errors.append(f"subtasks[{index}].id='{st_id}' 重复")
        else:
            subtask_ids.add(st_id)

    def _check_subtask_role(
        self,
        st_data: dict,
        index: int,
        errors: list[str],
    ) -> None:
        """校验 subtask role 必须是合法的 AgentRole"""
        if "role" not in st_data:
            return
        if get_role_by_name(st_data["role"]) is None:
            errors.append(f"subtasks[{index}].role='{st_data['role']}' 不是合法的 AgentRole")

    def _check_subtask_failure_mode(
        self,
        st_data: dict,
        index: int,
        errors: list[str],
    ) -> None:
        """校验 subtask failure_mode 必须是合法枚举值"""
        if "failure_mode" not in st_data:
            return
        if st_data["failure_mode"] not in {"skip", "retry", "fallback", "abort"}:
            errors.append(f"subtasks[{index}].failure_mode='{st_data['failure_mode']}' 不合法")

    def _check_subtask_depends_on(
        self,
        st_data: dict,
        index: int,
        errors: list[str],
    ) -> None:
        """校验 subtask depends_on 必须是数组"""
        if "depends_on" not in st_data:
            return
        if not isinstance(st_data["depends_on"], list):
            errors.append(f"subtasks[{index}].depends_on 必须是数组")

    def _check_depends_on_refs(
        self,
        data: dict,
        subtask_ids: set[str],
        errors: list[str],
    ) -> None:
        """检查 depends_on 引用的 id 必须存在"""
        for index, st_data in enumerate(data["subtasks"]):
            if not isinstance(st_data, dict):
                continue
            for dep_id in st_data.get("depends_on", []):
                if dep_id not in subtask_ids:
                    errors.append(f"subtasks[{index}].depends_on 引用了不存在的 id '{dep_id}'")
