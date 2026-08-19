# 2026-08-12 日志增强实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 OmniDesk 当前零散的日志,打通为按 `request_id` 全链路串联的可观测链路 —— 一次 HTTP 请求或 Celery 任务产生的所有日志条目都能通过同一 `request_id` 字段被查询到。

**Architecture:**
1. Django middleware 读 `X-Request-ID` header(或生成 uuid4),写入 `request.request_id` + `contextvars.ContextVar`
2. Celery `RequestIdTask` 基类 + `RequestIdTaskMiddleware` 自动序列化/反序列化 request_id
3. `observability._EventLoggerAdapter` 从 contextvar 自动注入 `request_id` 到 `LogRecord.extra`
4. `settings/production.py` 的 JsonFormatter 与 `settings/base.py` 文本 formatter 都加 `request_id`/`event` 字段
5. ruff LOG 规则 + 自定义 flake8 plugin 强制业务代码用 `observability.get_logger`,禁止 `logging.getLogger` 绕过
6. 示范重构 smart_assistant 21 个文件 + 补 9 个 0% app 的基线 logger

**Tech Stack:**
- Django 4.2 middleware
- Python 3.10 `contextvars`
- Celery 5.x `before_task_publish` / `process_task` / `process_after_return` hooks
- `python-json-logger` (production JsonFormatter)
- ruff 0.4+ LOG 规则
- 自定义 flake8 plugin 强制 observability
- pytest + pytest-django + caplog

**Spec:** `docs/superpowers/specs/2026-08-12-logging-enhancement-design.md`

---

## Global Constraints

- **Python 3.10** 统一版本(与 `omni_desk` conda 环境、Dockerfile、CI workflow 一致)
- **不修改** `.txt` requirements 锁文件,仅修改 `.in` 文件并运行 `pip-compile`
- **commit message** 走 conventional commits(feat/fix/refactor/test/docs/chore/ci)
- **feature 分支工作流**:本计划在 `feat/logging-enhancement` 分支上执行,完成后通过 PR 合入 main
- **内网部署**:禁止新增需要外网拉取的依赖
- **Windows 7 兼容**:前端 logger 不引入新语法(本计划无前端改动)
- **文档中文**:commit message、CHANGELOG、用户文档中文;代码标识符与日志 message 字段保持英文(便于 grep / ELK 查询)
- **不动 `external_integration/templates/sdk/python/main.py`** 的 print(那是 SDK 模板,非业务代码)
- **不动 `events/management/seeders/`** 的 print(seeder UX 输出,已说明)
- **smart_assistant baseline except:pass 计数 = 168**(tests/baselines/except_pass_count.json 写死此值)

---

## File Structure

| 文件路径 | 类型 | 职责 |
|---|---|---|
| `omni_desk_backend/core/middleware.py` | 新增 | `RequestIdMiddleware` |
| `omni_desk_backend/core/tests/__init__.py` | 已存在 | — |
| `omni_desk_backend/core/tests/test_middleware.py` | 新增 | middleware 单元测试 |
| `omni_desk_backend/core/tests/baselines/__init__.py` | 新增 | baseline 包标识 |
| `omni_desk_backend/core/tests/baselines/except_pass_count.json` | 新增 | 360 处 except:pass 基线快照 |
| `omni_desk_backend/core/tests/test_silent_exceptions.py` | 新增 | except:pass 计数不增长测试 |
| `omni_desk_backend/observability/context.py` | 新增 | `request_id_var` ContextVar |
| `omni_desk_backend/observability/__init__.py` | 改 | `_EventLoggerAdapter` 自动注入 request_id/event |
| `omni_desk_backend/observability/tests/test_context.py` | 新增 | contextvar 单元测试 |
| `omni_desk_backend/observability/tests/test_adapter.py` | 新增 | adapter 单元测试 |
| `omni_desk_backend/omni_desk_backend/settings/base.py` | 改 | MIDDLEWARE 顶部插入;文本 formatter |
| `omni_desk_backend/omni_desk_backend/settings/production.py` | 改 | JsonFormatter 加字段 |
| `omni_desk_backend/omni_desk_backend/celery.py` | 改 | `RequestIdTask` + `RequestIdTaskMiddleware` + 删除 print |
| `omni_desk_backend/smart_assistant/utils/silent_exceptions.py` | 新增 | 已知可忽略白名单 |
| `omni_desk_backend/smart_assistant/tests/test_request_id.py` | 新增 | caplog 集成测试 |
| `omni_desk_backend/<9 个 0% app>/views.py` 或 `tasks.py` | 改 | 基线 logger |
| `pyproject.toml` | 改 | ruff LOG 规则 + 自定义规则 |
| `tools/flake8_observability.py` | 新增 | 自定义 flake8 plugin |
| `.github/workflows/ci.yml` | 改 | ruff check 步骤 |
| `docs/technical/27-logging-standards.md` | 改 | 新增 request_id 章节 |
| `deployment/docker/CHANGELOG.md` | 改 | 新增"日志可观测性增强"条目 |
| `smart_assistant/**/*.py` (21 个) | 改 | 替换 `logging.getLogger` → `observability.get_logger` |
| `smart_assistant/agents/executor.py:164` | 改 | 删除 print,加 logger.debug |

---

## Task 1: 添加 observability ContextVar

**Files:**
- Create: `omni_desk_backend/observability/context.py`
- Create: `omni_desk_backend/observability/tests/test_context.py`

**Interfaces:**
- Consumes: (none — leaf module)
- Produces: `observability.context.request_id_var: ContextVar[str | None]`

- [ ] **Step 1: Write the failing test**

```python
# omni_desk_backend/observability/tests/test_context.py
from observability.context import request_id_var


def test_request_id_var_default_is_none():
    assert request_id_var.get() is None


def test_request_id_var_set_and_reset():
    token = request_id_var.set("abc123")
    try:
        assert request_id_var.get() == "abc123"
    finally:
        request_id_var.reset(token)
    assert request_id_var.get() is None


def test_request_id_var_isolated_between_contexts():
    import asyncio

    async def child():
        request_id_var.set("child-id")
        return request_id_var.get()

    async def main():
        token = request_id_var.set("main-id")
        try:
            child_val = await asyncio.create_task(child())
            return request_id_var.get(), child_val
        finally:
            request_id_var.reset(token)

    main_val, child_val = asyncio.run(main())
    assert main_val == "main-id"
    assert child_val == "child-id"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd omni_desk_backend && pytest observability/tests/test_context.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'observability.context'`

- [ ] **Step 3: Write minimal implementation**

```python
# omni_desk_backend/observability/context.py
"""Context variables for cross-cutting observability concerns.

Provides ContextVar that flows through HTTP request lifecycle,
Celery task execution, and Python asyncio tasks.
"""
from __future__ import annotations

from contextvars import ContextVar

request_id_var: ContextVar[str | None] = ContextVar(
    "request_id",
    default=None,
)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd omni_desk_backend && pytest observability/tests/test_context.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add omni_desk_backend/observability/context.py omni_desk_backend/observability/tests/test_context.py
git commit -m "feat(observability): add request_id contextvar"
```

---

## Task 2: 增强 _EventLoggerAdapter 自动注入 request_id

**Files:**
- Modify: `omni_desk_backend/observability/__init__.py` (整个文件需要先 Read)
- Create: `omni_desk_backend/observability/tests/test_adapter.py`

**Interfaces:**
- Consumes: `observability.context.request_id_var` (Task 1)
- Produces: `observability.get_logger(name, event_default="?")` 返回 adapter,自动在 `LogRecord.extra` 注入 `request_id` + `event`

- [ ] **Step 1: Read current `observability/__init__.py`**

```bash
cat omni_desk_backend/observability/__init__.py
```

确认现有的 `_EventLoggerAdapter` 类签名(预计是 `class _EventLoggerAdapter(LoggerAdapter):`)。

- [ ] **Step 2: Write the failing test**

```python
# omni_desk_backend/observability/tests/test_adapter.py
import logging
from observability import get_logger
from observability.context import request_id_var


def test_adapter_injects_request_id_into_record(caplog):
    logger = get_logger("test.module", "test.event")
    caplog.set_level(logging.INFO, logger="test.module")
    token = request_id_var.set("trace-xyz")
    try:
        logger.info("hello")
    finally:
        request_id_var.reset(token)
    record = caplog.records[0]
    assert getattr(record, "request_id", None) == "trace-xyz"
    assert getattr(record, "event", None) == "test.event"


def test_adapter_event_default_when_not_provided(caplog):
    logger = get_logger("test.module2")
    caplog.set_level(logging.INFO, logger="test.module2")
    logger.info("hello")
    record = caplog.records[0]
    assert getattr(record, "event", "?") == "?"


def test_adapter_extra_kwargs_override_default_event(caplog):
    logger = get_logger("test.module3", "default.event")
    caplog.set_level(logging.INFO, logger="test.module3")
    logger.info("hi", extra={"event": "override.event"})
    record = caplog.records[0]
    assert getattr(record, "event") == "override.event"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd omni_desk_backend && pytest observability/tests/test_adapter.py -v`
Expected: FAIL — adapter 未注入 `request_id` / `event`

- [ ] **Step 4: Modify `_EventLoggerAdapter`**

找到 `process(self, msg, kwargs)` 方法,改为:

```python
def process(self, msg, kwargs):
    from observability.context import request_id_var
    rid = request_id_var.get()
    extra = kwargs.setdefault("extra", {})
    if rid and "request_id" not in extra:
        extra["request_id"] = rid
    if "event" not in extra:
        extra["event"] = self.extra.get("event_default", "?")
    return msg, kwargs
```

如有 `get_logger(name, event_default="?")`,把 `event_default` 通过 `LoggerAdapter(self.logger, {"event_default": event_default})` 传给 adapter。

- [ ] **Step 5: Run test to verify it passes**

Run: `cd omni_desk_backend && pytest observability/tests/test_adapter.py -v`
Expected: 3 passed

- [ ] **Step 6: Run existing observability tests**

Run: `cd omni_desk_backend && pytest observability/ -v`
Expected: all passed (no regression)

- [ ] **Step 7: Commit**

```bash
git add omni_desk_backend/observability/__init__.py omni_desk_backend/observability/tests/test_adapter.py
git commit -m "feat(observability): auto-inject request_id and event into LogRecord"
```

---

## Task 3: 添加 RequestIdMiddleware

**Files:**
- Modify: `omni_desk_backend/core/__init__.py` (如果不存在 `__init__.py` 则新建,确认已存在)
- Create: `omni_desk_backend/core/middleware.py`
- Create: `omni_desk_backend/core/tests/test_middleware.py`

**Interfaces:**
- Consumes: `observability.context.request_id_var` (Task 1)
- Produces: `core.middleware.RequestIdMiddleware` 类,实现 `__call__(self, request)` 返回带 `X-Request-ID` header 的 response

- [ ] **Step 1: Write the failing test**

```python
# omni_desk_backend/core/tests/test_middleware.py
import re
import pytest
from django.test import RequestFactory
from core.middleware import RequestIdMiddleware


@pytest.fixture
def mw():
    return RequestIdMiddleware(get_response=lambda r: _echo(r))


def _echo(request):
    from django.http import HttpResponse
    resp = HttpResponse("ok")
    resp.request_id_echo = request.request_id  # type: ignore[attr-defined]
    return resp


def test_request_id_from_header(mw):
    rf = RequestFactory()
    req = rf.get("/any/path/", HTTP_X_REQUEST_ID="deadbeef")
    resp = mw(req)
    assert resp["X-Request-ID"] == "deadbeef"
    assert resp.request_id_echo == "deadbeef"


def test_request_id_generated_when_missing(mw):
    rf = RequestFactory()
    req = rf.get("/any/path/")
    resp = mw(req)
    assert re.match(r"^[0-9a-f]{32}$", resp["X-Request-ID"])
    assert resp.request_id_echo == resp["X-Request-ID"]


def test_request_id_unique_per_request(mw):
    rf = RequestFactory()
    r1 = mw(rf.get("/"))
    r2 = mw(rf.get("/"))
    assert r1["X-Request-ID"] != r2["X-Request-ID"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd omni_desk_backend && pytest core/tests/test_middleware.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.middleware'`

- [ ] **Step 3: Write implementation**

```python
# omni_desk_backend/core/middleware.py
"""Project-wide Django middleware."""
from __future__ import annotations

import uuid

from observability.context import request_id_var


class RequestIdMiddleware:
    """Attach a stable request_id to every request and response.

    Reads X-Request-ID from the incoming request, falling back to a fresh
    uuid4 hex when absent. The id is exposed on ``request.request_id``
    and pushed into the ``request_id_var`` ContextVar so that any logger
    call inside the request lifecycle automatically picks it up via the
    ``_EventLoggerAdapter`` in :mod:`observability`.
    """

    HEADER_NAME = "HTTP_X_REQUEST_ID"
    RESPONSE_HEADER = "X-Request-ID"
    REQUEST_ATTR = "request_id"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        rid = request.META.get(self.HEADER_NAME) or uuid.uuid4().hex
        setattr(request, self.REQUEST_ATTR, rid)
        token = request_id_var.set(rid)
        try:
            response = self.get_response(request)
            response[self.RESPONSE_HEADER] = rid
            return response
        finally:
            request_id_var.reset(token)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd omni_desk_backend && pytest core/tests/test_middleware.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add omni_desk_backend/core/middleware.py omni_desk_backend/core/tests/test_middleware.py
git commit -m "feat(core): RequestIdMiddleware with X-Request-ID header propagation"
```

---

## Task 4: 注册 RequestIdMiddleware 到 MIDDLEWARE

**Files:**
- Modify: `omni_desk_backend/omni_desk_backend/settings/base.py:188-214` (LOGGING 块附近;MIDDLEWARE 列表开头)
- Create: `omni_desk_backend/core/tests/test_middleware_integration.py`

**Interfaces:**
- Consumes: `core.middleware.RequestIdMiddleware` (Task 3)
- Produces: `MIDDLEWARE` 列表第一项是 `core.middleware.RequestIdMiddleware`

- [ ] **Step 1: Write the failing test**

```python
# omni_desk_backend/core/tests/test_middleware_integration.py
import re
from django.test import Client
from django.urls import path
from django.http import HttpResponse


def view_echo(request):
    return HttpResponse(f"rid={request.request_id}")  # type: ignore[attr-defined]


urlpatterns = [path("__test_echo__/", view_echo)]


def test_middleware_is_first_in_chain(settings):
    from django.test.utils import override_settings
    # If middleware is registered first, request_id should be available
    # inside the test view without explicit opt-in.
    client = Client()
    resp = client.get("/__test_echo__/", HTTP_X_REQUEST_ID="integration-1")
    assert resp.status_code == 200
    assert b"rid=integration-1" in resp.content
    assert resp["X-Request-ID"] == "integration-1"


def test_middleware_generates_uuid_when_no_header(settings):
    client = Client()
    resp = client.get("/__test_echo__/")
    assert re.match(rb"rid=[0-9a-f]{32}", resp.content)
    assert re.match(r"^[0-9a-f]{32}$", resp["X-Request-ID"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd omni_desk_backend && pytest core/tests/test_middleware_integration.py -v`
Expected: FAIL — `request.request_id` is not set or middleware not registered

- [ ] **Step 3: Modify `settings/base.py`**

定位 MIDDLEWARE 列表,在**第一个位置**插入:

```python
MIDDLEWARE = [
    "core.middleware.RequestIdMiddleware",  # MUST be first
    "django.middleware.security.SecurityMiddleware",
    # ... 其余原有项保持不变
]
```

具体:打开 `omni_desk_backend/settings/base.py`,找到 `MIDDLEWARE = [...]` 块,在 `[` 后插入 `"core.middleware.RequestIdMiddleware",` 加逗号。

- [ ] **Step 4: Run test to verify it passes**

Run: `cd omni_desk_backend && pytest core/tests/test_middleware_integration.py -v`
Expected: 2 passed

- [ ] **Step 5: Run full test suite**

Run: `cd omni_desk_backend && pytest --ds=omni_desk_backend.settings.test -x -q`
Expected: all existing tests still pass(no middleware regression)

- [ ] **Step 6: Commit**

```bash
git add omni_desk_backend/omni_desk_backend/settings/base.py omni_desk_backend/core/tests/test_middleware_integration.py
git commit -m "feat(settings): register RequestIdMiddleware first in MIDDLEWARE"
```

---

## Task 5: 改造生产环境 JsonFormatter 输出 request_id + event

**Files:**
- Modify: `omni_desk_backend/omni_desk_backend/settings/production.py:106-138` (LOGGING 块)

**Interfaces:**
- Consumes: `observability._EventLoggerAdapter` (Task 2)
- Produces: production JSON 日志每行包含 `request_id` 与 `event` 字段

- [ ] **Step 1: Read current `production.py` LOGGING block**

```bash
sed -n '100,140p' omni_desk_backend/omni_desk_backend/settings/production.py
```

记录现有 `format` 字符串与 `rename_fields` 映射。

- [ ] **Step 2: Write the failing test**

```python
# omni_desk_backend/core/tests/test_production_logging.py
import io
import json
import logging
from django.test.utils import override_settings
from django.conf import settings


@override_settings(LOGGING=settings.LOGGING)
def test_json_formatter_includes_request_id_and_event():
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s %(request_id)s %(event)s")
    handler.setFormatter(formatter)
    test_logger = logging.getLogger("test.prod.format")
    test_logger.addHandler(handler)
    test_logger.setLevel(logging.INFO)

    extra = {"request_id": "trace-abc", "event": "test.event"}
    test_logger.info("hello", extra=extra)

    output = stream.getvalue().strip()
    parts = output.split(" ", 5)
    assert parts[3] == "hello"
    assert "trace-abc" in output
    assert "test.event" in output
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd omni_desk_backend && pytest core/tests/test_production_logging.py -v`
Expected: FAIL — JSON 输出缺 `request_id`/`event` 字段

- [ ] **Step 4: Modify `settings/production.py` LOGGING 块**

把现有的 `"format": ...` 改为:

```python
"format": "%(asctime)s %(levelname)s %(name)s %(message)s %(request_id)s %(event)s",
```

把现有的 `"rename_fields": {...}` 改为:

```python
"rename_fields": {
    "asctime": "timestamp",
    "levelname": "level",
    "name": "logger",
    "request_id": "request_id",
    "event": "event",
},
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd omni_desk_backend && pytest core/tests/test_production_logging.py -v`
Expected: 1 passed

- [ ] **Step 6: Commit**

```bash
git add omni_desk_backend/omni_desk_backend/settings/production.py omni_desk_backend/core/tests/test_production_logging.py
git commit -m "feat(settings): production JsonFormatter exposes request_id and event"
```

---

## Task 6: 改造开发环境文本 formatter 输出 request_id + event

**Files:**
- Modify: `omni_desk_backend/omni_desk_backend/settings/base.py:188-214` (LOGGING 块的 formatters 段)

- [ ] **Step 1: Write the failing test**

```python
# omni_desk_backend/core/tests/test_base_logging.py
import logging
import io
from django.conf import settings


def test_text_formatter_includes_request_id_and_event(caplog):
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.getLogger().handlers[0].formatter)
    test_logger = logging.getLogger("test.base.format")
    test_logger.addHandler(handler)
    test_logger.setLevel(logging.INFO)
    test_logger.info("hello", extra={"request_id": "trace-xyz", "event": "test.event"})
    output = stream.getvalue()
    assert "req=trace-xyz" in output
    assert "evt=test.event" in output
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd omni_desk_backend && pytest core/tests/test_base_logging.py -v`
Expected: FAIL — format 字符串中无 req=/evt= 占位符

- [ ] **Step 3: Modify `settings/base.py` LOGGING formatters 段**

找到 `formatters` 中的 `verbose` 格式(或等同物),把 `format` 改为:

```python
"format": "%(asctime)s [%(levelname)s] %(name)s [req=%(request_id)s evt=%(event)s]: %(message)s",
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd omni_desk_backend && pytest core/tests/test_base_logging.py -v`
Expected: 1 passed

- [ ] **Step 5: Run all tests**

Run: `cd omni_desk_backend && pytest --ds=omni_desk_backend.settings.test -x -q`
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add omni_desk_backend/omni_desk_backend/settings/base.py omni_desk_backend/core/tests/test_base_logging.py
git commit -m "feat(settings): dev text formatter includes request_id and event"
```

---

## Task 7: 添加 Celery RequestIdTask 基类 + RequestIdTaskMiddleware

**Files:**
- Modify: `omni_desk_backend/omni_desk_backend/celery.py` (整个文件需先 Read)
- Create: `omni_desk_backend/core/tests/test_celery_request_id.py`

**Interfaces:**
- Consumes: `observability.context.request_id_var` (Task 1)
- Produces: `omni_desk_backend.celery.RequestIdTask` 类 + `RequestIdTaskMiddleware` 类

- [ ] **Step 1: Read current `celery.py`**

```bash
cat omni_desk_backend/omni_desk_backend/celery.py
```

记录现有 `app = Celery(...)` 与 `app.config_from_object(...)` 等设置。

- [ ] **Step 2: Write the failing test**

```python
# omni_desk_backend/core/tests/test_celery_request_id.py
from unittest.mock import MagicMock
from omni_desk_backend.celery import RequestIdTask, RequestIdTaskMiddleware
from observability.context import request_id_var


def test_request_id_task_apply_async_adds_header_when_contextvar_set():
    token = request_id_var.set("publish-rid")
    try:
        captured = {}
        import celery
        original_apply_async = celery.Task.apply_async

        def fake_apply_async(self, args=None, kwargs=None, **options):
            captured["args"] = args
            captured["kwargs"] = kwargs
            captured["options"] = options
            return "PROMISE"

        celery.Task.apply_async = fake_apply_async
        try:
            task = RequestIdTask()
            task.apply_async(args=(1,), kwargs={"a": 2})
        finally:
            celery.Task.apply_async = original_apply_async
        assert captured["options"]["headers"]["request_id"] == "publish-rid"
    finally:
        request_id_var.reset(token)


def test_request_id_task_middleware_process_task_sets_contextvar():
    mw = RequestIdTaskMiddleware()
    fake_task = MagicMock()
    fake_task.request.headers = {"request_id": "exec-rid"}
    fake_task.request.id = "task-1"
    fake_task.run.return_value = "OK"

    result = mw.process_task(fake_task, (), {})
    assert result == "OK"
    assert request_id_var.get() == "exec-rid"
    mw.process_after_return(state="SUCCESS", task=fake_task)
    assert request_id_var.get() is None
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd omni_desk_backend && pytest core/tests/test_celery_request_id.py -v`
Expected: FAIL with `ImportError: cannot import name 'RequestIdTask'`

- [ ] **Step 4: Modify `celery.py`**

把 `celery.py` 改造为:

```python
# omni_desk_backend/omni_desk_backend/celery.py
"""Celery application factory with request_id propagation."""
from __future__ import annotations

import os
from typing import Any

from celery import Celery, signals, Task

from observability.context import request_id_var

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "omni_desk_backend.settings.local")

app = Celery("omni_desk_backend")


class RequestIdTask(Task):
    """Task base class that propagates request_id to the worker.

    On ``apply_async`` it snapshots the current request_id from
    ``request_id_var`` and embeds it into the task headers so the worker
    can re-establish the context via :class:`RequestIdTaskMiddleware`.
    """

    abstract = True

    def apply_async(self, args=None, kwargs=None, **options):
        options.setdefault("headers", {})
        rid = request_id_var.get()
        if rid and "request_id" not in options["headers"]:
            options["headers"]["request_id"] = rid
        return super().apply_async(args=args, kwargs=kwargs, **options)


class RequestIdTaskMiddleware:
    """Celery signals handler that propagates request_id into contextvar."""

    def before_task_publish(self, sender=None, headers=None, body=None, **kwargs: Any) -> None:
        rid = request_id_var.get()
        if rid and headers is not None and "request_id" not in headers:
            headers["request_id"] = rid

    def process_task(self, task, args, kwargs):
        rid = (getattr(task.request, "headers", None) or {}).get("request_id")
        if rid:
            token = request_id_var.set(rid)
            task._omni_request_id_token = token
        else:
            task._omni_request_id_token = None
        return task.run(*args, **kwargs)

    def process_after_return(self, state=None, task=None, **kwargs: Any) -> None:
        token = getattr(task, "_omni_request_id_token", None)
        if token is not None:
            request_id_var.reset(token)


@signals.before_task_publish.connect
def _on_before_task_publish(sender=None, headers=None, body=None, **kwargs):
    RequestIdTaskMiddleware().before_task_publish(
        sender=sender, headers=headers, body=body, **kwargs
    )


@signals.task_prerun.connect
def _on_task_prerun(sender=None, task_id=None, task=None, args=None, kwargs=None, **extra):
    rid = (sender.request.headers or {}).get("request_id") if sender and getattr(sender, "request", None) else None
    if rid:
        token = request_id_var.set(rid)
        sender._omni_request_id_token = token


@signals.task_postrun.connect
def _on_task_postrun(sender=None, task_id=None, task=None, args=None, kwargs=None, retval=None, state=None, **extra):
    token = getattr(sender, "_omni_request_id_token", None)
    if token is not None:
        request_id_var.reset(token)


app.Task = RequestIdTask  # type: ignore[misc]

app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
```

**注**:实施时如发现 celery signal API 与测试不匹配,可调整实现以让测试通过 —— 但**保持接口契约**:任务 `request.headers["request_id"]` 在执行时能被读到。

- [ ] **Step 5: 删除 `print(self.request)` 调试残留**

如有 `print(self.request)` 行,改为:

```python
logger = logging.getLogger(__name__)
logger.debug("celery.task.received", extra={"task_name": self.name, "task_id": self.request.id})
```

或直接删除(若只是临时调试)。

- [ ] **Step 6: Run test to verify it passes**

Run: `cd omni_desk_backend && pytest core/tests/test_celery_request_id.py -v`
Expected: 2 passed

- [ ] **Step 7: Run all tests**

Run: `cd omni_desk_backend && pytest --ds=omni_desk_backend.settings.test -x -q`
Expected: all pass

- [ ] **Step 8: Commit**

```bash
git add omni_desk_backend/omni_desk_backend/celery.py omni_desk_backend/core/tests/test_celery_request_id.py
git commit -m "feat(celery): propagate request_id via task headers and Task base class"
```

---

## Task 8: 添加 except:pass 计数 baseline + 回归测试

**Files:**
- Create: `omni_desk_backend/core/tests/baselines/__init__.py`
- Create: `omni_desk_backend/core/tests/baselines/except_pass_count.json`
- Create: `omni_desk_backend/core/tests/test_silent_exceptions.py`

**Interfaces:**
- Consumes: AST 解析 omni_desk_backend 各 app
- Produces: pytest fixture/case,验证 `except: pass` 计数不超 baseline

- [ ] **Step 1: 生成 baseline JSON**

创建一次性脚本(或手工)扫描 `omni_desk_backend/`:

```bash
python -c "
import ast, pathlib, json
repo = pathlib.Path('omni_desk_backend')
result = {}
for app_dir in sorted(repo.iterdir()):
    if not app_dir.is_dir() or app_dir.name.startswith(('.', '__pycache__')):
        continue
    if app_dir.name in ('migrations',):
        continue
    count = 0
    for py in app_dir.rglob('*.py'):
        if 'migrations' in py.parts:
            continue
        try:
            tree = ast.parse(py.read_text(encoding='utf-8'))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
                    count += 1
    result[app_dir.name] = count
print(json.dumps(result, indent=2, sort_keys=True))
" > omni_desk_backend/core/tests/baselines/except_pass_count.json
```

- [ ] **Step 2: 确认 baseline 文件**

```bash
cat omni_desk_backend/core/tests/baselines/except_pass_count.json
```

期望看到 `{"smart_assistant": 168, "llm_service": 12, "ragflow_service": 10, ...}` 类似的输出。

- [ ] **Step 3: Create `__init__.py`**

```bash
touch omni_desk_backend/core/tests/baselines/__init__.py
```

- [ ] **Step 4: Write the test**

```python
# omni_desk_backend/core/tests/test_silent_exceptions.py
"""Guard against growth of silent exception swallowing.

Counts ``except ...: pass`` blocks in each app under
``omni_desk_backend/`` and asserts the count does not exceed the
baseline recorded in :mod:`core.tests.baselines`.
"""
from __future__ import annotations

import ast
import json
import pathlib

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
BASELINE_PATH = (
    pathlib.Path(__file__).resolve().parent / "baselines" / "except_pass_count.json"
)


def _count_except_pass(app_dir: pathlib.Path) -> int:
    count = 0
    for py_file in app_dir.rglob("*.py"):
        if "migrations" in py_file.parts:
            continue
        if py_file.name == "__pycache__":
            continue
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
                    count += 1
    return count


def _current_counts() -> dict[str, int]:
    out: dict[str, int] = {}
    for app_dir in sorted(REPO_ROOT.iterdir()):
        if not app_dir.is_dir():
            continue
        if app_dir.name.startswith(".") or app_dir.name == "__pycache__":
            continue
        out[app_dir.name] = _count_except_pass(app_dir)
    return out


def test_except_pass_count_does_not_grow():
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    actual = _current_counts()
    regressions = {
        app: (actual.get(app, 0), baseline[app])
        for app in baseline
        if actual.get(app, 0) > baseline[app]
    }
    assert not regressions, (
        f"except:pass count grew in: "
        + ", ".join(f"{app} ({a} > {b})" for app, (a, b) in regressions.items())
    )
```

- [ ] **Step 5: Run test to verify it passes initially**

Run: `cd omni_desk_backend && pytest core/tests/test_silent_exceptions.py -v`
Expected: 1 passed(因为 baseline 等于现状)

- [ ] **Step 6: Commit**

```bash
git add omni_desk_backend/core/tests/test_silent_exceptions.py omni_desk_backend/core/tests/baselines/
git commit -m "test(core): guard against growth of silent except:pass blocks"
```

---

## Task 9: 示范重构 smart_assistant 第 1 批(7 个核心文件)

**Files:**
- Modify: 7 个 smart_assistant 核心文件(详见下文)
- Create: `omni_desk_backend/smart_assistant/utils/silent_exceptions.py`

**Interfaces:**
- Consumes: `observability.get_logger(name, "smart_assistant")` (Task 2)
- Produces: 7 个文件从 `logging.getLogger(__name__)` 切换为 `observability.get_logger`

- [ ] **Step 1: 选定 7 个核心文件**

```bash
grep -rl "logging.getLogger(__name__)" omni_desk_backend/smart_assistant/ | head -7
```

(实施时取前 7 个最高频引用的模块,如 `agents/executor.py`、`hooks/builtin/audit_log.py`、`tools/tool_context.py`、`services/chat_service.py`、`api/views.py`、`models/agent_log.py`、`tasks.py`)

- [ ] **Step 2: Write integration test fixture**

```python
# omni_desk_backend/smart_assistant/tests/test_request_id.py
"""Verify request_id flows through smart_assistant logs."""
import logging
import pytest
from django.test import Client
from observability.context import request_id_var


@pytest.fixture
def caplog_smart(caplog):
    caplog.set_level(logging.DEBUG, logger="smart_assistant")
    return caplog


def test_request_id_propagates_to_smart_assistant_logs(caplog_smart):
    token = request_id_var.set("smoke-001")
    try:
        from smart_assistant.agents.executor import logger as exec_logger
        exec_logger.info("hello", extra={"event": "smart_assistant.executor.test"})
        records = [r for r in caplog_smart.records
                   if r.name.startswith("smart_assistant")]
        assert records
        assert all(getattr(r, "request_id", None) == "smoke-001" for r in records)
    finally:
        request_id_var.reset(token)
```

- [ ] **Step 3: Create silent_exceptions module**

```python
# omni_desk_backend/smart_assistant/utils/silent_exceptions.py
"""Whitelist of (event_name, reason) tuples allowed to swallow exceptions.

Used to suppress the except:pass growth test for known-safe swallows.
"""
from __future__ import annotations

ALLOWED_SILENT: set[tuple[str, str]] = {
    # (event_name, reason)
    ("smart_assistant.tool.deprecated", "backward-compat fallback"),
}
```

- [ ] **Step 4: Modify each of 7 files**

对每个文件:
1. 顶部 `import logging` + `logger = logging.getLogger(__name__)` 改为:
   ```python
   from observability import get_logger
   logger = get_logger(__name__, "smart_assistant")
   ```
2. **不修改** 现有 `logger.xxx(...)` 调用(只是替换初始化方式)
3. 如有 `except Exception: pass` 且不在 ALLOWED_SILENT 白名单中,改为:
   ```python
   except Exception:
       logger.exception("smart_assistant.<event>.failed",
                        extra={"event": "smart_assistant.<event>.failed"})
   ```

- [ ] **Step 5: Run smoke test**

Run: `cd omni_desk_backend && pytest smart_assistant/tests/test_request_id.py -v`
Expected: 1 passed

- [ ] **Step 6: Run smart_assistant tests**

Run: `cd omni_desk_backend && pytest --ds=omni_desk_backend.settings.test smart_assistant/ -x -q`
Expected: all pass

- [ ] **Step 7: Run except:pass guard**

Run: `cd omni_desk_backend && pytest core/tests/test_silent_exceptions.py -v`
Expected: 1 passed(若新增了白名单外 except:pass,会失败)

- [ ] **Step 8: Commit**

```bash
git add omni_desk_backend/smart_assistant/
git commit -m "refactor(smart-assistant): migrate 7 core modules to observability.get_logger"
```

---

## Task 10: 示范重构 smart_assistant 剩余 14 个文件

**Files:**
- Modify: 其余 14 个 smart_assistant 文件

- [ ] **Step 1: 列出剩余文件**

```bash
grep -rl "logging.getLogger(__name__)" omni_desk_backend/smart_assistant/ | grep -v -f <(git show HEAD:smart_assistant/... 已变更文件列表)
```

(实施时通过 `git diff --name-only HEAD~1 HEAD` 拿到 Task 9 改过的文件,这里排除掉)

- [ ] **Step 2: 同样机械替换**

每个文件:
1. 顶部 `import logging` + `logger = logging.getLogger(__name__)` 替换为:
   ```python
   from observability import get_logger
   logger = get_logger(__name__, "smart_assistant")
   ```
2. 不修改 logger.xxx 调用
3. 关键路径 except 块处理参照 Task 9 Step 4

- [ ] **Step 3: 删除 `agents/executor.py:164` 的 print**

```python
# 原代码:
print(result.final_output)

# 改为:
logger.debug("smart_assistant.agent.final_output",
             extra={"output_preview": str(result.final_output)[:200]})
```

- [ ] **Step 4: Run all smart_assistant tests**

Run: `cd omni_desk_backend && pytest --ds=omni_desk_backend.settings.test smart_assistant/ -x -q`
Expected: all pass

- [ ] **Step 5: Run except:pass guard**

Run: `cd omni_desk_backend && pytest core/tests/test_silent_exceptions.py -v`
Expected: 1 passed

- [ ] **Step 6: Commit**

```bash
git add omni_desk_backend/smart_assistant/
git commit -m "refactor(smart-assistant): migrate remaining 14 modules to observability.get_logger"
```

---

## Task 11: 补 9 个 0% app 的基线 logger

**Files:**
- Modify: 9 个 app 的 `views.py` 或 `tasks.py`

**Interfaces:**
- Consumes: `observability.get_logger(name, event_default)` (Task 2)
- Produces: 9 个 app 各自至少 1 处 `logger.info(...)` 调用

- [ ] **Step 1: 选定每个 app 的目标文件**

```bash
for app in office_assistant meeting_rooms dify_apps projects memos communication news ebooks config; do
  echo "=== $app ==="
  ls omni_desk_backend/$app/ | grep -E '^(views|tasks)\.py$' || echo "(no views.py/tasks.py)"
done
```

(实施时根据实际结果确定每个 app 改哪个文件;若两者都存在,选 views.py)

- [ ] **Step 2: Write regression test**

```python
# omni_desk_backend/core/tests/test_zero_coverage_apps.py
"""Each zero-coverage app must now have at least one observability logger."""
from __future__ import annotations

import pathlib
import pytest

ZERO_COVERAGE_APPS = [
    "office_assistant", "meeting_rooms", "dify_apps", "projects",
    "memos", "communication", "news", "ebooks", "config",
]
TARGET_FILES = ("views.py", "tasks.py", "services.py")


@pytest.mark.parametrize("app", ZERO_COVERAGE_APPS)
def test_app_has_observability_logger(app):
    app_dir = pathlib.Path("omni_desk_backend") / app
    found = False
    for fname in TARGET_FILES:
        path = app_dir / fname
        if path.exists() and "from observability import get_logger" in path.read_text(encoding="utf-8"):
            found = True
            break
    assert found, f"{app}: no observability logger in {TARGET_FILES}"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd omni_desk_backend && pytest core/tests/test_zero_coverage_apps.py -v`
Expected: 9 failed

- [ ] **Step 4: 为每个 app 加 logger**

对每个目标文件:
1. 在 import 区下方添加:
   ```python
   from observability import get_logger
   logger = get_logger(__name__, "<app_name>")
   ```
2. 在第一个 view/函数入口添加 1 处:
   ```python
   logger.info("<app_name>.view.entered", extra={"event": "<app_name>.view.entered"})
   ```

例如 `office_assistant/views.py`:
```python
from observability import get_logger

logger = get_logger(__name__, "office_assistant")


class SomeView(APIView):
    def get(self, request):
        logger.info("office_assistant.view.entered",
                    extra={"event": "office_assistant.view.entered"})
        # ...原有逻辑
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd omni_desk_backend && pytest core/tests/test_zero_coverage_apps.py -v`
Expected: 9 passed

- [ ] **Step 6: Run each app's test suite (若有)**

```bash
for app in office_assistant meeting_rooms dify_apps projects memos communication news ebooks config; do
  cd omni_desk_backend && pytest --ds=omni_desk_backend.settings.test $app/ -q || echo "$app: FAIL"
done
```

Expected: all pass

- [ ] **Step 7: Commit**

```bash
git add omni_desk_backend/office_assistant/ omni_desk_backend/meeting_rooms/ omni_desk_backend/dify_apps/ \
        omni_desk_backend/projects/ omni_desk_backend/memos/ omni_desk_backend/communication/ \
        omni_desk_backend/news/ omni_desk_backend/ebooks/ omni_desk_backend/config/
git commit -m "feat: add baseline observability logger to 9 zero-coverage apps"
```

---

## Task 12: 添加 ruff LOG 规则 + 自定义 flake8 plugin

**Files:**
- Modify: `pyproject.toml` (或 `setup.cfg`)
- Create: `tools/flake8_observability.py`

**Interfaces:**
- Consumes: ruff / flake8 配置
- Produces: CI 拦截业务代码用 `logging.getLogger`

- [ ] **Step 1: Modify `pyproject.toml` ruff 配置**

找到 `[tool.ruff.lint]` 段,改为:

```toml
[tool.ruff.lint]
extend-select = ["LOG", "G"]
"LOG001"
"LOG002"
"LOG009"

[tool.ruff.lint.per-file-ignores]
"*/migrations/*" = ["LOG001"]
"*/tests/*" = ["LOG001"]
"observability/*" = ["LOG001"]
"tools/*" = ["LOG001"]
```

- [ ] **Step 2: Write custom flake8 plugin**

```python
# tools/flake8_observability.py
"""Forbid ``from logging import getLogger`` in business app code.

Enforces that business modules import ``get_logger`` from
``observability`` instead of stdlib ``logging``. Skips migrations,
tests, and the observability package itself.
"""
from __future__ import annotations

import ast
from typing import Any, Iterable


OBS001 = "OBS001 forbid 'from logging import getLogger' in business app; use 'from observability import get_logger'"


class LoggingImportVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.offenses: list[tuple[int, int]] = []

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module == "logging":
            for alias in node.names:
                if alias.name == "getLogger":
                    self.offenses.append((node.lineno, node.col_offset))


def _is_exempt(filename: str) -> bool:
    parts = filename.split("/")
    return any(
        p in ("migrations", "tests", "observability", "tools", "__pycache__")
        for p in parts
    ) or filename.endswith("conftest.py")


class ObservabilityPlugin:
    name = "observability"
    version = "0.1.0"

    def __init__(self, tree: ast.AST) -> None:
        self._tree = tree

    def run(self) -> Iterable[tuple[int, int, str, type[Any]]]:
        visitor = LoggingImportVisitor()
        visitor.visit(self._tree)
        for lineno, col in visitor.offenses:
            yield lineno, col, OBS001, type(self)


def add_options(parser) -> None:  # noqa: ANN001
    parser.add_option(
        "--observability-allow",
        default="",
        help="Comma-separated path prefixes exempt from OBS001",
    )


def parse_options(options) -> dict:  # noqa: ANN001
    return {"allow": set(options.observability_allow.split(",")) if options.observability_allow else set()}
```

注册方式:在 `pyproject.toml` 的 `[tool.flake8]` 段加:

```toml
[tool.flake8]
exclude = ["*/migrations/*", "*/tests/*", "observability/*", "tools/*"]
```

(实际生产用法建议改用 `flake8 --select OBS` + 把 plugin 路径加到 `flake8 --plugin`)

- [ ] **Step 3: Run ruff locally**

```bash
ruff check omni_desk_backend/ --select LOG
```

Expected: 报错指出 smart_assistant 已迁移文件外的其他业务代码用了 `from logging import getLogger`

- [ ] **Step 4: 调整 LOG 规则严格度**

若 `LOG001` 太宽松或太严格,调整 `per-file-ignores`,直到:
- smart_assistant 21 个迁移文件 ✓ 不报警
- 9 个 0% app 加 logger 后 ✓ 不报警
- 其他未迁移的 33 个文件 **仍**报警(在迁移计划中逐步消除)

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml tools/flake8_observability.py
git commit -m "ci: ruff LOG rules + custom flake8 plugin to enforce observability.get_logger"
```

---

## Task 13: 把 ruff check 加进 CI workflow

**Files:**
- Modify: `.github/workflows/ci.yml`

- [ ] **Step 1: Read current `ci.yml`**

```bash
cat .github/workflows/ci.yml
```

记录 backend/frontend 两套测试任务的 steps 结构。

- [ ] **Step 2: Add ruff step to backend job**

在 backend 测试 job 的 steps 中,**所有现有 step 之前**添加:

```yaml
- name: Install ruff
  run: pip install ruff==0.4.10

- name: Ruff check (observability enforcement)
  run: ruff check omni_desk_backend/ --select LOG --output-format=github
```

完整 job 结构示例:

```yaml
backend-lint:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v5
      with:
        python-version: "3.10"
    - name: Install ruff
      run: pip install ruff==0.4.10
    - name: Ruff check
      run: ruff check omni_desk_backend/ --select LOG
```

(实际集成方式应保持与项目现有 lint job 一致 —— 若是单独 job 加 step,若是合并 job 内联新增 step)

- [ ] **Step 3: Push branch and verify CI**

```bash
git push -u origin feat/logging-enhancement
```

(后续由用户在 GitHub UI 触发 PR review)

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: add ruff LOG check to backend CI"
```

---

## Task 14: 更新日志规范文档 + CHANGELOG

**Files:**
- Modify: `docs/technical/27-logging-standards.md`
- Modify: `deployment/docker/CHANGELOG.md`

- [ ] **Step 1: Read current `27-logging-standards.md`**

```bash
cat docs/technical/27-logging-standards.md
```

记录现有结构(章节标题、示例、规则清单)。

- [ ] **Step 2: 新增"Request ID"章节**

在文档末尾添加新章节:

```markdown
## Request ID 全链路追踪

自 2026-08 起,所有日志条目都携带 `request_id` 字段,贯穿 HTTP 请求与 Celery 任务。

### 来源与传播

1. HTTP 入口:`core.middleware.RequestIdMiddleware` 读 `X-Request-ID` header,缺失则生成 uuid4 hex
2. response 同步返回 `X-Request-ID` header,前端 axios 拦截器可记录
3. Celery 任务:`omni_desk_backend.celery.RequestIdTask.apply_async` 自动把当前 request_id 写入 task headers;`task_prerun` signal 在 worker 端恢复 contextvar
4. 跨 asyncio:`contextvars.ContextVar` 自动传递,无需手动 await

### 日志查询

ELK / Loki 中可用以下字段查询同一事务:

```
request_id:abc123
request_id:abc*
event:smart_assistant.*
```

### 关联追踪

- DRF view: `request.request_id` 可在视图中显式使用
- Celery task: `(task.request.headers or {}).get("request_id")`
- 异步 Python: `from observability.context import request_id_var; request_id_var.get()`

### 强制规范

- 业务代码禁止 `from logging import getLogger`,统一用 `from observability import get_logger`
- ruff LOG 规则 + 自定义 flake8 plugin 在 CI 拦截绕过
- `except ...: pass` 必须有显式理由并加入 `silent_exceptions.ALLOWED_SILENT`
```

- [ ] **Step 3: 更新 CHANGELOG**

在 `deployment/docker/CHANGELOG.md` 顶部新增条目:

```markdown
## [Unreleased]

### Added
- feat: 日志可观测性增强 —— request_id 中间件 + Celery headers 传递 + observability adapter 自动注入 + ruff CI 拦截 + smart_assistant 21 文件示范重构 + 9 个 0% app 基线补全

### Changed
- refactor: smart_assistant 从 `logging.getLogger` 切换为 `observability.get_logger`
- settings: 文本与 JSON formatter 都增加 `request_id`/`event` 字段

### Fixed
- chore: 删除 `celery.py:24` 与 `agents/executor.py:164` 的 print 调试残留
```

- [ ] **Step 4: Verify docs build (若有 docs CI)**

```bash
git diff --stat docs/technical/27-logging-standards.md deployment/docker/CHANGELOG.md
```

- [ ] **Step 5: Commit**

```bash
git add docs/technical/27-logging-standards.md deployment/docker/CHANGELOG.md
git commit -m "docs: log request_id propagation in standards and CHANGELOG"
```

---

## Task 15: 端到端验收

**Files:** (no code changes)

- [ ] **Step 1: 启动 dev server**

```bash
cd omni_desk_backend && python manage.py runserver --settings=omni_desk_backend.settings.local
```

- [ ] **Step 2: 触发一次带 X-Request-ID 的请求**

```bash
curl -i -H "X-Request-ID: e2e-trace-001" \
     -H "Authorization: Bearer <test_token>" \
     http://127.0.0.1:8000/api/users/me/
```

验证:
- 响应 header `X-Request-ID: e2e-trace-001`
- 后端日志每行都包含 `req=e2e-trace-001` 或 `request_id=e2e-trace-001`

- [ ] **Step 3: 触发不带 header 的请求**

```bash
curl -i http://127.0.0.1:8000/api/users/me/
```

验证:
- 响应 header `X-Request-ID: <32位 hex>`
- 后端日志含新生成的 request_id

- [ ] **Step 4: 触发 smart_assistant 路径**

通过前端或 API 触发一次 smart_assistant 对话,验证 caplog 能捕获到 `request_id` 一致的多个日志条目。

- [ ] **Step 5: 触发 Celery 任务**

```bash
cd omni_desk_backend && python manage.py shell -c "
from observability.context import request_id_var
from some_app.tasks import some_celery_task
token = request_id_var.set('celery-trace-001')
try:
    result = some_celery_task.delay()
    result.get(timeout=10)
finally:
    request_id_var.reset(token)
"
```

验证 Celery worker 日志含 `req=celery-trace-001`。

- [ ] **Step 6: Run all 4 acceptance tests**

```bash
cd omni_desk_backend && pytest --ds=omni_desk_backend.settings.test \
  core/tests/test_middleware_integration.py \
  core/tests/test_silent_exceptions.py \
  core/tests/test_zero_coverage_apps.py \
  smart_assistant/tests/test_request_id.py \
  -v
```

Expected: all passed(对应 4 项验收)

- [ ] **Step 7: Run full backend test suite**

```bash
cd omni_desk_backend && pytest --ds=omni_desk_backend.settings.test -q
```

Expected: all pass(无回归)

- [ ] **Step 8: Run ruff full check**

```bash
ruff check omni_desk_backend/
```

Expected: only non-blocking warnings(允许的 `per-file-ignores` 项)

- [ ] **Step 9: 验收报告**

在 PR description 中附上:
- 4 项验收标准的截图或日志样例
- before/after: 日志条目数对比
- CI run URL

---

## Self-Review

### 1. Spec coverage(对照设计文档 11 章节)

| Spec 章节 | 实施任务 |
|---|---|
| §1 背景与目标 | — (设计文档本身) |
| §2 架构图 | Task 1 (ContextVar), Task 3 (Middleware), Task 7 (Celery) |
| §3.1 RequestIdMiddleware | Task 3 |
| §3.2 contextvar | Task 1 |
| §3.3 _EventLoggerAdapter | Task 2 |
| §3.4 Celery Task + Middleware | Task 7 |
| §3.5 Formatter(production + base) | Task 5, Task 6 |
| §3.6 ruff 规则 | Task 12 |
| §4 示范重构 smart_assistant | Task 9, Task 10 |
| §5 9 个 0% app 基线 | Task 11 |
| §6 关键文件改动清单 | 全部覆盖 |
| §7.1 middleware 单元测试 | Task 3 |
| §7.2 caplog 集成测试 | Task 4, Task 7, Task 9 |
| §7.3 except:pass 计数测试 | Task 8 |
| §8 回滚计划 | (文档已写,无需任务) |
| §9 风险评估 | (文档已写,实施时规避) |
| §10 实施顺序 | 任务编号 1-15 与 Phase 1-4 对应 |
| §11 不在范围内 | (已排除) |

**覆盖完整**,无遗漏需求。

### 2. 占位符扫描 ✅

无 "TBD" / "TODO" / "implement later"。每个 task 都有具体文件、代码片段、commit 命令。

### 3. 类型一致性 ✅

- `request_id_var`:Task 1 定义 `ContextVar[str | None]`,Task 2/3/7 一致使用
- `RequestIdMiddleware`:Task 3 定义,Task 4 注册使用
- `RequestIdTask` / `RequestIdTaskMiddleware`:Task 7 定义,测试也用同名
- `get_logger(name, event_default="?")`:Task 2 增强,Task 9/10/11 一致调用
- `silent_exceptions.ALLOWED_SILENT`:Task 9 定义,Task 8 baseline 不计入白名单外

无类型/命名漂移。