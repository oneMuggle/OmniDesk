"""评估执行器：逐条用例以对应角色经真实视图 ``/api/smart-assistant/chat/`` 执行。

- 端点与路径：每次 ``run()`` 按目标（端点 + 模型）和路径（native / json）写入
  ``LlmEndpoint`` / ``LlmAppConfig``，并覆盖原生调用开关；
- 工具执行记录：给每个已注册工具的 ``execute`` 包一层，记录工具名、是否 dry-run、是否
  返回数据；故障注入也在这一层完成；
- 写入检测：用例前后对业务表做行数 / 状态快照，任何变化都算真实写入（评估从不点确认）；
- 隔离：强制本地内存缓存、Celery 就地执行；每条用例前清缓存与路由单例。
"""

from __future__ import annotations

import json
import time
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass, field
from decimal import Decimal

from django.core.cache import cache
from django.db import connection
from django.test.utils import override_settings

from smart_assistant.hooks import base as hooks_base
from smart_assistant.hooks.wiring import register_builtin_hooks

from observability import get_logger

from .llm import LlmRecorder, ScriptedLLM, intercept_llm
from .scoring import CaseResult, ToolExec, score_case

logger = get_logger(__name__, "smart_assistant")

CHAT_URL = "/api/smart-assistant/chat/"
PATHS = ("native", "json")
PATH_LABELS = {
    "native": "原生函数调用（全员开放时）",
    "json": "旧 JSON 路径（未开放时普通员工走这条）",
}
FAULT_ERROR_MESSAGE = "评估注入的依赖故障"

_ISOLATED_CACHES = {
    "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "ai-eval"},
    "ratelimit": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "ai-eval-rl"},
}


@dataclass(frozen=True)
class Target:
    """被评估的端点 + 模型。"""

    name: str
    base_url: str
    model: str
    api_key: str = ""
    cost_per_1k: Decimal = Decimal("0")

    @classmethod
    def scripted(cls) -> Target:
        return cls(name="scripted", base_url="https://llm.eval.invalid", model="scripted-model")


@dataclass
class _ExecLog:
    items: list = field(default_factory=list)


def _context_flags(args, kwargs) -> tuple[bool, bool]:
    ctx = kwargs.get("context")
    if ctx is None and len(args) > 1:
        ctx = args[1]
    if isinstance(ctx, dict):
        return bool(ctx.get("dry_run")), bool(ctx.get("confirmed") or ctx.get("replay"))
    return bool(getattr(ctx, "dry_run", False)), bool(getattr(ctx, "confirmed", False) or getattr(ctx, "replay", False))


@contextmanager
def capture_tools(log: _ExecLog, fault_ref: dict):
    """给每个已注册工具的 ``execute`` 包一层：记录执行，并按 ``fault_ref['fault']`` 注入故障。"""
    from smart_assistant.hooks.builtin.timeout_guard import build_timeout_result
    from smart_assistant.tools.registry import ToolRegistry

    patched = []
    for name, tool in list(ToolRegistry._tools.items()):
        original = tool.execute
        had_instance_attr = "execute" in tool.__dict__

        def wrapper(*args, _orig=original, _tool=tool, _name=name, **kwargs):
            dry_run, confirmed = _context_flags(args, kwargs)
            entry = ToolExec(
                name=_name,
                write=bool(getattr(_tool, "require_confirmation", False))
                or getattr(_tool, "risk_level", "read") != "read",
                dry_run=dry_run,
                confirmed=confirmed,
            )
            log.items.append(entry)
            fault = fault_ref.get("fault")
            if fault is not None and fault.tool == _name:
                entry.fault = fault.kind
                if fault.kind == "timeout":
                    entry.found = False
                    return build_timeout_result(_name, 10)
                raise RuntimeError(FAULT_ERROR_MESSAGE)
            try:
                result = _orig(*args, **kwargs)
            except Exception as exc:
                entry.error = type(exc).__name__
                raise
            entry.found = bool(result.get("found")) if isinstance(result, dict) else None
            return result

        tool.execute = wrapper
        patched.append((tool, original, had_instance_attr))
    try:
        yield log
    finally:
        for tool, original, had_instance_attr in patched:
            if had_instance_attr:
                tool.execute = original
            else:
                try:
                    del tool.execute
                except AttributeError:
                    pass


def business_snapshot() -> dict:
    """业务表快照：行数 + 关键状态。评估从不点确认，任何变化都说明发生了真实写入。"""
    from communication.models import Post
    from compliance.models import ComplianceIssue
    from events.models import Announcement, ScheduleSwapRequest, Trial
    from meeting_rooms.models import MeetingRoomBooking
    from memos.models import Memo
    from notifications.models import Notification
    from smart_assistant.models import AgentWriteLog

    return {
        "memo": Memo.all_objects.count(),
        "memo_deleted": Memo.all_objects.filter(is_deleted=True).count(),
        "memo_changed": sorted(Memo.all_objects.values_list("id", "title", "is_completed")),
        "booking": MeetingRoomBooking.objects.count(),
        "notification": Notification.objects.count(),
        "notification_read": Notification.objects.filter(is_read=True).count(),
        "swap": sorted(ScheduleSwapRequest.objects.values_list("id", "status")),
        "post": Post.objects.count(),
        "trial": Trial.objects.count(),
        "announcement": Announcement.objects.count(),
        "compliance": sorted(ComplianceIssue.objects.values_list("id", "status")),
        "write_log": AgentWriteLog.objects.count(),
    }


def snapshot_diff(before: dict, after: dict) -> list[str]:
    return [key for key in before if before[key] != after.get(key)]


def configure_target(target: Target, path: str) -> None:
    """把目标端点写入（测试）库：smart_assistant 只保留这一个端点。"""
    from smart_assistant.models import LlmAppConfig, LlmEndpoint

    LlmAppConfig.objects.filter(app_name="smart_assistant").delete()
    endpoint = LlmEndpoint.objects.create(
        name=f"eval-{target.name}",
        api_endpoint=target.base_url,
        api_key=target.api_key,
        is_active=True,
        priority=1,
        model_capabilities=[{"native_tool_calls": path == "native"}],
        cost_per_1k_tokens=target.cost_per_1k,
    )
    LlmAppConfig.objects.create(
        app_name="smart_assistant",
        endpoint=endpoint,
        model_name=target.model,
        is_active=True,
    )


def reset_runtime_state() -> None:
    """清缓存与进程内单例，避免用例之间串味。"""
    from llm_service import router as router_module
    from smart_assistant.budget import policy as budget_policy

    cache.clear()
    router_module._routers.clear()
    budget_policy.invalidate_cache()


@contextmanager
def isolated_runtime(*, tool_timeout: bool | None = None):
    """评估期间的运行环境：本地内存缓存、Celery 就地执行、sqlite 下关闭工具超时线程。"""
    from omni_desk_backend.celery import app as celery_app

    if tool_timeout is None:
        # sqlite 内存库跨线程读不到未提交数据，工具超时线程会误判；其他数据库保持生产行为
        tool_timeout = connection.vendor != "sqlite"
    old_eager = celery_app.conf.task_always_eager
    celery_app.conf.task_always_eager = True
    old_registry = _install_production_hooks()
    try:
        with override_settings(
            CACHES=_ISOLATED_CACHES,
            RATELIMIT_USE_CACHE="ratelimit",
            SMART_ASSISTANT_TOOL_TIMEOUT_ENABLED=tool_timeout,
            USE_NATIVE_TOOL_CALLS=True,
        ):
            yield
    finally:
        celery_app.conf.task_always_eager = old_eager
        hooks_base._REGISTRY = old_registry


def _install_production_hooks():
    """换上一份只含生产内置钩子（确认、限流、预算、超时、脱敏）的全局注册表，返回旧的以便恢复。

    生产由 ``apps.ready()`` 注册；但同一进程里别的测试可能把全局注册表重置为空
    （``get_registry(reset=True)``），那样写工具会不经确认直接执行，门禁结果就不可信。
    """
    old = hooks_base._REGISTRY
    register_builtin_hooks(hooks_base.get_registry(reset=True))
    return old


class EvalRunner:
    """在一个目标端点上跑一批用例。"""

    def __init__(self, world, *, target: Target | None = None, scripted: bool = True):
        self.world = world
        self.target = target or Target.scripted()
        self.scripted = ScriptedLLM(objects=dict(world.objects)) if scripted else None
        self.recorder = LlmRecorder()

    def run(self, cases, *, paths=PATHS, repeat: int = 1, on_result=None) -> list[CaseResult]:
        results: list[CaseResult] = []
        exec_log = _ExecLog()
        fault_ref: dict = {"fault": None}
        with ExitStack() as stack:
            stack.enter_context(intercept_llm(self.recorder, scripted=self.scripted))
            stack.enter_context(capture_tools(exec_log, fault_ref))
            for path in paths:
                configure_target(self.target, path)
                with override_settings(USE_NATIVE_TOOL_CALLS_FOR_ALL=(path == "native")):
                    for case in cases:
                        if path not in case.paths:
                            continue
                        for attempt in range(max(1, repeat)):
                            result = self._run_one(case, path, exec_log, fault_ref, attempt)
                            results.append(result)
                            if on_result is not None:
                                on_result(result)
        return results

    def _run_one(self, case, path, exec_log, fault_ref, attempt) -> CaseResult:
        from rest_framework.test import APIClient

        reset_runtime_state()
        self.recorder.reset()
        exec_log.items = []
        fault_ref["fault"] = case.fault
        if self.scripted is not None:
            self.scripted.set_case(case)

        user = self.world.users[case.persona]
        client = APIClient()
        client.force_authenticate(user=user)
        before = business_snapshot()
        started = time.perf_counter()
        status_code, data, error = 0, {}, ""
        try:
            response = client.post(CHAT_URL, {"query": case.question}, format="json")
            status_code = response.status_code
            try:
                data = response.json()
            except (ValueError, TypeError):
                data = {"raw": getattr(response, "content", b"")[:2000].decode("utf-8", "replace")}
        except Exception as exc:  # 视图层以外的异常也要记录，不中断整批评估
            error = f"{type(exc).__name__}: {exc}"[:300]
            logger.warning("评估用例 %s 执行异常: %s", case.id, error)
        latency_ms = int((time.perf_counter() - started) * 1000)
        after = business_snapshot()
        fault_ref["fault"] = None

        result = CaseResult(
            case_id=case.id,
            category=case.category,
            persona=case.persona,
            path=path,
            target=self.target.name,
            attempt=attempt,
            status_code=status_code,
            response=data if isinstance(data, dict) else {"raw": json.dumps(data, ensure_ascii=False)},
            latency_ms=latency_ms,
            executions=list(exec_log.items),
            llm_calls=list(self.recorder.calls),
            db_changes=snapshot_diff(before, after),
            error=error,
        )
        score_case(result, case, self.world)
        return result
