# swap_request 工具业务逻辑补全 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 补全 `SwapRequestCreateTool` / `SwapRequestDecideTool` 的 `_dry_run` 和 `_confirmed` 业务逻辑,使 confirm-replay 流程在换班场景下端到端可用,并把 ViewSet 业务逻辑抽到 `events/services/swap_service.py` 复用。

**Architecture:**
- 抽出 `events/services/swap_service.py`,ViewSet 调 service(API 零变化)
- 新增 `smart_assistant/extractors/swap_extractor.py`,LLM 专用 prompt 解析中文 query
- 工具 `_dry_run` 解析 + 校验 → draft;`_confirmed` 走 service 落库
- 失败/缺字段 → `_dry_run` 直接 `found=False`,不让用户进入确认

**Tech Stack:** Django 4.2 + DRF + smart_assistant(LLM client + confirm-replay) + pytest(in-memory SQLite)

## Global Constraints

- Python 3.10
- I18N `zh-hans`,所有用户可见消息中文
- 测试环境:`pytest --ds=omni_desk_backend.settings.test`
- 覆盖率 ≥ 80%(项目标准)
- ruff check + mypy clean
- 现有 fixtures 复用(`user_a` / `user_b` / `personnel_a` / `personnel_b` / `schedule_a` / `schedule_b` / `swap_request`)
- 现有 API 集成测试 (`events/tests/test_swap_request_api.py`) 必须 0 退化
- 所有写操作走 `transaction.atomic()`
- LLM 失败/非法 JSON → 返回 `found=False`,不降级到规则

---

## File Structure

| 路径 | 操作 | 职责 |
|---|---|---|
| `omni_desk_backend/events/services/__init__.py` | 新 | 包初始化 |
| `omni_desk_backend/events/services/swap_service.py` | 新 | 4 个 service 函数 + 3 个异常类 |
| `omni_desk_backend/events/views/swap.py` | 改 | 4 个动作改为薄包装,调 service |
| `omni_desk_backend/smart_assistant/extractors/__init__.py` | 新 | 包初始化 |
| `omni_desk_backend/smart_assistant/extractors/prompts/__init__.py` | 新 | 包初始化 |
| `omni_desk_backend/smart_assistant/extractors/prompts/swap_create_prompt.py` | 新 | Create prompt 模板 |
| `omni_desk_backend/smart_assistant/extractors/prompts/swap_decide_prompt.py` | 新 | Decide prompt 模板 |
| `omni_desk_backend/smart_assistant/extractors/swap_extractor.py` | 新 | LLM 解析 + 鲁棒性 + 2 个 dataclass |
| `omni_desk_backend/smart_assistant/tools/swap_request_tool.py` | 改 | `_dry_run` / `_confirmed` 调 ext + service |
| `omni_desk_backend/smart_assistant/views/chat.py` | 改 | replay 路径注入 `user` |
| `omni_desk_backend/events/tests/test_swap_service.py` | 新 | 4 函数 × 3-5 case |
| `omni_desk_backend/smart_assistant/tests/test_swap_extractor.py` | 新 | 2 extractor × 4 case |
| `omni_desk_backend/smart_assistant/tests/test_swap_request_tool.py` | 改 | 现有 6 case + 新增 12 case |

---

## Task 1: events/services 包初始化 + 3 个异常类

**Files:**
- Create: `omni_desk_backend/events/services/__init__.py`
- Create: `omni_desk_backend/events/services/swap_service.py`
- Test: `omni_desk_backend/events/tests/test_swap_service.py`

**Interfaces:**
- Consumed by: Task 2 (在同文件定义 service 函数)
- Produces: `SwapServiceError`, `SwapPermissionError`, `SwapNotFoundError`(异常类)

- [ ] **Step 1: 写 init 文件**

```python
# omni_desk_backend/events/services/__init__.py
"""events 业务服务层包。

把 ViewSet 内的业务逻辑抽出来,供 HTTP API、CLI、Smart Assistant 工具等
不同入口复用,避免同一逻辑在多处维护产生分叉。
"""
```

- [ ] **Step 2: 写交换 service 异常类 + 模块 docstring**

```python
# omni_desk_backend/events/services/swap_service.py
"""events.services.swap_service — 换班申请业务逻辑

原 events/views/swap.py 的 perform_create / accept / reject / cancel 内部
逻辑抽到这里,ViewSet 改为薄包装。本模块不依赖 DRF Request,任何调用方
(工具/HTTP/CLI)都可复用。

调用方需捕获本模块定义的 3 种异常:
- SwapServiceError: 业务错误(目标人不存在 / 排班不存在 / 状态非法)
- SwapPermissionError: 权限错误(用户没关联 personnel / 不是接收方/申请方)
- SwapNotFoundError: swap_id 不存在

ViewSet 转换为:
- SwapPermissionError → DRF PermissionDenied(403)
- SwapNotFoundError → 404
- SwapServiceError → DRF ValidationError(400) 或 409
"""

from __future__ import annotations

from django.utils import timezone
from django.db import transaction


class SwapServiceError(Exception):
    """业务错误(非用户/权限),由调用方转为 HTTP 400/409。"""


class SwapPermissionError(Exception):
    """权限错误(用户没关联 personnel / 不是接收方/申请方)。"""


class SwapNotFoundError(Exception):
    """swap_id 不存在。"""
```

- [ ] **Step 3: 写测试 — 3 个异常类的实例化**

```python
# omni_desk_backend/events/tests/test_swap_service.py
"""swap_service 单元测试"""

import pytest

from events.services.swap_service import (
    SwapServiceError,
    SwapPermissionError,
    SwapNotFoundError,
)


class TestSwapServiceExceptions:
    """异常类可正确实例化 + 抛出/捕获语义正确"""

    def test_swap_service_error_inherits_exception(self):
        """SwapServiceError 是 Exception 子类"""
        assert issubclass(SwapServiceError, Exception)

    def test_swap_permission_error_inherits_exception(self):
        """SwapPermissionError 是 Exception 子类"""
        assert issubclass(SwapPermissionError, Exception)

    def test_swap_not_found_error_inherits_exception(self):
        """SwapNotFoundError 是 Exception 子类"""
        assert issubclass(SwapNotFoundError, Exception)

    def test_swap_service_error_catchable(self):
        """SwapServiceError 可被 except Exception 捕获"""
        with pytest.raises(SwapServiceError, match="业务错误"):
            raise SwapServiceError("业务错误")

    def test_swap_permission_error_distinct_from_service(self):
        """SwapPermissionError 不是 SwapServiceError 子类(独立异常层级)"""
        assert not issubclass(SwapPermissionError, SwapServiceError)

    def test_swap_not_found_error_distinct_from_service(self):
        """SwapNotFoundError 不是 SwapServiceError 子类"""
        assert not issubclass(SwapNotFoundError, SwapServiceError)
```

- [ ] **Step 4: 跑测试,验证 6 个都通过**

Run: `cd omni_desk_backend && pytest tests/test_swap_service.py::TestSwapServiceExceptions -v --ds=omni_desk_backend.settings.test`
Expected: PASS(6 passed)

- [ ] **Step 5: Commit**

```bash
git add omni_desk_backend/events/services/__init__.py \
        omni_desk_backend/events/services/swap_service.py \
        omni_desk_backend/events/tests/test_swap_service.py
git commit -m "feat(events): swap_service 模块骨架 + 3 个异常类"
```

---

## Task 2: swap_service.create_swap_from_serializer + create_swap_by_query

**Files:**
- Modify: `omni_desk_backend/events/services/swap_service.py`
- Modify: `omni_desk_backend/events/tests/test_swap_service.py`

**Interfaces:**
- Produces:
  - `create_swap_from_serializer(*, serializer) -> ScheduleSwapRequest`
  - `create_swap_by_query(*, requester: Personnel, target_name: str, duty_date: date, reason: str = "") -> ScheduleSwapRequest`

- [ ] **Step 1: 写失败测试 — create_swap_from_serializer 成功路径**

```python
# 在 test_swap_service.py 中追加
from datetime import date, timedelta
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone

from events.models import Schedule, ScheduleSwapRequest
from events.services import swap_service
from personnel.models import Personnel

User = get_user_model()


@pytest.fixture
def target_personnel(db):
    return Personnel.objects.create(name="王五")


@pytest.fixture
def future_schedule(db, target_personnel):
    """target_personnel 未来 7 天后的排班(用于测试非自己排班)"""
    return Schedule.objects.create(
        duty_date=date.today() + timedelta(days=7),
        duty_person=target_personnel,
    )


@pytest.mark.django_db
class TestCreateSwapFromSerializer:
    """create_swap_from_serializer:从 DRF serializer 创建 swap"""

    def test_create_success(self, swap_request, target_personnel, schedule_a, future_schedule):
        """正常路径:serializer 注入完整 validated_data,成功创建"""
        from unittest.mock import MagicMock
        mock_serializer = MagicMock()
        mock_serializer.validated_data = {
            "requester": swap_request.requester,
            "target_personnel": target_personnel,
            "original_schedule": schedule_a,
            "target_schedule": None,
            "scope": "duty_person",
            "reason": "测试换班",
        }

        result = swap_service.create_swap_from_serializer(serializer=mock_serializer)

        assert isinstance(result, ScheduleSwapRequest)
        assert result.id is not None
        assert result.status == ScheduleSwapRequest.STATUS_PENDING
        assert result.reason == "测试换班"
        ttl = getattr(settings, "SWAP_REQUEST_TTL_HOURS", 48)
        assert result.expires_at > timezone.now()
        assert result.expires_at <= timezone.now() + timedelta(hours=ttl + 1)

    def test_create_without_target_schedule(self, swap_request, target_personnel, schedule_a):
        """target_schedule 为 None 时单方面替班"""
        from unittest.mock import MagicMock
        mock_serializer = MagicMock()
        mock_serializer.validated_data = {
            "requester": swap_request.requester,
            "target_personnel": target_personnel,
            "original_schedule": schedule_a,
            "target_schedule": None,
            "scope": "duty_person",
            "reason": "单方面替班",
        }

        result = swap_service.create_swap_from_serializer(serializer=mock_serializer)

        assert result.target_schedule_id is None
```

- [ ] **Step 2: 跑测试,验证失败**

Run: `pytest tests/test_swap_service.py::TestCreateSwapFromSerializer -v --ds=omni_desk_backend.settings.test`
Expected: FAIL with "AttributeError: module 'events.services.swap_service' has no attribute 'create_swap_from_serializer'"

- [ ] **Step 3: 实现 create_swap_from_serializer**

```python
# 在 swap_service.py 追加
from datetime import timedelta
from datetime import date as date_type  # noqa: F401

from events.models import Schedule, ScheduleSwapRequest, ScheduleSwapAuditLog


def _create_swap_internal(
    *,
    requester,
    target_personnel,
    original_schedule,
    target_schedule,
    scope,
    reason,
) -> ScheduleSwapRequest:
    """内部共用:校验 + 构造 + 保存 swap。

    必须在 transaction.atomic() 内调用(外层 caller 已包)。
    """
    if target_personnel.id == requester.id:
        raise SwapServiceError("不能把班换给自己")
    if original_schedule.duty_person_id != requester.id:
        raise SwapServiceError("您不是该日的值班人员,无权发起换班")
    if original_schedule.duty_date < timezone.now().date():
        raise SwapServiceError("无法对已过去的排班发起换班申请")

    ttl = getattr(settings, "SWAP_REQUEST_TTL_HOURS", 48)
    instance = ScheduleSwapRequest(
        requester=requester,
        original_schedule=original_schedule,
        target_personnel=target_personnel,
        target_schedule=target_schedule,
        scope=scope,
        reason=reason,
        expires_at=timezone.now() + timedelta(hours=ttl),
        status=ScheduleSwapRequest.STATUS_PENDING,
    )
    instance.full_clean()
    instance.save()
    return instance


def create_swap_from_serializer(*, serializer) -> ScheduleSwapRequest:
    """从已校验的 DRF serializer 创建 swap(供 ViewSet 的 perform_create 使用)。

    serializer.validated_data 必须包含:
    - requester (Personnel): 由 perform_create 注入
    - original_schedule (Schedule)
    - target_personnel (Personnel)
    - target_schedule (Schedule | None)
    - scope (str): "duty_person" | "duty_leader"
    - reason (str)
    """
    validated = serializer.validated_data
    with transaction.atomic():
        return _create_swap_internal(
            requester=validated["requester"],
            target_personnel=validated["target_personnel"],
            original_schedule=validated["original_schedule"],
            target_schedule=validated.get("target_schedule"),
            scope=validated.get("scope", ScheduleSwapRequest.SCOPE_DUTY_PERSON),
            reason=validated.get("reason", ""),
        )
```

- [ ] **Step 4: 跑测试,验证通过**

Run: `pytest tests/test_swap_service.py::TestCreateSwapFromSerializer -v --ds=omni_desk_backend.settings.test`
Expected: PASS(2 passed)

- [ ] **Step 5: 写失败测试 — create_swap_by_query 4 个 case**

```python
# 在 test_swap_service.py 追加
@pytest.mark.django_db
class TestCreateSwapByQuery:
    """create_swap_by_query:从 query 参数(姓名/日期)创建 swap"""

    def test_create_success(self, swap_request, target_personnel, schedule_a):
        """正常路径:姓名 + 日期都能解析到"""
        result = swap_service.create_swap_by_query(
            requester=swap_request.requester,
            target_name="王五",
            duty_date=schedule_a.duty_date,
            reason="测试",
        )
        assert result.id is not None
        assert result.status == ScheduleSwapRequest.STATUS_PENDING

    def test_target_not_found(self, swap_request, schedule_a):
        """目标人不存在 → SwapServiceError"""
        with pytest.raises(SwapServiceError, match="未找到 '不存在的名字' 该人员"):
            swap_service.create_swap_by_query(
                requester=swap_request.requester,
                target_name="不存在的名字",
                duty_date=schedule_a.duty_date,
            )

    def test_schedule_not_found(self, swap_request, target_personnel):
        """该日不存在 requester 排班 → SwapServiceError"""
        past_date = date.today() - timedelta(days=30)
        with pytest.raises(SwapServiceError, match=f"找不到您 {past_date} 的排班记录"):
            swap_service.create_swap_by_query(
                requester=swap_request.requester,
                target_name="王五",
                duty_date=past_date,
            )

    def test_self_swap(self, target_personnel, schedule_a):
        """target == requester → SwapServiceError"""
        with pytest.raises(SwapServiceError, match="不能把班换给自己"):
            swap_service.create_swap_by_query(
                requester=target_personnel,
                target_name="王五",
                duty_date=schedule_a.duty_date,
            )
```

- [ ] **Step 6: 跑测试,验证失败**

Run: `pytest tests/test_swap_service.py::TestCreateSwapByQuery -v --ds=omni_desk_backend.settings.test`
Expected: FAIL with "AttributeError: module 'events.services.swap_service' has no attribute 'create_swap_by_query'"

- [ ] **Step 7: 实现 create_swap_by_query**

```python
# 在 swap_service.py 追加
def create_swap_by_query(
    *,
    requester,
    target_name: str,
    duty_date,
    reason: str = "",
) -> ScheduleSwapRequest:
    """从自由文本创建 swap(供 Smart Assistant 工具 + CLI 使用)。

    步骤:
    1. Personnel.objects.filter(name=target_name).first() 找 target
    2. Schedule.objects.filter(duty_date=duty_date, duty_person=requester).first() 找 schedule
    3. 校验 target_personnel != requester
    4. 调 _create_swap_internal

    Raises:
        SwapServiceError: 目标人不存在 / 排班不存在 / 自己换自己
    """
    target_personnel = Personnel.objects.filter(name=target_name).first()
    if target_personnel is None:
        raise SwapServiceError(f"未找到 '{target_name}' 该人员")
    original_schedule = Schedule.objects.filter(
        duty_date=duty_date, duty_person=requester
    ).first()
    if original_schedule is None:
        raise SwapServiceError(f"找不到您 {duty_date} 的排班记录")
    with transaction.atomic():
        return _create_swap_internal(
            requester=requester,
            target_personnel=target_personnel,
            original_schedule=original_schedule,
            target_schedule=None,
            scope=ScheduleSwapRequest.SCOPE_DUTY_PERSON,
            reason=reason,
        )
```

- [ ] **Step 8: 跑测试,验证通过**

Run: `pytest tests/test_swap_service.py -v --ds=omni_desk_backend.settings.test`
Expected: PASS(12 passed: 6 异常 + 2 from_serializer + 4 by_query)

- [ ] **Step 9: Commit**

```bash
git add omni_desk_backend/events/services/swap_service.py \
        omni_desk_backend/events/tests/test_swap_service.py
git commit -m "feat(events): swap_service.create_swap_from_serializer + create_swap_by_query"
```

---

## Task 3: swap_service.accept_swap / reject_swap / cancel_swap

**Files:**
- Modify: `omni_desk_backend/events/services/swap_service.py`
- Modify: `omni_desk_backend/events/tests/test_swap_service.py`

**Interfaces:**
- Produces:
  - `accept_swap(*, actor: User, swap_id: int, note: str = "") -> ScheduleSwapRequest`
  - `reject_swap(*, actor: User, swap_id: int, note: str = "") -> ScheduleSwapRequest`
  - `cancel_swap(*, actor: User, swap_id: int) -> ScheduleSwapRequest`

- [ ] **Step 1: 写失败测试 — accept_swap**

```python
# 在 test_swap_service.py 追加
@pytest.mark.django_db
class TestAcceptSwap:
    """accept_swap:接收方 accept → apply_swap + audit_log"""

    def test_accept_success(self, swap_request, user_b):
        """user_b 是 target_personnel 的 user_account,accept 成功"""
        from django.utils import timezone as tz
        ttl = getattr(settings, "SWAP_REQUEST_TTL_HOURS", 48)
        swap_request.expires_at = tz.now() + timedelta(hours=ttl)
        swap_request.save()

        result = swap_service.accept_swap(actor=user_b, swap_id=swap_request.id, note="同意")

        assert result.status == ScheduleSwapRequest.STATUS_APPROVED
        assert result.approver == user_b
        assert result.approved_at is not None
        assert result.audit_logs.count() == 1
        log = result.audit_logs.first()
        assert log.from_status == ScheduleSwapRequest.STATUS_PENDING
        assert log.to_status == ScheduleSwapRequest.STATUS_APPROVED
        assert log.actor == user_b
        assert log.note == "同意"

    def test_accept_not_target(self, swap_request, user_a):
        """user_a 是 requester 不是 target → SwapPermissionError"""
        with pytest.raises(SwapPermissionError):
            swap_service.accept_swap(actor=user_a, swap_id=swap_request.id)

    def test_accept_status_not_pending(self, swap_request, user_b):
        """swap 已 cancelled → SwapServiceError"""
        swap_request.status = ScheduleSwapRequest.STATUS_CANCELLED
        swap_request.save()
        with pytest.raises(SwapServiceError, match="not in pending"):
            swap_service.accept_swap(actor=user_b, swap_id=swap_request.id)

    def test_accept_swap_not_found(self, user_b):
        """swap_id 不存在 → SwapNotFoundError"""
        with pytest.raises(SwapNotFoundError):
            swap_service.accept_swap(actor=user_b, swap_id=99999)
```

- [ ] **Step 2: 跑测试,验证失败**

Run: `pytest tests/test_swap_service.py::TestAcceptSwap -v --ds=omni_desk_backend.settings.test`
Expected: FAIL with "AttributeError: module 'events.services.swap_service' has no attribute 'accept_swap'"

- [ ] **Step 3: 实现 accept_swap**

```python
# 在 swap_service.py 追加
def accept_swap(*, actor, swap_id: int, note: str = "") -> ScheduleSwapRequest:
    """接收方 accept → apply_swap + audit_log。

    权限:actor.user_account == swap.target_personnel.user_account
    前置状态:swap.status == STATUS_PENDING

    Raises:
        SwapNotFoundError: swap_id 不存在
        SwapPermissionError: actor 不是 target_personnel
        SwapServiceError: swap 不在 pending 状态
    """
    try:
        swap = ScheduleSwapRequest.objects.get(pk=swap_id)
    except ScheduleSwapRequest.DoesNotExist:
        raise SwapNotFoundError(f"换班申请 #{swap_id} 不存在")

    target_user = getattr(swap.target_personnel, "user_account", None)
    if target_user != actor:
        raise SwapPermissionError("仅接收方可以接受换班申请")
    if swap.status != ScheduleSwapRequest.STATUS_PENDING:
        raise SwapServiceError(f"该申请不在 pending 状态(当前:{swap.status}),无法 accept")

    with transaction.atomic():
        old_status = swap.status
        swap.apply_swap(approver=actor)
        ScheduleSwapAuditLog.objects.create(
            swap_request=swap,
            actor=actor,
            from_status=old_status,
            to_status=swap.status,
            note=note or "接收方同意",
        )
    return swap
```

- [ ] **Step 4: 跑测试,验证通过**

Run: `pytest tests/test_swap_service.py::TestAcceptSwap -v --ds=omni_desk_backend.settings.test`
Expected: PASS(4 passed)

- [ ] **Step 5: 写失败测试 — reject_swap + cancel_swap**

```python
# 在 test_swap_service.py 追加
@pytest.mark.django_db
class TestRejectSwap:
    """reject_swap:接收方 reject → status=rejected_by_target"""

    def test_reject_success(self, swap_request, user_b):
        """成功 reject"""
        from django.utils import timezone as tz
        ttl = getattr(settings, "SWAP_REQUEST_TTL_HOURS", 48)
        swap_request.expires_at = tz.now() + timedelta(hours=ttl)
        swap_request.save()

        result = swap_service.reject_swap(actor=user_b, swap_id=swap_request.id, note="不合适")

        assert result.status == ScheduleSwapRequest.STATUS_REJECTED
        assert result.target_decision_note == "不合适"
        assert result.target_decided_at is not None

    def test_reject_not_target(self, swap_request, user_a):
        """user_a 不是 target → SwapPermissionError"""
        with pytest.raises(SwapPermissionError):
            swap_service.reject_swap(actor=user_a, swap_id=swap_request.id)

    def test_reject_status_not_pending(self, swap_request, user_b):
        """swap 已 approved → SwapServiceError"""
        swap_request.status = ScheduleSwapRequest.STATUS_APPROVED
        swap_request.save()
        with pytest.raises(SwapServiceError):
            swap_service.reject_swap(actor=user_b, swap_id=swap_request.id)


@pytest.mark.django_db
class TestCancelSwap:
    """cancel_swap:申请方 cancel → status=cancelled"""

    def test_cancel_success(self, swap_request, user_a):
        """成功 cancel"""
        from django.utils import timezone as tz
        ttl = getattr(settings, "SWAP_REQUEST_TTL_HOURS", 48)
        swap_request.expires_at = tz.now() + timedelta(hours=ttl)
        swap_request.save()

        result = swap_service.cancel_swap(actor=user_a, swap_id=swap_request.id)

        assert result.status == ScheduleSwapRequest.STATUS_CANCELLED

    def test_cancel_not_requester(self, swap_request, user_b):
        """user_b 不是 requester → SwapPermissionError"""
        with pytest.raises(SwapPermissionError):
            swap_service.cancel_swap(actor=user_b, swap_id=swap_request.id)

    def test_cancel_status_not_pending(self, swap_request, user_a):
        """swap 已 approved → SwapServiceError"""
        swap_request.status = ScheduleSwapRequest.STATUS_APPROVED
        swap_request.save()
        with pytest.raises(SwapServiceError):
            swap_service.cancel_swap(actor=user_a, swap_id=swap_request.id)
```

- [ ] **Step 6: 跑测试,验证失败**

Run: `pytest tests/test_swap_service.py::TestRejectSwap tests/test_swap_service.py::TestCancelSwap -v --ds=omni_desk_backend.settings.test`
Expected: FAIL with "AttributeError: module 'events.services.swap_service' has no attribute 'reject_swap'"

- [ ] **Step 7: 实现 reject_swap + cancel_swap**

```python
# 在 swap_service.py 追加
def reject_swap(*, actor, swap_id: int, note: str = "") -> ScheduleSwapRequest:
    """接收方 reject → status=STATUS_REJECTED + audit_log。

    Raises:
        SwapNotFoundError: swap_id 不存在
        SwapPermissionError: actor 不是 target_personnel
        SwapServiceError: swap 不在 pending 状态
    """
    try:
        swap = ScheduleSwapRequest.objects.get(pk=swap_id)
    except ScheduleSwapRequest.DoesNotExist:
        raise SwapNotFoundError(f"换班申请 #{swap_id} 不存在")

    target_user = getattr(swap.target_personnel, "user_account", None)
    if target_user != actor:
        raise SwapPermissionError("仅接收方可以拒绝换班申请")
    if swap.status != ScheduleSwapRequest.STATUS_PENDING:
        raise SwapServiceError(f"该申请不在 pending 状态(当前:{swap.status})")

    with transaction.atomic():
        old_status = swap.status
        swap.status = ScheduleSwapRequest.STATUS_REJECTED
        swap.target_decided_at = timezone.now()
        swap.target_decision_note = note
        swap.save(
            update_fields=[
                "status",
                "target_decided_at",
                "target_decision_note",
                "updated_at",
            ]
        )
        ScheduleSwapAuditLog.objects.create(
            swap_request=swap,
            actor=actor,
            from_status=old_status,
            to_status=swap.status,
            note="接收方拒绝",
        )
    return swap


def cancel_swap(*, actor, swap_id: int) -> ScheduleSwapRequest:
    """申请方 cancel → status=STATUS_CANCELLED + audit_log。

    Raises:
        SwapNotFoundError: swap_id 不存在
        SwapPermissionError: actor 不是 requester
        SwapServiceError: swap 不在 pending 状态
    """
    try:
        swap = ScheduleSwapRequest.objects.get(pk=swap_id)
    except ScheduleSwapRequest.DoesNotExist:
        raise SwapNotFoundError(f"换班申请 #{swap_id} 不存在")

    requester_user = getattr(swap.requester, "user_account", None)
    if requester_user != actor:
        raise SwapPermissionError("仅申请方可以撤销换班申请")
    if swap.status != ScheduleSwapRequest.STATUS_PENDING:
        raise SwapServiceError(f"该申请不在 pending 状态(当前:{swap.status})")

    with transaction.atomic():
        old_status = swap.status
        swap.status = ScheduleSwapRequest.STATUS_CANCELLED
        swap.save(update_fields=["status", "updated_at"])
        ScheduleSwapAuditLog.objects.create(
            swap_request=swap,
            actor=actor,
            from_status=old_status,
            to_status=swap.status,
            note="申请方撤销",
        )
    return swap
```

- [ ] **Step 8: 跑测试,验证通过**

Run: `pytest tests/test_swap_service.py -v --ds=omni_desk_backend.settings.test`
Expected: PASS(18 passed: 6 + 2 + 4 + 3 + 3)

- [ ] **Step 9: Commit**

```bash
git add omni_desk_backend/events/services/swap_service.py \
        omni_desk_backend/events/tests/test_swap_service.py
git commit -m "feat(events): swap_service.accept_swap + reject_swap + cancel_swap"
```

---

## Task 4: ViewSet 改为薄包装(API 0 退化)

**Files:**
- Modify: `omni_desk_backend/events/views/swap.py`
- Test: `omni_desk_backend/events/tests/test_swap_request_api.py`(回归)

**Interfaces:**
- Consumes: `events.services.swap_service` 4 个函数 + 3 个异常

- [ ] **Step 1: 跑现有 API 集成测试,记录基线**

Run: `pytest tests/test_swap_request_api.py -v --ds=omni_desk_backend.settings.test`
Expected: 全部通过(基线)

- [ ] **Step 2: 改 view/swap.py — 4 个动作改为调 service**

```python
# omni_desk_backend/events/views/swap.py(整体替换)
"""events.views.swap — 换班申请 ViewSet(薄包装,业务逻辑在 services.swap_service)"""

import logging

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError as DRFValidationError
from rest_framework.response import Response

from events.services import swap_service
from events.services.swap_service import (
    SwapNotFoundError,
    SwapPermissionError,
    SwapServiceError,
)
from users.permissions import IsRequester, IsTargetPersonnel

from ..models import ScheduleSwapRequest
from ..serializers import (
    SwapRequestCreateSerializer,
    SwapRequestDetailSerializer,
    SwapRequestListSerializer,
    SwapRequestTargetActionSerializer,
)

logger = logging.getLogger(__name__)


class SwapRequestViewSet(viewsets.ModelViewSet):
    """排班换班申请 ViewSet(薄包装)。

    业务逻辑(events.services.swap_service)与 HTTP 层分离:
    - perform_create: 调 create_swap_from_serializer
    - accept / reject: 调 accept_swap / reject_swap
    - cancel: 调 cancel_swap
    """

    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_permissions(self):
        if self.action in ("cancel",):
            return [permissions.IsAuthenticated(), IsRequester()]
        if self.action in ("accept", "reject"):
            return [permissions.IsAuthenticated(), IsTargetPersonnel()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        personnel = getattr(user, "personnel", None)
        base = (
            ScheduleSwapRequest.objects.select_related(
                "requester",
                "target_personnel",
                "original_schedule",
                "target_schedule",
                "approver",
            )
            .prefetch_related("audit_logs")
            .order_by("-created_at")
        )
        role = self.request.query_params.get("role", "all")
        if personnel is None:
            return base.none()
        if role == "requester":
            return base.filter(requester=personnel)
        if role == "target":
            return base.filter(target_personnel=personnel)
        return base.filter(Q(requester=personnel) | Q(target_personnel=personnel))

    def get_serializer_class(self):
        if self.action == "list":
            return SwapRequestListSerializer
        if self.action in ("retrieve", "accept", "reject", "cancel"):
            if self.action in ("accept", "reject"):
                return SwapRequestTargetActionSerializer
            return SwapRequestDetailSerializer
        return SwapRequestCreateSerializer

    def perform_create(self, serializer):
        """薄包装:把 serializer 注入 requester 后调 service。"""
        requester = getattr(self.request.user, "personnel", None)
        if requester is None:
            raise PermissionDenied("当前用户尚未关联人员档案,请联系 HR")
        serializer.is_valid(raise_exception=True)
        serializer.validated_data["requester"] = requester
        try:
            instance = swap_service.create_swap_from_serializer(serializer=serializer)
        except SwapPermissionError as e:
            raise PermissionDenied(str(e))
        except SwapServiceError as e:
            raise DRFValidationError(e.message if hasattr(e, "message") else {"detail": str(e)})
        self._swap_instance = instance

    def create(self, request, *args, **kwargs):
        """重写 create:perform_create 走 service,直接返回详情 serializer。"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        instance = getattr(self, "_swap_instance", None)
        if instance is None:
            return Response(
                {"detail": "创建失败:perform_create 未设置 instance"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        return Response(
            SwapRequestDetailSerializer(instance).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"])
    def accept(self, request, pk=None):
        """接收方 accept。"""
        try:
            swap = swap_service.accept_swap(
                actor=request.user,
                swap_id=pk,
                note=request.data.get("target_decision_note", "接收方同意"),
            )
        except SwapNotFoundError:
            return Response({"detail": "换班申请不存在"}, status=status.HTTP_404_NOT_FOUND)
        except SwapPermissionError as e:
            raise PermissionDenied(str(e))
        except SwapServiceError as e:
            return Response({"detail": str(e)}, status=status.HTTP_409_CONFLICT)
        return Response(SwapRequestDetailSerializer(swap).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        """接收方 reject。"""
        try:
            swap = swap_service.reject_swap(
                actor=request.user,
                swap_id=pk,
                note=request.data.get("target_decision_note", ""),
            )
        except SwapNotFoundError:
            return Response({"detail": "换班申请不存在"}, status=status.HTTP_404_NOT_FOUND)
        except SwapPermissionError as e:
            raise PermissionDenied(str(e))
        except SwapServiceError as e:
            return Response({"detail": str(e)}, status=status.HTTP_409_CONFLICT)
        return Response(SwapRequestDetailSerializer(swap).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        """申请方 cancel。"""
        try:
            swap = swap_service.cancel_swap(actor=request.user, swap_id=pk)
        except SwapNotFoundError:
            return Response({"detail": "换班申请不存在"}, status=status.HTTP_404_NOT_FOUND)
        except SwapPermissionError as e:
            raise PermissionDenied(str(e))
        except SwapServiceError as e:
            return Response({"detail": str(e)}, status=status.HTTP_409_CONFLICT)
        return Response(SwapRequestDetailSerializer(swap).data)
```

- [ ] **Step 3: 跑现有 API 集成测试,验证 0 退化**

Run: `pytest tests/test_swap_request_api.py -v --ds=omni_desk_backend.settings.test`
Expected: 全部通过(与基线一致)

- [ ] **Step 4: 跑 service 单元测试,验证 view 重构没破坏 service**

Run: `pytest tests/test_swap_service.py -v --ds=omni_desk_backend.settings.test`
Expected: PASS(18 passed)

- [ ] **Step 5: Commit**

```bash
git add omni_desk_backend/events/views/swap.py
git commit -m "refactor(events): ViewSet 改为薄包装,业务逻辑抽到 swap_service"
```

---

## Task 5: extractors 包初始化 + LLM JSON 解析鲁棒性

**Files:**
- Create: `omni_desk_backend/smart_assistant/extractors/__init__.py`
- Create: `omni_desk_backend/smart_assistant/extractors/prompts/__init__.py`
- Create: `omni_desk_backend/smart_assistant/extractors/swap_extractor.py`
- Test: `omni_desk_backend/smart_assistant/tests/test_swap_extractor.py`

**Interfaces:**
- Produces:
  - `CreateParams` dataclass
  - `DecideParams` dataclass
  - `_call_llm_for_json(prompt: str) -> dict | None`

- [ ] **Step 1: 写 init 文件**

```python
# omni_desk_backend/smart_assistant/extractors/__init__.py
"""智能助手 LLM 提取器层。

把"自然语言 query → 结构化参数"封装为可独立测试、可替换 LLM 的模块。
每个工具领域(换班/会议室/...)+ 对应一个 extractor + 对应 prompt 文件。
"""
```

```python
# omni_desk_backend/smart_assistant/extractors/prompts/__init__.py
"""LLM prompt 模板集合。

按领域拆分(swap_create_prompt / swap_decide_prompt / ...),便于维护与单测。
"""
```

- [ ] **Step 2: 写失败测试 — `_call_llm_for_json` 鲁棒性**

```python
# omni_desk_backend/smart_assistant/tests/test_swap_extractor.py
"""swap_extractor 单元测试"""

import json
from unittest.mock import patch

import pytest

from smart_assistant.extractors.swap_extractor import (
    CreateParams,
    DecideParams,
    _call_llm_for_json,
)


class TestCallLlmForJson:
    """_call_llm_for_json:LLM 返回值 → 解析为 dict,失败 → None"""

    def test_valid_json(self):
        """纯 JSON 字符串直接解析"""
        with patch(
            "smart_assistant.extractors.swap_extractor._call_llm",
            return_value='{"target_name": "李四", "duty_date": "2026-08-12"}',
        ):
            result = _call_llm_for_json("fake prompt")
        assert result == {"target_name": "李四", "duty_date": "2026-08-12"}

    def test_json_embedded_in_text(self):
        """LLM 在文本中嵌入 JSON,正则提取首个 {}"""
        with patch(
            "smart_assistant.extractors.swap_extractor._call_llm",
            return_value='好的,以下是结果: {"target_name": "李四"} 完毕',
        ):
            result = _call_llm_for_json("fake prompt")
        assert result == {"target_name": "李四"}

    def test_empty_string(self):
        """LLM 返回空字符串 → None"""
        with patch(
            "smart_assistant.extractors.swap_extractor._call_llm",
            return_value="",
        ):
            result = _call_llm_for_json("fake prompt")
        assert result is None

    def test_invalid_json(self):
        """LLM 返回非 JSON 文本 → None"""
        with patch(
            "smart_assistant.extractors.swap_extractor._call_llm",
            return_value="抱歉,我无法理解",
        ):
            result = _call_llm_for_json("fake prompt")
        assert result is None

    def test_json_with_markdown_fence(self):
        """LLM 用 ```json 围栏 → 正则提取"""
        with patch(
            "smart_assistant.extractors.swap_extractor._call_llm",
            return_value='```json\n{"target_name": "李四"}\n```',
        ):
            result = _call_llm_for_json("fake prompt")
        assert result == {"target_name": "李四"}
```

- [ ] **Step 3: 跑测试,验证失败**

Run: `pytest tests/test_swap_extractor.py::TestCallLlmForJson -v --ds=omni_desk_backend.settings.test`
Expected: FAIL with "ModuleNotFoundError" 或 "has no attribute '_call_llm_for_json'"

- [ ] **Step 4: 实现 `_call_llm_for_json` + dataclass + 模块骨架**

```python
# omni_desk_backend/smart_assistant/extractors/swap_extractor.py
"""smart_assistant.extractors.swap_extractor — 换班查询的 LLM 提取器

LLM 解析"中文 query → CreateParams / DecideParams",失败兜底为 None(由调用方
返回 found=False,不降级到规则)。

鲁棒性:
- LLM 不可用 / 抛异常 → None
- LLM 返回非 JSON 文本 → 用正则提取首个 {…} 块再试
- 解析后字段缺失 → None

注意:_call_llm 的真实实现依赖项目 LLM 客户端,本模块提供 stub 接口,
单元测试全部 patch 它。生产代码接入在后续 PR 单独处理(spec §1.3 YAGNI)。
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class CreateParams:
    """换班创建参数(从 query 提取)"""

    target_name: str
    duty_date: str
    reason: str = ""


@dataclass
class DecideParams:
    """换班决策参数(从 query 提取)"""

    action: str
    swap_id: Optional[int] = None
    note: str = ""


def _call_llm(prompt: str) -> str:
    """调用项目现有 LLM 客户端。

    本函数作为 swap_extractor 与 LLM 客户端的唯一接触点,便于测试 mock。
    真实实现依赖项目 LLM 客户端(YAGNI:本任务范围只到 mock level,
    真实 LLM 接入在后续 PR 单独处理)。
    """
    raise NotImplementedError(
        "_call_llm 是 stub。请在生产环境接入项目 LLM 客户端后再使用 swap_extractor。"
    )


def _call_llm_for_json(prompt: str) -> dict | None:
    """调 LLM 拿 JSON。

    鲁棒性:
    1. LLM 抛异常/超时 → None
    2. 返回非 JSON → 用正则提取首个 {...} 块再试
    3. 仍无法解析 → None
    """
    try:
        raw = _call_llm(prompt)
    except Exception as e:
        logger.warning("_call_llm 失败: %s", e)
        return None
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{[\s\S]*\}", raw)
    if not m:
        logger.warning("_call_llm_for_json: 找不到 JSON 块. raw=%r", raw[:200])
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        logger.warning("_call_llm_for_json: 提取后仍非 JSON. raw=%r", raw[:200])
        return None
```

- [ ] **Step 5: 跑测试,验证通过**

Run: `pytest tests/test_swap_extractor.py::TestCallLlmForJson -v --ds=omni_desk_backend.settings.test`
Expected: PASS(5 passed)

- [ ] **Step 6: Commit**

```bash
git add omni_desk_backend/smart_assistant/extractors/__init__.py \
        omni_desk_backend/smart_assistant/extractors/prompts/__init__.py \
        omni_desk_backend/smart_assistant/extractors/swap_extractor.py \
        omni_desk_backend/smart_assistant/tests/test_swap_extractor.py
git commit -m "feat(smart-assistant): swap_extractor 骨架 + _call_llm_for_json 鲁棒性"
```

---

## Task 6: swap_create_prompt + extract_create_params

**Files:**
- Create: `omni_desk_backend/smart_assistant/extractors/prompts/swap_create_prompt.py`
- Modify: `omni_desk_backend/smart_assistant/extractors/swap_extractor.py`
- Modify: `omni_desk_backend/smart_assistant/tests/test_swap_extractor.py`

**Interfaces:**
- Produces:
  - `SWAP_CREATE_SYSTEM_PROMPT` (str)
  - `build_create_user_prompt(query: str, requester_name: str, today: str) -> str`
  - `extract_create_params(query: str, requester) -> CreateParams | None`

- [ ] **Step 1: 写失败测试 — extract_create_params**

```python
# 在 test_swap_extractor.py 追加
from datetime import date
from unittest.mock import MagicMock

from smart_assistant.extractors.swap_extractor import extract_create_params


@pytest.mark.django_db
class TestExtractCreateParams:
    """extract_create_params:LLM 解析 create 参数"""

    def test_valid_extraction(self):
        """LLM 返回有效 JSON → 构造 CreateParams"""
        with patch(
            "smart_assistant.extractors.swap_extractor._call_llm",
            return_value='{"target_name": "李四", "duty_date": "2026-08-12", "reason": "出差"}',
        ):
            mock_requester = MagicMock()
            mock_requester.name = "张三"
            result = extract_create_params("我想和李四换 8月12日 的班,因出差", mock_requester)
        assert isinstance(result, CreateParams)
        assert result.target_name == "李四"
        assert result.duty_date == "2026-08-12"
        assert result.reason == "出差"

    def test_missing_required_field(self):
        """LLM 缺 target_name → None"""
        with patch(
            "smart_assistant.extractors.swap_extractor._call_llm",
            return_value='{"duty_date": "2026-08-12"}',
        ):
            mock_requester = MagicMock()
            mock_requester.name = "张三"
            result = extract_create_params("模糊 query", mock_requester)
        assert result is None

    def test_llm_failure(self):
        """LLM 抛异常 → None"""
        with patch(
            "smart_assistant.extractors.swap_extractor._call_llm",
            side_effect=RuntimeError("LLM timeout"),
        ):
            mock_requester = MagicMock()
            mock_requester.name = "张三"
            result = extract_create_params("query", mock_requester)
        assert result is None

    def test_empty_reason_allowed(self):
        """reason 字段为空字符串是合法的"""
        with patch(
            "smart_assistant.extractors.swap_extractor._call_llm",
            return_value='{"target_name": "李四", "duty_date": "2026-08-12", "reason": ""}',
        ):
            mock_requester = MagicMock()
            mock_requester.name = "张三"
            result = extract_create_params("我想和李四换 8月12日 的班", mock_requester)
        assert result is not None
        assert result.reason == ""
```

- [ ] **Step 2: 跑测试,验证失败**

Run: `pytest tests/test_swap_extractor.py::TestExtractCreateParams -v --ds=omni_desk_backend.settings.test`
Expected: FAIL with "has no attribute 'extract_create_params'"

- [ ] **Step 3: 写 prompt 模板**

```python
# omni_desk_backend/smart_assistant/extractors/prompts/swap_create_prompt.py
"""swap_create_prompt — 换班创建 LLM 解构 prompt"""

SWAP_CREATE_SYSTEM_PROMPT = """你是 swap_request_extractor,负责把中文自然语言转换为换班申请结构化参数。

输入包含:
- 用户的原始 query
- 申请人姓名
- 当前日期

输出必须是合法 JSON,严格遵循以下 schema:
{
  "target_name": "接收方姓名(必填,字符串)",
  "duty_date": "值班日期,格式 YYYY-MM-DD(必填,字符串)",
  "reason": "申请理由(可选,字符串,默认空)"
}

要求:
1. 只输出 JSON,不要任何解释/前缀/后缀
2. 不可推断字段填 null
3. duty_date 必须是 YYYY-MM-DD,相对日期(如"下周三"、"明天")需要基于当前日期计算
4. 中文姓名照原样输出,不要拼音化
"""


def build_create_user_prompt(query: str, requester_name: str, today: str) -> str:
    """构造 user prompt 字符串"""
    return (
        f"申请人: {requester_name}\n"
        f"当前日期: {today}\n"
        f"用户请求: {query}\n"
        f"\n请输出 JSON:"
    )
```

- [ ] **Step 4: 实现 extract_create_params**

```python
# 在 swap_extractor.py 追加
from django.utils import timezone as dj_timezone

from .prompts.swap_create_prompt import (
    SWAP_CREATE_SYSTEM_PROMPT,
    build_create_user_prompt,
)


def extract_create_params(query: str, requester) -> CreateParams | None:
    """从 query 提取创建 swap 所需参数。

    Returns:
        CreateParams 实例;LLM 失败/缺字段 → None
    """
    requester_name = getattr(requester, "name", "未知")
    today = str(dj_timezone.now().date())
    user_prompt = build_create_user_prompt(query, requester_name, today)
    full_prompt = f"{SWAP_CREATE_SYSTEM_PROMPT}\n\n{user_prompt}"
    data = _call_llm_for_json(full_prompt)
    if data is None:
        return None
    target_name = data.get("target_name")
    duty_date = data.get("duty_date")
    if not target_name or not duty_date:
        logger.warning("extract_create_params: 缺字段. data=%s", data)
        return None
    return CreateParams(
        target_name=target_name,
        duty_date=duty_date,
        reason=data.get("reason") or "",
    )
```

- [ ] **Step 5: 跑测试,验证通过**

Run: `pytest tests/test_swap_extractor.py::TestExtractCreateParams -v --ds=omni_desk_backend.settings.test`
Expected: PASS(4 passed)

- [ ] **Step 6: 跑 extractor 全套测试**

Run: `pytest tests/test_swap_extractor.py -v --ds=omni_desk_backend.settings.test`
Expected: PASS(9 passed: 5 鲁棒性 + 4 create)

- [ ] **Step 7: Commit**

```bash
git add omni_desk_backend/smart_assistant/extractors/prompts/swap_create_prompt.py \
        omni_desk_backend/smart_assistant/extractors/swap_extractor.py \
        omni_desk_backend/smart_assistant/tests/test_swap_extractor.py
git commit -m "feat(smart-assistant): swap_create_prompt + extract_create_params"
```

---

## Task 7: swap_decide_prompt + extract_decide_params

**Files:**
- Create: `omni_desk_backend/smart_assistant/extractors/prompts/swap_decide_prompt.py`
- Modify: `omni_desk_backend/smart_assistant/extractors/swap_extractor.py`
- Modify: `omni_desk_backend/smart_assistant/tests/test_swap_extractor.py`

**Interfaces:**
- Produces:
  - `SWAP_DECIDE_SYSTEM_PROMPT` (str)
  - `build_decide_user_prompt(query: str, actor_name: str, pending_swaps: list) -> str`
  - `extract_decide_params(query: str, actor) -> DecideParams | None`

- [ ] **Step 1: 写失败测试 — extract_decide_params**

```python
# 在 test_swap_extractor.py 追加
from smart_assistant.extractors.swap_extractor import extract_decide_params, DecideParams


class TestExtractDecideParams:
    """extract_decide_params:LLM 解析 decide 参数"""

    def _make_actor(self):
        from personnel.models import Personnel
        from django.contrib.auth import get_user_model
        User = get_user_model()
        p = Personnel.objects.create(name="李四")
        return User.objects.create_user(username="li4", password="test", personnel=p)

    def test_accept_with_swap_id(self):
        """accept + swap_id 显式提供"""
        with patch(
            "smart_assistant.extractors.swap_extractor._call_llm",
            return_value='{"action": "accept", "swap_id": 7, "note": "可以"}',
        ):
            mock_actor = MagicMock()
            mock_actor.personnel.name = "李四"
            result = extract_decide_params("同意申请 #7", mock_actor)
        assert isinstance(result, DecideParams)
        assert result.action == "accept"
        assert result.swap_id == 7
        assert result.note == "可以"

    def test_reject_without_swap_id(self):
        """reject 不带 swap_id → 仍合法(swap_id 兜底逻辑)"""
        with patch(
            "smart_assistant.extractors.swap_extractor._call_llm",
            return_value='{"action": "reject", "swap_id": null, "note": ""}',
        ):
            mock_actor = MagicMock()
            mock_actor.personnel.name = "李四"
            result = extract_decide_params("拒绝张三的申请", mock_actor)
        assert result is not None
        assert result.action == "reject"
        assert result.swap_id is None

    def test_missing_action(self):
        """缺 action → None"""
        with patch(
            "smart_assistant.extractors.swap_extractor._call_llm",
            return_value='{"swap_id": 7}',
        ):
            mock_actor = MagicMock()
            mock_actor.personnel.name = "李四"
            result = extract_decide_params("query", mock_actor)
        assert result is None

    def test_invalid_action(self):
        """action 不在合法集合 → None"""
        with patch(
            "smart_assistant.extractors.swap_extractor._call_llm",
            return_value='{"action": "delete", "swap_id": 7}',
        ):
            mock_actor = MagicMock()
            mock_actor.personnel.name = "李四"
            result = extract_decide_params("query", mock_actor)
        assert result is None
```

- [ ] **Step 2: 跑测试,验证失败**

Run: `pytest tests/test_swap_extractor.py::TestExtractDecideParams -v --ds=omni_desk_backend.settings.test`
Expected: FAIL with "has no attribute 'extract_decide_params'"

- [ ] **Step 3: 写 prompt 模板**

```python
# omni_desk_backend/smart_assistant/extractors/prompts/swap_decide_prompt.py
"""swap_decide_prompt — 换班决策 LLM 解构 prompt"""

SWAP_DECIDE_SYSTEM_PROMPT = """你是 swap_request_extractor,负责把中文自然语言转换为换班决策结构化参数。

输入包含:
- 用户的原始 query
- 当前操作人姓名(我是接收方还是申请方?)
- 当前操作人作为 target_personnel / requester 的 pending 申请清单

输出必须是合法 JSON,严格遵循以下 schema:
{
  "action": "accept" | "reject" | "cancel"(必填,枚举),
  "swap_id": 申请 ID(可选,整数;若 query 中明确提到 ID 则填,否则 null,与 pending 清单匹配),
  "note": "决策备注(可选,字符串,默认空)"
}

要求:
1. 只输出 JSON,不要任何解释/前缀/后缀
2. action 必须是 accept / reject / cancel 之一,其他值视为非法
3. swap_id 优先从 query 提取数字;若 query 中说"那条申请""张三的",与 pending 清单的 requester.name 匹配
4. cancel 通常由申请方发起,accept/reject 通常由接收方
"""


def build_decide_user_prompt(query: str, actor_name: str, pending_swaps: list) -> str:
    """构造 user prompt 字符串

    pending_swaps: list of dict,每个 dict 含 swap_id / requester_name / target_name / duty_date
    """
    pending_text = "\n".join(
        f"  - #{s['swap_id']}: {s['requester_name']} → {s.get('target_name', '?')} "
        f"({s.get('duty_date', '?')})"
        for s in pending_swaps
    ) or "  (无 pending 申请)"
    return (
        f"操作人: {actor_name}\n"
        f"待决策申请清单:\n{pending_text}\n"
        f"用户请求: {query}\n"
        f"\n请输出 JSON:"
    )
```

- [ ] **Step 4: 实现 extract_decide_params**

```python
# 在 swap_extractor.py 追加
from .prompts.swap_decide_prompt import (
    SWAP_DECIDE_SYSTEM_PROMPT,
    build_decide_user_prompt,
)

VALID_ACTIONS = frozenset({"accept", "reject", "cancel"})


def _get_pending_swaps_for_actor(actor) -> list:
    """收集 actor 作为 target_personnel 或 requester 的 pending 申请。

    返回 list of dict,每项含 swap_id / requester_name / target_name / duty_date。
    """
    personnel = getattr(actor, "personnel", None)
    if personnel is None:
        return []
    qs = ScheduleSwapRequest.objects.filter(
        status=ScheduleSwapRequest.STATUS_PENDING
    ).filter(
        Q(target_personnel=personnel) | Q(requester=personnel)
    ).select_related("requester", "target_personnel", "original_schedule")[:20]
    return [
        {
            "swap_id": s.id,
            "requester_name": s.requester.name,
            "target_name": s.target_personnel.name,
            "duty_date": str(s.original_schedule.duty_date),
        }
        for s in qs
    ]


def extract_decide_params(query: str, actor) -> DecideParams | None:
    """从 query 提取 decide 参数。

    Returns:
        DecideParams 实例;LLM 失败/缺字段/action 不合法 → None
    """
    actor_name = getattr(getattr(actor, "personnel", None), "name", "未知")
    pending_swaps = _get_pending_swaps_for_actor(actor)
    user_prompt = build_decide_user_prompt(query, actor_name, pending_swaps)
    full_prompt = f"{SWAP_DECIDE_SYSTEM_PROMPT}\n\n{user_prompt}"
    data = _call_llm_for_json(full_prompt)
    if data is None:
        return None
    action = data.get("action")
    if action not in VALID_ACTIONS:
        logger.warning("extract_decide_params: action 非法. data=%s", data)
        return None
    swap_id = data.get("swap_id")
    if swap_id is not None and not isinstance(swap_id, int):
        try:
            swap_id = int(swap_id)
        except (TypeError, ValueError):
            swap_id = None
    return DecideParams(
        action=action,
        swap_id=swap_id,
        note=data.get("note") or "",
    )
```

- [ ] **Step 5: 跑测试,验证通过**

Run: `pytest tests/test_swap_extractor.py -v --ds=omni_desk_backend.settings.test`
Expected: PASS(13 passed: 5 + 4 + 4)

- [ ] **Step 6: Commit**

```bash
git add omni_desk_backend/smart_assistant/extractors/prompts/swap_decide_prompt.py \
        omni_desk_backend/smart_assistant/extractors/swap_extractor.py \
        omni_desk_backend/smart_assistant/tests/test_swap_extractor.py
git commit -m "feat(smart-assistant): swap_decide_prompt + extract_decide_params"
```

---

## Task 8: 工具 _dry_run 实现(create)

**Files:**
- Modify: `omni_desk_backend/smart_assistant/tools/swap_request_tool.py`
- Modify: `omni_desk_backend/smart_assistant/tests/test_swap_request_tool.py`

**Interfaces:**
- Consumes: `extract_create_params`, `Personnel.objects`, `Schedule.objects`
- Produces: `SwapRequestCreateTool._dry_run(query, ctx) -> dict`

- [ ] **Step 1: 写失败测试 — _dry_run 6 个 case**

```python
# 在 test_swap_request_tool.py 追加
from datetime import date, timedelta
from unittest.mock import patch


@pytest.mark.django_db
class TestSwapRequestCreateDryRun:
    """SwapRequestCreateTool._dry_run 各场景"""

    def test_dry_run_no_user(self):
        """ctx 无 user → found=False"""
        tool = SwapRequestCreateTool()
        result = tool._dry_run("我想和李四换班", ctx={})
        assert result["found"] is False
        assert "未关联" in result["message"]

    def test_dry_run_extractor_returns_none(self, user_a):
        """LLM 解析失败 → found=False"""
        with patch(
            "smart_assistant.tools.swap_request_tool.extract_create_params",
            return_value=None,
        ):
            tool = SwapRequestCreateTool()
            result = tool._dry_run("模糊 query", ctx={"user": user_a})
        assert result["found"] is False
        assert "无法识别" in result["message"]

    def test_dry_run_target_not_found(self, user_a):
        """目标人不存在 → found=False 说明'未找到'"""
        from smart_assistant.extractors.swap_extractor import CreateParams
        with patch(
            "smart_assistant.tools.swap_request_tool.extract_create_params",
            return_value=CreateParams(target_name="不存在的名字", duty_date="2026-08-12"),
        ):
            tool = SwapRequestCreateTool()
            result = tool._dry_run("query", ctx={"user": user_a})
        assert result["found"] is False
        assert "未找到" in result["message"]

    def test_dry_run_schedule_not_found(self, user_a, personnel_b):
        """该日 requester 无排班 → found=False"""
        from smart_assistant.extractors.swap_extractor import CreateParams
        past = date.today() - timedelta(days=30)
        with patch(
            "smart_assistant.tools.swap_request_tool.extract_create_params",
            return_value=CreateParams(target_name="李四", duty_date=past.isoformat()),
        ):
            tool = SwapRequestCreateTool()
            result = tool._dry_run("query", ctx={"user": user_a})
        assert result["found"] is False
        assert "找不到您" in result["message"]

    def test_dry_run_self_swap(self, user_a, personnel_a):
        """target == requester → found=False"""
        from smart_assistant.extractors.swap_extractor import CreateParams
        with patch(
            "smart_assistant.tools.swap_request_tool.extract_create_params",
            return_value=CreateParams(target_name="张三", duty_date="2026-08-12"),
        ):
            tool = SwapRequestCreateTool()
            result = tool._dry_run("query", ctx={"user": user_a})
        assert result["found"] is False
        assert "不能把班换给自己" in result["message"]

    def test_dry_run_success(self, user_a, personnel_b, schedule_a):
        """所有校验通过 → 返 draft"""
        from smart_assistant.extractors.swap_extractor import CreateParams
        with patch(
            "smart_assistant.tools.swap_request_tool.extract_create_params",
            return_value=CreateParams(
                target_name="李四", duty_date=schedule_a.duty_date.isoformat(), reason="出差"
            ),
        ):
            tool = SwapRequestCreateTool()
            result = tool._dry_run("query", ctx={"user": user_a})
        assert result["found"] is True
        assert "draft" in result
        draft = result["draft"]
        assert "fields" in draft
        assert draft["fields"]["target_personnel_id"] == personnel_b.id
        assert draft["fields"]["original_schedule_id"] == schedule_a.id
        assert draft["fields"]["reason"] == "出差"
```

- [ ] **Step 2: 跑测试,验证失败**

Run: `pytest tests/test_swap_request_tool.py::TestSwapRequestCreateDryRun -v --ds=omni_desk_backend.settings.test`
Expected: FAIL(6 failed)

- [ ] **Step 3: 实现 _dry_run(create)**

```python
# 在 swap_request_tool.py 替换 _dry_run 方法 + 加 import
from datetime import datetime, date

from events.services import swap_service
from events.services.swap_service import (
    SwapNotFoundError,
    SwapPermissionError,
    SwapServiceError,
)
from personnel.models import Personnel

from ..extractors.swap_extractor import extract_create_params, extract_decide_params


def _parse_date_string(s: str):
    """鲁棒地解析日期字符串,失败返回 None。

    接受格式:
    - "2026-08-12"(ISO)
    - "08-12"(MM-DD,默认当年)
    """
    if not s:
        return None
    s = s.strip()
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        pass
    try:
        return datetime.strptime(s, "%m-%d").date().replace(year=date.today().year)
    except ValueError:
        return None


class SwapRequestCreateTool(BaseTool):
    # ... (类其它属性保留)

    def _dry_run(self, query, ctx) -> dict:
        """dry_run 模式:解析 query,验证可行性,返 draft(不落库)"""
        user = ctx.get("user") if isinstance(ctx, dict) else None
        if user is None:
            return {"found": False, "message": "当前用户未关联人员档案"}
        requester = getattr(user, "personnel", None)
        if requester is None:
            return {"found": False, "message": "当前用户未关联人员档案"}

        params = extract_create_params(query, requester)
        if params is None:
            return {"found": False, "message": "无法识别换班意图,请明确换班对象(姓名)和日期"}

        target = Personnel.objects.filter(name=params.target_name).first()
        if target is None:
            return {"found": False, "message": f"未找到 '{params.target_name}' 该人员"}

        duty_date = _parse_date_string(params.duty_date)
        if duty_date is None:
            return {"found": False, "message": f"无法解析日期 '{params.duty_date}'"}

        schedule = Schedule.objects.filter(duty_date=duty_date, duty_person=requester).first()
        if schedule is None:
            return {"found": False, "message": f"找不到您 {duty_date} 的排班记录"}

        if target.id == requester.id:
            return {"found": False, "message": "不能把班换给自己"}

        return {
            "found": True,
            "draft": {
                "summary": f"为 {requester.name} → {target.name} {duty_date} 发起换班申请",
                "fields": {
                    "target_personnel_id": target.id,
                    "target_personnel_name": target.name,
                    "original_schedule_id": schedule.id,
                    "duty_date": duty_date.isoformat(),
                    "reason": params.reason,
                },
            },
        }
```

- [ ] **Step 4: 跑测试,验证通过**

Run: `pytest tests/test_swap_request_tool.py::TestSwapRequestCreateDryRun -v --ds=omni_desk_backend.settings.test`
Expected: PASS(6 passed)

- [ ] **Step 5: Commit**

```bash
git add omni_desk_backend/smart_assistant/tools/swap_request_tool.py \
        omni_desk_backend/smart_assistant/tests/test_swap_request_tool.py
git commit -m "feat(smart-assistant): SwapRequestCreateTool._dry_run 业务实现"
```

---

## Task 9: 工具 _confirmed 实现(create)

**Files:**
- Modify: `omni_desk_backend/smart_assistant/tools/swap_request_tool.py`
- Modify: `omni_desk_backend/smart_assistant/tests/test_swap_request_tool.py`

**Interfaces:**
- Produces: `SwapRequestCreateTool._confirmed(query, ctx) -> dict`

- [ ] **Step 1: 写失败测试 — _confirmed 3 个 case**

```python
# 在 test_swap_request_tool.py 追加
@pytest.mark.django_db
class TestSwapRequestCreateConfirmed:
    """SwapRequestCreateTool._confirmed 创建 swap 并落库"""

    def test_confirmed_success(self, user_a, personnel_b, schedule_a):
        """confirmed:成功创建 swap_request"""
        from smart_assistant.extractors.swap_extractor import CreateParams
        with patch(
            "smart_assistant.tools.swap_request_tool.extract_create_params",
            return_value=CreateParams(
                target_name="李四", duty_date=schedule_a.duty_date.isoformat(), reason="出差"
            ),
        ):
            tool = SwapRequestCreateTool()
            result = tool._confirmed("query", ctx={"user": user_a})
        assert result["found"] is True
        assert result["result"]["status"] == "pending"
        assert ScheduleSwapRequest.objects.count() == 1

    def test_confirmed_extractor_fail(self, user_a):
        """LLM 解析失败 → found=False"""
        with patch(
            "smart_assistant.tools.swap_request_tool.extract_create_params",
            return_value=None,
        ):
            tool = SwapRequestCreateTool()
            result = tool._confirmed("query", ctx={"user": user_a})
        assert result["found"] is False
        assert "无法识别" in result["message"]

    def test_confirmed_target_not_found(self, user_a, schedule_a):
        """目标人不存在 → found=False"""
        from smart_assistant.extractors.swap_extractor import CreateParams
        with patch(
            "smart_assistant.tools.swap_request_tool.extract_create_params",
            return_value=CreateParams(
                target_name="不存在", duty_date=schedule_a.duty_date.isoformat()
            ),
        ):
            tool = SwapRequestCreateTool()
            result = tool._confirmed("query", ctx={"user": user_a})
        assert result["found"] is False
        assert "未找到" in result["message"]
```

- [ ] **Step 2: 跑测试,验证失败**

Run: `pytest tests/test_swap_request_tool.py::TestSwapRequestCreateConfirmed -v --ds=omni_desk_backend.settings.test`
Expected: FAIL(3 failed)

- [ ] **Step 3: 实现 _confirmed(create)**

```python
# 在 SwapRequestCreateTool 内追加
def _confirmed(self, query, ctx) -> dict:
    """confirmed 模式:重 parse(query) → 调 swap_service.create_swap_by_query 落库"""
    user = ctx.get("user") if isinstance(ctx, dict) else None
    if user is None:
        return {"found": False, "message": "当前用户未关联人员档案"}
    requester = getattr(user, "personnel", None)
    if requester is None:
        return {"found": False, "message": "当前用户未关联人员档案"}

    params = extract_create_params(query, requester)
    if params is None:
        return {"found": False, "message": "无法识别换班意图"}

    duty_date = _parse_date_string(params.duty_date)
    if duty_date is None:
        return {"found": False, "message": f"无法解析日期 '{params.duty_date}'"}

    try:
        swap = swap_service.create_swap_by_query(
            requester=requester,
            target_name=params.target_name,
            duty_date=duty_date,
            reason=params.reason,
        )
    except (SwapServiceError, SwapPermissionError) as e:
        return {"found": False, "message": str(e)}
    except Exception as e:
        return {"found": False, "message": f"创建换班申请失败: {e}"}

    return {
        "found": True,
        "result": {"swap_id": swap.id, "status": swap.status},
        "summary": (
            f"换班申请已发起: #{swap.id} "
            f"{swap.requester.name} → {swap.target_personnel.name} "
            f"{swap.original_schedule.duty_date}"
        ),
    }
```

- [ ] **Step 4: 跑测试,验证通过**

Run: `pytest tests/test_swap_request_tool.py::TestSwapRequestCreateConfirmed -v --ds=omni_desk_backend.settings.test`
Expected: PASS(3 passed)

- [ ] **Step 5: 跑 create 工具全测试,验证 0 退化**

Run: `pytest tests/test_swap_request_tool.py -v --ds=omni_desk_backend.settings.test`
Expected: 全部通过(原有 6 + 新增 9 = 15)

- [ ] **Step 6: Commit**

```bash
git add omni_desk_backend/smart_assistant/tools/swap_request_tool.py \
        omni_desk_backend/smart_assistant/tests/test_swap_request_tool.py
git commit -m "feat(smart-assistant): SwapRequestCreateTool._confirmed 业务实现"
```

---

## Task 10: 工具 _dry_run + _confirmed 实现(decide)

**Files:**
- Modify: `omni_desk_backend/smart_assistant/tools/swap_request_tool.py`
- Modify: `omni_desk_backend/smart_assistant/tests/test_swap_request_tool.py`

**Interfaces:**
- Produces: `SwapRequestDecideTool._dry_run(query, ctx) -> dict`, `SwapRequestDecideTool._confirmed(query, ctx) -> dict`

- [ ] **Step 1: 写失败测试 — _dry_run(decide) 4 个 case**

```python
# 在 test_swap_request_tool.py 追加
@pytest.mark.django_db
class TestSwapRequestDecideDryRun:
    """SwapRequestDecideTool._dry_run 决策 draft"""

    def test_dry_run_no_user(self):
        """ctx 无 user → found=False"""
        tool = SwapRequestDecideTool()
        result = tool._dry_run("同意申请", ctx={})
        assert result["found"] is False
        assert "未关联" in result["message"]

    def test_dry_run_extractor_returns_none(self, user_b):
        """LLM 解析失败 → found=False"""
        with patch(
            "smart_assistant.tools.swap_request_tool.extract_decide_params",
            return_value=None,
        ):
            tool = SwapRequestDecideTool()
            result = tool._dry_run("query", ctx={"user": user_b})
        assert result["found"] is False

    def test_dry_run_swap_id_not_found(self, user_b):
        """swap_id 不存在 → found=False"""
        from smart_assistant.extractors.swap_extractor import DecideParams
        with patch(
            "smart_assistant.tools.swap_request_tool.extract_decide_params",
            return_value=DecideParams(action="accept", swap_id=99999),
        ):
            tool = SwapRequestDecideTool()
            result = tool._dry_run("query", ctx={"user": user_b})
        assert result["found"] is False
        assert "不存在" in result["message"]

    def test_dry_run_fallback_latest_pending(self, swap_request, user_b):
        """swap_id 缺失 → 兜底查 actor 作为 target_personnel 的最新 pending"""
        from smart_assistant.extractors.swap_extractor import DecideParams
        with patch(
            "smart_assistant.tools.swap_request_tool.extract_decide_params",
            return_value=DecideParams(action="accept", swap_id=None),
        ):
            tool = SwapRequestDecideTool()
            result = tool._dry_run("同意张三的申请", ctx={"user": user_b})
        assert result["found"] is True
        assert "draft" in result
        assert result["draft"]["fields"]["swap_id"] == swap_request.id
```

- [ ] **Step 2: 跑测试,验证失败**

Run: `pytest tests/test_swap_request_tool.py::TestSwapRequestDecideDryRun -v --ds=omni_desk_backend.settings.test`
Expected: FAIL(4 failed)

- [ ] **Step 3: 实现 _dry_run(decide)**

```python
# 在 SwapRequestDecideTool 内替换 _dry_run
class SwapRequestDecideTool(BaseTool):
    # ... (类其它属性保留)

    def _resolve_target_swap(self, params, actor):
        """基于 LLM 提取的 swap_id,或 actor 作为 target_personnel 的最新 pending 申请,解析目标 swap。

        Returns:
            ScheduleSwapRequest 实例;找不到 → None
        """
        from django.db.models import Q
        personnel = getattr(actor, "personnel", None)
        if personnel is None:
            return None
        if params.swap_id is not None:
            return ScheduleSwapRequest.objects.filter(
                pk=params.swap_id
            ).filter(
                Q(target_personnel=personnel) | Q(requester=personnel)
            ).first()
        # 兜底:actor 作为 target_personnel 的最新 pending 申请
        return ScheduleSwapRequest.objects.filter(
            target_personnel=personnel,
            status=ScheduleSwapRequest.STATUS_PENDING,
        ).order_by("-created_at").first()

    def _dry_run(self, query, ctx) -> dict:
        """dry_run 模式:解析 query + 校验 swap + 返 draft"""
        user = ctx.get("user") if isinstance(ctx, dict) else None
        if user is None:
            return {"found": False, "message": "当前用户未关联人员档案"}
        requester = getattr(user, "personnel", None)
        if requester is None:
            return {"found": False, "message": "当前用户未关联人员档案"}
        params = extract_decide_params(query, user)
        if params is None:
            return {"found": False, "message": "无法识别换班决策(accept/reject/cancel)"}
        swap = self._resolve_target_swap(params, user)
        if swap is None:
            return {"found": False, "message": "未找到您相关的待决策换班申请"}
        if swap.status != ScheduleSwapRequest.STATUS_PENDING:
            return {"found": False, "message": f"该申请不在 pending 状态(当前:{swap.status})"}
        return {
            "found": True,
            "draft": {
                "summary": (
                    f"确认 {params.action} #{swap.id} "
                    f"{swap.requester.name} → {swap.target_personnel.name} "
                    f"{swap.original_schedule.duty_date}"
                ),
                "fields": {
                    "swap_id": swap.id,
                    "action": params.action,
                    "current_status": swap.status,
                    "note": params.note,
                },
            },
        }
```

- [ ] **Step 4: 跑测试,验证通过**

Run: `pytest tests/test_swap_request_tool.py::TestSwapRequestDecideDryRun -v --ds=omni_desk_backend.settings.test`
Expected: PASS(4 passed)

- [ ] **Step 5: 写失败测试 — _confirmed(decide) 3 个 case**

```python
# 在 test_swap_request_tool.py 追加
@pytest.mark.django_db
class TestSwapRequestDecideConfirmed:
    """SwapRequestDecideTool._confirmed 决策 swap"""

    def test_confirmed_accept(self, swap_request, user_b):
        """accept 成功"""
        from django.utils import timezone as tz
        from datetime import timedelta
        from django.conf import settings
        from smart_assistant.extractors.swap_extractor import DecideParams
        ttl = getattr(settings, "SWAP_REQUEST_TTL_HOURS", 48)
        swap_request.expires_at = tz.now() + timedelta(hours=ttl)
        swap_request.save()

        with patch(
            "smart_assistant.tools.swap_request_tool.extract_decide_params",
            return_value=DecideParams(action="accept", swap_id=swap_request.id, note="同意"),
        ):
            tool = SwapRequestDecideTool()
            result = tool._confirmed("query", ctx={"user": user_b})
        assert result["found"] is True
        assert result["result"]["status"] == "approved"
        swap_request.refresh_from_db()
        assert swap_request.status == "approved"

    def test_confirmed_reject(self, swap_request, user_b):
        """reject 成功"""
        from django.utils import timezone as tz
        from datetime import timedelta
        from django.conf import settings
        from smart_assistant.extractors.swap_extractor import DecideParams
        ttl = getattr(settings, "SWAP_REQUEST_TTL_HOURS", 48)
        swap_request.expires_at = tz.now() + timedelta(hours=ttl)
        swap_request.save()

        with patch(
            "smart_assistant.tools.swap_request_tool.extract_decide_params",
            return_value=DecideParams(action="reject", swap_id=swap_request.id),
        ):
            tool = SwapRequestDecideTool()
            result = tool._confirmed("query", ctx={"user": user_b})
        assert result["found"] is True
        assert result["result"]["status"] == "rejected_by_target"

    def test_confirmed_extractor_fail(self, user_b):
        """LLM 解析失败 → found=False"""
        with patch(
            "smart_assistant.tools.swap_request_tool.extract_decide_params",
            return_value=None,
        ):
            tool = SwapRequestDecideTool()
            result = tool._confirmed("query", ctx={"user": user_b})
        assert result["found"] is False
```

- [ ] **Step 6: 跑测试,验证失败**

Run: `pytest tests/test_swap_request_tool.py::TestSwapRequestDecideConfirmed -v --ds=omni_desk_backend.settings.test`
Expected: FAIL(3 failed)

- [ ] **Step 7: 实现 _confirmed(decide)**

```python
# 在 SwapRequestDecideTool 内追加 _confirmed
def _confirmed(self, query, ctx) -> dict:
    """confirmed 模式:重 parse → 调对应 service 函数"""
    user = ctx.get("user") if isinstance(ctx, dict) else None
    if user is None:
        return {"found": False, "message": "当前用户未关联人员档案"}
    params = extract_decide_params(query, user)
    if params is None:
        return {"found": False, "message": "无法识别换班决策"}
    swap = self._resolve_target_swap(params, user)
    if swap is None:
        return {"found": False, "message": "未找到您相关的换班申请"}
    try:
        if params.action == "accept":
            new_swap = swap_service.accept_swap(
                actor=user, swap_id=swap.id, note=params.note,
            )
        elif params.action == "reject":
            new_swap = swap_service.reject_swap(
                actor=user, swap_id=swap.id, note=params.note,
            )
        elif params.action == "cancel":
            new_swap = swap_service.cancel_swap(actor=user, swap_id=swap.id)
        else:
            return {"found": False, "message": f"非法 action: {params.action}"}
    except (SwapNotFoundError, SwapPermissionError, SwapServiceError) as e:
        return {"found": False, "message": str(e)}
    except Exception as e:
        return {"found": False, "message": f"决策失败: {e}"}
    action_text = {"accept": "已接受", "reject": "已拒绝", "cancel": "已撤销"}[params.action]
    return {
        "found": True,
        "result": {"swap_id": new_swap.id, "status": new_swap.status},
        "summary": (
            f"换班申请 {action_text}: #{new_swap.id} "
            f"{new_swap.requester.name} → {new_swap.target_personnel.name}"
        ),
    }
```

- [ ] **Step 8: 跑测试,验证通过**

Run: `pytest tests/test_swap_request_tool.py -v --ds=omni_desk_backend.settings.test`
Expected: 全部通过(原有 6 + 新增 9 create + 4+3 decide = 22)

- [ ] **Step 9: Commit**

```bash
git add omni_desk_backend/smart_assistant/tools/swap_request_tool.py \
        omni_desk_backend/smart_assistant/tests/test_swap_request_tool.py
git commit -m "feat(smart-assistant): SwapRequestDecideTool._dry_run + _confirmed 业务实现"
```

---

## Task 11: 视图 chat.py replay 路径注入 user

**Files:**
- Modify: `omni_desk_backend/smart_assistant/views/chat.py`
- Test: `omni_desk_backend/smart_assistant/tests/test_view_confirm_replay.py`(回归)

- [ ] **Step 1: 跑现有 replay 测试,记录基线**

Run: `pytest tests/test_view_confirm_replay.py -v --ds=omni_desk_backend.settings.test`
Expected: 全部通过(基线)

- [ ] **Step 2: 改 view/chat.py — replay 路径注入 user**

```python
# omni_desk_backend/smart_assistant/views/chat.py 第 100-105 行附近
# 原代码:
#                 context={"history": [], "confirmed": True, "confirm_token": confirm_token},
# 改为:
#                 context={"history": [], "confirmed": True, "confirm_token": confirm_token, "user": request.user},
```

- [ ] **Step 3: 跑现有 replay 测试,验证仍通过**

Run: `pytest tests/test_view_confirm_replay.py -v --ds=omni_desk_backend.settings.test`
Expected: 全部通过(基线一致)

- [ ] **Step 4: 跑 swap_request_tool 端到端测试,验证 user 注入工作**

Run: `pytest tests/test_swap_request_tool.py -v --ds=omni_desk_backend.settings.test`
Expected: 全部通过

- [ ] **Step 5: Commit**

```bash
git add omni_desk_backend/smart_assistant/views/chat.py
git commit -m "fix(smart-assistant): chat view replay 路径注入 user 到 context"
```

---

## Task 12: 跑全套 + 覆盖率 + 质量门

- [ ] **Step 1: 跑 backend 全测**

Run: `cd omni_desk_backend && pytest -v --ds=omni_desk_backend.settings.test`
Expected: 全部通过(0 失败)

- [ ] **Step 2: 跑覆盖率(只关注本次新增模块)**

Run: `pytest --cov=events.services.swap_service --cov=smart_assistant.extractors --cov=smart_assistant.tools.swap_request_tool --cov-report=term-missing --ds=omni_desk_backend.settings.test tests/`
Expected: 覆盖率 ≥ 80%

- [ ] **Step 3: ruff check**

Run: `cd omni_desk_backend && ruff check .`
Expected: 0 错误

- [ ] **Step 4: mypy(本次新增模块)**

Run: `cd omni_desk_backend && mypy smart_assistant/extractors events/services/swap_service.py smart_assistant/tools/swap_request_tool.py`
Expected: 0 错误

- [ ] **Step 5: 跑前端 lint(本任务未改前端,确认 0 退化)**

Run: `cd omni_desk_frontend && npm run lint`
Expected: 0 错误

- [ ] **Step 6: 整理 commit 历史**

```bash
git log --oneline main..HEAD
# 11 commits(每个 task 一个 commit)
```

- [ ] **Step 7: Push + 开 PR**

```bash
git push -u origin swap/tool-business-logic
gh pr create --title "feat(smart-assistant): swap_request 工具业务逻辑补全 (LLM 解析 + service 复用)" --body "..."
```

- [ ] **Step 8: 监控 CI 直至绿**

Run: `gh pr checks <pr-number> --watch`
Expected: CI 绿

- [ ] **Step 9: 等 AI review + 用户 merge**

---

## Self-Review

### 1. Spec coverage

| Spec 章节 | 任务 |
|---|---|
| §1.2 自然语言解析 | Task 6 + 7 |
| §1.2 业务逻辑抽出 | Task 1-3 |
| §1.2 dry_run 拒绝 | Task 8 + 10 |
| §1.2 LLM 失败兜底 | Task 5 + 6 + 7 |
| §1.2 API 行为不变 | Task 4 (回归测试) |
| §3.1 service 函数 | Task 2 + 3 |
| §3.2 ViewSet 薄包装 | Task 4 |
| §3.3 extractor + dataclass | Task 5 + 6 + 7 |
| §3.4 prompt 模板 | Task 6 + 7 |
| §3.5 工具 _dry_run / _confirmed | Task 8 + 9 + 10 |
| §3.6 性能(优先用 draft_fields) | spec §3.6 备注中提及,本期仅用 query 二次解析;后续 PR 与 LLM 客户端接入一起做 |
| §6 测试策略 | Task 1-10 全部覆盖 |

### 2. Placeholder scan

- 无 "TBD" / "TODO" / "implement later"
- 唯一一处 `_call_llm` 是真实 stub(在模块 docstring 中明确说明,测试都用 patch)

### 3. Type consistency

- `CreateParams`, `DecideParams` 在 Task 5 定义,Task 6/7 用法一致
- `schedule_a.duty_date.isoformat()` / `_parse_date_string()` 双向一致
- `swap_service.create_swap_by_query(...)` 在 Task 2 定义,Task 9 调用,签名一致
- `swap_service.accept_swap / reject_swap / cancel_swap` 在 Task 3 定义,Task 10 调用,签名一致
- `_dry_run(self, query, ctx)` / `_confirmed(self, query, ctx)` 三个工具一致
- `ctx.get("user") if isinstance(ctx, dict) else None` 模式 3 个工具一致

### 修复

发现一处:`_parse_date_string` 在工具文件内定义,Task 8 Step 3 中的同级 utility 应该引用 — 已在 Task 8 Step 3 代码块中明确放在 import 区域,无问题。

发现另一处:Task 9 Step 3 `_confirmed` 缺 `from datetime import datetime, date` 与 `_parse_date_string`(因为文件顶部 `_parse_date_string` 已在 Task 8 Step 3 引入,Task 9 复用即可)— 已在 Task 9 Step 3 完整代码块中说明文件顶部 import 已含。
