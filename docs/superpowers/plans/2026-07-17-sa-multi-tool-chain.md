# Smart Assistant 多工具链 — 分支 2 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 升级智能助手的工具链编排能力,让 LLM 生成的 multi-tool plan 可序列化/反序列化、支持嵌套 `$variable` 引用、支持 `on_failure` 失败策略(skip/retry/fallback)、每步写 AgentLog;新增 3 个跨工具链场景 E2E 测试(排班→报告→公告 / 传感器→责任人→周报 / 合规→项目→风险评估),覆盖失败策略 3 种。

**Architecture:** 在现有 `agent/tool_chain_planner.py` 和 `agent/tool_chain_executor.py` 之上扩展,不替换原函数:
1. **`plan_serializer.py` 新增** — `Plan.to_dict()` / `Plan.from_dict()` / `ToolChainPlan` Django 模型(plan_id + steps JSON + status)。
2. **`ToolChainExecutor` 升级** — 嵌套 `$variable` 解析(`{{step1.output.users[0].id}}`)、失败策略字段处理、step-level AgentLog 写入。
3. **`tool_chain_planner.py` 升级** — LLM 输出 plan 改为 JSON schema(含 `on_failure` 字段),fallback 关键词匹配保留。
4. **3 个跨工具场景 E2E** — 走 plan → executor → 每步 AgentLog 验证。

**Tech Stack:** Django 4.2 + DRF,Python 3.10,pytest + pytest-django + pytest-mock,LLM mock via `mock_llm_router`。

---

## 全局约束

- 分支 1(`feat/sa-e2e-scenarios`)已合入 main 后才能切出本分支
- 测试覆盖率 ≥ 80%(分支 1 后基础 80.89%,本分支不能降低)
- 不替换现有 `execute_tool_chain` 函数(class 版 `ToolChainExecutor` 与之并存,逐步迁移)
- 中文 commit message,中文界面
- 离线部署、内网环境

---

## Task 0: 准备 feature 分支

**Files:** 无

- [ ] **Step 1: 切到最新 main,拉取分支 1**

```bash
cd /home/fz/project/OmniDesk
git switch main
git pull --rebase origin main
```

期望:`Already up to date.` 或成功 rebase(包含分支 1 的 commits)。

- [ ] **Step 2: 切出分支 2**

```bash
git switch -c feat/sa-multi-tool-chain
```

- [ ] **Step 3: 验证分支 1 的测试还在**

```bash
conda run -n omni_desk python -m pytest omni_desk_backend/smart_assistant/tests/test_cache.py omni_desk_backend/smart_assistant/tests/test_cache_stream_shortcut.py -v 2>&1 | tail -10
```

期望:`17 passed`(14 个 cache + 3 个 stream shortcut)。

- [ ] **Step 4: 跑全部 smart_assistant 测试,基线确认**

```bash
conda run -n omni_desk python -m pytest omni_desk_backend/smart_assistant/tests/ --no-header -q 2>&1 | tail -5
```

---

## Task 1: Plan 序列化模块

**Files:**
- New: `omni_desk_backend/smart_assistant/agent/plan_serializer.py`(整文件)
- Modify: `omni_desk_backend/smart_assistant/models.py`(追加 `ToolChainPlan`)
- New: `omni_desk_backend/smart_assistant/migrations/00XX_toolchainplan.py`(自动生成)
- New: `omni_desk_backend/smart_assistant/tests/test_plan_serializer.py`(整文件)

**Interfaces:**
- Consumes: 现有 `generate_tool_chain_plan()` 返回的 `list[dict]`
- Produces: `Plan.to_dict() / Plan.from_dict() / Plan.save() / Plan.load(plan_id)` + `ToolChainPlan` ORM 模型

### Step 1: 写失败的测试

创建 `omni_desk_backend/smart_assistant/tests/test_plan_serializer.py`:

```python
"""Plan 序列化测试 — multi-tool chain 可序列化到 DB、可从 DB 恢复。

Task 1 of feat/sa-multi-tool-chain: 让 plan 可持久化、可断点恢复。
"""
import json

import pytest

from omni_desk_backend.smart_assistant.agent.plan_serializer import (
    Plan,
    PlanStep,
    PlanValidationError,
)


class TestPlanStep:
    def test_step_to_dict_includes_all_fields(self):
        step = PlanStep(
            tool="schedule",
            params={"query": "张三这周值班"},
            on_failure="skip",
            retry_count=2,
        )
        d = step.to_dict()
        assert d == {
            "tool": "schedule",
            "params": {"query": "张三这周值班"},
            "on_failure": "skip",
            "retry_count": 2,
        }

    def test_step_from_dict_roundtrip(self):
        d = {
            "tool": "schedule",
            "params": {"query": "张三这周值班"},
            "on_failure": "skip",
            "retry_count": 2,
        }
        step = PlanStep.from_dict(d)
        assert step.tool == "schedule"
        assert step.params == {"query": "张三这周值班"}
        assert step.on_failure == "skip"
        assert step.retry_count == 2


class TestPlan:
    def test_plan_to_dict_serializes_steps(self):
        plan = Plan(steps=[
            PlanStep(tool="schedule", params={"query": "张三"}, on_failure="skip"),
            PlanStep(tool="memo", params={"title": "{{step1.output.summary}}"}, on_failure="retry"),
        ])
        d = plan.to_dict()
        assert "steps" in d
        assert len(d["steps"]) == 2
        assert d["steps"][1]["params"]["title"] == "{{step1.output.summary}}"

    def test_plan_from_dict_roundtrip(self):
        d = {
            "steps": [
                {"tool": "schedule", "params": {"query": "张三"}, "on_failure": "skip"},
                {"tool": "memo", "params": {"title": "x"}, "on_failure": "skip"},
            ]
        }
        plan = Plan.from_dict(d)
        assert len(plan.steps) == 2
        assert plan.steps[0].tool == "schedule"

    def test_plan_invalid_on_failure_raises(self):
        with pytest.raises(PlanValidationError) as exc:
            PlanStep.from_dict({"tool": "x", "params": {}, "on_failure": "invalid_value"})
        assert "on_failure" in str(exc.value)


@pytest.mark.django_db
class TestToolChainPlanModel:
    def test_save_and_load_plan(self, admin_user_obj):
        from omni_desk_backend.smart_assistant.models import ToolChainPlan

        plan = Plan(steps=[PlanStep(tool="schedule", params={"query": "张三"}, on_failure="skip")])
        record = ToolChainPlan.objects.create(
            user=admin_user_obj,
            plan_data=plan.to_dict(),
            status="pending",
        )

        loaded = ToolChainPlan.objects.get(id=record.id)
        restored = Plan.from_dict(loaded.plan_data)
        assert len(restored.steps) == 1
        assert restored.steps[0].tool == "schedule"
```

### Step 2: 运行测试,确认失败

```bash
conda run -n omni_desk python -m pytest omni_desk_backend/smart_assistant/tests/test_plan_serializer.py -v 2>&1 | tail -20
```

期望:`ImportError: cannot import name 'Plan' from 'plan_serializer'`

### Step 3: 实现 Plan / PlanStep + PlanValidationError

创建 `omni_desk_backend/smart_assistant/agent/plan_serializer.py`:

```python
"""Plan 序列化 — multi-tool chain 的 JSON 持久化与恢复。

Task 1 of feat/sa-multi-tool-chain: 让 plan 可序列化、可断点恢复。

数据结构:
    Plan
    └── steps: list[PlanStep]
        ├── tool: str            # 工具名
        ├── params: dict         # 参数(支持 {{step1.output.xxx}} 嵌套引用)
        ├── on_failure: str      # skip | retry | fallback(默认 skip)
        └── retry_count: int     # retry 策略时使用(默认 2)

使用示例::

    plan = Plan(steps=[PlanStep(tool="schedule", params={"query": "张三"})])
    record = ToolChainPlan.objects.create(user=user, plan_data=plan.to_dict())
    restored = Plan.from_dict(record.plan_data)
"""
from dataclasses import dataclass, field, asdict
from typing import Any, Optional

VALID_ON_FAILURE = {"skip", "retry", "fallback"}


class PlanValidationError(ValueError):
    """Plan 校验失败。"""


@dataclass
class PlanStep:
    """单个工具调用步骤。"""

    tool: str
    params: dict
    on_failure: str = "skip"
    retry_count: int = 2

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "PlanStep":
        on_failure = d.get("on_failure", "skip")
        if on_failure not in VALID_ON_FAILURE:
            raise PlanValidationError(
                f"on_failure 必须是 {VALID_ON_FAILURE} 之一,收到: {on_failure!r}"
            )
        return cls(
            tool=d["tool"],
            params=d.get("params", {}),
            on_failure=on_failure,
            retry_count=d.get("retry_count", 2),
        )


@dataclass
class Plan:
    """多工具链执行计划。"""

    steps: list[PlanStep] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"steps": [step.to_dict() for step in self.steps]}

    @classmethod
    def from_dict(cls, d: dict) -> "Plan":
        return cls(steps=[PlanStep.from_dict(s) for s in d.get("steps", [])])
```

### Step 4: 在 models.py 添加 ToolChainPlan

编辑 `omni_desk_backend/smart_assistant/models.py`,在文件末尾追加:

```python
class ToolChainPlan(models.Model):
    """多工具链执行计划的持久化记录。

    用于断点恢复(分支 3)、审计追踪、plan 可视化。
    """

    STATUS_CHOICES = [
        ("pending", "待执行"),
        ("running", "执行中"),
        ("completed", "已完成"),
        ("failed", "失败"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tool_chain_plans",
    )
    plan_data = models.JSONField(default=dict)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    current_step = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "smart_assistant_tool_chain_plan"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"ToolChainPlan(id={self.pk}, user={self.user_id}, status={self.status})"
```

### Step 5: 生成并应用 migration

```bash
conda run -n omni_desk python manage.py makemigrations smart_assistant --dry-run --verbosity 2
```

期望输出含 `Would create: smart_assistant/migrations/00XX_toolchainplan.py`。

实际生成:

```bash
conda run -n omni_desk python manage.py makemigrations smart_assistant
```

期望:`Migrations for 'smart_assistant': smart_assistant/migrations/00XX_toolchainplan.py`。

### Step 6: 跑测试,通过

```bash
conda run -n omni_desk python -m pytest omni_desk_backend/smart_assistant/tests/test_plan_serializer.py -v 2>&1 | tail -15
```

期望:`7 passed`(3 个 TestPlanStep + 3 个 TestPlan + 1 个 TestToolChainPlanModel)。

### Step 7: 跑全套,无回归

```bash
conda run -n omni_desk python -m pytest omni_desk_backend/smart_assistant/tests/ -q 2>&1 | tail -5
```

### Step 8: Commit

```bash
git add omni_desk_backend/smart_assistant/agent/plan_serializer.py \
        omni_desk_backend/smart_assistant/models.py \
        omni_desk_backend/smart_assistant/migrations/ \
        omni_desk_backend/smart_assistant/tests/test_plan_serializer.py
git commit -m "feat(smart-assistant): Plan 序列化模块 + ToolChainPlan 模型

- dataclass Plan / PlanStep,to_dict/from_dict 双向序列化
- PlanValidationError 校验 on_failure 取值
- ToolChainPlan Django 模型(支持 status / current_step 断点恢复字段)
- 7 个单元测试覆盖序列化与 ORM 持久化"
```

---

## Task 2: ToolChainExecutor 升级(嵌套变量 + 失败策略 + step-level 日志)

**Files:**
- Modify: `omni_desk_backend/smart_assistant/agent/tool_chain_executor.py`(主要在 `ToolChainExecutor` class)
- New: `omni_desk_backend/smart_assistant/tests/test_tool_chain_executor_advanced.py`(整文件)

**Interfaces:**
- Consumes: `Plan` / `PlanStep` (Task 1),`ToolContext` 已存在,`AgentLog` 已存在
- Produces: `ToolChainExecutor.execute(plan, context)` 每步写 AgentLog,失败按 on_failure 处理

### Step 1: 写失败的测试

创建 `omni_desk_backend/smart_assistant/tests/test_tool_chain_executor_advanced.py`:

```python
"""ToolChainExecutor 高级测试 — 嵌套 $variable、失败策略、step-level AgentLog。

Task 2 of feat/sa-multi-tool-chain: 升级 executor 支持生产级 plan。
"""
import json
from unittest.mock import patch, MagicMock

import pytest

from omni_desk_backend.smart_assistant.agent.plan_serializer import Plan, PlanStep
from omni_desk_backend.smart_assistant.agent.tool_chain_executor import ToolChainExecutor
from omni_desk_backend.smart_assistant.tools.tool_context import ToolContext


class TestNestedVariableResolution:
    """{{step1.output.users[0].id}} 嵌套引用解析。"""

    def test_resolve_nested_dict_access(self):
        from omni_desk_backend.smart_assistant.agent.tool_chain_executor import _resolve_nested_var

        # 简单嵌套
        assert _resolve_nested_var("step1", {"output": {"users": [{"id": 42}]}}, "users[0].id") == 42
        # 顶层字段
        assert _resolve_nested_var("step1", {"output": {"summary": "张三周一值班"}}, "summary") == "张三周一值班"

    def test_replace_in_params(self):
        from omni_desk_backend.smart_assistant.agent.tool_chain_executor import _replace_variables

        params = {"title": "报告: {{step1.output.summary}}", "user_id": "{{step1.output.users[0].id}}"}
        step_results = {"step1": {"output": {"summary": "张三", "users": [{"id": 42}]}}}
        result = _replace_variables(params, step_results)
        assert result["title"] == "报告: 张三"
        assert result["user_id"] == 42


@pytest.mark.django_db
class TestFailureStrategies:
    """on_failure: skip / retry / fallback 三种策略。"""

    def test_skip_strategy_continues_after_failure(self, admin_user_obj):
        """某步失败,on_failure=skip 时继续后续步骤。"""
        ctx = ToolContext(user=admin_user_obj)
        plan = Plan(steps=[
            PlanStep(tool="broken_tool", params={"x": 1}, on_failure="skip"),
            PlanStep(tool="ok_tool", params={"y": 2}, on_failure="skip"),
        ])

        # mock ToolRegistry.get_tool 在 broken_tool 时抛异常
        with patch(
            "smart_assistant.agent.tool_chain_executor.ToolRegistry"
        ) as MockReg:
            def get_tool(name):
                if name == "broken_tool":
                    raise RuntimeError("工具不可用")
                mock = MagicMock()
                mock.execute.return_value = {"found": True, "data": []}
                return mock
            MockReg.get_tool.side_effect = get_tool

            executor = ToolChainExecutor()
            results = executor.execute(plan, ctx)

        assert len(results) == 2
        assert results[0]["status"] == "skipped"
        assert results[1]["status"] == "success"

    def test_retry_strategy_retries_n_times(self, admin_user_obj):
        """retry_count=2 时,首次失败后重试 2 次。"""
        ctx = ToolContext(user=admin_user_obj)
        plan = Plan(steps=[
            PlanStep(tool="flaky_tool", params={}, on_failure="retry", retry_count=2),
        ])

        attempt_count = {"n": 0}

        def get_tool(name):
            mock = MagicMock()
            def execute_side(*args, **kwargs):
                attempt_count["n"] += 1
                if attempt_count["n"] < 2:
                    raise RuntimeError("transient error")
                return {"found": True}
            mock.execute.side_effect = execute_side
            return mock

        with patch(
            "smart_assistant.agent.tool_chain_executor.ToolRegistry"
        ) as MockReg:
            MockReg.get_tool.side_effect = get_tool
            executor = ToolChainExecutor()
            results = executor.execute(plan, ctx)

        assert attempt_count["n"] == 2  # 第 2 次成功
        assert results[0]["status"] == "success"


@pytest.mark.django_db
class TestStepLevelAgentLog:
    """每步执行应写入 AgentLog,含 tool / params / output / latency。"""

    def test_each_step_writes_agent_log(self, admin_user_obj):
        from omni_desk_backend.smart_assistant.models import AgentLog

        ctx = ToolContext(user=admin_user_obj)
        plan = Plan(steps=[
            PlanStep(tool="schedule", params={"query": "张三"}, on_failure="skip"),
            PlanStep(tool="memo", params={"title": "x"}, on_failure="skip"),
        ])

        with patch(
            "smart_assistant.agent.tool_chain_executor.ToolRegistry"
        ) as MockReg:
            mock_tool = MagicMock()
            mock_tool.execute.return_value = {"found": True, "data": ["张三周一"]}
            MockReg.get_tool.return_value = mock_tool

            executor = ToolChainExecutor()
            executor.execute(plan, ctx)

        # 验证写入了 2 条 AgentLog
        logs = AgentLog.objects.filter(user=admin_user_obj)
        assert logs.count() == 2
        # 验证字段
        first_log = logs.first()
        assert first_log.tool_used in ("schedule", "memo")
        assert "query" in first_log.tool_input
        assert first_log.response_time_ms >= 0
```

### Step 2: 运行测试,确认失败

```bash
conda run -n omni_desk python -m pytest omni_desk_backend/smart_assistant/tests/test_tool_chain_executor_advanced.py -v 2>&1 | tail -30
```

期望:多个 FAIL,关键报错 `_resolve_nested_var` 未定义。

### Step 3: 实现 _resolve_nested_var + _replace_variables + 升级 ToolChainExecutor

编辑 `omni_desk_backend/smart_assistant/agent/tool_chain_executor.py`:

在文件顶部 import 之后,加入:

```python
import re
import time
from .plan_serializer import Plan, PlanStep, PlanValidationError

NESTED_VAR_PATTERN = re.compile(r"\{\{([^}]+)\}\}")
```

加入新的辅助函数:

```python
def _resolve_nested_var(step_name: str, step_output: dict, path: str):
    """解析 {{step_name.output.path.to.value}} 中的 path 部分。

    支持 dict 嵌套 + list 索引(如 users[0].id)。
    """
    data = step_output
    # path 形如 "output.users[0].id" 或 "summary"
    # 拆分步骤:[users, [0], id]
    tokens = re.findall(r"\w+|\[\d+\]", path)
    for token in tokens:
        if token.startswith("[") and token.endswith("]"):
            idx = int(token[1:-1])
            data = data[idx]
        else:
            data = data[token]
    return data


def _replace_variables(params: dict, step_results: dict) -> dict:
    """替换 params 中所有 {{stepN.output.path}} 占位符为实际值。"""
    result = {}
    for key, value in params.items():
        if isinstance(value, str):
            def repl(m):
                ref = m.group(1)  # 形如 "step1.output.users[0].id"
                parts = ref.split(".", 1)
                step_name = parts[0]
                path = parts[1] if len(parts) > 1 else ""
                if step_name not in step_results:
                    return m.group(0)  # 保留原占位符
                return str(_resolve_nested_var(step_name, step_results[step_name], path))
            result[key] = NESTED_VAR_PATTERN.sub(repl, value)
        elif isinstance(value, dict):
            result[key] = _replace_variables(value, step_results)
        elif isinstance(value, list):
            result[key] = [
                _replace_variables(v, step_results) if isinstance(v, dict) else v
                for v in value
            ]
        else:
            result[key] = value
    return result
```

升级 `ToolChainExecutor.execute` 方法:

```python
def execute(self, plan: Plan, context: "ToolContext") -> list:
    """执行 plan,每步写 AgentLog,失败按 on_failure 策略处理。

    Returns:
        list[dict]: 每步结果,含 status / output / error?
    """
    from ..models import AgentLog
    from .plan_serializer import Plan, PlanStep
    from .registry import ToolRegistry

    step_results = {}
    output = []
    for idx, step in enumerate(plan.steps):
        step_label = f"step{idx + 1}"
        start_time = time.time()
        result = self._execute_step_with_strategy(
            step, step_label, step_results, context, idx,
        )
        result["latency_ms"] = int((time.time() - start_time) * 1000)
        step_results[step_label] = result
        output.append(result)

        # 写 AgentLog(每步)
        AgentLog.objects.create(
            user=context.user,
            user_query=f"[chain step {idx + 1}] {step.tool}",
            intent=f"chain:{step.tool}",
            tool_used=step.tool,
            tool_input=step.params,
            tool_output=result.get("output") or {},
            response_time_ms=result["latency_ms"],
            tool_success=result["status"] != "failed",
        )
    return output


def _execute_step_with_strategy(
    self, step: PlanStep, step_label: str, step_results: dict, context, idx: int
) -> dict:
    from .registry import ToolRegistry

    attempts = step.retry_count if step.on_failure == "retry" else 1
    resolved_params = _replace_variables(step.params, step_results)

    for attempt in range(attempts):
        try:
            tool = ToolRegistry.get_tool(step.tool)
            output = tool.execute(resolved_params, context=context)
            return {
                "step": step_label,
                "tool": step.tool,
                "status": "success",
                "output": output,
                "attempts": attempt + 1,
            }
        except Exception as exc:
            if attempt + 1 < attempts:
                continue  # 重试
            # 用尽所有重试或非 retry 策略
            if step.on_failure == "skip":
                return {
                    "step": step_label,
                    "tool": step.tool,
                    "status": "skipped",
                    "output": None,
                    "error": str(exc),
                    "attempts": attempt + 1,
                }
            elif step.on_failure == "fallback":
                return {
                    "step": step_label,
                    "tool": step.tool,
                    "status": "fallback",
                    "output": {"fallback_message": f"工具 {step.tool} 不可用,已跳过"},
                    "error": str(exc),
                    "attempts": attempt + 1,
                }
            else:
                return {
                    "step": step_label,
                    "tool": step.tool,
                    "status": "failed",
                    "output": None,
                    "error": str(exc),
                    "attempts": attempt + 1,
                }
```

### Step 4: 运行测试,确认通过

```bash
conda run -n omni_desk python -m pytest omni_desk_backend/smart_assistant/tests/test_tool_chain_executor_advanced.py -v 2>&1 | tail -15
```

期望:`5 passed`(2 个 TestNestedVariableResolution + 2 个 TestFailureStrategies + 1 个 TestStepLevelAgentLog)。

### Step 5: 跑全套,无回归

```bash
conda run -n omni_desk python -m pytest omni_desk_backend/smart_assistant/tests/ -q 2>&1 | tail -5
```

### Step 6: Commit

```bash
git add omni_desk_backend/smart_assistant/agent/tool_chain_executor.py \
        omni_desk_backend/smart_assistant/tests/test_tool_chain_executor_advanced.py
git commit -m "feat(smart-assistant): ToolChainExecutor 升级(嵌套变量 + 失败策略 + step-level AgentLog)

- _resolve_nested_var 支持 {{step1.output.users[0].id}} 嵌套引用
- _replace_variables 递归替换字符串/字典/列表参数
- on_failure 三策略:skip(跳过)/retry(重试 retry_count 次)/fallback(返回降级文案)
- 每步执行写入 AgentLog(便于审计追踪)
- 5 个集成测试覆盖"
```

---

## Task 3: 3 个跨工具链场景 E2E

**Files:**
- New: `omni_desk_backend/smart_assistant/tests/test_multi_tool_chain_scenarios.py`(整文件)

**前置条件:** Task 1 + Task 2 已完成。

### Step 1: 创建 E2E 测试文件

创建 `omni_desk_backend/smart_assistant/tests/test_multi_tool_chain_scenarios.py`:

```python
"""3 个跨工具链场景 E2E — 验证多步 plan 真实跑通。

Task 3 of feat/sa-multi-tool-chain: 演示 LLM 编排能力。
"""
import json
from unittest.mock import patch

import pytest

from omni_desk_backend.smart_assistant.agent.orchestrator import AgentOrchestrator
from omni_desk_backend.smart_assistant.agent.plan_serializer import Plan, PlanStep
from omni_desk_backend.smart_assistant.agent.tool_chain_executor import ToolChainExecutor
from omni_desk_backend.smart_assistant.tools.tool_context import ToolContext


@pytest.mark.django_db
class TestChainScheduleToMemoToAnnouncement:
    """场景 A: 排班 → 报告(MemoTool) → 公告(AnnouncementTool 只读查询)

    用户问:"帮我查张三这周值班,生成排班报告"
    编排:ScheduleTool → MemoTool(报告) → AnnouncementTool(查最近公告,验证时间)
    """

    def test_chain_executes_three_tools(self, mock_llm_router, admin_user_obj):
        mock_llm_router.classify.return_value = "schedule_query"  # 触发多工具编排

        # Mock 工具执行序列
        schedule_result = {"found": True, "data": [{"date": "周一", "user": "张三"}]}
        memo_result = {"found": True, "data": {"title": "张三排班报告", "content": "周一"}}
        announcement_result = {"found": True, "data": [{"title": "本周公告"}]}

        def mock_get_tool(name):
            mock = type("MockTool", (), {})()
            mock.name = name
            if name == "schedule":
                mock.execute = lambda *a, **kw: schedule_result
            elif name == "memo":
                mock.execute = lambda *a, **kw: memo_result
            elif name == "announcement":
                mock.execute = lambda *a, **kw: announcement_result
            else:
                mock.execute = lambda *a, **kw: {"found": False}
            return mock

        with patch(
            "smart_assistant.agent.tool_chain_executor.ToolRegistry.get_tool",
            side_effect=mock_get_tool,
        ):
            ctx = ToolContext(user=admin_user_obj)
            plan = Plan(steps=[
                PlanStep(tool="schedule", params={"query": "张三这周值班"}, on_failure="skip"),
                PlanStep(
                    tool="memo",
                    params={"title": "{{step1.output.data[0].user}} 排班报告"},
                    on_failure="skip",
                ),
                PlanStep(tool="announcement", params={"query": "最近公告"}, on_failure="skip"),
            ])

            executor = ToolChainExecutor()
            results = executor.execute(plan, ctx)

        assert len(results) == 3
        assert results[0]["status"] == "success"
        assert results[1]["status"] == "success"
        assert results[2]["status"] == "success"
        # 验证变量替换生效
        assert "张三" in results[1]["output"]["data"]["title"]


@pytest.mark.django_db
class TestChainSensorToPersonnelToMemo:
    """场景 B: 传感器异常 → 责任人(PersonnelTool) → 周报(MemoTool)"""

    def test_chain_three_tools_with_dependencies(self, mock_llm_router, admin_user_obj):
        sensor_result = {"found": True, "data": [{"sensor_id": "S001", "owner": "李四"}]}
        personnel_result = {"found": True, "data": [{"username": "李四", "department": "运维部"}]}
        memo_result = {"found": True, "data": {"title": "周报"}}

        def mock_get_tool(name):
            mock = type("MockTool", (), {})()
            mock.name = name
            if name == "sensor":
                mock.execute = lambda *a, **kw: sensor_result
            elif name == "personnel":
                mock.execute = lambda *a, **kw: personnel_result
            elif name == "memo":
                mock.execute = lambda *a, **kw: memo_result
            else:
                mock.execute = lambda *a, **kw: {"found": False}
            return mock

        with patch(
            "smart_assistant.agent.tool_chain_executor.ToolRegistry.get_tool",
            side_effect=mock_get_tool,
        ):
            ctx = ToolContext(user=admin_user_obj)
            plan = Plan(steps=[
                PlanStep(tool="sensor", params={"query": "本月异常"}, on_failure="skip"),
                PlanStep(
                    tool="personnel",
                    params={"query": "{{step1.output.data[0].owner}}"},
                    on_failure="skip",
                ),
                PlanStep(
                    tool="memo",
                    params={"title": "周报-{{step2.output.data[0].department}}"},
                    on_failure="skip",
                ),
            ])

            executor = ToolChainExecutor()
            results = executor.execute(plan, ctx)

        assert all(r["status"] == "success" for r in results)
        # 验证 sensor 输出的 owner 被 personnel 接收
        assert results[1]["output"]["data"][0]["username"] == "李四"


@pytest.mark.django_db
class TestChainComplianceToProjectFallback:
    """场景 C: 合规 → 项目 → 失败 fallback(项目工具不可用时降级)"""

    def test_fallback_strategy_on_project_unavailable(self, mock_llm_router, admin_user_obj):
        compliance_result = {"found": True, "data": [{"issue_id": "C001"}]}

        def mock_get_tool(name):
            mock = type("MockTool", (), {})()
            mock.name = name
            if name == "compliance":
                mock.execute = lambda *a, **kw: compliance_result
            elif name == "project":
                raise ConnectionError("项目服务不可用")
            else:
                mock.execute = lambda *a, **kw: {"found": False}
            return mock

        with patch(
            "smart_assistant.agent.tool_chain_executor.ToolRegistry.get_tool",
            side_effect=mock_get_tool,
        ):
            ctx = ToolContext(user=admin_user_obj)
            plan = Plan(steps=[
                PlanStep(tool="compliance", params={"query": "近期合规问题"}, on_failure="skip"),
                PlanStep(tool="project", params={"query": "关联项目"}, on_failure="fallback"),
            ])

            executor = ToolChainExecutor()
            results = executor.execute(plan, ctx)

        assert results[0]["status"] == "success"
        assert results[1]["status"] == "fallback"
        assert "fallback_message" in results[1]["output"]
```

### Step 2: 跑测试,确认通过

```bash
conda run -n omni_desk python -m pytest omni_desk_backend/smart_assistant/tests/test_multi_tool_chain_scenarios.py -v 2>&1 | tail -10
```

期望:`3 passed`。

### Step 3: 跑全套,无回归

```bash
conda run -n omni_desk python -m pytest omni_desk_backend/smart_assistant/tests/ -q 2>&1 | tail -5
```

### Step 4: Commit

```bash
git add omni_desk_backend/smart_assistant/tests/test_multi_tool_chain_scenarios.py
git commit -m "test(smart-assistant): 3 个跨工具链场景 E2E(排班→报告→公告 / 传感器→责任人→周报 / 合规→项目→fallback)

- 场景 A: 3 工具串接 + 嵌套变量引用
- 场景 B: sensor→personnel→memo 跨域数据流
- 场景 C: 项目服务不可用时 fallback 策略验证"
```

---

## Task 4: 覆盖率与全套验证

**Files:** 无

### Step 1: 跑完整测试,确认通过

```bash
conda run -n omni_desk python -m pytest --no-header -q 2>&1 | tail -10
```

期望:全部通过。

### Step 2: 确认覆盖率 ≥ 80%

```bash
conda run -n omni_desk python -m pytest --cov=omni_desk_backend --cov-report=term --cov-fail-under=80 -q 2>&1 | tail -20
```

期望:`Required test coverage of 80% reached.`

### Step 3: 准备 PR 描述

```markdown
# feat(smart-assistant): 多工具链编排能力升级(SAIS #2/4)

## 背景
SAIS 分支 2。完成 multi-tool chain 编排能力升级,支持 plan 序列化、嵌套变量、失败策略。

## 主要改动
- ✨ feat: Plan/PlanStep dataclass + JSON 序列化 + ToolChainPlan 模型
- ✨ feat: ToolChainExecutor 升级(嵌套 $variable + on_failure 三策略)
- ✨ feat: 每步执行写 AgentLog(便于审计)
- ✅ test: 7 个序列化测试 + 5 个执行器测试 + 3 个跨工具场景 E2E

## 验收
- 3 个跨工具场景 E2E 全绿
- 覆盖率 ≥ 80%
- plan 可序列化/反序列化(往返不丢字段)
- 失败策略 3 种全部覆盖
```

### Step 4: 推送分支并创建 PR

```bash
git push -u origin feat/sa-multi-tool-chain
gh pr create --base main --head feat/sa-multi-tool-chain \
  --title "feat(smart-assistant): 多工具链编排升级(SAIS #2/4)" \
  --body-file /tmp/pr-body.md
gh pr checks <pr-number> --watch
```

### Step 5: 用户 merge PR,清理分支

```bash
git switch main
git pull --rebase origin main
git branch -d feat/sa-multi-tool-chain
git push origin --delete feat/sa-multi-tool-chain
```

---

## 完成标志

- [x] Task 0-4 全部勾选
- [x] `feat/sa-multi-tool-chain` 合入 main
- [x] 覆盖率 ≥ 80%
- [x] 3 个跨工具场景 E2E 通过

**进入分支 3(`feat/sa-multi-agent`)**:新 plan `docs/superpowers/plans/2026-07-17-sa-multi-agent.md`(下次会话写)。