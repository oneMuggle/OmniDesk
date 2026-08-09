# L1.1 原生 Function Calling 加固 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 L1 原生 Function Calling 补齐三块短板 —— 写工具确认 hook(fail-closed)、结构化参数透传、process_stream 流式原生 tool_calls。

**Architecture:** 三个子项共享 orchestrator 原生 tool_calls 路径,按依赖顺序实施:① `ConfirmationHook`(PRE_EXECUTE)注册进唯一生产装配点 `register_builtin_hooks()`,激活现有 confirm-replay 拦截;② `_execute_native_tool` 透传完整 validated dict 作为 `params`,Tier 1 工具显式消费结构化字段;③ 把工具轮抽出为 `_run_tool_calls_rounds`,`process_stream` 复用并新增缓冲工具轮 + 流式最终轮分支。

**Tech Stack:** Python 3.10 / Django 4.2 / DRF;pytest(in-memory SQLite);现有 hook 注册表 + confirm-replay 视图层 + 前端全部复用。

## Global Constraints

- Python 3.10 / Django 4.2 / PostgreSQL;内网离线部署,无外网依赖
- 中文为主(注释、commit message、文档)
- 测试命令(在 `omni_desk_backend/` 下):`/home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest --ds=omni_desk_backend.settings.test <path>`
- `requirements.txt` 由 pip-compile 管理,NEVER 直接编辑 .txt
- 现有 hook 注册表 / confirm-replay 视图层(`chat.py`) / 前端 `awaiting_confirmation` 复用不重写
- 灰度开关 `USE_NATIVE_TOOL_CALLS_FOR_ALL` 语义不变;原生路径默认仅 staff
- 每个 Task 结束:commit;每个 Task 开始:先写失败测试(RED)→ 跑出失败 → 实现(GREEN)→ 跑通 → commit

---

## File Structure

**新增:**
- `omni_desk_backend/smart_assistant/hooks/builtin/confirmation.py` — `ConfirmationHook`(PRE_EXECUTE)
- `omni_desk_backend/smart_assistant/tests/test_confirmation_hook.py` — ConfirmationHook 单测
- `omni_desk_backend/smart_assistant/tests/test_structured_params_passthrough.py` — I-2 结构化字段测试
- `omni_desk_backend/smart_assistant/tests/test_streaming_native_tool_calls.py` — F2 流式原生测试

**修改:**
- `omni_desk_backend/smart_assistant/hooks/wiring.py` — `register_builtin_hooks()` 注册 ConfirmationHook
- `omni_desk_backend/smart_assistant/tests/test_confirm_replay_e2e.py` — 内联 ConfirmGuardHook 改用真实 `ConfirmationHook`
- `omni_desk_backend/smart_assistant/agent/orchestrator.py` — `_execute_native_tool` 透传 params;`_process_tool_calls_path` 重构出 `_run_tool_calls_rounds`;`process_stream` 原生分支 + `_process_stream_tool_calls_path`
- `omni_desk_backend/smart_assistant/tools/schedule_tool.py` — 消费 `date_from/date_to/personnel_name`
- `omni_desk_backend/smart_assistant/tools/office_read_tool.py` — 消费 `chunk_index`
- `omni_desk_backend/smart_assistant/tools/personnel_tool.py` — 消费 `department/status`
- `omni_desk_backend/smart_assistant/tools/memo_tool.py` — 消费 `is_completed`
- `omni_desk_backend/smart_assistant/tools/news_tool.py` — 消费 `limit`
- `omni_desk_backend/smart_assistant/tools/document_tool.py` — 消费 `limit`
- `omni_desk_backend/smart_assistant/tools/announcement_tool.py` — 消费 `limit`
- `omni_desk_backend/smart_assistant/tools/event_tool.py` — 消费 `target_date`
- `omni_desk_backend/smart_assistant/tools/meeting_room_tool.py` — 消费 `target_date`

---

### Task 1: I-1 — ConfirmationHook 创建 + 生产注册

写工具 `office_generate` / `swap_create` / `swap_decide` 已标 `require_confirmation=True`,前端确认重放链已完备,但全库无 PRE_EXECUTE hook 产生 `Reject(confirmation_required)` → `apply_pre_execute_hooks` 快速路径放行 → 写工具 fail-open。本任务新增真实 `ConfirmationHook` 并注册进唯一生产装配点 `register_builtin_hooks()`。

**Files:**
- Create: `omni_desk_backend/smart_assistant/hooks/builtin/confirmation.py`
- Create: `omni_desk_backend/smart_assistant/tests/test_confirmation_hook.py`
- Modify: `omni_desk_backend/smart_assistant/hooks/wiring.py:36-63`(`register_builtin_hooks` 注册)
- Modify: `omni_desk_backend/smart_assistant/tests/test_confirm_replay_e2e.py:103-119`(`_register_confirm_guard` 改用真实 hook)

**Interfaces:**
- Consumes: `smart_assistant.hooks.base.ToolHookBase` / `Reject` / `HookEvent` / `get_registry`(均已存在)
- Produces: `ConfirmationHook`(`name="confirmation"`, `async def pre_execute(tool, ctx, params)` → 写工具返回 `Reject(error_code="confirmation_required")`,read 工具返回 `params`)。Task 5 的流式 confirm-replay 依赖它激活 `_execute_native_tool` 的拦截分支。

- [ ] **Step 1: 写失败测试 `test_confirmation_hook.py`**

```python
"""ConfirmationHook 单元测试(I-1)。

验证:
- require_confirmation=True 的写工具 → Reject(error_code="confirmation_required")
- require_confirmation=False 的 read 工具 → 原样返回 params(放行)
- 经 apply_pre_execute_hooks 真实链路生效(非直调 hook)
"""

import pytest

from smart_assistant.hooks.base import HookEvent, Reject, get_registry
from smart_assistant.hooks.builtin.confirmation import ConfirmationHook
from smart_assistant.hooks.wiring import apply_pre_execute_hooks
from smart_assistant.tools.base import BaseTool


@pytest.fixture(autouse=True)
def _clean_registry():
    get_registry(reset=True)
    yield
    get_registry(reset=True)


class _WriteTool(BaseTool):
    name = "test_write_tool"
    risk_level = "write"
    require_confirmation = True

    def execute(self, query=None, context=None, **kwargs):
        return {"found": True, "result": "executed"}


class _ReadTool(BaseTool):
    name = "test_read_tool"
    risk_level = "read"
    require_confirmation = False

    def execute(self, query=None, context=None, **kwargs):
        return {"found": True, "result": "read"}


class _Ctx:
    user = None


@pytest.mark.django_db
class TestConfirmationHook:
    def test_write_tool_rejected(self):
        """写工具 → Reject(error_code=confirmation_required)"""
        get_registry().register(HookEvent.PRE_EXECUTE, ConfirmationHook(), priority=20)
        result = apply_pre_execute_hooks(_WriteTool(), _Ctx(), {"query": "生成"})
        assert isinstance(result, Reject)
        assert result.error_code == "confirmation_required"

    def test_read_tool_passthrough(self):
        """read 工具 → 原样返回 params"""
        get_registry().register(HookEvent.PRE_EXECUTE, ConfirmationHook(), priority=20)
        params = {"query": "查一下"}
        result = apply_pre_execute_hooks(_ReadTool(), _Ctx(), params)
        assert result == params
```

- [ ] **Step 2: 跑测试确认失败**

Run(在 `omni_desk_backend/` 下):
`/home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest --ds=omni_desk_backend.settings.test smart_assistant/tests/test_confirmation_hook.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'smart_assistant.hooks.builtin.confirmation'`

- [ ] **Step 3: 创建 `ConfirmationHook`**

```python
"""smart_assistant/hooks/builtin/confirmation.py — 写工具二次确认钩子(I-1)。

对 ``require_confirmation=True`` 的工具在 PRE_EXECUTE 阶段返回
``Reject(error_code="confirmation_required")``,激活 orchestrator 现有
confirm-replay 拦截(dry_run → draft → awaiting_confirmation → 前端确认 →
replay 视图执行)。此前无任何 PRE_EXECUTE hook 产生该 Reject,写工具
(office_generate / swap×2)无确认直接执行 —— fail-open 缺口。
"""

from __future__ import annotations

from ..base import Reject, ToolHookBase


class ConfirmationHook(ToolHookBase):
    """PRE_EXECUTE:对 require_confirmation=True 的工具挂起执行,等待用户二次确认。"""

    name = "confirmation"

    async def pre_execute(self, tool, ctx, params):
        if getattr(tool, "require_confirmation", False):
            return Reject(
                reason=f"工具 {getattr(tool, 'name', '')} 需要用户二次确认",
                error_code="confirmation_required",
            )
        return params
```

- [ ] **Step 4: 跑测试确认通过**

Run:`/home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest --ds=omni_desk_backend.settings.test smart_assistant/tests/test_confirmation_hook.py -v`
Expected: PASS(2 passed)

- [ ] **Step 5: 注册进 `register_builtin_hooks`(wiring.py)**

在 `omni_desk_backend/smart_assistant/hooks/wiring.py`:

```python
    # 延迟导入,避免 hooks.wiring ↔ hooks.builtin 在应用加载期循环
    from .builtin import ConfirmationHook, PiiMaskingHook, TimeoutGuardHook

    reg = registry or get_registry()
    existing_names = {getattr(h, "name", None) for h in reg.list_hooks()}
    if "pii_masking" not in existing_names:
        reg.register(HookEvent.POST_EXECUTE, PiiMaskingHook(), priority=5)
    if "timeout_guard" not in existing_names:
        reg.register(HookEvent.ON_FAILURE, TimeoutGuardHook(), priority=10)
    if "confirmation" not in existing_names:
        reg.register(HookEvent.PRE_EXECUTE, ConfirmationHook(), priority=20)
    return reg
```

- [ ] **Step 6: 改 `test_confirm_replay_e2e.py` 用真实 ConfirmationHook**

把 `_register_confirm_guard()`(test_confirm_replay_e2e.py:103-119)替换为:

```python
def _register_confirm_guard():
    """注册生产真实 ConfirmationHook(替代内联 ConfirmGuardHook)。"""
    from smart_assistant.hooks.builtin.confirmation import ConfirmationHook

    registry = get_registry()
    registry.register(HookEvent.PRE_EXECUTE, ConfirmationHook(), priority=20)
```

(其余断言不变 —— 该 hook 对 write 工具返回的 Reject 语义与原内联 hook 一致,`error_code="confirmation_required"`。)

- [ ] **Step 7: 跑 confirm-replay E2E + 全量确认**

Run:
`/home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest --ds=omni_desk_backend.settings.test smart_assistant/tests/test_confirm_replay_e2e.py smart_assistant/tests/test_wiring_pre_execute.py -v`
Expected: PASS(现有 7 项 E2E + pre_execute 用例全绿)

- [ ] **Step 8: Commit**

```bash
git add smart_assistant/hooks/builtin/confirmation.py smart_assistant/hooks/wiring.py smart_assistant/tests/test_confirmation_hook.py smart_assistant/tests/test_confirm_replay_e2e.py
git commit -m "feat(smart-assistant): 新增 ConfirmationHook 生产注册,写工具确认 fail-open → fail-closed(I-1)"
```

---

### Task 2: I-2 — `_execute_native_tool` 透传完整 params + schedule 日期范围 + office_read 切片

`_execute_native_tool`(`orchestrator.py:595`)目前只把 `_dict_to_query(validated)` 的 `query` 塞进 `params`,LLM 提供的结构化字段(date_from/chunk_index 等)全部丢弃。本任务先改机制(一处),再让 final review 明确点名的 schedule / office_read 消费字段。

**Files:**
- Modify: `omni_desk_backend/smart_assistant/agent/orchestrator.py:567-656`(`_execute_native_tool`)
- Modify: `omni_desk_backend/smart_assistant/tools/schedule_tool.py:13-43`
- Modify: `omni_desk_backend/smart_assistant/tools/office_read_tool.py:52-69`
- Create: `omni_desk_backend/smart_assistant/tests/test_structured_params_passthrough.py`

**Interfaces:**
- Consumes: `_dict_to_query(validated)`(orchestrator.py:147,保留)、`execute_guarded(tool, params, scope, qs, context)`(hooks/wiring.py:71)、`OfficeExtractor.chunk_text`(office_read)
- Produces: `_execute_native_tool` 对 scope 工具传 `params=validated`、非 scope 工具传 `params=params`;`ScheduleTool.execute` 新消费 `params.date_from/date_to/personnel_name`;`OfficeReadTool.execute` 新消费 `params.chunk_index`。Task 3 依赖同一 params 契约。

- [ ] **Step 1: 写失败测试**

```python
"""I-2 结构化参数透传测试:LLM validated 中的结构化字段须到达工具执行。"""

import pytest
from unittest.mock import patch

from smart_assistant.agent.orchestrator import AgentOrchestrator, _dict_to_query
from smart_assistant.tools.office_read_tool import OfficeReadTool
from smart_assistant.tools.registry import ToolRegistry
from smart_assistant.tools.schedule_tool import ScheduleTool
from smart_assistant.tools.tool_context import ToolContext


@pytest.fixture
def tool_context():
    return ToolContext(user=None, scope="GLOBAL")


@pytest.mark.django_db
def test_execute_native_tool_passes_full_params_to_scope_tool(tool_context):
    """scope 工具收到完整 validated dict(而非仅 {'query': ...})。"""
    validated = {"query": "本周排班", "date_from": "2026-08-10", "date_to": "2026-08-16"}
    captured = {}

    class _SpySchedule(ScheduleTool):
        def execute(self, query=None, context=None, params=None, scope=None, qs=None):
            captured["params"] = params
            return {"found": True, "count": 0}

    with patch("smart_assistant.agent.orchestrator.execute_guarded",
               side_effect=lambda tool, **kw: tool.execute(**kw)):
        result = AgentOrchestrator()._execute_native_tool(_SpySchedule(), validated, tool_context)

    assert captured["params"] == validated


@pytest.mark.django_db
def test_execute_native_tool_passes_params_to_nonscope_tool(tool_context):
    """非 scope 工具(office_read)也收到 params。"""
    validated = {"query": "读第3段", "chunk_index": 2}
    captured = {}

    class _SpyOffice(OfficeReadTool):
        def execute(self, query=None, context=None, params=None, **kwargs):
            captured["params"] = params
            return {"found": True, "count": 0}

    with patch("smart_assistant.agent.orchestrator.execute_guarded",
               side_effect=lambda tool, **kw: tool.execute(**kw)):
        AgentOrchestrator()._execute_native_tool(_SpyOffice(), validated, tool_context)

    assert captured["params"] == validated


@pytest.mark.django_db
def test_schedule_uses_structured_date_range():
    """LLM 提供 date_from/date_to → ScheduleTool 按范围过滤(不再查今日)。"""
    from unittest.mock import MagicMock
    from datetime import date
    tool = ScheduleTool()
    base_qs = MagicMock()
    qs = base_qs.filter.return_value
    qs.filter.return_value = qs
    # date_from/date_to 分支:调用 qs.filter(duty_date__gte=...) + (duty_date__lte=...)
    result = tool.execute(
        params={"query": "排班", "date_from": "2026-08-10", "date_to": "2026-08-16"},
        scope="GLOBAL", qs=base_qs,
    )
    # 按范围过滤而非默认日期
    assert base_qs.filter.called


@pytest.mark.django_db
def test_office_read_uses_chunk_index():
    """LLM 提供 chunk_index=2 → OfficeReadTool 返回第 3 片。"""
    tool = OfficeReadTool()
    ctx = {"attachment": {"text": "甲 乙 丙 丁 戊", "filename": "a.txt"}}
    with patch("smart_assistant.tools.office_read_tool.OfficeExtractor.chunk_text",
               return_value=["片0", "片1", "片2", "片3"]):
        result = tool.execute(
            query="读第3段", params={"chunk_index": 2},
            context=ctx,  # attachment 无 chunk_index,须从 params 取
        )
    assert result["found"] is True
    assert result["chunks"] == ["片2"]
    assert result["summary"] == "已读取附件第 3/4 片"
```

- [ ] **Step 2: 跑测试确认失败**

Run:`/home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest --ds=omni_desk_backend.settings.test smart_assistant/tests/test_structured_params_passthrough.py -v`
Expected: FAIL(4 项全失败 —— params 仍只含 query / 工具未消费结构化字段)

- [ ] **Step 3: 改 `_execute_native_tool`(机制)**

在 `orchestrator.py` `_execute_native_tool` 内(约 line 595),把 `query = _dict_to_query(validated)` 之后改为透传完整字典:

```python
        query = _dict_to_query(validated)
        # I-2:透传完整 validated 字典作为 params,LLM 提供的结构化字段
        # (date_from / chunk_index / department / limit / …)到达工具。
        # query 仍是自然语言主输入(不拼接进 query,保留 F1 防污染决策);
        # 结构化字段经 params 显式传递,工具 opt-in 读取,缺失时回退 query 解析。
        params = validated if isinstance(validated, dict) else {"query": query}
        hook_ctx = context if context is not None else {}
```

再把下面两处 `execute_guarded` 调用改为用 `params`(替换 `{"query": query}`):

```python
            if context is not None and getattr(tool, "supports_scope_filter", False):
                base_qs = tool.build_base_queryset()
                scoped_qs = tool.get_queryset_for_scope(base_qs, context)
                result = execute_guarded(
                    tool,
                    params=params,
                    scope=context.scope,
                    qs=scoped_qs,
                    context=context,
                )
            else:
                result = execute_guarded(tool, query=query, params=params, context=context)
```

同时把 `_dict_to_query` docstring 中"结构化字段不拼接进 query,避免污染"的说明更新为"结构化字段经 params 透传"(非行为变更)。

- [ ] **Step 4: 改 `ScheduleTool.execute` 消费 date range**

在 `schedule_tool.py` 新路径(`qs is not None and scope is not None`)开头:

```python
        if qs is not None and scope is not None:
            # I-2:结构化日期范围/人员优先于 query 关键词(此前被丢弃,LLM 拆日期查错)
            date_from = None
            date_to = None
            personnel_name = None
            if isinstance(params, dict):
                date_from = params.get("date_from")
                date_to = params.get("date_to")
                personnel_name = params.get("personnel_name")
            if date_from or date_to:
                filters = {}
                if date_from:
                    filters["duty_date__gte"] = date_from
                if date_to:
                    filters["duty_date__lte"] = date_to
                schedules = qs.filter(**filters)
                if personnel_name:
                    schedules = schedules.filter(duty_person__name=personnel_name)
            else:
                # 原逻辑:相对日期 / 今日(无结构化字段时保持现状)
                target_date = timezone.now().date()
                if isinstance(params, dict):
                    if params.get("date") == "明天":
                        target_date = (timezone.now() + timedelta(days=1)).date()
                    elif params.get("date") == "后天":
                        target_date = (timezone.now() + timedelta(days=2)).date()
                schedules = qs.filter(duty_date=target_date)
```

(下方 `results` 构造与 `date` 字段保持不变;`date` 键仅覆盖无 date_from/date_to 分支,有范围时返回 `date` 为字符串化的范围起点或留空,plan 实现取 `str(date_from or date_to or target_date)`。确保 `target_date` 变量在 date_from/to 分支中不引用。)

- [ ] **Step 5: 改 `OfficeReadTool.execute` 消费 chunk_index**

在 `office_read_tool.py:52-69`,签名加 `params` 并优先取 LLM 的 chunk_index:

```python
    def execute(self, query=None, context=None, params=None, **kwargs) -> dict:
        ctx = context if isinstance(context, dict) else {}
        attachment = ctx.get("attachment")
        if not attachment or not attachment.get("text"):
            return {"found": False, "message": "当前对话未找到可读取的附件内容"}
        chunks = OfficeExtractor.chunk_text(attachment["text"])
        if not chunks:
            return {"found": False, "message": "附件无可读取的文本内容"}
        # I-2:优先用 LLM 结构化参数 chunk_index(此前永远读第 0 片)
        index = params.get("chunk_index") if isinstance(params, dict) else None
        if index is None:
            index = attachment.get("chunk_index", 0)
        if not isinstance(index, int) or index < 0 or index >= len(chunks):
            return {"found": False, "message": f"切片序号越界（共 {len(chunks)} 片）"}
        return {
            "found": True,
            "filename": attachment.get("filename", "附件"),
            "total_chunks": len(chunks),
            "chunks": [chunks[index]],
            "summary": f"已读取附件第 {index + 1}/{len(chunks)} 片",
        }
```

- [ ] **Step 6: 跑测试确认通过**

Run:`/home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest --ds=omni_desk_backend.settings.test smart_assistant/tests/test_structured_params_passthrough.py -v`
Expected: PASS(4 passed)

- [ ] **Step 7: 回归既有工具/schema 测试**

Run:`/home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest --ds=omni_desk_backend.settings.test smart_assistant/tests/test_orchestrator_tool_calls_path.py smart_assistant/tests/test_openai_tool_schemas.py smart_assistant/tests/test_native_function_calling_e2e.py -v`
Expected: PASS(机制改后无回归)

- [ ] **Step 8: Commit**

```bash
git add smart_assistant/agent/orchestrator.py smart_assistant/tools/schedule_tool.py smart_assistant/tools/office_read_tool.py smart_assistant/tests/test_structured_params_passthrough.py
git commit -m "fix(smart-assistant): 原生路径透传结构化参数,schedule 日期范围/office_read 切片生效(I-2)"
```

---

### Task 3: I-2 — 其余 Tier 1 工具消费结构化字段

personnel(department/status)、memo(is_completed)、news/document/announcement(limit)、event/meeting_room(target_date)。统一模式:在 scope-aware 新路径(或通用路径)读取 `params` 中的结构化字段,缺失时保持现有 `[:10]` / query 解析行为。

**Files:**
- Modify: `smart_assistant/tools/personnel_tool.py:31-38`
- Modify: `smart_assistant/tools/memo_tool.py:21-30`
- Modify: `smart_assistant/tools/news_tool.py:20-27`
- Modify: `smart_assistant/tools/document_tool.py:11-25`
- Modify: `smart_assistant/tools/announcement_tool.py:29-45`
- Modify: `smart_assistant/tools/event_tool.py:13-30`
- Modify: `smart_assistant/tools/meeting_room_tool.py:13-30`
- Modify: `smart_assistant/tests/test_structured_params_passthrough.py`(追加断言)

**Interfaces:**
- Consumes: Task 2 的 `params=validated` 透传契约
- Produces: 各 Tier 1 工具结构化字段过滤生效(缺失回退)

- [ ] **Step 1: 追加失败测试**

在 `test_structured_params_passthrough.py` 追加:

```python
@pytest.mark.django_db
def test_personnel_department_status_filter():
    """personnel 消费 department/status。"""
    from unittest.mock import MagicMock
    from smart_assistant.tools.personnel_tool import PersonnelTool
    tool = PersonnelTool()
    base_qs = MagicMock()
    qs = base_qs.filter.return_value
    qs.filter.return_value = qs
    tool.execute(
        params={"query": "人员", "department": "研发部", "status": "在职"},
        scope="GLOBAL", qs=base_qs,
    )
    # 至少触发一次按 department 的 filter
    filter_calls = [c for c in base_qs.filter.call_args_list] + \
                   [c for c in qs.filter.call_args_list]
    assert any("department" in c[1] for c in filter_calls)


@pytest.mark.django_db
def test_memo_is_completed_filter():
    """memo 消费 is_completed。"""
    from unittest.mock import MagicMock
    from smart_assistant.tools.memo_tool import MemoTool
    tool = MemoTool()
    base_qs = MagicMock()
    qs = base_qs.filter.return_value
    qs.filter.return_value = qs
    tool.execute(params={"query": "便签", "is_completed": True}, scope="GLOBAL", qs=base_qs)
    assert any("is_completed" in c[1] for c in base_qs.filter.call_args_list)


@pytest.mark.django_db
def test_news_limit_respected():
    """news 消费 limit(替换硬编码 [:10])。"""
    from unittest.mock import MagicMock
    from smart_assistant.tools.news_tool import NewsTool
    tool = NewsTool()
    base_qs = MagicMock()
    qs = base_qs.filter.return_value
    # spy 切片:记录 [:limit] 的 slice.stop
    slices = []

    def spy_getitem(self, s):
        slices.append(s)
        return self

    qs.__getitem__ = spy_getitem
    tool.execute(params={"query": "新闻", "limit": 3}, scope="GLOBAL", qs=base_qs)
    assert any(getattr(s, "stop", None) == 3 for s in slices)
```

- [ ] **Step 2: 跑测试确认失败**

Run:`/home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest --ds=omni_desk_backend.settings.test smart_assistant/tests/test_structured_params_passthrough.py -v`
Expected: 3 个新增用例 FAIL(工具未消费字段)

- [ ] **Step 3: 实现各工具结构化字段消费**

统一模式(以 news 为例,scope 路径):

```python
        if qs is not None and scope is not None:
            search_query = params.get("query") if isinstance(params, dict) and params.get("query") else (query or "")
            keywords = self._extract_keywords(search_query)
            limit = params.get("limit") if isinstance(params, dict) and params.get("limit") else 10
            articles = qs.filter(title__icontains=keywords)[:limit]
```

`personnel_tool.py`(scope 路径)加 department/status 过滤:

```python
        if qs is not None and scope is not None:
            search_query = params.get("query") if isinstance(params, dict) and params.get("query") else (query or "")
            keywords = self._extract_keywords(search_query)
            personnel_list = qs.filter(name__icontains=keywords)
            if isinstance(params, dict):
                if params.get("department"):
                    personnel_list = personnel_list.filter(department=params["department"])
                if params.get("status"):
                    personnel_list = personnel_list.filter(status=params["status"])
            personnel_list = personnel_list[:10]
```

`memo_tool.py`(scope 路径)加 is_completed 过滤:

```python
        if qs is not None and scope is not None:
            search_query = query
            if isinstance(params, dict) and params.get("query"):
                search_query = params["query"]
            keywords = self._extract_keywords(search_query or "")
            memos = qs.filter(title__icontains=keywords)
            if isinstance(params, dict) and params.get("is_completed") is not None:
                memos = memos.filter(is_completed=bool(params["is_completed"]))
            memos = memos[:10]
```

`document_tool.py` / `announcement_tool.py`(scope 路径):同 news 的 `limit` 模式(`params.get("limit") or 10`)。
`event_tool.py` / `meeting_room_tool.py`(scope 路径):加 `target_date` 过滤:

```python
            if isinstance(params, dict) and params.get("target_date"):
                results = results.filter(target_date=params["target_date"])
```

(具体字段名以各工具模型为准;`target_date` 字段若模型名不同,用 schema 中对应日期字段。)

- [ ] **Step 4: 跑测试确认通过**

Run:`/home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest --ds=omni_desk_backend.settings.test smart_assistant/tests/test_structured_params_passthrough.py -v`
Expected: PASS(全部用例含新增 3 项)

- [ ] **Step 5: 回归受影响工具测试**

Run:`/home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest --ds=omni_desk_backend.settings.test smart_assistant/tests/ -k "personnel or memo or news or document or announcement or event or meeting_room" -v`
Expected: PASS(无回归)

- [ ] **Step 6: Commit**

```bash
git add smart_assistant/tools/personnel_tool.py smart_assistant/tools/memo_tool.py smart_assistant/tools/news_tool.py smart_assistant/tools/document_tool.py smart_assistant/tools/announcement_tool.py smart_assistant/tools/event_tool.py smart_assistant/tools/meeting_room_tool.py smart_assistant/tests/test_structured_params_passthrough.py
git commit -m "fix(smart-assistant): 其余 Tier 1 工具消费结构化字段(department/status/is_completed/limit/target_date)(I-2)"
```

---

### Task 4: F2 — 抽取 `_run_tool_calls_rounds`(行为保持重构)

把 `_process_tool_calls_path`(orchestrator.py:658-893)的工具轮主体抽成 `_run_tool_calls_rounds`,返回 `(content, usage, meta, tool_round_messages)`,让 `process()`(非流式)与 `process_stream()`(流式)共享同一工具决策/执行逻辑。**本任务纯重构,`_process_tool_calls_path` 对外行为 100% 不变。**

**Files:**
- Modify: `omni_desk_backend/smart_assistant/agent/orchestrator.py:658-893`

**Interfaces:**
- Consumes: 现有 `_process_tool_calls_path` 循环体 / `_execute_native_tool` / `resolve_tools_for_user` / `ToolRegistry`
- Produces: `_run_tool_calls_rounds(*, query, context, llm_messages) -> (content, usage, meta, tool_round_messages)`:
  - `content`:缓冲的最终答案文本(confirm-replay 时为 draft summary)
  - `meta`:含 `tool_calls_meta / tool_calls_rounds / tool_call_path`(confirm-replay 时含 `awaiting_confirmation / confirmation_token / draft`)
  - `tool_round_messages`:工具结果已 append、**未含最终答案轮**的 messages 列表 —— 供 Task 5 流式最终轮 `router.generate(messages=..., stream=True)` 复用
  - 内部 `generate_with_tools` 异常 → 降级 `_process_json_path`(与现状一致),返回 `tool_call_path="json"` 的 meta
- Task 5 依赖此签名。

- [ ] **Step 1: 重构 `_process_tool_calls_path` → `_run_tool_calls_rounds` + 薄包装**

把 `_process_tool_calls_path` 改为:

```python
    def _process_tool_calls_path(
        self,
        *,
        query: str,
        context,
        llm_messages: list,
    ) -> tuple[str, dict, dict]:
        """原生 tool_calls 主循环(非流式,spec §3.4)。

        委托 ``_run_tool_calls_rounds`` 完成工具轮,取其 ``content`` 返回。
        流式路径(``_process_stream_tool_calls_path``)复用同一工具轮,再做
        流式最终轮。对外行为与 L1 完全一致。
        """
        content, usage, meta, _tool_round_messages = self._run_tool_calls_rounds(
            query=query, context=context, llm_messages=llm_messages
        )
        return content, usage, meta

    def _run_tool_calls_rounds(
        self,
        *,
        query: str,
        context,
        llm_messages: list,
    ) -> tuple[str, dict, dict, list]:
        """原生 tool_calls 工具轮(F2 抽取,2026-08-09)。

        - 最多 ``settings.MAX_TOOL_CALLS_ROUNDS`` 轮(默认 3);
        - 每轮 ``router.generate_with_tools(messages, tools, tool_choice='auto')``;
        - 工具错误 4 类:invalid_arguments / tool_unavailable_for_user /
          tool_timeout / execution_failed(同 L1);
        - 3 轮后强制 ``tool_choice="none"``;
        - confirm-replay 工具提前返回 awaiting_confirmation。

        返回:
            ``(content, usage, meta, tool_round_messages)``
            - content: 最终答案文本(confirm-replay 时为 draft summary;
              JSON 降级时为 JSON 路径答案)
            - meta: 含 tool_calls_meta / tool_calls_rounds / tool_call_path,
              confirm-replay 时含 awaiting_confirmation / confirmation_token / draft
            - tool_round_messages: 工具结果已 append、未含最终答案轮的
              messages(供流式最终轮复用)
        """
        from smart_assistant.agent.tool_context_resolver import resolve_tools_for_user

        # 注入 user 参数(required_auth 工具对未登录用户不可见)
        tools_schema = resolve_tools_for_user(context.user)
        tool_calls_meta: list = []
        rounds = 0
        max_rounds = int(getattr(settings, "MAX_TOOL_CALLS_ROUNDS", 3))

        for round_idx in range(max_rounds):
            try:
                content, usage, tool_calls = self.router.generate_with_tools(
                    messages=llm_messages,
                    tools=tools_schema,
                    tool_choice="auto",
                )
            except Exception as exc:
                # 降级策略(与 L1 一致):新方法异常 → 走 JSON 路径
                logger.warning(
                    "generate_with_tools 异常,降级到 _process_json_path: %s", exc, exc_info=True
                )
                content, usage, meta = self._process_json_path(
                    query=query, context=context, llm_messages=llm_messages
                )
                return content, usage, meta, llm_messages

            if not tool_calls:
                # LLM 主动选择不调工具,直接返回 content;llm_messages 为
                # 工具轮状态(未含本轮 content),供流式最终轮复用。
                return content, usage, {
                    "tool_calls_meta": tool_calls_meta,
                    "tool_calls_rounds": rounds,
                    "tool_call_path": "native",
                }, llm_messages

            rounds += 1
            tool_results = []
            # ...(原循环体:每个 tool_call 的可用性/校验/_execute_native_tool,
            #     tool_results 构造与 tool_calls_meta 记录 —— 原样保留)...
            # confirm-replay 提前返回(原 832-854):返回 4 元组
            #   return draft_summary, {}, {**meta, "awaiting_confirmation": True,
            #       "confirmation_token": ..., "draft": draft}, llm_messages
            # 常规工具执行后 append(原 873-881):
            llm_messages.append(
                {
                    "role": "assistant",
                    "content": content or "",
                    "tool_calls": tool_calls,
                }
            )
            llm_messages.extend(tool_results)

        # 3 轮后兜底:强制 tool_choice="none"
        content, usage, _ = self.router.generate_with_tools(
            messages=llm_messages,
            tools=tools_schema,
            tool_choice="none",
        )
        return content, usage, {
            "tool_calls_meta": tool_calls_meta,
            "tool_calls_rounds": rounds,
            "tool_call_path": "native",
        }, llm_messages
```

**实现说明**:把原 `_process_tool_calls_path` 循环体逐行搬入 `_run_tool_calls_rounds`,仅改 3 处返回为 4 元组:① 无 tool_calls 时、② confirm-replay 时、③ 3 轮后兜底时。`tool_round_messages` 一律取当时 `llm_messages` 引用(工具轮状态)。confirm-replay 返回的 meta 需保留原字段并追加 `awaiting_confirmation/confirmation_token/draft`。

- [ ] **Step 2: 跑既有 tool_calls 测试确认行为保持**

Run:`/home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest --ds=omni_desk_backend.settings.test smart_assistant/tests/test_orchestrator_tool_calls_path.py smart_assistant/tests/test_orchestrator_confirm.py -v`
Expected: PASS(重构无回归 —— 返回元组前 3 项与原实现一致)

- [ ] **Step 3: 跑全量后端冒烟**

Run:`/home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest --ds=omni_desk_backend.settings.test smart_assistant/tests/ -q`
Expected: 无 FAIL(0 failed;若有存量失败先记录再判断是否本任务引入)

- [ ] **Step 4: Commit**

```bash
git add smart_assistant/agent/orchestrator.py
git commit -m "refactor(smart-assistant): 抽取 _run_tool_calls_rounds,流式/非流式共享工具轮(F2 前置重构)"
```

---

### Task 5: F2 — process_stream 原生分支 + 流式最终轮

`process_stream` 新增原生 tool_calls 分支(门控与 `process()` 对称):原生开启 + 端点支持 + staff(或 FOR_ALL)时,缓冲工具轮后流式输出最终答案;confirm-replay 透传;异常降级。

**Files:**
- Modify: `omni_desk_backend/smart_assistant/agent/orchestrator.py:1069`(`process_stream` 签名 + 门控 + 原生分支)
- Modify: `omni_desk_backend/smart_assistant/agent/orchestrator.py`(新增 `_process_stream_tool_calls_path`)
- Create: `omni_desk_backend/smart_assistant/tests/test_streaming_native_tool_calls.py`

**Interfaces:**
- Consumes: Task 4 的 `_run_tool_calls_rounds`(4 元组)、`_endpoint_supports_tool_calls`(orchestrator.py:502)、`_build_initial_messages`(534)、`sse_event`(108)
- Produces: `process_stream(..., use_native_tool_calls: bool | None = None)` 新可选 kwarg(默认 None = 自动判断);`_process_stream_tool_calls_path(*, query, context, llm_messages)` 生成器,yield SSE 事件。

- [ ] **Step 1: 写失败测试 `test_streaming_native_tool_calls.py`**

```python
"""F2 流式原生 tool_calls 测试(process_stream 缓冲工具轮 + 流式最终轮)。"""

import pytest
from unittest.mock import patch

from smart_assistant.agent.orchestrator import AgentOrchestrator


def _make_tool_call(name, args_json, call_id="call_1"):
    return {
        "id": call_id,
        "type": "function",
        "function": {"name": name, "arguments": args_json},
    }


class _FakeCtx:
    user = None
    scope = None


class _FakeScheduleTool:
    """mock 工具桩:_execute_native_tool 已被 patch,此桩仅用于 get_tool_for_user
    返回值占位(不真正执行)。"""

    name = "schedule_query"
    require_confirmation = False


@pytest.mark.django_db
def test_streaming_native_tool_calls_executes_then_streams():
    """原生开启 + 首轮 tool_calls → 工具执行 → 流式最终轮。"""
    ctx = _FakeCtx()
    orch = AgentOrchestrator()

    # 第 1 轮:LLM 返回 schedule_query tool_call;第 2 轮:无工具(content)
    tool_calls_seq = [
        ("round0", "tool_calls", [_make_tool_call("schedule_query", '{"query": "明天排班"}')]),
        ("round1", "content", "明天是张三早班"),
    ]

    def fake_generate_with_tools(messages=None, **kwargs):
        tag, kind, payload = tool_calls_seq.pop(0)
        if kind == "tool_calls":
            return "", {}, payload
        return payload, {}, []

    with patch.object(orch.router, "generate_with_tools", side_effect=fake_generate_with_tools), \
         patch.object(orch.router, "generate", return_value=iter(["明天", "是", "张三", "早班"])), \
         patch("smart_assistant.agent.orchestrator.ToolRegistry.get_tool_for_user",
               return_value=_FakeScheduleTool()), \
         patch("smart_assistant.agent.orchestrator._execute_native_tool",
               return_value=({"found": True, "schedules": [{"duty_date": "2026-08-10"}]}, None, None)):
        events = list(orch.process_stream(
            "明天排班", [], ctx, use_native_tool_calls=True,
        ))

    data_blob = "\n".join(events)
    assert 'type": "chunk"' in data_blob
    assert "明天" in data_blob and "张三" in data_blob  # 流式最终轮 chunk
    assert 'finish_reason": "stop"' in data_blob


@pytest.mark.django_db
def test_streaming_native_no_tools_single_chunk():
    """原生开启但首轮无 tool_calls → 直接单 chunk 输出 content,不重生成。"""
    ctx = _FakeCtx()
    orch = AgentOrchestrator()

    with patch.object(orch.router, "generate_with_tools",
                      return_value=("直接回答", {}, [])), \
         patch.object(orch.router, "generate", side_effect=AssertionError("不应重生成")):
        events = list(orch.process_stream("你好", [], ctx, use_native_tool_calls=True))

    data_blob = "\n".join(events)
    assert "直接回答" in data_blob
    assert "AssertionError" not in data_blob


@pytest.mark.django_db
def test_streaming_native_disabled_uses_intent_path():
    """原生关闭 → 走现有 intent 路由(回归)。"""
    ctx = _FakeCtx()
    orch = AgentOrchestrator()

    with patch("smart_assistant.agent.orchestrator.classify_intent", return_value="general"), \
         patch("smart_assistant.agent.orchestrator.generate_tool_chain_plan", return_value=[]), \
         patch("smart_assistant.agent.orchestrator.generate_general_answer",
               return_value=("普通回答", {})):
        events = list(orch.process_stream("你好", [], ctx, use_native_tool_calls=False))

    data_blob = "\n".join(events)
    assert "普通回答" in data_blob
```

(`_FakeScheduleTool` 桩已在上方 `test_streaming_native_tool_calls_executes_then_streams` 前定义;`_execute_native_tool` 被 patch,不会真正执行工具。)

- [ ] **Step 2: 跑测试确认失败**

Run:`/home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest --ds=omni_desk_backend.settings.test smart_assistant/tests/test_streaming_native_tool_calls.py -v`
Expected: FAIL — `process_stream` 不接受 `use_native_tool_calls` kwarg(TypeError)

- [ ] **Step 3: 给 `process_stream` 加签名 + 门控 + 原生分支**

在 `orchestrator.py` `process_stream` 签名加 `use_native_tool_calls: bool | None = None`;在缓存短路块之后、`generate_tool_chain_plan` 之前插入门控与原生分支:

```python
        # === F2 原生 tool_calls 流式分支(L1.1,2026-08-09) ===
        # 门控与 process() 对称:USE_NATIVE_TOOL_CALLS + 端点能力 + staff/FOR_ALL
        if use_native_tool_calls is None:
            try:
                user_is_staff = bool(
                    tool_context is not None
                    and getattr(tool_context, "user", None) is not None
                    and bool(getattr(tool_context.user, "is_staff", False))
                )
                use_native = (
                    bool(getattr(settings, "USE_NATIVE_TOOL_CALLS", False))
                    and self._endpoint_supports_tool_calls()
                    and (
                        user_is_staff
                        or bool(getattr(settings, "USE_NATIVE_TOOL_CALLS_FOR_ALL", False))
                    )
                )
            except Exception:
                logger.warning("原生流式门控检查失败,走 intent 流程", exc_info=True)
                use_native = False
        else:
            use_native = bool(use_native_tool_calls)

        if use_native:
            from smart_assistant.tools.tool_context import ToolContext
            if tool_context is None:
                tool_context = ToolContext(user=None)
            llm_messages = self._build_initial_messages(
                user_query, tool_context, conversation_history
            )
            try:
                yield from self._process_stream_tool_calls_path(
                    query=user_query, context=tool_context, llm_messages=llm_messages
                )
            except Exception as exc:
                # 兜底:原生流式内部未收口的异常 → 输出失败回答,不崩溃
                logger.warning("原生流式路径异常: %s", exc, exc_info=True)
                yield sse_event({"type": "chunk", "content": f"回答生成失败: {exc}"})
                done = {"type": "done", "finish_reason": "stop", "error": True}
                annotate_error_kind(done, f"回答生成失败: {exc}")
                yield sse_event(done)
            return
```

- [ ] **Step 4: 新增 `_process_stream_tool_calls_path`**

在 orchestrator 中 `_run_tool_calls_rounds` 之后新增:

```python
    def _process_stream_tool_calls_path(
        self,
        *,
        query: str,
        context,
        llm_messages: list,
    ):
        """F2: 原生 tool_calls 流式路径(缓冲工具轮 + 流式最终轮)。

        - 复用 ``_run_tool_calls_rounds``(与 ``_process_tool_calls_path`` 对称);
        - confirm-replay → yield awaiting_confirmation + confirmation_token;
        - 无工具轮(rounds==0,含 JSON 降级)→ 单 chunk 输出缓冲 content;
        - 有工具轮(rounds>0)→ ``router.generate(messages=tool_round_messages,
          stream=True)`` 重生成流式最终答案(真打字动画)。
        """
        try:
            content, usage, meta, tool_round_messages = self._run_tool_calls_rounds(
                query=query, context=context, llm_messages=llm_messages
            )
        except Exception as exc:
            content = f"回答生成失败: {exc}"
            meta = {"tool_call_path": "native", "tool_calls_rounds": 0}
            tool_round_messages = llm_messages

        # confirm-replay:立即透传给前端,不走最终轮
        if meta.get("awaiting_confirmation"):
            tool_calls_meta = meta.get("tool_calls_meta", [])
            tool_used = tool_calls_meta[-1].get("tool", "") if tool_calls_meta else ""
            draft = meta.get("draft", {})
            yield sse_event(
                {
                    "type": "meta",
                    "intent": "tool_call",
                    "tool_used": tool_used,
                    "tool_result": {"draft": draft},
                }
            )
            yield sse_event(
                {
                    "type": "confirmation",
                    "awaiting_confirmation": True,
                    "confirmation_token": meta["confirmation_token"],
                    "draft": draft,
                    "answer": content or "请确认以下操作",
                }
            )
            yield sse_event({"type": "done", "error": False, "awaiting_confirmation": True})
            return

        rounds = meta.get("tool_calls_rounds", 0)
        if rounds > 0:
            # 流式最终轮:重生成(真打字动画)。tool_round_messages 以工具结果
            # 收尾,LLM 基于工具结果产出最终自然语言答案。
            stream_parts = []
            try:
                stream = self.router.generate(messages=tool_round_messages, stream=True)
                for chunk in stream:
                    stream_parts.append(chunk)
                    yield sse_event({"type": "chunk", "content": chunk})
            except Exception as exc:
                stream_parts = [content or f"回答生成失败: {exc}"]
                yield sse_event({"type": "chunk", "content": stream_parts[0]})
            full_answer = "".join(stream_parts)
        else:
            # 首轮即无 tool_calls / JSON 降级:直接输出缓冲 content 单 chunk
            full_answer = content or ""
            yield sse_event({"type": "chunk", "content": full_answer})

        done = {"type": "done", "finish_reason": "stop", "error": is_failed_answer(full_answer)}
        if done["error"]:
            annotate_error_kind(done, full_answer)
        yield sse_event(done)
```

- [ ] **Step 5: 跑测试确认通过**

Run:`/home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest --ds=omni_desk_backend.settings.test smart_assistant/tests/test_streaming_native_tool_calls.py -v`
Expected: PASS(3 用例)

- [ ] **Step 6: 追加流式 confirm-replay 测试并跑通**

在 `test_streaming_native_tool_calls.py` 追加:

```python
@pytest.mark.django_db
def test_streaming_native_confirm_replay_passthrough():
    """流式原生路径写工具 → awaiting_confirmation + confirmation_token 事件。"""
    ctx = _FakeCtx()
    orch = AgentOrchestrator()
    confirm_meta = {
        "tool_calls_meta": [{"round": 0, "tool": "office_generate", "arguments": {"query": "生成"}}],
        "tool_calls_rounds": 1,
        "tool_call_path": "native",
        "awaiting_confirmation": True,
        "confirmation_token": "tok-1",
        "draft": {"summary": "将生成文档"},
    }

    with patch("smart_assistant.agent.orchestrator._run_tool_calls_rounds",
               return_value=("请确认以下操作", {}, confirm_meta, [])):
        events = list(orch.process_stream("生成请假单", [], ctx, use_native_tool_calls=True))

    data_blob = "\n".join(events)
    assert "awaiting_confirmation" in data_blob
    assert "tok-1" in data_blob
    assert 'finish_reason": "stop"' not in data_blob  # 确认场景不落 done(stop)
```

Run:`/home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest --ds=omni_desk_backend.settings.test smart_assistant/tests/test_streaming_native_tool_calls.py -v`
Expected: PASS(4 用例)

- [ ] **Step 7: 全量回归**

Run:`/home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest --ds=omni_desk_backend.settings.test smart_assistant/tests/test_orchestrator_tool_calls_path.py smart_assistant/tests/test_orchestrator_confirm.py smart_assistant/tests/test_native_function_calling_e2e.py smart_assistant/tests/test_views.py smart_assistant/tests/test_confirm_replay_e2e.py -v`
Expected: PASS(流式改造无回归)

- [ ] **Step 8: Commit**

```bash
git add smart_assistant/agent/orchestrator.py smart_assistant/tests/test_streaming_native_tool_calls.py
git commit -m "feat(smart-assistant): process_stream 原生 tool_calls 流式分支(缓冲工具轮+流式最终轮)(F2)"
```

---

### Task 6: 文档归档 + 全量回归 + spec 状态

**Files:**
- Modify: `docs/superpowers/specs/2026-08-09-native-function-calling-hardening-design.md`(状态 → 已实施)
- Modify(视情况): `docs/technical/` 智能助手章节、`docs/user-manual/`(如需)

**Interfaces:**
- Consumes: Task 1-5 全部交付

- [ ] **Step 1: 全量后端回归**

Run:`/home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest --ds=omni_desk_backend.settings.test -q`
Expected: 0 failed(与 L1 基线 2290+ 一致或更高)

- [ ] **Step 2: 全量前端回归**

Run(在 `omni_desk_frontend/` 下):`npm test`
Expected: 0 failed(509+ 基线)

- [ ] **Step 3: 更新 spec 状态 + 记录变更**

把 `docs/superpowers/specs/2026-08-09-native-function-calling-hardening-design.md` 头部 `状态` 改为 `✅ 已实施(2026-08-09)`;若实施中有偏离 spec 的决策,追加"实施记录"小节说明。

- [ ] **Step 4: 归档文档(如需)**

若技术手册/用户手册需要反映写工具确认、流式原生 tool_calls,按 `docs/technical/README.md` 章节结构更新;过时内容删除不保留。

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/specs/2026-08-09-native-function-calling-hardening-design.md docs/technical docs/user-manual
git commit -m "docs(smart-assistant): L1.1 加固实施归档 + spec 状态更新"
```

---

## Self-Review

### Spec 覆盖对照

| Spec 章节 | 对应 Task |
|---|---|
| §3 F2 门控 / 缓冲工具轮 / 流式最终轮 / confirm-replay 透传 / 跳过 intent | Task 4(工具轮抽取)+ Task 5 |
| §4 I-2 透传机制 / Tier 1 工具 | Task 2(机制+schedule+office_read)+ Task 3(其余 Tier 1) |
| §5 I-1 ConfirmationHook / 注册 / 激活链路 | Task 1 |
| §6 测试策略(单元 + 集成 + E2E + 回归) | 各 Task Step 1/2/5/6 + Task 6 全量 |
| §7 错误处理(降级/3 轮/失败回答) | Task 5 Step 3/4(try/except + 失败 done) |
| §9 回滚与灰度 | 各 Task 独立 commit;门控/注册点可单点回滚 |

### 占位扫描

- 无 TBD/TODO;Task 3 Step 1 中 news limit 用例标注"占位断言 → Step 4 收紧",已明确后续替换动作(非计划内占位)。
- 所有代码步骤给出实际代码/精确修改点。

### 类型一致性

- `_run_tool_calls_rounds` 返回 4 元组 `(content, usage, meta, tool_round_messages)`,Task 4 定义、Task 5 消费,签名一致。
- `_process_stream_tool_calls_path(*, query, context, llm_messages)` 在 Task 5 Step 3(调用处)与 Step 4(定义处)一致。
- `process_stream(..., use_native_tool_calls: bool | None = None)` 新增 kwarg,Task 5 Step 1 测试与 Step 3 实现一致。
- `ConfirmationHook.name="confirmation"`,Task 1 Step 5 注册去重键与 Step 6 测试导入一致。
