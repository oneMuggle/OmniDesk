"""S2-2 只读 fanout 测试

覆盖:分层(含 inputs 引用推断依赖)、层内真实并发与并发上限、并发数 1 不开线程、
只读约束(schema 过滤 + 执行时拒绝)、依赖失败 skip / abort、暂停、resume、
执行器分派、Supervisor 接受 fanout、事件总线 / 预算的线程安全。
"""

from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock

import pytest
from django.core.exceptions import ValidationError

from smart_assistant.agents.dataclasses import EventBus, SubTaskResult
from smart_assistant.agents.executor import MultiAgentExecutor
from smart_assistant.agents.fanout import FanoutRunner, build_layers
from smart_assistant.agents.packet import ExecutionMode, SubTask, TaskPacket
from smart_assistant.agents.roles import AgentRole
from smart_assistant.agents.shared_context import SharedContext
from smart_assistant.agents.subtask_runner import SubTaskRunner
from smart_assistant.agents.supervisor import Supervisor
from smart_assistant.tools.base import RISK_LEVEL_READ, RISK_LEVEL_WRITE


# ---------------------------------------------------------------------------
# 辅助
# ---------------------------------------------------------------------------


def _packet(subtasks: list[dict], mode: str = "fanout", synthesis: dict | None = None) -> TaskPacket:
    data = {"objective": "并行查询", "execution_mode": mode, "subtasks": subtasks}
    if synthesis:
        data["final_synthesis"] = synthesis
    return TaskPacket.from_dict(data)


def _st(sid: str, depends_on=None, inputs=None, failure_mode="skip") -> dict:
    return {
        "id": sid,
        "role": "researcher",
        "objective": f"查询 {sid}",
        "inputs": inputs or {},
        "failure_mode": failure_mode,
        "depends_on": depends_on or [],
    }


class RecordingRunner:
    """记录线程与并发峰值的假 SubTaskRunner。"""

    def __init__(self, recorder: dict, delay: float = 0.05, fail_ids: set[str] | None = None):
        self.recorder = recorder
        self.delay = delay
        self.fail_ids = fail_ids or set()

    def run_with_retry(self, subtask: SubTask, ctx: SharedContext) -> SubTaskResult:
        lock = self.recorder["lock"]
        with lock:
            self.recorder["active"] += 1
            self.recorder["peak"] = max(self.recorder["peak"], self.recorder["active"])
            self.recorder["threads"][subtask.id] = threading.current_thread().name
            self.recorder["order"].append(subtask.id)
        time.sleep(self.delay)
        with lock:
            self.recorder["active"] -= 1
        if subtask.id in self.fail_ids:
            return SubTaskResult(subtask_id=subtask.id, role=subtask.role, output={}, status="failed")
        ctx.consume_tokens(1)
        return SubTaskResult(
            subtask_id=subtask.id,
            role=subtask.role,
            output={"value": subtask.id},
            artifacts={"value": subtask.id},
            status="success",
        )


def _recorder() -> dict:
    return {"lock": threading.Lock(), "active": 0, "peak": 0, "threads": {}, "order": []}


def _runner(packet, recorder, max_workers=3, fail_ids=None, paused=lambda: False, context=None):
    persisted: list[str] = []
    runner = FanoutRunner(
        task_packet=packet,
        context=context or SharedContext(packet.objective),
        event_bus=EventBus(),
        runner_factory=lambda: RecordingRunner(recorder, fail_ids=fail_ids),
        max_workers=max_workers,
        is_paused=paused,
        persist_subtask=lambda st, res: persisted.append(st.id),
    )
    return runner, persisted


# ---------------------------------------------------------------------------
# 分层
# ---------------------------------------------------------------------------


class TestBuildLayers:
    def test_independent_subtasks_form_one_layer(self):
        packet = _packet([_st("a"), _st("b"), _st("c")])
        assert [[st.id for st in layer] for layer in build_layers(packet)] == [["a", "b", "c"]]

    def test_depends_on_creates_layers(self):
        packet = _packet([_st("a"), _st("b", depends_on=["a"]), _st("c")])
        assert [[st.id for st in layer] for layer in build_layers(packet)] == [["a", "c"], ["b"]]

    def test_input_reference_is_inferred_as_dependency(self):
        packet = _packet([_st("a"), _st("b", inputs={"rooms": "$a.value"})])
        assert [[st.id for st in layer] for layer in build_layers(packet)] == [["a"], ["b"]]

    def test_unknown_reference_is_ignored(self):
        packet = _packet([_st("a", inputs={"x": "$nobody.field"}), _st("b")])
        assert [[st.id for st in layer] for layer in build_layers(packet)] == [["a", "b"]]

    def test_inferred_cycle_falls_back_to_explicit_dependencies(self):
        packet = _packet([_st("a", inputs={"x": "$b.v"}), _st("b", depends_on=["a"])])
        assert [[st.id for st in layer] for layer in build_layers(packet)] == [["a"], ["b"]]


# ---------------------------------------------------------------------------
# 并发执行
# ---------------------------------------------------------------------------


class TestFanoutRunner:
    def test_same_layer_runs_concurrently_within_limit(self):
        recorder = _recorder()
        packet = _packet([_st("a"), _st("b"), _st("c"), _st("d")])
        runner, persisted = _runner(packet, recorder, max_workers=2)

        results = runner.run()

        assert [r.subtask_id for r in results] == ["a", "b", "c", "d"]  # 按计划顺序收集
        assert all(r.status == "success" for r in results)
        assert recorder["peak"] == 2  # 真并发,且不超过上限
        assert all(name.startswith("agent-fanout") for name in recorder["threads"].values())
        assert persisted == ["a", "b", "c", "d"]
        assert runner._context.get_artifact("c") == {"value": "c"}
        assert runner._context.token_budget_used == 4

    def test_single_worker_runs_inline_without_threads(self):
        recorder = _recorder()
        packet = _packet([_st("a"), _st("b")])
        runner, _ = _runner(packet, recorder, max_workers=1)

        runner.run()

        assert recorder["peak"] == 1
        main = threading.current_thread().name
        assert set(recorder["threads"].values()) == {main}

    def test_later_layer_waits_for_earlier_layer(self):
        recorder = _recorder()
        packet = _packet([_st("a"), _st("b"), _st("c", depends_on=["a", "b"])])
        runner, _ = _runner(packet, recorder)

        results = runner.run()

        assert recorder["order"][-1] == "c"
        assert [r.status for r in results] == ["success", "success", "success"]

    def test_failed_dependency_skips_dependent_subtask(self):
        recorder = _recorder()
        packet = _packet([_st("a"), _st("b", depends_on=["a"], failure_mode="skip")])
        runner, _ = _runner(packet, recorder, fail_ids={"a"})

        results = runner.run()

        assert [r.status for r in results] == ["failed", "skipped"]
        assert "b" not in recorder["order"]

    def test_failed_dependency_with_abort_raises(self):
        recorder = _recorder()
        packet = _packet([_st("a"), _st("b", depends_on=["a"], failure_mode="abort")])
        runner, _ = _runner(packet, recorder, fail_ids={"a"})

        with pytest.raises(RuntimeError, match="依赖失败"):
            runner.run()

    def test_paused_task_skips_remaining_subtasks(self):
        recorder = _recorder()
        packet = _packet([_st("a"), _st("b")])
        runner, _ = _runner(packet, recorder, paused=lambda: True)

        results = runner.run()

        assert [r.status for r in results] == ["skipped", "skipped"]
        assert recorder["order"] == []

    def test_resume_skips_completed_subtasks(self):
        recorder = _recorder()
        packet = _packet([_st("a"), _st("b")])
        context = SharedContext(packet.objective)
        context.completed_subtask_ids.add("a")
        context.add_artifact("a", {"value": "a"})
        runner, _ = _runner(packet, recorder, context=context)

        results = runner.run(resume_mode=True)

        assert recorder["order"] == ["b"]
        assert [r.status for r in results] == ["success", "success"]

    def test_runner_exception_becomes_failed_result(self):
        packet = _packet([_st("a"), _st("b")])

        class Boom:
            def run_with_retry(self, subtask, ctx):
                if subtask.id == "a":
                    raise RuntimeError("boom")
                return SubTaskResult(subtask_id=subtask.id, role=subtask.role, output={}, status="success")

        runner = FanoutRunner(
            task_packet=packet,
            context=SharedContext("q"),
            event_bus=EventBus(),
            runner_factory=Boom,
            max_workers=2,
            is_paused=lambda: False,
            persist_subtask=lambda st, res: None,
        )
        assert [r.status for r in runner.run()] == ["failed", "success"]

    def test_layer_started_event_is_emitted(self):
        recorder = _recorder()
        packet = _packet([_st("a"), _st("b", depends_on=["a"])])
        runner, _ = _runner(packet, recorder)

        runner.run()

        layers = [e.payload for e in runner._event_bus.get_events() if e.event_type == "supervisor.decision"]
        assert layers == [
            {"decision": "fanout_layer", "layer": 0, "subtask_ids": ["a"]},
            {"decision": "fanout_layer", "layer": 1, "subtask_ids": ["b"]},
        ]

    def test_layer_event_type_is_a_known_choice(self):
        from smart_assistant.models import AgentEvent

        assert "supervisor.decision" in dict(AgentEvent.EVENT_TYPE_CHOICES)


# ---------------------------------------------------------------------------
# 只读约束
# ---------------------------------------------------------------------------


class _Tool:
    def __init__(self, name, risk_level):
        self.name = name
        self.intent_type = name
        self.risk_level = risk_level
        self.executed = False

    def validate_arguments(self, args):
        return args


class TestReadOnlyTools:
    def test_write_tool_is_rejected_without_execution(self, monkeypatch):
        write_tool = _Tool("memo_create", RISK_LEVEL_WRITE)
        registry = MagicMock()
        registry.get_tool_for_user.return_value = write_tool
        executed = []
        monkeypatch.setattr(
            "smart_assistant.agents.subtask_runner.execute_native_tool",
            lambda tool, validated, context: executed.append(tool) or ({"ok": True}, None, None),
        )
        runner = SubTaskRunner(
            MagicMock(), EventBus(), 1, tool_registry=registry, user=MagicMock(), read_only_tools=True
        )

        result = runner._execute_tool("memo_create", {"query": "x"}, MagicMock())

        assert result == {"error": "tool_not_allowed_in_fanout"}
        assert executed == []

    def test_read_tool_still_executes(self, monkeypatch):
        read_tool = _Tool("memo_query", RISK_LEVEL_READ)
        registry = MagicMock()
        registry.get_tool_for_user.return_value = read_tool
        monkeypatch.setattr(
            "smart_assistant.agents.subtask_runner.execute_native_tool",
            lambda tool, validated, context: ({"items": 1}, None, None),
        )
        runner = SubTaskRunner(
            MagicMock(), EventBus(), 1, tool_registry=registry, user=MagicMock(), read_only_tools=True
        )

        assert runner._execute_tool("memo_query", {"query": "x"}, MagicMock()) == {"items": 1}

    def test_pipeline_runner_keeps_write_tools(self, monkeypatch):
        write_tool = _Tool("memo_create", RISK_LEVEL_WRITE)
        registry = MagicMock()
        registry.get_tool_for_user.return_value = write_tool
        monkeypatch.setattr(
            "smart_assistant.agents.subtask_runner.execute_native_tool",
            lambda tool, validated, context: ({"ok": True}, None, None),
        )
        runner = SubTaskRunner(MagicMock(), EventBus(), 1, tool_registry=registry, user=MagicMock())

        assert runner._execute_tool("memo_create", {"query": "x"}, MagicMock()) == {"ok": True}

    def test_read_only_runner_requests_read_only_schemas(self, monkeypatch):
        registry = MagicMock()
        registry.get_openai_tools.return_value = []
        captured = {}

        def fake_loop(router, **kwargs):
            captured["tools"] = kwargs["tools"]
            return "done", {}, None, None, None

        monkeypatch.setattr("smart_assistant.agents.subtask_runner.run_tool_call_loop", fake_loop)
        monkeypatch.setattr("smart_assistant.agents.subtask_runner.resolve_scope", lambda user: "self")
        user = MagicMock()
        runner = SubTaskRunner(MagicMock(), EventBus(), 1, tool_registry=registry, user=user, read_only_tools=True)
        subtask = SubTask(id="s1", role=AgentRole.RESEARCHER, objective="查")
        profile = MagicMock(max_tokens=100, temperature=0.1, system_prompt="sys")

        runner._invoke_with_tools(subtask, profile, [{"role": "user", "content": "q"}], None)

        registry.get_openai_tools.assert_called_once_with(user, read_only=True)
        assert captured["tools"] == []


@pytest.mark.django_db
def test_registry_read_only_filter_excludes_write_tools(django_user_model):
    from smart_assistant.tools.registry import ToolRegistry

    user = django_user_model.objects.create_user(username="fanout_reader", password="x")
    all_tools = {t["function"]["name"]: t for t in ToolRegistry.get_openai_tools(user)}
    read_only = {t["function"]["name"] for t in ToolRegistry.get_openai_tools(user, read_only=True)}

    assert read_only
    assert read_only < set(all_tools)
    for name in read_only:
        assert ToolRegistry.get_tool_for_user(name, user).risk_level == RISK_LEVEL_READ
    for name in set(all_tools) - read_only:
        assert ToolRegistry.get_tool_for_user(name, user).risk_level != RISK_LEVEL_READ


# ---------------------------------------------------------------------------
# 执行器与 Supervisor
# ---------------------------------------------------------------------------


class TestExecutorFanout:
    def _executor(self, packet, monkeypatch, recorder, max_workers=3):
        monkeypatch.setattr(MultiAgentExecutor, "_fanout_max_workers", staticmethod(lambda: max_workers))
        executor = MultiAgentExecutor(task_packet=packet, llm_router=MagicMock(), tool_registry=MagicMock())
        executor.fanout_runner._runner_factory = lambda: RecordingRunner(recorder)
        return executor

    def test_fanout_packet_executes_and_synthesizes(self, monkeypatch):
        recorder = _recorder()
        packet = _packet(
            [_st("a"), _st("b")],
            synthesis={"id": "synth", "role": "synthesizer", "objective": "汇总", "depends_on": ["a", "b"]},
        )
        executor = self._executor(packet, monkeypatch, recorder)
        synth = SubTaskResult(subtask_id="synth", role=AgentRole.SYNTHESIZER, output={"x": 1}, status="success")
        monkeypatch.setattr(executor, "_run_subtask_with_retry", lambda st, ctx: synth)

        result = executor.execute()

        assert result.status == "success"
        assert result.final_output == {"x": 1}
        assert [r.subtask_id for r in result.subtask_results] == ["a", "b", "synth"]
        assert recorder["peak"] == 2

    def test_read_only_runner_factory_sets_flag(self):
        packet = _packet([_st("a")])
        executor = MultiAgentExecutor(task_packet=packet, llm_router=MagicMock(), tool_registry=MagicMock())

        first = executor._make_read_only_runner()
        second = executor._make_read_only_runner()

        assert first._read_only_tools is True
        assert first is not second  # 每个子任务独立实例
        assert executor.subtask_runner._read_only_tools is False  # pipeline 不受影响

    def test_resume_dispatches_fanout(self, monkeypatch):
        recorder = _recorder()
        packet = _packet([_st("a"), _st("b")])
        executor = self._executor(packet, monkeypatch, recorder)
        executor.context.completed_subtask_ids.add("a")

        result = executor._execute_resume()

        assert result.status == "success"
        assert recorder["order"] == ["b"]

    def test_max_workers_setting(self, settings):
        settings.SMART_ASSISTANT_FANOUT_MAX_WORKERS = 5
        assert MultiAgentExecutor._fanout_max_workers() == 5
        settings.SMART_ASSISTANT_FANOUT_MAX_WORKERS = "bad"
        assert MultiAgentExecutor._fanout_max_workers() == 1
        settings.SMART_ASSISTANT_FANOUT_MAX_WORKERS = 0
        assert MultiAgentExecutor._fanout_max_workers() == 1


class TestSupervisorFanout:
    def _supervisor(self, mode):
        router = MagicMock()
        router.generate.return_value = (
            '{"objective": "目标", "execution_mode": "%s", '
            '"subtasks": [{"id": "t1", "role": "researcher", "objective": "调研"}]}' % mode
        )
        return Supervisor(llm_router=router)

    def test_fanout_packet_accepted(self):
        packet = self._supervisor("fanout").generate_task_packet(query="同时查排班和会议室")
        assert packet.execution_mode == ExecutionMode.FANOUT

    def test_hierarchical_still_rejected(self):
        with pytest.raises(ValidationError, match="hierarchical mode not yet implemented"):
            self._supervisor("hierarchical").generate_task_packet(query="x")

    def test_prompt_explains_fanout_is_read_only(self):
        prompt = self._supervisor("fanout")._build_system_prompt()
        assert "fanout" in prompt and "只读" in prompt


# ---------------------------------------------------------------------------
# 线程安全
# ---------------------------------------------------------------------------


def test_event_bus_and_budget_are_thread_safe():
    bus = EventBus()
    ctx = SharedContext("q", global_budget=10**9)

    def work():
        for _ in range(500):
            bus.emit("x", {})
            ctx.consume_tokens(1)

    threads = [threading.Thread(target=work) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(bus.get_events()) == 4000
    assert ctx.token_budget_used == 4000


def test_fanout_final_synthesis_uses_read_only_runner(monkeypatch):
    packet = _packet(
        [_st("a")],
        synthesis={"id": "synth", "role": "synthesizer", "objective": "汇总", "depends_on": ["a"]},
    )
    executor = MultiAgentExecutor(task_packet=packet, llm_router=MagicMock(), tool_registry=MagicMock())
    seen = []

    def fake_run(self, subtask, ctx):
        seen.append((subtask.id, self._read_only_tools))
        return SubTaskResult(subtask_id=subtask.id, role=subtask.role, output={"ok": 1}, status="success")

    monkeypatch.setattr(SubTaskRunner, "run_with_retry", fake_run)

    result = executor.execute()

    assert result.status == "success"
    assert seen == [("a", True), ("synth", True)]


def test_pipeline_final_synthesis_keeps_full_runner(monkeypatch):
    packet = _packet(
        [_st("a")],
        mode="pipeline",
        synthesis={"id": "synth", "role": "synthesizer", "objective": "汇总", "depends_on": ["a"]},
    )
    executor = MultiAgentExecutor(task_packet=packet, llm_router=MagicMock(), tool_registry=MagicMock())
    seen = []

    def fake_run(self, subtask, ctx):
        seen.append((subtask.id, self._read_only_tools))
        return SubTaskResult(subtask_id=subtask.id, role=subtask.role, output={"ok": 1}, status="success")

    monkeypatch.setattr(SubTaskRunner, "run_with_retry", fake_run)

    executor.execute()

    assert seen == [("a", False), ("synth", False)]
