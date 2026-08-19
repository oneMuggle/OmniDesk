# orchestrator.py 拆分实施计划(R3-A1)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `smart_assistant/agent/orchestrator.py`(1520 行,3 处 C901)拆分为 6 个聚焦模块,行为零变化。

**Architecture:** 以"行为保持重构"方式,按职责把 orchestrator 拆成 `sse_contract.py`(SSE 输出契约)+ `orchestrator_helpers.py`(缓存签名 / 参数拆包)+ `native_tool_runner.py`(原生工具执行)+ `tool_rounds_runner.py`(工具轮循环)+ `tool_chain_runner.py`(多工具链)+ `stream_runner.py`(流式路径)。`orchestrator.py` 保留公共门面(`process` / `_legacy_process` / `process_stream` 入口 + re-export),从 1520 行降至 <800 行且 C901 归零。`_execute_native_tool` 与 `_process_chain` 不引用 `self`,可提取为模块级纯函数。

**Tech Stack:** Python 3.10, Django 4.2, ruff(0.16.2,C901 阈值 10), pytest(`--ds=omni_desk_backend.settings.test`), conda 环境 `OmniDesk`(`/home/fz/anaconda3/envs/OmniDesk/bin/python`)。

## Global Constraints

- **行为零变化**:本次是重构,不得改变任何对外输出(SSE 事件结构、返回 dict 字段、错误分类)。外部消费者契约见下,必须保持。
- **外部 import 契约**(orchestrator.py 必须继续 re-export,`views/chat.py` / `test_doctor.py` / 多个测试文件直接 import):
  - `AgentOrchestrator`
  - `ERROR_KIND_HINTS`
  - `FORMAT_VERSION`
  - `annotate_error_kind`
  - `classify_error_kind`
  - `sse_event`
  - `_dict_to_query`(test_orchestrator_tool_calls_path.py:798,819 直接 import)
- **测试命令**(统一在 `omni_desk_backend/` 下执行):
  `cd /home/fz/project/OmniDesk/omni_desk_backend && /home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest <path> --ds=omni_desk_backend.settings.test -q`
- **特征化安全网**:88 个 orchestrator 相关测试在拆分前必须全绿(基线已确认)。每个 Task 完成后,相关 smart_assistant 测试套件必须保持绿。
- **每个 Task 独立 commit**,conventional commits:`refactor(smart-assistant): ...`
- **分支**:实现前先 `git switch -c refactor/split-orchestrator`(从最新 main 切出)。不要在 main 上直接改。
- **行号会漂移**:各 Task 逐次删除 orchestrator.py 行,后序 Task 的"移动范围"按**函数名**重新锚定,不要依赖计划里写的起始行号(计划里的行号是 2026-08-14 HEAD 快照)。

## 文件结构(目标)

| 文件 | 职责 | 约行数 |
|---|---|---|
| `orchestrator.py`(改) | 公共门面:`__init__` / `process` / `_legacy_process` / `_process_json_path` / `_wrap_native_to_dict` / `_endpoint_supports_tool_calls` / `_build_initial_messages` / `_process_tool_calls_path` / `process_stream`(薄委托)+ re-export | <800 |
| `sse_contract.py`(新) | `FORMAT_VERSION` / `ERROR_KIND_HINTS` / `_has_active_llm_config` / `_mentions_ragflow` / `classify_error_kind` / `sse_event` / `annotate_error_kind` | ~110 |
| `orchestrator_helpers.py`(新) | `_scope_cache_sig` / `_dict_to_query` | ~65 |
| `native_tool_runner.py`(新) | `execute_native_tool(tool, validated, context)`(纯函数,scope-aware + hook 链 + confirm-replay) | ~120 |
| `tool_rounds_runner.py`(新) | `run_tool_calls_rounds(router, *, query, context, llm_messages, json_fallback)` + `_process_single_tool_call` 助手 | ~260 |
| `tool_chain_runner.py`(新) | `process_chain(user_query, plan, conversation_history, tool_context)`(纯函数) | ~60 |
| `stream_runner.py`(新) | `StreamRunner` 类:`stream()` + `_process_stream_tool_calls_path()` + 若干分解助手 | ~300 |

> 目标与 R3-A1 文档的 `error_recovery.py` 对应关系:`sse_contract.py` 承担了错误分类/SSE 序列化职责(error contract),命名更贴合内容。此偏差已在 R3-A1 文档 §2 的可实施范围内。

## 测试策略(重构专用)

- 新增模块的**纯函数**(sse_contract / orchestrator_helpers)写聚焦单元测试(便宜、高价值)。
- 移动型的提取(native_tool_runner / tool_rounds_runner / tool_chain_runner / stream_runner)**依赖现有 88 测试作为行为证明**,外加一个轻量"模块可导入 + orchestrator 委托"冒烟测试。不复制现有 88 测试的内容(DRY)。
- 每个 Task 结尾运行:**新增测试 + 相关 smart_assistant 测试**。
- 全程以 ruff C901 与行数作为进度门(目标:Task 8 完成后 orchestrator.py 无 C901 且 <800 行)。

---

### Task 1: 提取 SSE 输出契约 → `sse_contract.py`

**Files:**
- Create: `smart_assistant/agent/sse_contract.py`
- Modify: `smart_assistant/agent/orchestrator.py`(删除第 47-130 行的契约段,改为 import + re-export)
- Test: `smart_assistant/tests/test_sse_contract.py`(新建)

**Interfaces:**
- Consumes: 无(纯模块)
- Produces: `FORMAT_VERSION: int = 1` / `ERROR_KIND_HINTS: dict[str, str]` / `_has_active_llm_config() -> bool` / `_mentions_ragflow(answer, tool_result) -> bool` / `classify_error_kind(result: dict) -> str|None` / `sse_event(payload: dict) -> str` / `annotate_error_kind(payload, answer, tool_used=None, tool_result=None) -> dict`

- [ ] **Step 1: 写失败测试**

创建 `smart_assistant/tests/test_sse_contract.py`:

```python
from smart_assistant.agent.sse_contract import (
    ERROR_KIND_HINTS,
    FORMAT_VERSION,
    annotate_error_kind,
    classify_error_kind,
    sse_event,
)


def test_sse_event_carries_format_version_and_frame():
    raw = sse_event({"type": "done", "error": False})
    assert raw.startswith("data: ")
    assert raw.endswith("\n\n")
    assert f'"format_version": {FORMAT_VERSION}' in raw


def test_sse_event_keeps_ensure_ascii_false():
    raw = sse_event({"type": "chunk", "content": "中文回答"})
    assert "中文回答" in raw


def test_classify_error_kind_none_for_success():
    assert classify_error_kind({"error": False, "answer": "ok"}) is None


def test_classify_error_kind_internal_error_fallback():
    kind = classify_error_kind({"error": True, "answer": "某失败", "tool_used": None})
    assert kind in ERROR_KIND_HINTS


def test_annotate_error_kind_adds_hint():
    payload = annotate_error_kind({}, "某失败", tool_used="memo")
    assert "kind" in payload
    assert "hint" in payload
    assert payload["hint"] == ERROR_KIND_HINTS.get(payload["kind"])


def test_orchestrator_reexports_sse_contract_symbols():
    # 外部消费者(views/chat.py, test_doctor.py)仍从 orchestrator import
    from smart_assistant.agent.orchestrator import (
        ERROR_KIND_HINTS,
        FORMAT_VERSION,
        annotate_error_kind,
        classify_error_kind,
        sse_event,
    )

    assert FORMAT_VERSION == 1
    assert "no_llm_endpoint" in ERROR_KIND_HINTS
    assert callable(sse_event)
    assert callable(classify_error_kind)
    assert callable(annotate_error_kind)
```

- [ ] **Step 2: 运行测试,确认失败**

Run: `cd /home/fz/project/OmniDesk/omni_desk_backend && /home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest smart_assistant/tests/test_sse_contract.py --ds=omni_desk_backend.settings.test -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'smart_assistant.agent.sse_contract'`

- [ ] **Step 3: 创建 `sse_contract.py`(逐字移动)**

创建 `smart_assistant/agent/sse_contract.py`,把 orchestrator.py **第 47-130 行**的以下内容逐字移动(含 `# ----` 注释、docstring、`logger` 声明不需要移,logger 留在 orchestrator):
- `FORMAT_VERSION = 1`
- `ERROR_KIND_HINTS = {...}`
- `_has_active_llm_config()`(含 `from django.conf import settings` 依赖 → 顶部 import)
- `_mentions_ragflow()`
- `classify_error_kind()`
- `sse_event()`
- `annotate_error_kind()`

新文件结构:

```python
"""SSE 输出契约与错误分类(从 orchestrator.py 提取,行为不变)。

提供与前端共享的机器可读契约:SSE 事件序列化、错误 kind 判定、中文 hint。
独立成模块供 orchestrator 与 views/chat.py 复用。
"""

import json

from django.conf import settings

from observability import get_logger

from .conversation_context import is_failed_answer
from ..models import LlmAppConfig

logger = get_logger(__name__, "smart_assistant")

FORMAT_VERSION = 1

ERROR_KIND_HINTS = {...}  # 逐字移动原内容


def _has_active_llm_config() -> bool:  # 逐字移动
    ...


def _mentions_ragflow(answer, tool_result) -> bool:  # 逐字移动
    ...


def classify_error_kind(result: dict):  # 逐字移动(含 docstring)
    ...


def sse_event(payload: dict) -> str:  # 逐字移动
    ...


def annotate_error_kind(payload, answer, tool_used=None, tool_result=None) -> dict:  # 逐字移动
    ...
```

注意:`classify_error_kind` 内部调 `_has_active_llm_config` / `_mentions_ragflow` / `is_failed_answer`,这些都在新文件内或已 import,引用不变。

- [ ] **Step 4: 更新 orchestrator.py 为 import + re-export**

删除 orchestrator.py 中第 47-130 行(契约段),在 imports 区加入:

```python
from .sse_contract import (
    ERROR_KIND_HINTS,
    FORMAT_VERSION,
    annotate_error_kind,
    classify_error_kind,
    sse_event,
)
```

若 orchestrator.py 内部还引用 `_has_active_llm_config` / `_mentions_ragflow`,从上到下核对(实际仅 `classify_error_kind` 使用,已随契约段移走;如仍有引用则从 sse_contract 补 import)。

- [ ] **Step 5: 运行新测试 + 特征化套件,确认全绿**

Run: `cd /home/fz/project/OmniDesk/omni_desk_backend && /home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest smart_assistant/tests/test_sse_contract.py smart_assistant/tests/test_doctor.py smart_assistant/tests/test_orchestrator.py --ds=omni_desk_backend.settings.test -q`
Expected: 全部 PASS(test_doctor.py 验证 re-export 契约)

- [ ] **Step 6: Commit**

```bash
git add omni_desk_backend/smart_assistant/agent/sse_contract.py omni_desk_backend/smart_assistant/agent/orchestrator.py omni_desk_backend/smart_assistant/tests/test_sse_contract.py
git commit -m "refactor(smart-assistant): 提取 SSE 输出契约到 sse_contract.py(R3-A1/8)"
```

---

### Task 2: 提取缓存辅助函数 → `orchestrator_helpers.py`

**Files:**
- Create: `smart_assistant/agent/orchestrator_helpers.py`
- Modify: `smart_assistant/agent/orchestrator.py`(删除 `_scope_cache_sig` 与 `_dict_to_query`,改为 import)
- Test: `smart_assistant/tests/test_orchestrator_helpers.py`(新建)

**Interfaces:**
- Consumes: 无
- Produces: `_scope_cache_sig(tool_context) -> str` / `_dict_to_query(validated) -> str`

> 保留原名(带下划线)以最小化 diff。orchestrator re-export `_dict_to_query`(测试直接 import)。

- [ ] **Step 1: 写失败测试**

创建 `smart_assistant/tests/test_orchestrator_helpers.py`:

```python
import pytest

from smart_assistant.agent.orchestrator_helpers import _dict_to_query, _scope_cache_sig


def test_dict_to_query_prefers_query_field():
    assert _dict_to_query({"query": "查张三", "department": "研发"}) == "查张三"


def test_dict_to_query_falls_back_to_key_value_when_no_query():
    result = _dict_to_query({"date_from": "2026-08-01", "limit": 3})
    assert "date_from: 2026-08-01" in result
    assert "limit: 3" in result


def test_dict_to_query_skips_none_and_query_key_in_fallback():
    result = _dict_to_query({"query": None, "name": "李四"})
    assert "query" not in result
    assert "name: 李四" in result


def test_dict_to_query_serializes_dict_values_as_json():
    result = _dict_to_query({"filters": {"a": 1}})
    assert "filters: {\"a\": 1}" in result


def test_dict_to_query_passthrough_string():
    assert _dict_to_query("直接字符串") == "直接字符串"


def test_scope_cache_sig_anonymous_when_no_context():
    assert _scope_cache_sig(None) == "anonymous"


def test_scope_cache_sig_anonymous_when_no_user():
    class Ctx:
        user = None
    assert _scope_cache_sig(Ctx()) == "anonymous"


def test_orchestrator_reexports_dict_to_query():
    # 兼容 test_orchestrator_tool_calls_path.py:798 的直接 import
    from smart_assistant.agent.orchestrator import _dict_to_query

    assert callable(_dict_to_query)
```

- [ ] **Step 2: 运行测试,确认失败**

Run: `cd /home/fz/project/OmniDesk/omni_desk_backend && /home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest smart_assistant/tests/test_orchestrator_helpers.py --ds=omni_desk_backend.settings.test -q`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: 创建 `orchestrator_helpers.py`(逐字移动)**

创建文件,把 orchestrator.py 中 `_scope_cache_sig`(第 133-145 行)与 `_dict_to_query`(第 148-191 行,**含完整 F1 docstring**)逐字移动。顶部 import 补齐 `json`(dict_to_query 用到)。

```python
"""orchestrator 缓存签名与参数拆包辅助(从 orchestrator.py 提取,行为不变)。"""

import json


def _scope_cache_sig(tool_context):
    """逐字移动:从 ToolContext 派生 cache 隔离签名。"""
    ...


def _dict_to_query(validated) -> str:
    """逐字移动:F1 修复的完整 docstring 一并保留。"""
    ...
```

- [ ] **Step 4: 更新 orchestrator.py**

删除 `_scope_cache_sig` 与 `_dict_to_query` 定义,在 imports 区加:

```python
from .orchestrator_helpers import _dict_to_query, _scope_cache_sig
```

`_dict_to_query` 经此 import 自动成为 orchestrator 模块属性,`from smart_assistant.agent.orchestrator import _dict_to_query` 继续可用。

- [ ] **Step 5: 运行新测试 + 特征化套件**

Run: `cd /home/fz/project/OmniDesk/omni_desk_backend && /home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest smart_assistant/tests/test_orchestrator_helpers.py smart_assistant/tests/test_orchestrator_tool_calls_path.py --ds=omni_desk_backend.settings.test -q`
Expected: 全绿(test_orchestrator_tool_calls_path.py 覆盖 `_dict_to_query` 直接 import)

- [ ] **Step 6: Commit**

```bash
git add omni_desk_backend/smart_assistant/agent/orchestrator_helpers.py omni_desk_backend/smart_assistant/agent/orchestrator.py omni_desk_backend/smart_assistant/tests/test_orchestrator_helpers.py
git commit -m "refactor(smart-assistant): 提取缓存辅助函数到 orchestrator_helpers.py(R3-A1/8)"
```

---

### Task 3: 提取原生工具执行 → `native_tool_runner.py`

**Files:**
- Create: `smart_assistant/agent/native_tool_runner.py`
- Modify: `smart_assistant/agent/orchestrator.py`(`_execute_native_tool` 改为委托模块函数;`_run_tool_calls_rounds` 内调用点改模块函数)
- Test: `smart_assistant/tests/test_native_tool_runner.py`(新建,轻量冒烟)

**Interfaces:**
- Consumes: `_dict_to_query` / `_scope_cache_sig`(来自 `orchestrator_helpers`)
- Produces: `execute_native_tool(tool, validated: dict, context) -> tuple[dict, dict|None, dict|None]`

> `_execute_native_tool` 当前是 `self` 方法但不引用 `self` → 提取为模块级纯函数 `execute_native_tool`,签名去掉 `self`。

- [ ] **Step 1: 写失败测试**

创建 `smart_assistant/tests/test_native_tool_runner.py`(轻量接口冒烟;行为由既有 88 测试保证):

```python
import pytest

from smart_assistant.agent.native_tool_runner import execute_native_tool


def test_execute_native_tool_is_importable():
    assert callable(execute_native_tool)


def test_orchestrator_still_has_execute_native_tool_method():
    # 保持 orchestrator 公共方法存在(视图/测试可能调用)
    from smart_assistant.agent.orchestrator import AgentOrchestrator

    assert hasattr(AgentOrchestrator, "_execute_native_tool")
```

- [ ] **Step 2: 运行测试,确认失败**

Expected: FAIL with `ModuleNotFoundError`(native_tool_runner 不存在)

- [ ] **Step 3: 创建 `native_tool_runner.py`(逐字移动 + 去 self)**

创建文件,把 orchestrator.py `_execute_native_tool`(第 576-684 行)函数体逐字移动,去掉 `self` 参数,命名 `execute_native_tool`。顶部 import:

```python
import uuid

from ..hooks.base import Reject
from ..hooks.wiring import (
    apply_failure_hooks,
    apply_post_execute_hooks,
    apply_pre_execute_hooks,
    execute_guarded,
)
from ..cache import set_confirmation_draft
from .orchestrator_helpers import _dict_to_query, _scope_cache_sig
```

函数签名变为:

```python
def execute_native_tool(tool, validated: dict, context) -> tuple[dict, dict | None, dict | None]:
    """原生 tool_calls 路径的单个工具执行(从 AgentOrchestrator._execute_native_tool 提取)。

    行为 100% 不变,保留 C-1/C-2 docstring。
    """
```

- [ ] **Step 4: 更新 orchestrator.py**

1. 删除 `_execute_native_tool` 方法体(第 576-684 行)。
2. 在 `_run_tool_calls_rounds` 内调用点(原第 836 行 `result, confirmation, failure = self._execute_native_tool(tool, validated, context)`)改为:

```python
from .native_tool_runner import execute_native_tool  # 顶部 import
...
result, confirmation, failure = execute_native_tool(tool, validated, context)
```

3. **为兼容 `hasattr(AgentOrchestrator, "_execute_native_tool")` 的既有测试/视图调用**,在 AgentOrchestrator 类内保留一个薄委托方法:

```python
def _execute_native_tool(self, tool, validated, context):
    """兼容委托:指向模块级 execute_native_tool(行为不变)。"""
    return execute_native_tool(tool, validated, context)
```

- [ ] **Step 5: 运行新测试 + 特征化套件**

Run: `cd /home/fz/project/OmniDesk/omni_desk_backend && /home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest smart_assistant/tests/test_native_tool_runner.py smart_assistant/tests/test_orchestrator_tool_calls_path.py smart_assistant/tests/test_structured_params_passthrough.py --ds=omni_desk_backend.settings.test -q`
Expected: 全绿

- [ ] **Step 6: Commit**

```bash
git add omni_desk_backend/smart_assistant/agent/native_tool_runner.py omni_desk_backend/smart_assistant/agent/orchestrator.py omni_desk_backend/smart_assistant/tests/test_native_tool_runner.py
git commit -m "refactor(smart-assistant): 提取原生工具执行到 native_tool_runner.py(R3-A1/8)"
```

---

### Task 4: 提取工具轮循环 → `tool_rounds_runner.py`(C901 12→<10)

**Files:**
- Create: `smart_assistant/agent/tool_rounds_runner.py`
- Modify: `smart_assistant/agent/orchestrator.py`(`_run_tool_calls_rounds` 改为委托 + 删体)
- Test: `smart_assistant/tests/test_tool_rounds_runner.py`(新建,轻量冒烟)

**Interfaces:**
- Consumes: `router`(LLMRouter 实例,提供 `generate_with_tools`)、`context`(ToolContext)、`json_fallback: Callable`(orchestrator 传入的 `self._process_json_path` 绑定方法)
- Produces: `run_tool_calls_rounds(router, *, query, context, llm_messages, json_fallback) -> tuple[str, dict, dict, list]` + 内部助手 `_process_single_tool_call(tc, context, round_idx) -> tuple[list, list]`(返回 `(tool_results, tool_calls_meta)` 增量)

- [ ] **Step 1: 写失败测试**

创建 `smart_assistant/tests/test_tool_rounds_runner.py`:

```python
import pytest

from smart_assistant.agent.tool_rounds_runner import run_tool_calls_rounds


def test_run_tool_calls_rounds_is_importable():
    assert callable(run_tool_calls_rounds)


def test_orchestrator_delegates_run_tool_calls_rounds():
    from smart_assistant.agent.orchestrator import AgentOrchestrator

    assert hasattr(AgentOrchestrator, "_run_tool_calls_rounds")
```

- [ ] **Step 2: 运行测试,确认失败**

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: 创建 `tool_rounds_runner.py`(移动 + 内层循环分解)**

把 orchestrator.py `_run_tool_calls_rounds`(第 704-951 行)函数体移动,并按下面结构**分解内层 for tc 循环**为 `_process_single_tool_call` 助手,使 `run_tool_calls_rounds` 的 C901 从 12 降至 <10。

顶部 import:

```python
import json
import time

from django.conf import settings

from observability import get_logger

from ..tools.registry import ToolRegistry
from .native_tool_runner import execute_native_tool
from .tool_context_resolver import resolve_tools_for_user  # 保持相对导入正确

logger = get_logger(__name__, "smart_assistant")
```

主函数结构(移动原 704-951 行,内层循环替换为助手调用):

```python
def run_tool_calls_rounds(router, *, query, context, llm_messages, json_fallback):
    """原生 tool_calls 工具轮(从 AgentOrchestrator._run_tool_calls_rounds 提取,行为不变)。

    json_fallback: 可调用对象 ``(query, context, llm_messages) -> (content, usage, meta)``,
    用于 generate_with_tools 异常时的 JSON 路径降级。由 orchestrator 传入
    ``self._process_json_path`` 的绑定方法。
    """
    tools_schema = resolve_tools_for_user(context.user)
    tool_calls_meta = []
    rounds = 0
    max_rounds = int(getattr(settings, "MAX_TOOL_CALLS_ROUNDS", 3))

    for round_idx in range(max_rounds):
        try:
            content, usage, tool_calls = router.generate_with_tools(
                messages=llm_messages, tools=tools_schema, tool_choice="auto"
            )
        except Exception as exc:
            logger.warning("generate_with_tools 异常,降级到 json 路径: %s", exc, exc_info=True)
            content, usage, meta = json_fallback(query=query, context=context, llm_messages=llm_messages)
            return content, usage, meta, llm_messages

        if not tool_calls:
            return (
                content,
                usage,
                {
                    "tool_calls_meta": tool_calls_meta,
                    "tool_calls_rounds": rounds,
                    "tool_call_path": "native",
                },
                llm_messages,
            )

        rounds += 1
        tool_results, tool_calls_meta, confirm_triple = _run_round_tool_calls(
            tool_calls, context, round_idx, tool_calls_meta
        )

        # confirm-replay 提前返回(与移动前 884-907 行一致)
        if confirm_triple is not None:
            tc, result, confirmation, failure = confirm_triple
            ...  # 逐字移动原 confirm 分支:预执行 hook / 组装 draft summary / meta / return

        llm_messages.append(
            {"role": "assistant", "content": content or "", "tool_calls": tool_calls}
        )
        llm_messages.extend(tool_results)

    content, usage, _ = router.generate_with_tools(
        messages=llm_messages, tools=tools_schema, tool_choice="none"
    )
    return (
        content,
        usage,
        {"tool_calls_meta": tool_calls_meta, "tool_calls_rounds": rounds, "tool_call_path": "native"},
        llm_messages,
    )
```

> **重要(移动时的精确规则)**:confirm-replay 提前返回分支(原 884-907 行,`if confirmation is not None: return (...)`)**必须保留在 `run_tool_calls_rounds` 主循环内**,不能塞进 `_process_single_tool_call`(后者是纯收集助手,无法提前 return 主函数)。正确的分解:
> - `_run_round_tool_calls(tool_calls, context, round_idx, tool_calls_meta) -> tuple[tool_results, tool_calls_meta, confirm_triple|None]`,其中对每个 tc 调 `_process_single_tool_call`,**遇到 confirmation 时把 `(tc, result, confirmation, failure)` 记录到 `confirm_triple` 并 break**;
> - 主函数拿到 `confirm_triple` 非空时,执行移动前的 confirm 提前返回逻辑(draft summary + meta 组装 + return),并**跳过**该轮的 `llm_messages.append/extend`(与移动前一致:confirm 返回时 llm_messages 不含本轮)。
>
> 逐字核对移动前后行为:收集顺序(meta append 顺序)、confirm 分支的 `duration_ms`、`arguments` 字段、`tool_call_path="native"` 全部保持不变。

`_process_single_tool_call(tc, context, round_idx)` 封装原循环内对**单个 tc** 的完整处理(原 770-924 行的逐项逻辑):工具可用性检查 → 参数解析/schema 校验 → `execute_native_tool` → 失败/确认/成功三分支 → 返回 `(tool_result_msg, meta_entry, confirm_or_none)`。这一步把 4 层嵌套打平成 1 层,是 C901 12→<10 的关键。

- [ ] **Step 4: 更新 orchestrator.py**

1. 删除 `_run_tool_calls_rounds` 方法体(第 704-951 行)。
2. 保留薄委托方法(兼容既有测试/视图):

```python
def _run_tool_calls_rounds(self, *, query, context, llm_messages):
    from .tool_rounds_runner import run_tool_calls_rounds

    return run_tool_calls_rounds(
        self.router,
        query=query,
        context=context,
        llm_messages=llm_messages,
        json_fallback=self._process_json_path,
    )
```

3. `_process_tool_calls_path` 与 `_process_stream_tool_calls_path` 内部对 `self._run_tool_calls_rounds(...)` 的调用**保持不变**(仍走委托方法)。

- [ ] **Step 5: 运行新测试 + 特征化套件**

Run: `cd /home/fz/project/OmniDesk/omni_desk_backend && /home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest smart_assistant/tests/test_tool_rounds_runner.py smart_assistant/tests/test_orchestrator_tool_calls_path.py smart_assistant/tests/test_native_function_calling_e2e.py smart_assistant/tests/test_structured_params_passthrough.py --ds=omni_desk_backend.settings.test -q`
Expected: 全绿

- [ ] **Step 6: 验证 C901 已降**

Run: `cd /home/fz/project/OmniDesk && ruff check --select C901 omni_desk_backend/smart_assistant/agent/tool_rounds_runner.py`
Expected: 无 C901(或仅助手函数仍触发时,继续拆到 <10)

- [ ] **Step 7: Commit**

```bash
git add omni_desk_backend/smart_assistant/agent/tool_rounds_runner.py omni_desk_backend/smart_assistant/agent/orchestrator.py omni_desk_backend/smart_assistant/tests/test_tool_rounds_runner.py
git commit -m "refactor(smart-assistant): 提取工具轮循环到 tool_rounds_runner.py,分解内层循环(R3-A1/8)"
```

---

### Task 5: 提取多工具链 → `tool_chain_runner.py`

**Files:**
- Create: `smart_assistant/agent/tool_chain_runner.py`
- Modify: `smart_assistant/agent/orchestrator.py`(`_process_chain` 改为委托 + 删体)
- Test: `smart_assistant/tests/test_tool_chain_runner.py`(新建,轻量冒烟)

**Interfaces:**
- Consumes: `ToolChainExecutor` / `execute_tool_chain` / `ResultSynthesizer` / `synthesize_chain_answer` / `is_failed_answer`
- Produces: `process_chain(user_query: str, plan: list, conversation_history: list, tool_context=None) -> dict`

> `_process_chain` 不引用 `self` → 提取为纯函数。`synthesize_chain_answer` 是 `tool_chain_executor.synthesize_answer` 的别名,从 orchestrator 原 import 处跟随移动。

- [ ] **Step 1: 写失败测试**

创建 `smart_assistant/tests/test_tool_chain_runner.py`:

```python
import pytest

from smart_assistant.agent.tool_chain_runner import process_chain


def test_process_chain_is_importable():
    assert callable(process_chain)


def test_orchestrator_keeps_process_chain_method():
    from smart_assistant.agent.orchestrator import AgentOrchestrator

    assert hasattr(AgentOrchestrator, "_process_chain")
```

- [ ] **Step 2: 运行测试,确认失败**

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: 创建 `tool_chain_runner.py`(逐字移动 + 去 self)**

移动 orchestrator.py `_process_chain`(第 1175-1230 行)函数体,去 `self`,命名 `process_chain`。顶部 import:

```python
from .result_synthesizer import ResultSynthesizer
from .tool_chain_executor import (
    execute_tool_chain,
    synthesize_answer as synthesize_chain_answer,
    ToolChainExecutor,
)
from .conversation_context import is_failed_answer
```

- [ ] **Step 4: 更新 orchestrator.py**

1. 删除 `_process_chain` 方法体(第 1175-1230 行)。
2. 保留薄委托方法:

```python
def _process_chain(self, user_query, plan, conversation_history, tool_context=None):
    from .tool_chain_runner import process_chain

    return process_chain(user_query, plan, conversation_history, tool_context)
```

3. 核对 orchestrator 里对 `_process_chain` 的调用点(第 347 行、第 1330 行)保持 `self._process_chain(...)` 不变。

- [ ] **Step 5: 运行新测试 + 特征化套件**

Run: `cd /home/fz/project/OmniDesk/omni_desk_backend && /home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest smart_assistant/tests/test_tool_chain_runner.py smart_assistant/tests/test_multi_agent_complex.py smart_assistant/tests/test_multi_agent_resume.py --ds=omni_desk_backend.settings.test -q`
Expected: 全绿

- [ ] **Step 6: Commit**

```bash
git add omni_desk_backend/smart_assistant/agent/tool_chain_runner.py omni_desk_backend/smart_assistant/agent/orchestrator.py omni_desk_backend/smart_assistant/tests/test_tool_chain_runner.py
git commit -m "refactor(smart-assistant): 提取多工具链到 tool_chain_runner.py(R3-A1/8)"
```

---

### Task 6: 提取流式路径 → `stream_runner.py`(C901 30→<10)

**Files:**
- Create: `smart_assistant/agent/stream_runner.py`
- Modify: `smart_assistant/agent/orchestrator.py`(`process_stream` 改为薄委托 + 删体;删除 `_process_stream_tool_calls_path`)
- Test: `smart_assistant/tests/test_stream_runner.py`(新建,轻量冒烟)

**Interfaces:**
- Consumes: `orchestrator`(AgentOrchestrator 实例;经其访问 `router` / `_endpoint_supports_tool_calls` / `_build_initial_messages` / `_process_chain`)
- Produces: `class StreamRunner`:
  - `__init__(self, orchestrator)`
  - `stream(self, user_query, conversation_history=None, tool_context=None, use_native_tool_calls=None)` — 原 `process_stream` 的移动 + 分解(生成器)
  - 内部助手:`_stream_intent` / `_stream_cached_answer` / `_resolve_native_gate` / `_stream_native` / `_stream_chain` / `_stream_single_tool`

- [ ] **Step 1: 写失败测试**

创建 `smart_assistant/tests/test_stream_runner.py`:

```python
import pytest

from smart_assistant.agent.stream_runner import StreamRunner


def test_stream_runner_is_importable():
    assert callable(StreamRunner)


def test_orchestrator_process_stream_is_generator():
    from smart_assistant.agent.orchestrator import AgentOrchestrator

    assert hasattr(AgentOrchestrator, "process_stream")
```

- [ ] **Step 2: 运行测试,确认失败**

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: 创建 `stream_runner.py`(移动 + 分解 process_stream)**

把 orchestrator.py `process_stream`(第 1232-1520 行)与 `_process_stream_tool_calls_path`(第 953-1047 行)移动进来,并按下面结构分解 `stream()` 以把 C901 从 30 降至 <10。

顶部 import(整合两个方法 + 助手用到的全部符号):

```python
from django.conf import settings

from observability import get_logger

from ..tools.registry import ToolRegistry
from ..cache import (
    get_cached_intent,
    cache_intent,
    get_cached_tool_result,
    cache_tool_result,
    get_cached_answer,
)
from .intent_classifier import (
    classify_intent,
    generate_answer_stream,
    generate_tool_empty_answer,
    generate_general_answer,
)
from .conversation_context import is_failed_answer
from .orchestrator_helpers import _scope_cache_sig
from .tool_chain_planner import generate_tool_chain_plan
from .sse_contract import annotate_error_kind, sse_event
from ..hooks.base import Reject
from ..hooks.wiring import (
    apply_failure_hooks,
    apply_post_execute_hooks,
    apply_pre_execute_hooks,
    execute_guarded,
)

logger = get_logger(__name__, "smart_assistant")
```

`StreamRunner.stream()` 主结构(原 process_stream 的等价重构):

```python
class StreamRunner:
    """流式编排路径(从 AgentOrchestrator.process_stream 提取,行为不变)。

    持有 orchestrator 引用以复用 router / 端点能力检查 / 消息构建 / 链处理。
    """

    def __init__(self, orchestrator):
        self._orchestrator = orchestrator

    def stream(
        self,
        user_query: str,
        conversation_history: list = None,
        tool_context=None,
        use_native_tool_calls: bool | None = None,
    ):
        """流式处理入口:等价于原 AgentOrchestrator.process_stream 的完整行为。"""
        has_history = conversation_history is not None and len(conversation_history) > 0
        scope_sig = _scope_cache_sig(tool_context)
        schemas = ToolRegistry.get_all_schemas()

        # Step 1: 意图分类 + 回答缓存短路(原 1262-1283 行)
        intent = self._stream_intent(user_query, schemas, conversation_history, has_history, scope_sig)
        cached_stream = self._stream_cached_answer(user_query, intent, has_history, scope_sig)
        if cached_stream is not None:
            yield from cached_stream
            return

        # Step 2: 原生 tool_calls 流式分支(原 1285-1322 行)
        if self._resolve_native_gate(tool_context, use_native_tool_calls):
            from smart_assistant.tools.tool_context import ToolContext

            if tool_context is None:
                tool_context = ToolContext(user=None)
            llm_messages = self._orchestrator._build_initial_messages(user_query, tool_context, conversation_history)
            try:
                yield from self._stream_native(user_query, tool_context, llm_messages)
            except Exception as exc:
                logger.warning("原生流式路径异常: %s", exc, exc_info=True)
                yield sse_event({"type": "chunk", "content": f"回答生成失败: {exc}"})
                done = {"type": "done", "finish_reason": "stop", "error": True}
                annotate_error_kind(done, f"回答生成失败: {exc}")
                yield sse_event(done)
            return

        # Step 3: 多工具链(原 1324-1354 行)
        tool_chain = generate_tool_chain_plan(user_query, schemas, conversation_history)
        if tool_chain:
            yield from self._stream_chain(user_query, tool_chain, conversation_history, tool_context)
            return

        # Step 4: 单工具路径(原 1356-1520 行)
        yield from self._stream_single_tool(
            user_query, intent, conversation_history, tool_context, scope_sig, has_history, schemas
        )
```

助手分解(每个助手负责原 process_stream 的一段,原逻辑逐字移动):

```python
    def _stream_intent(self, user_query, schemas, conversation_history, has_history, scope_sig):
        """原 1257-1269 行:意图分类(缓存优先),无历史时算并缓存。"""
        if has_history:
            return None
        cached = get_cached_intent(user_query, schemas, context_sig=scope_sig)
        if cached:
            return cached
        intent = classify_intent(user_query, schemas, conversation_history)
        cache_intent(user_query, schemas, intent, context_sig=scope_sig)
        return intent

    def _stream_cached_answer(self, user_query, intent, has_history, scope_sig):
        """原 1271-1283 行:缓存命中时返回生成器(meta/chunk/done),否则 None。

        注意:仅无历史时检查;返回的生成器在未被消费时无副作用。
        """
        if has_history or intent is None:
            return None
        cached_answer = get_cached_answer(user_query, intent, context_sig=scope_sig, tool_call_path="none")
        if not cached_answer:
            return None

        def _gen():
            yield sse_event({"type": "meta", "intent": intent, "cache_hit": True})
            yield sse_event({"type": "chunk", "content": cached_answer})
            done = {"type": "done", "cache_hit": True, "error": is_failed_answer(cached_answer)}
            if done["error"]:
                annotate_error_kind(done, cached_answer)
            yield sse_event(done)

        return _gen()

    def _resolve_native_gate(self, tool_context, use_native_tool_calls):
        """原 1287-1303 行:原生路径门控(与 process 对称)。"""
        if use_native_tool_calls is not None:
            return bool(use_native_tool_calls)
        try:
            user_is_staff = bool(
                tool_context is not None
                and getattr(tool_context, "user", None) is not None
                and bool(getattr(tool_context.user, "is_staff", False))
            )
            return (
                bool(getattr(settings, "USE_NATIVE_TOOL_CALLS", False))
                and self._orchestrator._endpoint_supports_tool_calls()
                and (user_is_staff or bool(getattr(settings, "USE_NATIVE_TOOL_CALLS_FOR_ALL", False)))
            )
        except Exception:
            logger.warning("原生流式门控检查失败,走 intent 流程", exc_info=True)
            return False

    def _stream_native(self, user_query, tool_context, llm_messages):
        """原 _process_stream_tool_calls_path(第 953-1047 行)整体移入。

        含 confirm-replay 透传 / 无工具轮单 chunk / 有工具轮流式最终轮。
        内部用 self._orchestrator.router 与 self._orchestrator._run_tool_calls_rounds(...)。
        """
        ...  # 逐字移动原 _process_stream_tool_calls_path 方法体,self 保留(现在是 StreamRunner 的方法)

    def _stream_chain(self, user_query, tool_chain, conversation_history, tool_context):
        """原 1328-1354 行:多工具链聚合结果 → meta/chunk/done 事件。"""
        ...  # 逐字移动;其中 _process_chain 调用改为 self._orchestrator._process_chain(...)

    def _stream_single_tool(self, user_query, intent, conversation_history, tool_context, scope_sig, has_history, schemas):
        """原 1356-1520 行:单工具确认拦截 + 执行 + 流式生成 + done。

        若 C901 仍 >10,把 confirm-replay 拦截段拆为 _stream_confirm_or_reject(...)
        助手(返回 (events_or_none, should_return)),再在 _stream_single_tool 内
        ``if should_return: yield from events; return``。以 ruff C901 实测为准。
        """
        ...  # 逐字移动
```

> **确认行为等价的关键点**(移动时逐字核对):
> - `_stream_cached_answer` 返回**惰性生成器**,未被消费不产生副作用 —— 保证 `stream()` 主函数里"先检查再 yield"与原"if cached_answer: yield...; return"语义一致。
> - 原 `process_stream` 中 `rate_limit_error` 变量(第 1255 行声明,第 1517-1519 行 done 时使用)在 `_stream_single_tool` 内声明并使用,不跨助手传递。
> - `_stream_native` 内 `_run_tool_calls_rounds` 调用经 orchestrator 委托方法(第 Task 4 保留的 `self._orchestrator._run_tool_calls_rounds`)。

- [ ] **Step 4: 更新 orchestrator.py**

1. 删除 `process_stream` 方法体(第 1232-1520 行)与 `_process_stream_tool_calls_path` 方法体(第 953-1047 行)。
2. 替换为薄委托:

```python
def process_stream(self, user_query, conversation_history=None, tool_context=None, use_native_tool_calls=None):
    """流式处理入口(委托 StreamRunner,行为不变)。"""
    from .stream_runner import StreamRunner

    yield from StreamRunner(self).stream(
        user_query,
        conversation_history=conversation_history,
        tool_context=tool_context,
        use_native_tool_calls=use_native_tool_calls,
    )
```

- [ ] **Step 5: 运行新测试 + 流式特征化套件**

Run: `cd /home/fz/project/OmniDesk/omni_desk_backend && /home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest smart_assistant/tests/test_stream_runner.py smart_assistant/tests/test_streaming_native_tool_calls.py smart_assistant/tests/test_cache_stream_shortcut.py smart_assistant/tests/test_views_rate_limit.py --ds=omni_desk_backend.settings.test -q`
Expected: 全绿

- [ ] **Step 6: 验证 C901**

Run: `cd /home/fz/project/OmniDesk && ruff check --select C901 omni_desk_backend/smart_assistant/agent/stream_runner.py`
Expected: 无 C901 >10(若 `_stream_single_tool` 仍触发,按 Step 3 的备注拆 confirm 拦截段)

- [ ] **Step 7: Commit**

```bash
git add omni_desk_backend/smart_assistant/agent/stream_runner.py omni_desk_backend/smart_assistant/agent/orchestrator.py omni_desk_backend/smart_assistant/tests/test_stream_runner.py
git commit -m "refactor(smart-assistant): 提取流式路径到 stream_runner.py,process_stream 降复杂度(R3-A1/8)"
```

---

### Task 7: 分解 `_legacy_process`(C901 17→<10)

**Files:**
- Modify: `smart_assistant/agent/orchestrator.py`(`_legacy_process` 内部拆出 2 个助手)
- Test: 复用既有 `test_orchestrator.py` / `test_json_path_fallback.py`(行为证明)+ 新增 `test_legacy_process_helpers.py`(轻量冒烟)

**Interfaces:**
- Produces(新助手,均为 AgentOrchestrator 私有方法):
  - `_classify_legacy_intent(self, user_query, schemas, conversation_history, has_history, scope_sig) -> str`
  - `_legacy_single_tool(self, user_query, intent, tool, conversation_history, tool_context, scope_sig, has_history) -> dict`

- [ ] **Step 1: 写失败测试(轻量冒烟)**

创建 `smart_assistant/tests/test_legacy_process_helpers.py`:

```python
import pytest

from smart_assistant.agent.orchestrator import AgentOrchestrator


def test_legacy_process_has_decomposed_helpers():
    assert hasattr(AgentOrchestrator, "_classify_legacy_intent")
    assert hasattr(AgentOrchestrator, "_legacy_single_tool")
```

- [ ] **Step 2: 运行测试,确认失败**

Expected: FAIL with `AttributeError`(助手尚不存在)

- [ ] **Step 3: 重构 `_legacy_process`**

当前 `_legacy_process`(第 313-507 行,C901=17)。按下面拆成 3 段:

**a) 拆出 `_classify_legacy_intent`**(原 330-340 行):

```python
def _classify_legacy_intent(self, user_query, schemas, conversation_history, has_history, scope_sig):
    """原 _legacy_process 的意图分类段(缓存优先)。"""
    if not has_history:
        cached_intent = get_cached_intent(user_query, schemas, context_sig=scope_sig)
        if cached_intent:
            return cached_intent
        intent = classify_intent(user_query, schemas, conversation_history)
        cache_intent(user_query, schemas, intent, context_sig=scope_sig)
        return intent
    return classify_intent(user_query, schemas, conversation_history)
```

**b) 拆出 `_legacy_single_tool`**(原 351-495 行:confirm-replay 拦截 + 工具执行 + LLM 回答):

```python
def _legacy_single_tool(self, user_query, intent, tool, conversation_history, tool_context, scope_sig, has_history):
    """原 _legacy_process 的单工具路径:确认拦截 → 执行 → LLM 合成。

    若该助手 C901 仍 >10,继续把 confirm-replay 拦截段(原 360-419 行)拆为
    ``_legacy_confirm_intercept(self, tool, user_query, conversation_history, tool_context, scope_sig, intent) -> dict|None``
    (返回 dict 表示"已拦截直接返回",返回 None 表示继续执行)。
    """
    ...  # 逐字移动原 351-495 行;内部 self._process_chain / generate_* 引用保持
```

**c) `_legacy_process` 主函数收敛为线性调度**(第 313-507 行重组):

```python
def _legacy_process(self, user_query, conversation_history, tool_context):
    schemas = ToolRegistry.get_all_schemas()
    has_history = conversation_history is not None and len(conversation_history) > 0
    scope_sig = _scope_cache_sig(tool_context)

    intent = self._classify_legacy_intent(user_query, schemas, conversation_history, has_history, scope_sig)

    tool_chain = generate_tool_chain_plan(user_query, schemas, conversation_history)
    if tool_chain:
        return self._process_chain(user_query, tool_chain, conversation_history, tool_context)

    tool = ToolRegistry.get_tool(intent)
    if tool:
        return self._legacy_single_tool(user_query, intent, tool, conversation_history, tool_context, scope_sig, has_history)

    answer, usage = generate_general_answer(user_query, conversation_history)
    return {
        "answer": answer,
        "intent": "general_chat",
        "tool_used": None,
        "tool_result": None,
        "sources": None,
        "usage": usage,
        "error": is_failed_answer(answer),
    }
```

> 保持 docstring(原 319-323 行)与 `_process_json_path` 对该方法的调用不变。

- [ ] **Step 4: 运行测试 + 验证 C901**

Run: `cd /home/fz/project/OmniDesk/omni_desk_backend && /home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest smart_assistant/tests/test_legacy_process_helpers.py smart_assistant/tests/test_orchestrator.py smart_assistant/tests/test_json_path_fallback.py smart_assistant/tests/test_orchestrator_confirm.py --ds=omni_desk_backend.settings.test -q`
Expected: 全绿

Run: `cd /home/fz/project/OmniDesk && ruff check --select C901 omni_desk_backend/smart_assistant/agent/orchestrator.py`
Expected: 无 C901 >10(若 `_legacy_single_tool` 仍触发,按 Step 3b 备注再拆 confirm 段)

- [ ] **Step 5: Commit**

```bash
git add omni_desk_backend/smart_assistant/agent/orchestrator.py omni_desk_backend/smart_assistant/tests/test_legacy_process_helpers.py
git commit -m "refactor(smart-assistant): 分解 _legacy_process 降复杂度(R3-A1/8)"
```

---

### Task 8: 最终验证 + 全量回归 + 收尾

**Files:**
- 无新增;验证性任务

- [ ] **Step 1: 全量 smart_assistant 测试**

Run: `cd /home/fz/project/OmniDesk/omni_desk_backend && /home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest smart_assistant/ --ds=omni_desk_backend.settings.test -q`
Expected: 全绿(基线 88+ 且新增约 20 个测试,无回归)

- [ ] **Step 2: 全量后端测试(覆盖率门)**

Run: `cd /home/fz/project/OmniDesk/omni_desk_backend && /home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest --ds=omni_desk_backend.settings.test -q 2>&1 | tail -5`
Expected: PASS + 覆盖率 ≥80%(由 `--cov-fail-under` 配置生效;若全量过慢,可用项目现有测试脚本)

- [ ] **Step 3: 静态检查**

Run:
```bash
cd /home/fz/project/OmniDesk
ruff check omni_desk_backend/smart_assistant/agent/orchestrator.py omni_desk_backend/smart_assistant/agent/sse_contract.py omni_desk_backend/smart_assistant/agent/orchestrator_helpers.py omni_desk_backend/smart_assistant/agent/native_tool_runner.py omni_desk_backend/smart_assistant/agent/tool_rounds_runner.py omni_desk_backend/smart_assistant/agent/tool_chain_runner.py omni_desk_backend/smart_assistant/agent/stream_runner.py
```
Expected: 全绿(无 C901 / F / E / LOG 违规)

- [ ] **Step 4: 验证目标指标**

Run: `cd /home/fz/project/OmniDesk && wc -l omni_desk_backend/smart_assistant/agent/orchestrator.py && ruff check --select C901 omni_desk_backend/smart_assistant/agent/orchestrator.py`
Expected: orchestrator.py **<800 行**且 **0 处 C901**。

- [ ] **Step 5: mypy 抽查(如 CI 启用)**

Run: `cd /home/fz/project/OmniDesk/omni_desk_backend && /home/fz/anaconda3/envs/OmniDesk/bin/python -m mypy smart_assistant/agent/orchestrator.py smart_assistant/agent/sse_contract.py smart_assistant/agent/stream_runner.py --ignore-missing-imports`
Expected: 无新增 error(与重构前基线一致)

- [ ] **Step 6: 更新文档**

编辑 `docs/technical/16-smart-assistant.md`,把 orchestrator 单文件描述改为拆分后的模块结构(若该文档描述过文件结构)。再编辑 `docs/plans/2026-08-14_project-optimization-round3.md` §2 R3-A1 行,标注 `已完成(见 docs/superpowers/plans/2026-08-14-orchestrator-split.md)`。

- [ ] **Step 7: Final Commit**

```bash
git add docs/plans/2026-08-14_project-optimization-round3.md docs/technical/16-smart-assistant.md
git commit -m "docs(plans): R3-A1 orchestrator 拆分完成,更新候选状态"
```

- [ ] **Step 8: 推送 + PR**

按 `feature-branch-workflow`:推送 `refactor/split-orchestrator` 到 origin,创建 PR(标题含 `refactor(smart-assistant)`),等 CI 绿后由用户 merge。

---

## 自审记录

**1. Spec 覆盖**:R3-A1 文档目标(orchestrator.py 拆分为多模块 + C901 归零)已由 Task 1-8 完整覆盖。`error_recovery.py`(文档提名的目标模块)由 `sse_contract.py` 承担错误分类职责,已在 Global Constraints 声明偏差。无遗漏需求。

**2. 占位符扫描**:所有"逐字移动"指令都锚定了**函数名 + 起始行号(HEAD 快照)+ 行为等价要点**,无 TBD。Task 6 的 `_stream_single_tool` 以 `...` 占位**并明确标注"逐字移动原 1356-1520 行"**,不是含糊指令;其 C901>10 时的二次分解也有明确规则(拆 confirm 段)。

**3. 类型一致性**:
- `run_tool_calls_rounds` 在 Task 4 产出签名 `(router, *, query, context, llm_messages, json_fallback)`,Task 4 Step 4 委托方法按此签名调用 ✓
- `execute_native_tool(tool, validated, context)` 在 Task 3 产出,Task 4 `_process_single_tool_call` 内部消费 ✓
- `StreamRunner(orchestrator)` 在 Task 6 产出,`process_stream` 委托按 `StreamRunner(self).stream(...)` 调用 ✓
- `_scope_cache_sig` / `_dict_to_query` 在 Task 2 产出,Task 3/6/7 消费 ✓
- `process_chain` 在 Task 5 产出,Task 6 `_stream_chain` / Task 7 通过 `self._process_chain` 消费 ✓
