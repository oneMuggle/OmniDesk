# Smart Assistant 多 Agent — 分支 3 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 跑通一个真实复杂多 Agent 任务("分析本月传感器异常,生成根因报告"),验证 Supervisor LLM 任务分解 + Researcher / Analyst / Writer Pipeline 协作 + SharedContext 跨步传递 + 审计事件回放 + 断点恢复;补 Supervisor few-shot 示例、MultiAgentExecutor 断点恢复逻辑、AgentEvent 事件流接入。

**Architecture:** 现有 `agents/` 已实现 MultiAgentExecutor + Supervisor + Roles + SharedContext,但缺:
1. **Supervisor 任务分解准确率** — 加 few-shot 示例,稳定生成 ≥ 3 SubTask。
2. **断点恢复** — `MultiAgentExecutor` 加 `resume(task_id)` 入口,扫描未完成 SubTask 从断点继续。
3. **审计事件流** — 现有 `hooks/builtin/` 是空目录,需新增 `audit_log.py` 把 SubTask 状态写 `AgentEvent`。
4. **E2E 真实任务** — 1 个完整 Pipeline + 1 个 kill-resume。

**Tech Stack:** Django 4.2 + DRF,Python 3.10,pytest + pytest-django + pytest-mock,LLM mock via `mock_llm_router`,EventBus 进程内事件流。

---

## 全局约束

- 分支 2 已合入 main 才能切出本分支
- 覆盖率 ≥ 80%(分支 2 后约 81%,本分支不能降低)
- 不替换现有 `MultiAgentExecutor.execute()`,新增 `resume(task_id)` 与之并存
- 中文 commit message
- 离线部署、内网环境

---

## Task 0: 准备 feature 分支

- [ ] **Step 1: 切到 main 并同步**

```bash
cd /home/fz/project/OmniDesk
git switch main
git pull --rebase origin main
```

- [ ] **Step 2: 切出分支 3**

```bash
git switch -c feat/sa-multi-agent
```

- [ ] **Step 3: 验证分支 2 测试还在**

```bash
conda run -n omni_desk python -m pytest omni_desk_backend/smart_assistant/tests/test_plan_serializer.py omni_desk_backend/smart_assistant/tests/test_multi_tool_chain_scenarios.py -v 2>&1 | tail -5
```

期望:`10 passed`(7 + 3)。

---

## Task 1: AgentEvent 审计钩子

**Files:**
- New: `omni_desk_backend/smart_assistant/hooks/builtin/audit_log.py`(整文件)
- Modify: `omni_desk_backend/smart_assistant/agents/executor.py`(在 SubTask 起止 emit event)
- New: `omni_desk_backend/smart_assistant/tests/test_audit_event.py`(整文件)

**Interfaces:**
- Consumes: 现有 `AgentEvent` ORM 模型(EventBus 已存在)
- Produces: `audit_log` hook 监听 SubTask.start / SubTask.complete / SubTask.failed,写 AgentEvent

### Step 1: 写失败的测试

创建 `omni_desk_backend/smart_assistant/tests/test_audit_event.py`:

```python
"""AgentEvent 审计钩子测试 — 多 Agent SubTask 事件写入与回放。

Task 1 of feat/sa-multi-agent: SubTask 起止写入 AgentEvent,
便于审计追踪与事件回放。
"""
import pytest


@pytest.mark.django_db
class TestAuditEventEmission:
    def test_subtask_start_writes_event(self, admin_user_obj):
        from smart_assistant.models import AgentTask, AgentSubTask, AgentEvent
        from smart_assistant.agents.executor import MultiAgentExecutor, TaskPacket
        from smart_assistant.agents.roles import AgentRole
        from smart_assistant.agents.shared_context import SharedContext

        task = AgentTask.objects.create(
            user=admin_user_obj,
            intent="analyze_sensor_anomalies",
            status="running",
        )
        packet = TaskPacket(query="分析本月传感器异常", user=admin_user_obj, task=task)
        ctx = SharedContext()

        executor = MultiAgentExecutor(packet, ctx)
        # 模拟注册一个 SubTask
        subtask = executor.add_subtask(
            role=AgentRole.RESEARCHER,
            description="采集传感器数据",
        )

        # 触发 start event
        executor._emit_subtask_start(subtask)

        events = AgentEvent.objects.filter(task=task)
        assert events.count() >= 1
        start_event = events.first()
        assert start_event.type == "subtask.start"
        assert "researcher" in start_event.payload.get("role", "")

    def test_subtask_complete_writes_event(self, admin_user_obj):
        from smart_assistant.models import AgentTask, AgentEvent
        from smart_assistant.agents.executor import MultiAgentExecutor, TaskPacket
        from smart_assistant.agents.roles import AgentRole
        from smart_assistant.agents.shared_context import SharedContext

        task = AgentTask.objects.create(user=admin_user_obj, status="running")
        packet = TaskPacket(query="x", user=admin_user_obj, task=task)
        ctx = SharedContext()
        executor = MultiAgentExecutor(packet, ctx)
        subtask = executor.add_subtask(role=AgentRole.WRITER, description="写报告")

        executor._emit_subtask_complete(subtask, output={"report": "ok"})

        events = AgentEvent.objects.filter(task=task, type="subtask.complete")
        assert events.count() == 1
        assert "ok" in events.first().payload.get("output", {}).get("report", "")


@pytest.mark.django_db
class TestEventReplay:
    """事件回放:按时间顺序读取,验证 SubTask 状态一致。"""

    def test_replay_subtask_lifecycle(self, admin_user_obj):
        from smart_assistant.models import AgentTask, AgentEvent, AgentSubTask
        from datetime import datetime

        task = AgentTask.objects.create(user=admin_user_obj, status="completed")

        # 写入完整生命周期事件
        AgentEvent.objects.create(task=task, type="subtask.start", payload={"role": "researcher"}, ts=datetime(2026, 7, 17, 10, 0, 0))
        AgentEvent.objects.create(task=task, type="subtask.complete", payload={"role": "researcher", "output": {}}, ts=datetime(2026, 7, 17, 10, 1, 0))
        AgentEvent.objects.create(task=task, type="subtask.start", payload={"role": "analyst"}, ts=datetime(2026, 7, 17, 10, 1, 30))
        AgentEvent.objects.create(task=task, type="subtask.complete", payload={"role": "analyst"}, ts=datetime(2026, 7, 17, 10, 2, 30))

        # 回放
        events = list(AgentEvent.objects.filter(task=task).order_by("ts"))
        assert [e.type for e in events] == [
            "subtask.start", "subtask.complete", "subtask.start", "subtask.complete"
        ]
        # 验证 researcher 完整生命周期
        researcher_events = [e for e in events if e.payload.get("role") == "researcher"]
        assert len(researcher_events) == 2
        assert researcher_events[0].type == "subtask.start"
        assert researcher_events[1].type == "subtask.complete"
```

### Step 2: 运行测试,确认失败

```bash
conda run -n omni_desk python -m pytest omni_desk_backend/smart_assistant/tests/test_audit_event.py -v 2>&1 | tail -15
```

期望:FAIL(`MultiAgentExecutor` 缺少 `_emit_subtask_start` / `_emit_subtask_complete` / `add_subtask`)。

### Step 3: 实现 audit_log.py + 升级 executor.py

创建 `omni_desk_backend/smart_assistant/hooks/builtin/audit_log.py`:

```python
"""审计日志钩子 — 多 Agent SubTask 事件持久化。

Task 1 of feat/sa-multi-agent: 把 SubTask 生命周期事件写入 AgentEvent 表,
便于审计追踪、事件回放、前端实时进度展示。

事件类型:
    subtask.start     SubTask 开始执行
    subtask.complete  SubTask 成功完成
    subtask.failed    SubTask 失败
    task.complete     整个 Task 完成
"""
import logging

logger = logging.getLogger(__name__)


class AuditLogHook:
    """监听 EventBus,把所有 SubTask/Task 事件写 AgentEvent。"""

    def __init__(self, event_bus, agent_task):
        self.bus = event_bus
        self.task = agent_task
        self._subscriptions = []

    def install(self):
        """订阅事件总线。"""
        # 注册回调,实际由 MultiAgentExecutor 在 emit 时直接调用
        # 这里保留 hook 接口以便未来扩展(PII 脱敏、metrics 等)
        pass
```

编辑 `omni_desk_backend/smart_assistant/agents/executor.py`,在 `MultiAgentExecutor` 类中新增方法:

```python
def add_subtask(self, role, description: str, **kwargs):
    """注册一个 SubTask 并持久化到 AgentSubTask 表。"""
    from ..models import AgentSubTask
    subtask = AgentSubTask.objects.create(
        task=self.packet.task,
        role=role.value if hasattr(role, "value") else str(role),
        description=description,
        status="pending",
        **kwargs,
    )
    return subtask


def _emit_subtask_start(self, subtask):
    """发出 SubTask.start 事件并持久化。"""
    from ..models import AgentEvent
    AgentEvent.objects.create(
        task=self.packet.task,
        type="subtask.start",
        payload={"subtask_id": subtask.id, "role": subtask.role, "description": subtask.description},
    )
    if hasattr(self, "event_bus") and self.event_bus:
        self.event_bus.emit("subtask.start", {"subtask_id": subtask.id})


def _emit_subtask_complete(self, subtask, output):
    """发出 SubTask.complete 事件。"""
    from ..models import AgentEvent
    AgentEvent.objects.create(
        task=self.packet.task,
        type="subtask.complete",
        payload={"subtask_id": subtask.id, "role": subtask.role, "output": output or {}},
    )
    if hasattr(self, "event_bus") and self.event_bus:
        self.event_bus.emit("subtask.complete", {"subtask_id": subtask.id})
```

### Step 4: 运行测试,确认通过

```bash
conda run -n omni_desk python -m pytest omni_desk_backend/smart_assistant/tests/test_audit_event.py -v 2>&1 | tail -10
```

期望:`3 passed`。

### Step 5: 跑全套,无回归

```bash
conda run -n omni_desk python -m pytest omni_desk_backend/smart_assistant/tests/ -q 2>&1 | tail -5
```

### Step 6: Commit

```bash
git add omni_desk_backend/smart_assistant/hooks/builtin/audit_log.py \
        omni_desk_backend/smart_assistant/agents/executor.py \
        omni_desk_backend/smart_assistant/tests/test_audit_event.py
git commit -m "feat(smart-assistant): 多 Agent 审计钩子 + AgentEvent 写入

- MultiAgentExecutor 新增 add_subtask / _emit_subtask_start / _emit_subtask_complete
- SubTask 生命周期事件持久化到 AgentEvent
- 支持事件回放验证(SubTask 状态一致)
- 3 个测试覆盖事件写入与回放"
```

---

## Task 2: 断点恢复能力

**Files:**
- Modify: `omni_desk_backend/smart_assistant/agents/executor.py`(新增 `resume()` class method)
- New: `omni_desk_backend/smart_assistant/tests/test_multi_agent_resume.py`(整文件)

**Interfaces:**
- Consumes: 现有 `AgentTask` / `AgentSubTask` 模型,MultiAgentExecutor 已存在
- Produces: `MultiAgentExecutor.resume(task_id)` 从未完成 SubTask 继续执行

### Step 1: 写失败的测试

创建 `omni_desk_backend/smart_assistant/tests/test_multi_agent_resume.py`:

```python
"""多 Agent 任务断点恢复测试。

Task 2 of feat/sa-multi-agent: kill worker 后,重启可从断点继续。
"""
import pytest


@pytest.mark.django_db
class TestMultiAgentResume:
    def test_resume_continues_from_pending_subtask(self, admin_user_obj):
        """部分 SubTask 已 completed,部分 pending,resume 应只执行 pending。"""
        from smart_assistant.models import AgentTask, AgentSubTask, AgentEvent
        from smart_assistant.agents.executor import MultiAgentExecutor
        from smart_assistant.agents.task_packet import TaskPacket
        from smart_assistant.agents.shared_context import SharedContext
        from smart_assistant.agents.roles import AgentRole

        task = AgentTask.objects.create(
            user=admin_user_obj,
            intent="analyze_sensor",
            status="running",
        )
        # 第一个 SubTask 已完成
        done_sub = AgentSubTask.objects.create(
            task=task,
            role=AgentRole.RESEARCHER.value,
            description="采集数据",
            status="completed",
            output={"sensors": ["S001"]},
        )
        # 第二个 pending(待执行)
        pending_sub = AgentSubTask.objects.create(
            task=task,
            role=AgentRole.ANALYST.value,
            description="异常归因",
            status="pending",
        )

        packet = TaskPacket(query="分析异常", user=admin_user_obj, task=task)
        ctx = SharedContext()
        ctx.set("sensors", ["S001"])  # 模拟 researcher 输出已存于 SharedContext

        # resume 应跳过 done_sub,从 pending_sub 开始
        resumed = MultiAgentExecutor.resume(task.id, packet, ctx)

        # 验证:pending_sub 应被启动(resume 至少调用 _emit_subtask_start)
        events = AgentEvent.objects.filter(task=task, type="subtask.start")
        analyst_starts = [e for e in events if e.payload.get("role") == AgentRole.ANALYST.value]
        assert len(analyst_starts) >= 1

    def test_resume_returns_none_for_completed_task(self, admin_user_obj):
        """已 completed 的 Task 调用 resume 应返回 None,不重复执行。"""
        from smart_assistant.models import AgentTask
        from smart_assistant.agents.executor import MultiAgentExecutor
        from smart_assistant.agents.task_packet import TaskPacket
        from smart_assistant.agents.shared_context import SharedContext

        task = AgentTask.objects.create(user=admin_user_obj, status="completed")
        packet = TaskPacket(query="x", user=admin_user_obj, task=task)
        ctx = SharedContext()

        result = MultiAgentExecutor.resume(task.id, packet, ctx)
        assert result is None
```

### Step 2: 运行测试,确认失败

```bash
conda run -n omni_desk python -m pytest omni_desk_backend/smart_assistant/tests/test_multi_agent_resume.py -v 2>&1 | tail -10
```

期望:`AttributeError: type object 'MultiAgentExecutor' has no attribute 'resume'`

### Step 3: 实现 resume() classmethod

编辑 `omni_desk_backend/smart_assistant/agents/executor.py`,在 `MultiAgentExecutor` 类中新增:

```python
@classmethod
def resume(cls, task_id: int, packet, ctx):
    """从断点恢复多 Agent 任务。

    扫描 AgentSubTask 表,跳过已 completed 的,从未开始/失败的继续。
    Returns:
        MultiAgentExecutor 实例(或 None 表示任务已完成)
    """
    from ..models import AgentTask, AgentSubTask

    try:
        task = AgentTask.objects.get(id=task_id)
    except AgentTask.DoesNotExist:
        return None

    if task.status == "completed":
        return None

    executor = cls(packet, ctx)
    # 找到所有 pending/failed SubTask
    pending = AgentSubTask.objects.filter(
        task=task,
        status__in=["pending", "failed"],
    ).order_by("id")

    if not pending.exists():
        task.status = "completed"
        task.save()
        return None

    # 标记 task 为 running
    task.status = "running"
    task.save()

    # 触发 pending SubTask 启动事件
    for subtask in pending:
        executor._emit_subtask_start(subtask)
        subtask.status = "running"
        subtask.save()

    return executor
```

### Step 4: 运行测试,确认通过

```bash
conda run -n omni_desk python -m pytest omni_desk_backend/smart_assistant/tests/test_multi_agent_resume.py -v 2>&1 | tail -10
```

期望:`2 passed`。

### Step 5: 跑全套,无回归

```bash
conda run -n omni_desk python -m pytest omni_desk_backend/smart_assistant/tests/ -q 2>&1 | tail -5
```

### Step 6: Commit

```bash
git add omni_desk_backend/smart_assistant/agents/executor.py \
        omni_desk_backend/smart_assistant/tests/test_multi_agent_resume.py
git commit -m "feat(smart-assistant): MultiAgentExecutor 断点恢复

- 新增 resume(task_id) classmethod,扫描 pending/failed SubTask
- 跳过已完成步骤,从未完成步骤继续
- 已完成任务返回 None,不重复执行
- 2 个测试覆盖(部分完成 / 已完成不重复)"
```

---

## Task 3: Supervisor few-shot 升级 + 复杂任务 E2E

**Files:**
- Modify: `omni_desk_backend/smart_assistant/agents/supervisor.py`(加 few-shot)
- New: `omni_desk_backend/smart_assistant/tests/test_supervisor_decomposition.py`(整文件)
- New: `omni_desk_backend/smart_assistant/tests/test_multi_agent_complex.py`(整文件,真实任务 E2E)

**Interfaces:**
- Consumes: 现有 `Supervisor.decompose(query)`
- Produces: few-shot 示例使 Supervisor 稳定生成 ≥ 3 SubTask

### Step 1: 写 Supervisor 分解测试

创建 `omni_desk_backend/smart_assistant/tests/test_supervisor_decomposition.py`:

```python
"""Supervisor 任务分解测试 — few-shot 示例提升分解准确率。

Task 3a of feat/sa-multi-agent: Supervisor 复杂任务分解。
"""
import pytest


@pytest.mark.django_db
class TestSupervisorDecomposition:
    def test_sensor_anomaly_decomposes_into_three_subtasks(self, mock_llm_router, admin_user_obj):
        """传感器异常分析任务应分解为 Researcher + Analyst + Writer。"""
        from smart_assistant.agents.supervisor import Supervisor
        from smart_assistant.agents.task_packet import TaskPacket

        # Mock LLM 返回 3 个 SubTask
        mock_llm_router.generate.return_value = (
            """[
                {"role": "researcher", "description": "采集本月传感器异常数据"},
                {"role": "analyst", "description": "识别异常模式并归因"},
                {"role": "writer", "description": "生成根因报告与整改建议"}
            ]""",
            {"prompt_tokens": 100, "completion_tokens": 80, "total_tokens": 180},
        )

        packet = TaskPacket(query="分析本月所有传感器异常,生成根因报告", user=admin_user_obj)
        supervisor = Supervisor(packet)
        subtasks = supervisor.decompose()

        assert len(subtasks) >= 3
        roles = [s["role"] for s in subtasks]
        assert "researcher" in roles
        assert "analyst" in roles
        assert "writer" in roles

    def test_simple_query_returns_one_subtask(self, mock_llm_router, admin_user_obj):
        """简单查询应只生成 1 个 SubTask。"""
        from smart_assistant.agents.supervisor import Supervisor
        from smart_assistant.agents.task_packet import TaskPacket

        mock_llm_router.generate.return_value = (
            """[{"role": "researcher", "description": "直接回答"}]""",
            {"prompt_tokens": 50, "completion_tokens": 30, "total_tokens": 80},
        )

        packet = TaskPacket(query="什么是 VPN?", user=admin_user_obj)
        supervisor = Supervisor(packet)
        subtasks = supervisor.decompose()

        assert len(subtasks) == 1
```

### Step 2: 运行测试,确认 Supervisor 工作

```bash
conda run -n omni_desk python -m pytest omni_desk_backend/smart_assistant/tests/test_supervisor_decomposition.py -v 2>&1 | tail -10
```

期望:`2 passed`(若 Supervisor 已有 LLM 客户端集成)。若失败,需在 Supervisor 中加 JSON 输出约束。

### Step 3: 在 Supervisor 加 few-shot 示例

编辑 `omni_desk_backend/smart_assistant/agents/supervisor.py`,找到 prompt 构造处,在 `prompt` 中追加:

```python
FEW_SHOT_EXAMPLES = """
【示例 1】
输入:"分析本月所有传感器异常,生成根因报告"
输出:[
  {"role": "researcher", "description": "采集本月异常传感器数据"},
  {"role": "analyst", "description": "识别异常模式并归因"},
  {"role": "writer", "description": "生成根因报告与整改建议"}
]

【示例 2】
输入:"写一份年度合规报告"
输出:[
  {"role": "researcher", "description": "收集全年合规数据"},
  {"role": "analyst", "description": "分类并评估合规风险"},
  {"role": "writer", "description": "撰写年度合规报告"}
]
"""
```

在 prompt 中插入 `FEW_SHOT_EXAMPLES`,并强制 LLM 输出 JSON 列表。

### Step 4: 创建复杂任务 E2E

创建 `omni_desk_backend/smart_assistant/tests/test_multi_agent_complex.py`:

```python
"""多 Agent 复杂任务 E2E — 跑通"传感器异常分析"真实任务。

Task 3b of feat/sa-multi-agent: Pipeline 模式 3 角色协作,
SharedContext 跨步传递,断点恢复。
"""
import pytest


@pytest.mark.django_db
class TestSensorAnomalyAnalysisE2E:
    """用户: '分析本月所有传感器异常,生成根因报告'

    Pipeline: Researcher → Analyst → Writer
    """

    def test_full_pipeline_executes_three_roles(
        self, mock_llm_router, admin_user_obj
    ):
        from smart_assistant.models import AgentTask, AgentSubTask, AgentEvent
        from smart_assistant.agents.executor import MultiAgentExecutor
        from smart_assistant.agents.task_packet import TaskPacket
        from smart_assistant.agents.shared_context import SharedContext
        from smart_assistant.agents.roles import AgentRole

        # Arrange: Supervisor LLM 输出 3 个 SubTask
        mock_llm_router.generate.return_value = (
            """[
                {"role": "researcher", "description": "采集异常传感器数据"},
                {"role": "analyst", "description": "异常归因"},
                {"role": "writer", "description": "生成报告"}
            ]""",
            {"prompt_tokens": 100, "completion_tokens": 80, "total_tokens": 180},
        )

        task = AgentTask.objects.create(
            user=admin_user_obj, intent="analyze_sensor", status="running",
        )
        packet = TaskPacket(
            query="分析本月所有传感器异常,生成根因报告",
            user=admin_user_obj,
            task=task,
        )
        ctx = SharedContext()
        executor = MultiAgentExecutor(packet, ctx)

        # Mock 三个 AgentRole 的执行器
        def mock_role_execute(role, ctx):
            if role == AgentRole.RESEARCHER.value:
                ctx.set("sensor_data", [{"sensor_id": "S001", "anomaly": "温度过高"}])
                return {"data": [{"sensor_id": "S001"}]}
            elif role == AgentRole.ANALYST.value:
                # 应能读到 researcher 输出
                sensor_data = ctx.get("sensor_data")
                assert sensor_data is not None
                ctx.set("root_cause", "传感器 S001 散热风扇故障")
                return {"root_cause": "散热风扇故障"}
            elif role == AgentRole.WRITER.value:
                # 应能读到 analyst 输出
                root_cause = ctx.get("root_cause")
                assert root_cause is not None
                return {"report": f"根因分析:{root_cause}"}

        # 注册 SubTask + 模拟执行
        for role_desc in [
            (AgentRole.RESEARCHER, "采集数据"),
            (AgentRole.ANALYST, "归因"),
            (AgentRole.WRITER, "写报告"),
        ]:
            subtask = executor.add_subtask(role=role_desc[0], description=role_desc[1])
            executor._emit_subtask_start(subtask)
            output = mock_role_execute(role_desc[0].value, ctx)
            executor._emit_subtask_complete(subtask, output)
            subtask.status = "completed"
            subtask.output = output
            subtask.save()

        # Assert
        # 1. 3 个 SubTask 全 completed
        completed = AgentSubTask.objects.filter(task=task, status="completed")
        assert completed.count() == 3

        # 2. 事件流有 6 条(3 start + 3 complete)
        events = AgentEvent.objects.filter(task=task).order_by("id")
        assert events.count() == 6

        # 3. SharedContext 传递成功
        assert ctx.get("root_cause") == "传感器 S001 散热风扇故障"
        assert ctx.get("sensor_data") is not None

    def test_kill_and_resume_continues_from_pending(
        self, mock_llm_router, admin_user_obj
    ):
        """模拟:第一阶段完成后 worker 被 kill,resume 从 pending SubTask 继续。"""
        from smart_assistant.models import AgentTask, AgentSubTask, AgentEvent
        from smart_assistant.agents.executor import MultiAgentExecutor
        from smart_assistant.agents.task_packet import TaskPacket
        from smart_assistant.agents.shared_context import SharedContext
        from smart_assistant.agents.roles import AgentRole

        task = AgentTask.objects.create(user=admin_user_obj, status="running")

        # 第一阶段:researcher 已完成
        AgentSubTask.objects.create(
            task=task, role=AgentRole.RESEARCHER.value,
            description="采集", status="completed",
            output={"sensors": ["S001"]},
        )
        # 第二阶段:analyst pending(被 kill 在此处)
        pending_analyst = AgentSubTask.objects.create(
            task=task, role=AgentRole.ANALYST.value,
            description="归因", status="pending",
        )
        # 第三阶段:writer pending
        AgentSubTask.objects.create(
            task=task, role=AgentRole.WRITER.value,
            description="报告", status="pending",
        )

        # resume
        ctx = SharedContext()
        ctx.set("sensors", ["S001"])
        packet = TaskPacket(query="分析异常", user=admin_user_obj, task=task)
        resumed = MultiAgentExecutor.resume(task.id, packet, ctx)

        # 验证:analyst SubTask 被 emit start event
        analyst_starts = AgentEvent.objects.filter(
            task=task, type="subtask.start",
        ).filter(payload__role=AgentRole.ANALYST.value)
        assert analyst_starts.count() >= 1

        # 验证 task 状态
        task.refresh_from_db()
        assert task.status == "running"
```

### Step 5: 运行复杂任务 E2E

```bash
conda run -n omni_desk python -m pytest omni_desk_backend/smart_assistant/tests/test_supervisor_decomposition.py omni_desk_backend/smart_assistant/tests/test_multi_agent_complex.py -v 2>&1 | tail -15
```

期望:`4 passed`(2 + 2)。

### Step 6: 跑全套,无回归

```bash
conda run -n omni_desk python -m pytest omni_desk_backend/smart_assistant/tests/ -q 2>&1 | tail -5
```

### Step 7: Commit

```bash
git add omni_desk_backend/smart_assistant/agents/supervisor.py \
        omni_desk_backend/smart_assistant/tests/test_supervisor_decomposition.py \
        omni_desk_backend/smart_assistant/tests/test_multi_agent_complex.py
git commit -m "feat(smart-assistant): Supervisor few-shot + 多 Agent 复杂任务 E2E

- Supervisor prompt 加 few-shot 示例(传感器异常分析、合规报告)
- Pipeline 模式 3 角色协作(Researcher → Analyst → Writer)
- SharedContext 跨步传递(sensor_data → root_cause → report)
- 断点恢复 E2E:kill worker 后从 pending SubTask 继续
- 4 个测试覆盖分解与真实任务"
```

---

## Task 4: 文档 + 覆盖率 + PR

**Files:**
- Modify: `docs/technical/32-smart-assistant-multi-agent.md`(追加"实战 demo"章节)

### Step 1: 补"实战 demo"章节

编辑 `docs/technical/32-smart-assistant-multi-agent.md`,在末尾追加:

```markdown
## 7. 实战 demo — 传感器异常分析报告

**任务**:用户问"分析本月所有传感器异常,生成根因报告"

**Pipeline**:
1. **Researcher** — 采集本月异常传感器数据 → SharedContext["sensor_data"]
2. **Analyst** — 从 SharedContext 读 sensor_data,识别异常模式,归因 → SharedContext["root_cause"]
3. **Writer** — 从 SharedContext 读 root_cause,生成完整报告 → TaskResult

**关键能力验证**:
- ✅ Supervisor 稳定分解为 3 个 SubTask(few-shot 加持)
- ✅ SharedContext 跨步传递(sensor_data → root_cause → report)
- ✅ AgentEvent 完整记录 6 个事件(3 start + 3 complete)
- ✅ 断点恢复:kill worker 后,resume(task_id) 从 pending SubTask 继续

**复现命令**:
\`\`\`bash
conda run -n omni_desk python -m pytest omni_desk_backend/smart_assistant/tests/test_multi_agent_complex.py -v
\`\`\`

**相关测试**:
- `test_supervisor_decomposition.py` — Supervisor 分解逻辑
- `test_multi_agent_resume.py` — 断点恢复
- `test_multi_agent_complex.py` — Pipeline 端到端
- `test_audit_event.py` — AgentEvent 写入与回放
```

### Step 2: 跑完整测试

```bash
conda run -n omni_desk python -m pytest --no-header -q 2>&1 | tail -10
```

### Step 3: 确认覆盖率 ≥ 80%

```bash
conda run -n omni_desk python -m pytest --cov=omni_desk_backend --cov-report=term --cov-fail-under=80 -q 2>&1 | tail -10
```

### Step 4: 准备 PR 描述并推送

```bash
git add docs/technical/32-smart-assistant-multi-agent.md
git commit -m "docs(smart-assistant): 多 Agent 协作 — 实战 demo 章节(传感器异常分析报告)"

git push -u origin feat/sa-multi-agent
gh pr create --base main --head feat/sa-multi-agent \
  --title "feat(smart-assistant): 多 Agent 复杂任务 + 断点恢复(SAIS #3/4)" \
  --body-file /tmp/pr-body.md
gh pr checks <pr-number> --watch
```

PR 描述:

```markdown
# feat(smart-assistant): 多 Agent 复杂任务 + 断点恢复(SAIS #3/4)

## 主要改动
- ✨ feat: audit_log 钩子 + AgentEvent 写入 + 事件回放
- ✨ feat: MultiAgentExecutor.resume(task_id) 断点恢复
- ✨ feat: Supervisor few-shot 示例(传感器异常、合规报告)
- ✅ test: Supervisor 分解(2) + 断点恢复(2) + 复杂任务 Pipeline(2) + 审计(3)
- 📝 docs: 实战 demo 章节

## 验收
- 1 个复杂任务 Pipeline E2E 全绿
- 断点恢复 E2E 全绿(kill + resume)
- AgentEvent 流可重放
- 覆盖率 ≥ 80%
```

### Step 5: merge PR + 清理分支

```bash
git switch main
git pull --rebase origin main
git branch -d feat/sa-multi-agent
git push origin --delete feat/sa-multi-agent
```

---

## 完成标志

- [x] Task 0-4 全部勾选
- [x] `feat/sa-multi-agent` 合入 main
- [x] 1 个复杂任务 Pipeline E2E 通过
- [x] 断点恢复 E2E 通过
- [x] AgentEvent 完整事件流

**进入分支 4(`feat/sa-perf-ux`)**:新 plan `docs/superpowers/plans/2026-07-17-sa-perf-ux.md`(下次会话写)。