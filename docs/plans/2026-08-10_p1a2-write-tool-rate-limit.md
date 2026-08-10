# P1A-2 写工具速率限制 — 实施 Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `smart_assistant` pre_execute 钩子链中新增 `RateLimitHook`,对所有 `require_confirmation=True` 工具做用户级固定窗口频次控制(默认 10/min,env var 可配);超限返回 `Reject(error_code="rate_limit_exceeded", retry_after=Ns)`,复用 chat 限流的 Django cache 基础设施。

**Architecture:**
- 新增 `check_write_rate_limit(user_id)` helper 到 `middleware/rate_limit.py`,复用既有 fixed window + `cache.incr` 回落模式
- 新增 `RateLimitHook`(`ToolHookBase` 子类)在 `hooks/builtin/rate_limit.py`,优先级 25(高于 ConfirmationHook 的 20,先跑拦截——避免被限流时仍触发 draft 缓存写)
- 视图层(`views/chat.py`)错误响应透传 `error_code` + `retry_after` 字段
- `doctor.py` 扩展加 `cache_write_rate_limit` 自检项
- **Reject dataclass 加 `retry_after` 字段**(向后兼容,默认 `None`)

**Tech Stack:** Django 4.2 + Python 3.10 + DRF 3.14 + djangorestframework-simplejwt + Django cache(开发/测试 LocMemCache,生产 Redis)

---

## Global Constraints

(适用于所有任务。来源:`docs/superpowers/specs/2026-08-10-p1a2-write-tool-rate-limit-design.md`)

- **Python 3.10 统一**:conda 环境 `omni_desk`,所有 Python 命令必须从 conda env 执行(`/home/fz/anaconda3/envs/omni_desk/bin/python` 或 `conda run -n omni_desk ...`)
- **测试 settings**: `pytest --ds=omni_desk_backend.settings.test`(test.py 中 `in-memory SQLite + fast MD5 hasher + logging disabled + LocMemCache`)
- **Django apps.ready() 多次触发幂等**:register_builtin_hooks 用 `if "<name>" not in existing_names` 守卫防重复注册
- **不破坏既有契约**:`Reject(reason, should_abort=False, error_code=None)` 现有调用方不受影响(新字段 `retry_after` 可选)
- **commit message 走 conventional commits**:`feat:` / `refactor:` / `test:` / `docs:` / `fix:` / `chore:`
- **不引入新依赖**:所有逻辑用 Django cache + 标准库,不动 `requirements.in`
- **不接 LlmAppConfig DB 调谐**:阈值只来自 `SMART_ASSISTANT_WRITE_RATE_LIMIT` env var
- **固定窗口**(非滑动 / token bucket):与 chat 限流同源,运维单一心智模型
- **cache key 命名空间分离**:`smart_assistant:write_rate_limit:{user_id}`(写工具,本 plan 引入) vs `smart_assistant:rate_limit:{user_id}`(chat,既有)
- **PR 流程**:plan 完成后走 `feat/p1a2-write-tool-rate-limit` 分支 → push → `gh pr create` → CI 绿 → 用户 merge → 清理

---

## File Structure

| 文件 | 类型 | 行数级别 | 职责 |
|---|---|---|---|
| `omni_desk_backend/smart_assistant/middleware/rate_limit.py` | 改 | +50 行 | `check_write_rate_limit()` helper + 常量 |
| `omni_desk_backend/smart_assistant/hooks/base.py` | 改 | +5 行 | `Reject` dataclass 加 `retry_after` 字段 |
| `omni_desk_backend/smart_assistant/hooks/builtin/rate_limit.py` | 新 | ~50 行 | `RateLimitHook` class + `_extract_user` helper |
| `omni_desk_backend/smart_assistant/hooks/builtin/__init__.py` | 改 | +2 行 | 导出 `RateLimitHook` + 更新顶部 docstring |
| `omni_desk_backend/smart_assistant/hooks/wiring.py` | 改 | +3 行 | `register_builtin_hooks` 注册新 hook |
| `omni_desk_backend/smart_assistant/views/chat.py` | 改 | +20 行 | create()/stream() 错误响应透传字段 |
| `omni_desk_backend/smart_assistant/views/doctor.py` | 改 | +15 行 | `_check_cache_rate_limit` 加 write 版本 |
| `omni_desk_backend/smart_assistant/tests/test_rate_limit_hook.py` | 新 | ~200 行 | 6 个测试(hook 单测 + 集成) |
| `omni_desk_backend/smart_assistant/tests/test_reject_retry_after.py` | 新 | ~40 行 | Reject dataclass 新字段测试 |
| `omni_desk_backend/smart_assistant/tests/test_views_rate_limit.py` | 新 | ~80 行 | 视图层字段透传测试 |
| `docs/technical/16-smart-assistant.md` | 改 | +10 行 | hook 列表新增条目(无新建章节) |

总计: 1 个新模块化文件 + 3 处 dataclass/wiring 微改 + 6 个测试文件 + 1 处文档更新。

---

## Task 1: 扩展 `Reject` dataclass 增加 `retry_after` 字段

**Files:**
- Modify: `omni_desk_backend/smart_assistant/hooks/base.py:44-55`(Reject 类定义)
- Test: `omni_desk_backend/smart_assistant/tests/test_reject_retry_after.py`(新)

**Interfaces:**
- Consumes: 无
- Produces: `Reject.reason: str`、`Reject.should_abort: bool`、`Reject.error_code: str | None`、`Reject.retry_after: int | None`(新增,默认 None)

**DRY 提示:** 现有 Reject 调用点全项目约 8 处(看 grep),均为位置参数 `Reject(reason="...", error_code="...")` 或关键字参数。新增字段在末尾,默认 None,无 breaking change。

- [ ] **Step 1: 写失败的测试**

`omni_desk_backend/smart_assistant/tests/test_reject_retry_after.py`:
```python
"""P1A-2: Reject 新增 retry_after 字段,默认值与显式赋值行为。"""

import pytest

from smart_assistant.hooks.base import Reject


class TestRejectRetryAfter:
    def test_default_retry_after_is_none(self):
        """既有 Reject 调用不受影响,默认值 None。"""
        r = Reject(reason="forbidden", error_code="forbidden")
        assert r.retry_after is None

    def test_explicit_retry_after_set(self):
        """显式传 retry_after 时字段可读。"""
        r = Reject(reason="rate_limited", error_code="rate_limit_exceeded", retry_after=42)
        assert r.retry_after == 42

    def test_reject_is_immutable(self):
        """frozen=True 不变,不能改 retry_after。"""
        r = Reject(reason="x", error_code="x")
        with pytest.raises(Exception):  # FrozenInstanceError
            r.retry_after = 99

    def test_positional_kwargs_compatibility(self):
        """既有 Reject(reason=..., error_code=...) kwargs 调用仍能工作。

        注:由于 retry_after 加在 dataclass 末尾,既有的 2-arg 位置调用
        ``Reject(reason_str, code_str)`` 实际会把 code_str 误塞进
        should_abort 字段(因 reason 之后是 should_abort),bool 转换后
        恒为 True。但本项目所有现有 Reject 调用都用 keyword args(grep
        验证),所以本测试只验证 kwargs 路径。
        """
        r = Reject(reason="reason-only", error_code="code-only")
        assert r.retry_after is None
        assert r.should_abort is False
```

- [ ] **Step 2: 跑测试,确认失败**

运行命令:
```bash
cd /home/fz/project/OmniDesk && \
  /home/fz/anaconda3/envs/omni_desk/bin/python -m pytest \
    omni_desk_backend/smart_assistant/tests/test_reject_retry_after.py -v
```

预期输出:`FAILED` 4 个,因为 `Reject` 暂不接受 `retry_after` 参数 → `TypeError: unexpected keyword argument` 或类似。

- [ ] **Step 3: 修改 `Reject` 增加 `retry_after` 字段**

`omni_desk_backend/smart_assistant/hooks/base.py` line 44-55,把:
```python
@dataclass(frozen=True)
class Reject:
    """pre_execute 拒绝执行时的返回结构

    Attributes:
        reason: 拒绝原因(用于日志和审计)
        should_abort: True 表示整个任务终止;False 表示跳过当前工具继续
        error_code: 可选的错误码(给前端用)
    """

    reason: str
    should_abort: bool = False
    error_code: str | None = None
```

改为(关键修改:docstring + 字段):
```python
@dataclass(frozen=True)
class Reject:
    """pre_execute 拒绝执行时的返回结构

    Attributes:
        reason: 拒绝原因(用于日志和审计)
        should_abort: True 表示整个任务终止;False 表示跳过当前工具继续
        error_code: 可选的错误码(给前端用)
        retry_after: 可选的退避秒数(给前端 retry 用,典型场景:限流/P1A-2)
    """

    reason: str
    should_abort: bool = False
    error_code: str | None = None
    retry_after: int | None = None
```

- [ ] **Step 4: 跑测试,确认通过**

运行命令同上(Step 2)。预期:`PASSED` 4 个。

- [ ] **Step 5: Commit**

```bash
cd /home/fz/project/OmniDesk && \
  git add omni_desk_backend/smart_assistant/hooks/base.py \
          omni_desk_backend/smart_assistant/tests/test_reject_retry_after.py && \
  git commit -m "feat(hooks): Reject 新增 retry_after 字段(P1A-2 前置)

为 P1A-2 RateLimitHook 准备:超限时需携带退避秒数,扩展现有 Reject
契约。新增字段 retry_after: int | None = None,向后兼容,既有 8
处 Reject 调用方不受影响。"
```

---

## Task 2: 新增 `check_write_rate_limit` helper + 常量

**Files:**
- Modify: `omni_desk_backend/smart_assistant/middleware/rate_limit.py`(末尾追加)
- Test: 在既有 `omni_desk_backend/smart_assistant/tests/test_middleware_chain_coverage.py` 末尾追加 class `TestWriteRateLimitHelper`(避免散落)

**Interfaces:**
- Consumes: `user_id: int`
- Produces:
  - 常量 `SMART_ASSISTANT_WRITE_RATE_LIMIT: int`(默认 10,env var 覆写)
  - 常量 `WRITE_RATE_WINDOW: int = 60`(秒)
  - 函数 `check_write_rate_limit(user_id: int) -> tuple[bool, int, int]`:返回 `(allowed, remaining, retry_after)`

**与既有 chat helper 的差异**: 只换 env var 名 + namespace 前缀 + 默认值,其余算法一字不差复用(避免重复 DRY 失败)。

- [ ] **Step 1: 写失败的测试**

在 `omni_desk_backend/smart_assistant/tests/test_middleware_chain_coverage.py` 末尾(最后空行后)追加:
```python

# =============================================================================
# P1A-2: middleware/rate_limit.py write-tool helper
# =============================================================================


from smart_assistant.middleware.rate_limit import (
    SMART_ASSISTANT_WRITE_RATE_LIMIT,
    WRITE_RATE_WINDOW,
    check_write_rate_limit,
)


class TestWriteRateLimitHelper:
    def setup_method(self):
        from django.core.cache import cache
        cache.clear()

    def test_first_call_allowed_with_remaining(self):
        """首次调用应放行,remaining = limit - 1。"""
        allowed, remaining, _ = check_write_rate_limit(1001)
        assert allowed is True
        assert remaining == SMART_ASSISTANT_WRITE_RATE_LIMIT - 1
        # cache key 已被设置,值 = 1
        from django.core.cache import cache
        assert cache.get(f"smart_assistant:write_rate_limit:1001") == 1

    def test_at_limit_returns_reject_with_retry_after(self):
        """第 N+1 次调用应被拒,retry_after > 0。"""
        for _ in range(SMART_ASSISTANT_WRITE_RATE_LIMIT):
            check_write_rate_limit(1002)
        allowed, remaining, retry_after = check_write_rate_limit(1002)
        assert allowed is False
        assert remaining == 0
        assert 0 < retry_after <= WRITE_RATE_WINDOW

    def test_independent_user_counters(self):
        """用户 A 满不影响用户 B。"""
        for _ in range(SMART_ASSISTANT_WRITE_RATE_LIMIT):
            check_write_rate_limit(1003)
        allowed_b, _, _ = check_write_rate_limit(1004)  # 不同 user
        assert allowed_b is True

    def test_namespace_separation_from_chat(self):
        """写工具 cache key 与 chat 不共享。"""
        check_write_rate_limit(1005)
        from django.core.cache import cache
        # 写工具 key 命中
        assert cache.get("smart_assistant:write_rate_limit:1005") == 1
        # chat key 不存在
        assert cache.get("smart_assistant:rate_limit:1005") is None
```

- [ ] **Step 2: 跑测试,确认失败**

```bash
cd /home/fz/project/OmniDesk && \
  /home/fz/anaconda3/envs/omni_desk/bin/python -m pytest \
    omni_desk_backend/smart_assistant/tests/test_middleware_chain_coverage.py::TestWriteRateLimitHelper -v
```

预期:4 个 `FAILED`(`cannot import name 'SMART_ASSISTANT_WRITE_RATE_LIMIT'` / `cannot import name 'check_write_rate_limit'`)。

- [ ] **Step 3: 实现 helper + 常量**

`omni_desk_backend/smart_assistant/middleware/rate_limit.py` 末尾(Step 1:43 之后)追加:

```python

# ---------------------------------------------------------------------------
# P1A-2: 写工具速率限制(per user, fixed window)
# ---------------------------------------------------------------------------

# 每用户每分钟最大写工具调用数(配合 ConfirmationHook 的二次确认,
# 防止用户在窗口内频繁触发预演+确认)。
SMART_ASSISTANT_WRITE_RATE_LIMIT = int(
    os.environ.get("SMART_ASSISTANT_WRITE_RATE_LIMIT", "10")
)
WRITE_RATE_WINDOW = 60
WRITE_RATE_NAMESPACE = "smart_assistant:write_rate_limit"


def check_write_rate_limit(user_id):
    """检查用户是否超出写工具速率限制。

    算法同 chat 限流:固定窗口 + cache.incr(失败时回落到 cache.set(key, 1, window))。
    Cache key 命名空间分离,与 chat 限流互不干扰。

    Args:
        user_id: 用户 ID(int)

    Returns:
        (allowed, remaining, retry_after): 同 check_rate_limit 语义。
        retry_after 仅在 allowed=False 时 > 0。
    """
    key = f"{WRITE_RATE_NAMESPACE}:{user_id}"
    current = cache.get(key, 0)

    if current >= SMART_ASSISTANT_WRITE_RATE_LIMIT:
        try:
            ttl = cache.ttl(key) or WRITE_RATE_WINDOW
        except (AttributeError, NotImplementedError):
            ttl = WRITE_RATE_WINDOW
        return False, 0, ttl

    try:
        new_value = cache.incr(key)
    except ValueError:
        cache.set(key, 1, WRITE_RATE_WINDOW)
        new_value = 1
    else:
        cache.set(key, new_value, WRITE_RATE_WINDOW)

    remaining = SMART_ASSISTANT_WRITE_RATE_LIMIT - new_value
    return True, max(remaining, 0), 0
```

- [ ] **Step 4: 跑测试,确认通过**

```bash
cd /home/fz/project/OmniDesk && \
  /home/fz/anaconda3/envs/omni_desk/bin/python -m pytest \
    omni_desk_backend/smart_assistant/tests/test_middleware_chain_coverage.py::TestWriteRateLimitHelper -v
```

预期:4 个 `PASSED`。

- [ ] **Step 5: 跑现有 chat helper 测试确认不被影响**

```bash
cd /home/fz/project/OmniDesk && \
  /home/fz/anaconda3/envs/omni_desk/bin/python -m pytest \
    omni_desk_backend/smart_assistant/tests/test_middleware_chain_coverage.py -v
```

预期:全部 `PASSED`(原 4 chat 测试 + 新 4 write 测试 = 8 个)。

- [ ] **Step 6: Commit**

```bash
cd /home/fz/project/OmniDesk && \
  git add omni_desk_backend/smart_assistant/middleware/rate_limit.py \
          omni_desk_backend/smart_assistant/tests/test_middleware_chain_coverage.py && \
  git commit -m "feat(smart-assistant): 写工具速率限制 helper 与测试(P1A-2)

新增 SMART_ASSISTANT_WRITE_RATE_LIMIT 常量(env var 默认 10)+ 
check_write_rate_limit(user_id) helper,固定窗口算法与 chat 限流
同源;cache key 命名空间 smart_assistant:write_rate_limit: 与 chat
smart_assistant:rate_limit: 互不干扰。

覆盖 4 个测试:
  - 首次允许 + remaining
  - 达到上限返回 retry_after
  - 用户间独立计数
  - 命名空间分离

为 P1A-2 RateLimitHook 提供后端原语。"
```

---

## Task 3: 新增 `RateLimitHook` 类 + 5 个单元测试 + `_extract_user` helper

**Files:**
- Create: `omni_desk_backend/smart_assistant/hooks/builtin/rate_limit.py`
- Modify: `omni_desk_backend/smart_assistant/hooks/builtin/__init__.py`(导出 + 更新顶部 docstring)
- Create: `omni_desk_backend/smart_assistant/tests/test_rate_limit_hook.py`

**Interfaces:**
- Consumes:`check_write_rate_limit(user_id)`(Task 2)、`Reject(reason, error_code, retry_after)`(Task 1)
- Produces:
  - `RateLimitHook`(`ToolHookBase` 子类):`name="write_rate_limit"`、`async def pre_execute(self, tool, ctx, params) -> dict | Reject`
  - `_extract_user(ctx) -> Any | None` 模块私有 helper:支持 `ToolContext.user`、`ctx["user"]`、`getattr(ctx, "user")` 三种形态

**前置阅读:** `BaseTool.require_confirmation: bool = False`(tools/base.py:67)。无需认证用户 / 无 ctx.user 信息时放行(由 `RateLimitMiddleware` 上层兜底)。

- [ ] **Step 1: 写失败的测试**

`omni_desk_backend/smart_assistant/tests/test_rate_limit_hook.py`:
```python
"""P1A-2: RateLimitHook(写工具速率限制钩子)单元测试。

覆盖 hook 在不同上下文(写工具 / 只读工具 / 跨用户 / 匿名 / ctx 形态)下的行为。
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from smart_assistant.hooks.base import Reject
from smart_assistant.hooks.builtin.rate_limit import (
    RateLimitHook,
    _extract_user,
)


def _run(coro):
    """同步驱动 async hook 协程(测试用)。"""
    return asyncio.get_event_loop().run_until_complete(coro)


class _FakeWriteTool:
    """require_confirmation=True 的假写工具。"""
    name = "swap_request_tool"
    require_confirmation = True


class _FakeReadTool:
    """require_confirmation=False 的假只读工具。"""
    name = "schedule_query_tool"
    require_confirmation = False


@pytest.mark.django_db
class TestRateLimitHook:
    def setup_method(self):
        from django.core.cache import cache
        cache.clear()
        self.hook = RateLimitHook()
        self.hook_increment = RateLimitHook()  # 第二个实例同用同一个 helper

    # --- T2: 只读工具直接放行 ---
    def test_read_tool_bypasses_without_counting(self):
        ctx = SimpleNamespace(user=SimpleNamespace(id=2001, is_authenticated=True))
        result = _run(self.hook.pre_execute(_FakeReadTool(), ctx, {"query": "x"}))
        assert result == {"query": "x"}
        from django.core.cache import cache
        assert cache.get("smart_assistant:write_rate_limit:2001") is None

    # --- T1: 写工具首次调用计数 +1 ---
    def test_write_tool_increments_counter(self):
        ctx = SimpleNamespace(user=SimpleNamespace(id=2002, is_authenticated=True))
        result = _run(self.hook.pre_execute(_FakeWriteTool(), ctx, {"query": "x"}))
        assert result == {"query": "x"}
        from django.core.cache import cache
        assert cache.get("smart_assistant:write_rate_limit:2002") == 1

    # --- T3: 超限返回 Reject ---
    def test_limit_exceeded_returns_reject_with_retry_after(self):
        ctx = SimpleNamespace(user=SimpleNamespace(id=2003, is_authenticated=True))
        # 撑到上限
        for _ in range(10):
            _run(self.hook.pre_execute(_FakeWriteTool(), ctx, {"query": "x"}))
        # 第 11 次
        result = _run(self.hook.pre_execute(_FakeWriteTool(), ctx, {"query": "x"}))
        assert isinstance(result, Reject)
        assert result.error_code == "rate_limit_exceeded"
        assert result.retry_after is not None
        assert 0 < result.retry_after <= 60

    # --- T4: 跨用户独立 ---
    def test_different_users_independent_counters(self):
        ctx_a = SimpleNamespace(user=SimpleNamespace(id=2004, is_authenticated=True))
        ctx_b = SimpleNamespace(user=SimpleNamespace(id=2005, is_authenticated=True))
        for _ in range(10):
            _run(self.hook.pre_execute(_FakeWriteTool(), ctx_a, {"query": "x"}))
        # user A 已满
        result_a = _run(self.hook.pre_execute(_FakeWriteTool(), ctx_a, {"query": "x"}))
        assert isinstance(result_a, Reject)
        # user B 不受影响
        result_b = _run(self.hook.pre_execute(_FakeWriteTool(), ctx_b, {"query": "x"}))
        assert result_b == {"query": "x"}

    # --- T5: 未认证放行(由 ChatMiddleware 兜底) ---
    def test_anonymous_passthrough(self):
        ctx = SimpleNamespace(user=SimpleNamespace(id=2006, is_authenticated=False))
        # 写工具 + 未认证 → 放行,不计数
        for _ in range(15):
            result = _run(self.hook.pre_execute(_FakeWriteTool(), ctx, {"query": "x"}))
            assert result == {"query": "x"}
        from django.core.cache import cache
        assert cache.get("smart_assistant:write_rate_limit:2006") is None


@pytest.mark.django_db
class TestExtractUserHelper:
    def test_toolcontext_attribute(self):
        from smart_assistant.tools.tool_context import ToolContext

        user_obj = SimpleNamespace(id=99)
        ctx = ToolContext(user=user_obj)
        assert _extract_user(ctx) is user_obj

    def test_dict_user_value(self):
        user_obj = SimpleNamespace(id=100)
        ctx = {"user": user_obj, "history": []}
        assert _extract_user(ctx) is user_obj

    def test_simple_namespace_fallback(self):
        user_obj = SimpleNamespace(id=101)
        ctx = SimpleNamespace(user=user_obj, history=[])
        assert _extract_user(ctx) is user_obj

    def test_no_user_returns_none(self):
        ctx = {"history": []}
        assert _extract_user(ctx) is None
        assert _extract_user(None) is None
```

- [ ] **Step 2: 跑测试,确认失败**

```bash
cd /home/fz/project/OmniDesk && \
  /home/fz/anaconda3/envs/omni_desk/bin/python -m pytest \
    omni_desk_backend/smart_assistant/tests/test_rate_limit_hook.py -v
```

预期:9 个 `FAILED`(`ImportError: cannot import name 'RateLimitHook' from 'smart_assistant.hooks.builtin.rate_limit'`)。

- [ ] **Step 3: 实现 `RateLimitHook` 类 + `_extract_user` helper**

新文件 `omni_desk_backend/smart_assistant/hooks/builtin/rate_limit.py`:
```python
"""smart_assistant/hooks/builtin/rate_limit.py — 写工具速率限制钩子(P1A-2)。

对 ``require_confirmation=True`` 的工具在 PRE_EXECUTE 阶段返回
``Reject(error_code="rate_limit_exceeded", retry_after=Ns)``,截断同一
用户在固定窗口(默认 60s)内对写工具的反复预演,防止 draft 缓存写风暴
与 audit log 膨胀。

限流算法复用 ``middleware/rate_limit.check_write_rate_limit``(与 chat
限流同源,固定窗口 + Django cache.incr 回落),仅 cache key 命名空间分离。

设计要点:
- read 工具(``require_confirmation=False``)完全不进限流路径,直接放行
- 匿名 / ctx.user 缺失 → 放行,由 ChatMiddleware 兜底匿名拦截
- admin 不豁免(任何人同 1 个用户额度)
- 视 replay 路径(views/chat.py:create())不重跑 hooks,自动避免双计
"""

from __future__ import annotations

import logging
from typing import Any

from smart_assistant.middleware.rate_limit import (
    SMART_ASSISTANT_WRITE_RATE_LIMIT,
    check_write_rate_limit,
)

from ..base import Reject, ToolHookBase

logger = logging.getLogger(__name__)


def _extract_user(ctx: Any) -> Any | None:
    """从 hook ctx 中抽取 user(支持 ToolContext / dict / SimpleNamespace)。

    Returns:
        user 对象;若 ctx 为 None 或不含 user 字段则返回 None。
    """
    if ctx is None:
        return None
    # dict 形态
    if isinstance(ctx, dict):
        return ctx.get("user")
    # dataclass / SimpleNamespace 形态
    return getattr(ctx, "user", None)


class RateLimitHook(ToolHookBase):
    """PRE_EXECUTE:对 require_confirmation=True 工具做 per-user 频次控制。

    注册优先级 25(高于 ConfirmationHook 的 20),保证被限流时不走
    draft / awaiting_confirmation 缓存,避免无效 IO。
    """

    name = "write_rate_limit"

    async def pre_execute(self, tool: Any, ctx: Any, params: dict) -> dict | Reject:
        # read 工具直接放行,不计数
        if not getattr(tool, "require_confirmation", False):
            return params

        user = _extract_user(ctx)
        if user is None or not getattr(user, "is_authenticated", False):
            return params  # 匿名 / ctx 无 user 由 ChatMiddleware 兜底

        allowed, _remaining, retry_after = check_write_rate_limit(user.id)
        if not allowed:
            logger.warning(
                "写工具限流拦截: user_id=%d, retry_after=%ds",
                getattr(user, "id", -1),
                retry_after,
            )
            return Reject(
                reason=(
                    f"写工具调用过于频繁,请 {retry_after} 秒后再试。"
                    f"当前每用户每分钟上限 {SMART_ASSISTANT_WRITE_RATE_LIMIT} 次"
                ),
                error_code="rate_limit_exceeded",
                retry_after=retry_after,
            )
        return params
```

- [ ] **Step 4: 更新 `__init__.py` 导出**

修改 `omni_desk_backend/smart_assistant/hooks/builtin/__init__.py`,把:
```python
"""内置 Hook 实现

已落地:
- AuditLogHook: 统一写 AgentLog(工具级审计,含 risk_level)+ AgentEvent(任务级审计)
- PiiMaskingHook: 对工具输出中的手机号/身份证/邮箱做掩码(post_execute)
- TimeoutGuardHook: 工具超时熔断(配置入口 + 执行包装层,详见模块文档)
- ConfirmationHook: 写工具二次确认(PRE_EXECUTE,require_confirmation=True 时
  返回 Reject(confirmation_required),见模块文档)

规划中:
- SensitiveDataGateHook: 权限门控(替代硬编码 required_auth=True)
"""
```

改为:
```python
"""内置 Hook 实现

已落地:
- AuditLogHook: 统一写 AgentLog(工具级审计,含 risk_level)+ AgentEvent(任务级审计)
- PiiMaskingHook: 对工具输出中的手机号/身份证/邮箱做掩码(post_execute)
- TimeoutGuardHook: 工具超时熔断(配置入口 + 执行包装层,详见模块文档)
- ConfirmationHook: 写工具二次确认(PRE_EXECUTE,require_confirmation=True 时
  返回 Reject(confirmation_required),见模块文档)
- RateLimitHook: 写工具速率限制(PRE_EXECUTE,require_confirmation=True 时
  按 user_id 固定窗口计 count,超限返回 Reject(rate_limit_exceeded),
  P1A-2,见模块文档)

规划中:
- SensitiveDataGateHook: 权限门控(替代硬编码 required_auth=True)
"""
```

并在 import 段把:
```python
from .audit_log import AuditLogHook
from .confirmation import ConfirmationHook
from .pii_masking import PiiMaskingHook
from .timeout_guard import TimeoutGuardHook

__all__ = [
    "AuditLogHook",
    "ConfirmationHook",
    "PiiMaskingHook",
    "TimeoutGuardHook",
]
```

改为:
```python
from .audit_log import AuditLogHook
from .confirmation import ConfirmationHook
from .pii_masking import PiiMaskingHook
from .rate_limit import RateLimitHook
from .timeout_guard import TimeoutGuardHook

__all__ = [
    "AuditLogHook",
    "ConfirmationHook",
    "PiiMaskingHook",
    "RateLimitHook",
    "TimeoutGuardHook",
]
```

- [ ] **Step 5: 跑测试,确认通过**

```bash
cd /home/fz/project/OmniDesk && \
  /home/fz/anaconda3/envs/omni_desk/bin/python -m pytest \
    omni_desk_backend/smart_assistant/tests/test_rate_limit_hook.py -v
```

预期:9 个 `PASSED`(5 个 hook 测试 + 4 个 _extract_user 测试)。

- [ ] **Step 6: Commit**

```bash
cd /home/fz/project/OmniDesk && \
  git add omni_desk_backend/smart_assistant/hooks/builtin/rate_limit.py \
          omni_desk_backend/smart_assistant/hooks/builtin/__init__.py \
          omni_desk_backend/smart_assistant/tests/test_rate_limit_hook.py && \
  git commit -m "feat(smart-assistant): RateLimitHook(P1A-2 前置)

新增 RateLimitHook(PRE_EXECUTE)对 require_confirmation=True 工
具做 user 级固定窗口频次控制,使用 middleware/rate_limit.check_
write_rate_limit helper 与 Django cache。超限返回 Reject(rate_
limit_exceeded, retry_after=Ns)。

注册优先级 25,高于 ConfirmationHook(20),先频次再确认,避免
被限流时仍触发 draft 缓存写。

新增 _extract_user(ctx) helper 兼容 ToolContext / dict / SimpleNamespace
三种 ctx 形态。

5 hook 单测 + 4 helper 单测,9 个用例全绿。"
```

---

## Task 4: 把 `RateLimitHook` 接入 `register_builtin_hooks`

**Files:**
- Modify: `omni_desk_backend/smart_assistant/hooks/wiring.py:36-65`(`register_builtin_hooks` 函数)
- Modify: `omni_desk_backend/smart_assistant/tests/test_hooks_wiring.py`(追加 1 测试)

**Interfaces:**
- Consumes: `RateLimitHook`(Task 3)
- Produces: 修了的 `register_builtin_hooks()` + 测试断言 "register 后 list_hooks(PRE_EXECUTE) 包含 'write_rate_limit'"

**幂等保证:** 沿用现有 `if "<name>" not in existing_names` 模式,避免 apps.ready() 多次调用重复挂载。

- [ ] **Step 1: 写失败的测试**

在 `omni_desk_backend/smart_assistant/tests/test_hooks_wiring.py` 末尾追加(若文件结尾为某函数则在其外层缩进加;若不存在则创建):
```python
"""P1A-2: register_builtin_hooks 应自动挂载 RateLimitHook。"""

import pytest

from smart_assistant.hooks.base import HookEvent, get_registry


@pytest.mark.django_db
class TestBuiltinHooksRegistration:
    def setup_method(self):
        # 强制重置全局注册表,保证测试独立
        get_registry(reset=True)

    def test_rate_limit_hook_registered_after_call(self):
        """register_builtin_hooks() 后 PRE_EXECUTE 链应包含 RateLimitHook。"""
        from smart_assistant.hooks.wiring import register_builtin_hooks

        register_builtin_hooks()

        reg = get_registry()
        pre_hooks = reg.list_hooks(HookEvent.PRE_EXECUTE)
        names = {getattr(h, "name", type(h).__name__) for h in pre_hooks}
        assert "write_rate_limit" in names
        assert "confirmation" in names  # 既有 hook 也应在

    def test_register_is_idempotent(self):
        """多次调用 register_builtin_hooks 不会重复挂载。"""
        from smart_assistant.hooks.wiring import register_builtin_hooks

        register_builtin_hooks()
        register_builtin_hooks()
        register_builtin_hooks()

        reg = get_registry()
        names = [getattr(h, "name", type(h).__name__) for h in reg.list_hooks(HookEvent.PRE_EXECUTE)]
        # write_rate_limit 只挂一次
        assert names.count("write_rate_limit") == 1
```

若 `test_hooks_wiring.py` 不存在,需先 `touch` 并加 minimum 内容:
```python
"""smart_assistant hook wiring 测试占位(P1A-2 补充)。"""
```
再追加上述 class。

- [ ] **Step 2: 跑测试,确认失败**

```bash
cd /home/fz/project/OmniDesk && \
  /home/fz/anaconda3/envs/omni_desk/bin/python -m pytest \
    omni_desk_backend/smart_assistant/tests/test_hooks_wiring.py -v
```

预期:`AssertionError: 'write_rate_limit' not in names`(因为还没接线)。

- [ ] **Step 3: 修改 `register_builtin_hooks`**

`omni_desk_backend/smart_assistant/hooks/wiring.py`,把 line 36-65 函数体改为:

```python
def register_builtin_hooks(registry: HookRegistry | None = None) -> HookRegistry:
    """把内置钩子注册进全局(或指定)注册表,幂等。

    - ``PiiMaskingHook`` → ``POST_EXECUTE``,priority=5
      (约定先审计后脱敏:审计钩子 priority=10 先跑,拿到原文)
    - ``TimeoutGuardHook`` → ``ON_FAILURE``,priority=10
      (超时异常泄漏到钩子链时提供结构化 fallback 兜底;真正的计时
      由 ``execute_guarded`` 执行包装层完成,见模块级文档)
    - ``ConfirmationHook`` → ``PRE_EXECUTE``,priority=20
      (写工具二次确认,配合前端 confirm-replay 流程)
    - ``RateLimitHook`` → ``PRE_EXECUTE``,priority=25
      (写工具速率限制,P1A-2;优先级高于 ConfirmationHook 是因
      为被限流时不应再触发 draft 缓存,先频次再确认)

    幂等保证:Django ``apps.ready()`` 在测试环境可能被多次调用,按 hook
    ``name`` 去重,避免同一钩子重复挂载导致输出被多次处理。

    Args:
        registry: 目标注册表;None 表示全局单例 ``get_registry()``。

    Returns:
        注册完成后的注册表实例。
    """
    # 延迟导入,避免 hooks.wiring ↔ hooks.builtin 在应用加载期循环
    from .builtin import (
        ConfirmationHook,
        PiiMaskingHook,
        RateLimitHook,
        TimeoutGuardHook,
    )

    reg = registry or get_registry()
    existing_names = {getattr(h, "name", None) for h in reg.list_hooks()}
    if "pii_masking" not in existing_names:
        reg.register(HookEvent.POST_EXECUTE, PiiMaskingHook(), priority=5)
    if "timeout_guard" not in existing_names:
        reg.register(HookEvent.ON_FAILURE, TimeoutGuardHook(), priority=10)
    if "confirmation" not in existing_names:
        reg.register(HookEvent.PRE_EXECUTE, ConfirmationHook(), priority=20)
    if "write_rate_limit" not in existing_names:
        reg.register(HookEvent.PRE_EXECUTE, RateLimitHook(), priority=25)
    return reg
```

同时更新模块顶部 docstring(line 5-6 把"register_builtin_hooks():在 apps.ready() 中调用,把 PiiMaskingHook / TimeoutGuardHook 幂等注册进全局 HookRegistry"中的内置列表一并补充 RateLimitHook / ConfirmationHook)。最小改动:在 line 5 字符串中加 "ConfirmationHook / RateLimitHook"。

- [ ] **Step 4: 跑测试,确认通过**

```bash
cd /home/fz/project/OmniDesk && \
  /home/fz/anaconda3/envs/omni_desk/bin/python -m pytest \
    omni_desk_backend/smart_assistant/tests/test_hooks_wiring.py -v
```

预期:2 个 `PASSED`。

- [ ] **Step 5: Commit**

```bash
cd /home/fz/project/OmniDesk && \
  git add omni_desk_backend/smart_assistant/hooks/wiring.py \
          omni_desk_backend/smart_assistant/tests/test_hooks_wiring.py && \
  git commit -m "feat(hooks): 接线 RateLimitHook(P1A-2)

register_builtin_hooks() 在 PRE_EXECUTE 链以 priority=25 挂载
RateLimitHook(高于 ConfirmationHook 的 20),被限流时不走 draft
缓存。

通过 existing_names 守卫保证 idempotent;apps.ready() 多次调用
不会重复挂载。"
```

---

## Task 5: 视图层透传 `error_code` + `retry_after` 到前端响应

**Files:**
- Modify: `omni_desk_backend/smart_assistant/views/chat.py:40`(顶部导入 + `_resolve_error` 函数),`create()` 和 `stream()` 错误分支
- Create: `omni_desk_backend/smart_assistant/tests/test_views_rate_limit.py`

**Interfaces:**
- Consumes: `Reject` 中 `error_code` / `retry_after`(Task 1),Orchestrator 在 `process_query` 路径下的 Reject 结果
- Produces:
  - `POST /api/smart-assistant/chat/` 错误响应 payload 增加 `error_code` + `retry_after` 字段(若 Reject 有)
  - `POST /api/smart-assistant/chat/stream/` SSE 事件载荷同上

**注意:** Orchestrator 当前在第 360 行调用 `apply_pre_execute_hooks`,但仅对 `error_code == "confirmation_required"` 做特殊分支。其他 Reject(例如 `rate_limit_exceeded`)目前会被透传给视图——本任务要确保视图层把它正确塞进 JSON 响应。

- [ ] **Step 1: 读 `orchestrator.py` 第 359-405 行确认 RateLimit Reject 透传路径**

阅读代码确认 orchestrator 在收到 `Reject(error_code="rate_limit_exceeded")` 时 **不会**走 draft / awaiting 路径,而是落到既有 `result.get("error")` 分支。

如果发现 orchestrator 对**任何非 `confirmation_required` 的 Reject** 抛错或忽略,在本任务 Step 2 之前的 orchestrator 微调作为本 Task 的前置子步骤(放入同一 commit,docstring 标注"P1A-2:让非 confirmation_required Reject 透传")。

**预期现状(已确认):** orchestrator 第 359-405 行逻辑——`isinstance(hook_result, Reject) and hook_result.error_code == "confirmation_required"` 才走 draft 分支;否则透传 result(在 `process_query` 末尾的 `_format_result` 已含 `error: True` 分支,但 **不含** `error_code` 字段)。

- [ ] **Step 2: 修改 Orchestrator `_format_result` 透传字段**

`omni_desk_backend/smart_assistant/agent/orchestrator.py`,在第 360 行附近查找(已有 `hook_result = apply_pre_execute_hooks(...)`):
```python
                hook_result = apply_pre_execute_hooks(tool, hook_ctx, {"query": user_query})
                if isinstance(hook_result, Reject) and hook_result.error_code == "confirmation_required":
                    ...
                # 非 confirmation_required 的 Reject 或其他情况:走既有路径
                # (apply_pre_execute_hooks 内部已做失败降级,透传 params)
```

修改为(把"非 confirmation_required 的 Reject"分支用 dict 把 Reject 字段塞进后续 result;不破坏 confirmation 路径):
```python
                hook_result = apply_pre_execute_hooks(tool, hook_ctx, {"query": user_query})
                if isinstance(hook_result, Reject) and hook_result.error_code == "confirmation_required":
                    ...
                # 非 confirmation_required 的 Reject(如 rate_limit_exceeded):
                # 把 error_code / retry_after 挂到 result 上,
                # 由视图层透传给前端(P1A-2)。
                rate_limit_error = None
                if isinstance(hook_result, Reject):
                    rate_limit_error = {
                        "error_code": hook_result.error_code,
                        "retry_after": getattr(hook_result, "retry_after", None),
                        "message": hook_result.reason,
                    }
                # 既有路径(apply_pre_execute_hooks 内部已做失败降级)
```

然后在 orchestrator 末尾的 `_format_result` / 错误分支中追加(查找 `result = {` 或 `return {...}` 的位置):
```python
                if rate_limit_error and result.get("error"):
                    result["error_code"] = rate_limit_error["error_code"]
                    result["retry_after"] = rate_limit_error["retry_after"]
                    result["answer"] = rate_limit_error["message"]
```

注:若 `_format_result` 实现是另一个函数,把上面 2 处修改合并到该函数(实际位置由 grep 确认)。

- [ ] **Step 3: 修改视图层 `chat.py` 透传字段**

`omni_desk_backend/smart_assistant/views/chat.py`,在 `create()` 与 `stream()` 错误响应分支追加字段(grep `"error": True` 定位)。

最小补丁(在 `return Response(...)` 含 `"error": True` 处):
```python
            return Response({
                ...
                "error": True,
                "error_code": result.get("error_code"),  # P1A-2:透传
                "retry_after": result.get("retry_after"),  # P1A-2:透传
                ...
            }, status=...)
```

确认 create() / stream() 各 1 处错误路径,字段缺省时返回 `None` ——前端按通用错误展示,无 breaking。

- [ ] **Step 4: 写失败的测试**

`omni_desk_backend/smart_assistant/tests/test_views_rate_limit.py`:
```python
"""P1A-2: 视图层透传 rate_limit_exceeded error_code + retry_after。"""

import json

import pytest
from django.test import RequestFactory

from omni_desk_backend.smart_assistant.views.chat import SmartChatViewSet


@pytest.mark.django_db
class TestChatViewRateLimitPassthrough:
    def setup_method(self):
        from django.core.cache import cache
        cache.clear()
        self.factory = RequestFactory()
        self.view = SmartChatViewSet.as_view({"post": "create"})

    def _post(self):
        req = self.factory.post(
            "/api/smart-assistant/chat/",
            data=json.dumps({"query": "swap"}),
            content_type="application/json",
        )
        from django.contrib.auth.models import AnonymousUser
        # 实际测试用 admin_user_obj fixture;这里简化为登入用户
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user = User.objects.create_user(username="p1a2_tester", password="x")
        req.user = user
        return req

    def test_rate_limit_error_in_response(self, monkeypatch):
        """orchestrator 返回 rate_limit_exceeded 时,响应含 error_code + retry_after。"""
        # 用 monkeypatch 让 orchestrator 直接返回 rate_limit_exceeded error
        from smart_assistant.agent import orchestrator as orch_mod

        def fake_process_query(*args, **kwargs):
            return {
                "answer": "写工具调用过于频繁,请 30 秒后再试",
                "intent": "swap_request",
                "tool_used": "swap_request_tool",
                "tool_result": None,
                "error": True,
                "error_code": "rate_limit_exceeded",
                "retry_after": 30,
            }
        monkeypatch.setattr(
            orch_mod.AgentOrchestrator, "process_query", fake_process_query
        )

        req = self._post()
        resp = self.view(req)
        resp.render()
        data = json.loads(resp.content)

        assert data["error"] is True
        assert data["error_code"] == "rate_limit_exceeded"
        assert data["retry_after"] == 30
```

> 注:完整 e2e 测试(走真实 RateLimitHook + orchestrator)留给 Task 5 重构后在 task 7 中跑全量 pytest 兜底;此处聚焦"视图层透传契约"。

- [ ] **Step 5: 跑测试,确认先红后绿**

```bash
cd /home/fz/project/OmniDesk && \
  /home/fz/anaconda3/envs/omni_desk/bin/python -m pytest \
    omni_desk_backend/smart_assistant/tests/test_views_rate_limit.py -v
```

第一次跑前(Step 2/3 未做):预期 `FAIL`(`data["error_code"] is None`)。

应用 Step 2/3 修改后再跑:预期 `PASSED`。

- [ ] **Step 6: Commit**

```bash
cd /home/fz/project/OmniDesk && \
  git add omni_desk_backend/smart_assistant/agent/orchestrator.py \
          omni_desk_backend/smart_assistant/views/chat.py \
          omni_desk_backend/smart_assistant/tests/test_views_rate_limit.py && \
  git commit -m "feat(smart-assistant): 透传 error_code + retry_after 响应字段(P1A-2)

orchestrator.process_query 对 PRE_EXECUTE 非 confirmation_required
的 Reject(如 RateLimitHook 的 rate_limit_exceeded)把 error_code /
retry_after 挂到 result,视图层 create() / stream() 透传给前端。

错误响应结构新增(向后兼容,旧字段缺省时为 None):
  error_code: str | None
  retry_after: int | None

前端按既有 toast / error display 处理;特殊文案为 rate_limit_exceeded
时显示 retry_after 秒数。"
```

---

## Task 6: doctor.py 扩展 + 文档更新 + 全量验证

**Files:**
- Modify: `omni_desk_backend/smart_assistant/views/doctor.py:208-`(`_check_cache_rate_limit` 函数)
- Modify: `docs/technical/16-smart-assistant.md`(末尾追加 hook 列表项)
- Test: 在 `omni_desk_backend/smart_assistant/tests/test_doctor.py` 追加 1 个 case

**Interfaces:**
- Consumes: `check_write_rate_limit` helper + env var `SMART_ASSISTANT_WRITE_RATE_LIMIT`
- Produces: `/api/smart-assistant/doctor/` 响应中 `cache_write_rate_limit` 项,与 `cache_rate_limit` 同结构

**文档更新范围**: 仅在 `16-smart-assistant.md` 内置 Hook 一览表中追加"RateLimitHook" 行;**不**新建独立章节(后续与 Phase 文档一并整理)。

- [ ] **Step 1: 写失败的测试**

在 `omni_desk_backend/smart_assistant/tests/test_doctor.py` 中追加(用 `pytest.mark.django_db` 与既有 class 同层):
```python

class TestDoctorWriteRateLimitCheck:
    def setup_method(self):
        from django.core.cache import cache
        cache.clear()

    def test_cache_write_rate_limit_check_present(self, admin_user_obj):
        """doctor 端点应同时报告 chat 与 write-tool 两套限流配置。"""
        from smart_assistant.views.doctor import get_doctor_status

        result = get_doctor_status()
        checks_by_name = {c["name"]: c for c in result["checks"]}
        assert "cache_write_rate_limit" in checks_by_name
        assert checks_by_name["cache_write_rate_limit"]["status"] == "ok"
        assert checks_by_name["cache_write_rate_limit"]["kind"] == "info"
```

- [ ] **Step 2: 跑测试,确认失败**

```bash
cd /home/fz/project/OmniDesk && \
  /home/fz/anaconda3/envs/omni_desk/bin/python -m pytest \
    omni_desk_backend/smart_assistant/tests/test_doctor.py::TestDoctorWriteRateLimitCheck -v
```

预期:`FAIL`(因为还没有 `cache_write_rate_limit` 项)。

- [ ] **Step 3: 扩展 doctor 检查项**

`omni_desk_backend/smart_assistant/views/doctor.py`,把 `_check_cache_rate_limit` 改名并复制一份为 `_check_cache_write_rate_limit`:

(具体修改模式:把现有 `_check_cache_rate_limit` 函数复制,改名 + 改 import + 改阈值常量来源 + 改 `name="cache_write_rate_limit"`。约 +15 行。)

简化做法(避免重复代码):抽取 helper `_rate_limit_check(name, limit_const, env_name)`:
```python
def _rate_limit_check(name: str, limit_const: int, env_name: str) -> dict:
    from smart_assistant.middleware.rate_limit import SMART_CHAT_RATE_LIMIT, SMART_ASSISTANT_WRITE_RATE_LIMIT
    config = {
        "limit": limit_const,
        "window_seconds": 60,
        "env_name": env_name,
        "cache_backend": settings.CACHES["default"]["BACKEND"],
    }
    return {
        "name": name,
        "status": "ok",
        "kind": "info",
        "message": f"速率限制配置: {config['cache_backend'].rsplit('.', 1)[-1]} / 每用户 {config['limit']} 次/{config['window_seconds']}s",
        "config": config,
    }


def _check_cache_rate_limit() -> list:
    return [_rate_limit_check("cache_rate_limit", SMART_CHAT_RATE_LIMIT, "SMART_ASSISTANT_CHAT_RATE_LIMIT"),
            _rate_limit_check("cache_write_rate_limit", SMART_ASSISTANT_WRITE_RATE_LIMIT, "SMART_ASSISTANT_WRITE_RATE_LIMIT")]
```

把这两项作为列表返回(若现有 `_check_cache_rate_limit` 是单 dict,需要把调用方改为累加 list)。

具体路径由 grep 决定:看现有 `_check_cache_rate_limit()` 返回类型 + 在 `/api/smart-assistant/doctor/` 视图中的调用方式。

- [ ] **Step 4: 跑测试,确认通过**

```bash
cd /home/fz/project/OmniDesk && \
  /home/fz/anaconda3/envs/omni_desk/bin/python -m pytest \
    omni_desk_backend/smart_assistant/tests/test_doctor.py -v
```

预期:全绿(包括既有 + 新 case)。

- [ ] **Step 5: 更新技术文档**

`docs/technical/16-smart-assistant.md`,查 grep `"内置 Hook"` 或 `"AuditLogHook"` 定位,在既有 Hook 列表末尾追加:
```markdown
- **RateLimitHook**(P1A-2,2026-08-10):PRE_EXECUTE,priority=25;对所有
  `require_confirmation=True` 工具按用户 fixed window(默认 10/60s,
  env var `SMART_ASSISTANT_WRITE_RATE_LIMIT` 可配)限频;超限返回
  `Reject(error_code="rate_limit_exceeded", retry_after=Ns)`,前端
  toast 显示 Ns 后重试。详情见
  `docs/superpowers/specs/2026-08-10-p1a2-write-tool-rate-limit-design.md`(实施
  plan `docs/plans/2026-08-10_p1a2-write-tool-rate-limit.md`)。
```

若该 markdown 文件中 hook 列表用表格/章节结构,沿用同结构追加。

- [ ] **Step 6: 跑全量 backend 测试 + ruff**

```bash
cd /home/fz/project/OmniDesk && \
  /home/fz/anaconda3/envs/omni_desk/bin/python -m pytest \
    --ds=omni_desk_backend.settings.test \
    -x -q 2>&1 | tail -30
```

预期:全绿(测试数 ≥ 2309,无新增失败)。任何 failed 测试停下来定位。

同时跑 ruff:
```bash
cd /home/fz/project/OmniDesk && \
  /home/fz/anaconda3/envs/omni_desk/bin/python -m ruff check omni_desk_backend/smart_assistant/
```
预期:无 error,warning 可忽略。

也跑 frontend 烟雾测试:
```bash
cd /home/fz/project/OmniDesk/omni_desk_frontend && \
  npm test -- --watchAll=false --silent 2>&1 | tail -10
```
预期:`Tests:` 末行 ≥ 517 passed(前端无改动,数字应一致)。

- [ ] **Step 7: 整理 commit + 推送准备**

```bash
cd /home/fz/project/OmniDesk && \
  git add omni_desk_backend/smart_assistant/views/doctor.py \
          omni_desk_backend/smart_assistant/tests/test_doctor.py \
          docs/technical/16-smart-assistant.md && \
  git commit -m "docs+feat(smart-assistant): RateLimitHook 上线文档 + doctor 自检(P1A-2)

- doctor 端点 cache_write_rate_limit 自检项,与 cache_rate_limit 同结构
- 16-smart-assistant.md 内置 Hook 列表追加 RateLimitHook 条目
- 引用 spec + plan 路径供追踪

为 PR 准备。"
```

完成后:
```bash
cd /home/fz/project/OmniDesk && \
  git log --oneline main..HEAD  # 列出本分支所有 commit
```
预期:6 个 commit(Task 1-6 各一个)+ 1 个 chore。

- [ ] **Step 8: 推送 + 开 PR**

```bash
cd /home/fz/project/OmniDesk && \
  git push -u origin feat/p1a2-write-tool-rate-limit
```

然后用 `gh pr create`:
```bash
gh pr create \
  --base main \
  --head feat/p1a2-write-tool-rate-limit \
  --title "feat(smart-assistant): P1A-2 写工具速率限制" \
  --body "## 概要
- 新增 RateLimitHook(PRE_EXECUTE,priority=25)
- 复用 chat 限流 helper,新增 check_write_rate_limit(user_id)
- 视图层透传 error_code + retry_after 到前端响应

## 设计 spec
docs/superpowers/specs/2026-08-10-p1a2-write-tool-rate-limit-design.md

## 实施 plan
docs/plans/2026-08-10_p1a2-write-tool-rate-limit.md

## 测试覆盖
- Reject dataclass 新字段(4)
- write rate limit helper(4)
- RateLimitHook 单元(5)
- _extract_user helper(4)
- register_builtin_hooks 集成(2)
- chat 视图层契约(1)
- doctor 自检(1)

新测试合计 21 个,既有测试不退步。

## 配置
- env var SMART_ASSISTANT_WRITE_RATE_LIMIT(默认 10)
- 不接 LlmAppConfig DB 调谐
- cache backend 复用既有(生产 Redis / dev LocMemCache)

## 验收
- [ ] backend pytest 全绿
- [ ] frontend jest 全绿
- [ ] ruff lint 通过
- [ ] 配置自检(cache_write_rate_limit)通过

关联:docs/superpowers/specs/2026-08-10-p1a2-write-tool-rate-limit-design.md"
```

---

## Self-Review (执行前自审)

按 writing-plans skill 清单:
1. ✅ Spec 覆盖 — 7 个 spec 要求都映射到 Task: helper 创建(T2)/ Reject retry_after(T1)/ RateLimitHook 行为(T3)/ 接线(T4)/ 视图层透传(T5)/ doctor 自检+ 文档(T6)
2. ✅ 占位符扫描 — 无 TBD/TODO/未定义 type/未实现接口
3. ✅ 类型一致性 — `check_write_rate_limit(user_id) -> tuple[bool, int, int]`、`RateLimitHook.name = "write_rate_limit"`、`cache_key = "smart_assistant:write_rate_limit:{user_id}"` 在所有 Task 中相同
4. ⚠️ **潜在歧义点**:
   - Task 5 Step 1 提到 orchestrator 改动是基于 §3.3 contract,但实际 orchestrator `_format_result` 的位置需要 grep 确认——Step 2 留 fallback
   - Task 6 Step 3 的 doctor 重构包含改造既有 `_check_cache_rate_limit` 为 list,这与既有 doc 契约略变;若既有测试期待单 dict,需协调兜底

---

## 验收总表

跑过下列命令后 P1A-2 视为完成:

```bash
# 1. backend 全量 pytest
/home/fz/anaconda3/envs/omni_desk/bin/python -m pytest --ds=omni_desk_backend.settings.test -q

# 2. frontend jest
cd omni_desk_frontend && npm test -- --watchAll=false --silent

# 3. backend lint
cd ../ && /home/fz/anaconda3/envs/omni_desk/bin/python -m ruff check omni_desk_backend/smart_assistant/

# 4. doctor 端点实地检查
cd ../ && /home/fz/anaconda3/envs/omni_desk/bin/python manage.py runserver &
sleep 3
curl -H "Authorization: Bearer <token>" http://127.0.0.1:8000/api/smart-assistant/doctor/ | jq '.checks[] | select(.name | startswith("cache_"))'

# 5. PR 状态 CI 绿
gh pr checks --watch
```

完成标准:
- ✅ backend pytest ≥ 2309 个测试,0 failed
- ✅ frontend jest ≥ 517 个测试,0 failed
- ✅ ruff 0 error
- ✅ doctor 报告含 `cache_write_rate_limit` 项
- ✅ gh pr checks 全绿
- ✅ 用户 merge PR

---

## 不在范围内(本 plan 明确不做,留待后续)

- per-tool 细粒度限流(等 P1A-6 工具注册中心雏形时再加)
- LlmAppConfig DB 调谐阈值(只 env var)
- 滑动窗口 / token bucket(固定窗口已够)
- admin 豁免(任何人同等额度)
- 数字员工 P1B-2 主动巡检写操作的限额(同 hook 自动覆盖)
- 前端 UI 大改版(只加字符串分支;若需改文案超过 1 行作为 follow-up)