"""Celery 任务结构化日志测试。

覆盖 events.tasks.logged_task 装饰器:
- 任务成功:celery.task.start + celery.task.success 两个事件 + duration_ms
- 任务失败:celery.task.start + celery.task.failure + error 字段 + 异常重抛

测试通过直接同步调用包装后的 task(不走 broker)。logged_task 装饰器把
@shared_task 包在外层 wrapper 上,直接调用 wrapper 仍会触发 logging,
且 Celery 的 task.request 在未通过 worker 调度时无 id(为 None),此处容许。
"""
import logging

import pytest

from events.models import Schedule, ScheduleSwapRequest
from events.tasks import cleanup_expired_swap_requests
from observability.events import CeleryEvent
from personnel.models import Personnel


@pytest.fixture
def expired_swap(db):
    """创建一个已过期 pending 的 swap,用于触发 cleanup 真实逻辑。"""
    import datetime

    from django.utils import timezone

    requester = Personnel.objects.create(name="测试-张三")
    target = Personnel.objects.create(name="测试-李四")
    schedule = Schedule.objects.create(
        duty_date=timezone.now().date() + datetime.timedelta(days=7),
        duty_person=requester,
    )

    return ScheduleSwapRequest.objects.create(
        requester=requester,
        original_schedule=schedule,
        target_personnel=target,
        reason="logging test",
        expires_at=timezone.now() - datetime.timedelta(hours=1),
    )


@pytest.mark.django_db
class TestCeleryTaskLogging:
    def test_task_success_emits_start_and_success_events(self, expired_swap, caplog):
        """任务成功:发 celery.task.start + celery.task.success,含 task_name 和 duration_ms。"""
        with caplog.at_level(logging.INFO, logger="events.tasks"):
            cleanup_expired_swap_requests()

        events = [r.event for r in caplog.records if hasattr(r, "event")]

        # 必须有 start 和 success 两个事件
        assert CeleryEvent.TASK_START in events, (
            f"missing {CeleryEvent.TASK_START}, got: {events}"
        )
        assert CeleryEvent.TASK_SUCCESS in events, (
            f"missing {CeleryEvent.TASK_SUCCESS}, got: {events}"
        )

        # start 事件含 task_name
        start_record = next(
            r for r in caplog.records if getattr(r, "event", None) == CeleryEvent.TASK_START
        )
        assert start_record.task_name == "cleanup_expired_swap_requests"
        assert start_record.levelname == "INFO"

        # success 事件含 task_name 和 duration_ms(duration 应是数值)
        success_record = next(
            r for r in caplog.records if getattr(r, "event", None) == CeleryEvent.TASK_SUCCESS
        )
        assert success_record.task_name == "cleanup_expired_swap_requests"
        assert isinstance(success_record.duration_ms, (int, float))
        assert success_record.duration_ms >= 0
        assert success_record.levelname == "INFO"

    def test_task_failure_emits_failure_event_and_reraises(self, caplog, monkeypatch):
        """任务失败:发 celery.task.start + celery.task.failure,且异常向上抛。"""

        def boom(*args, **kwargs):
            raise RuntimeError("simulated cleanup failure")

        # patch 模型 manager 让 cleanup 走到抛异常的代码路径
        from events import tasks as tasks_mod

        class _FailingQS:
            def __iter__(self):
                raise RuntimeError("simulated cleanup failure")

        monkeypatch.setattr(
            tasks_mod.ScheduleSwapRequest.objects,
            "filter",
            lambda *a, **kw: _FailingQS(),
        )

        with caplog.at_level(logging.INFO, logger="events.tasks"):
            with pytest.raises(RuntimeError, match="simulated cleanup failure"):
                cleanup_expired_swap_requests()

        events = [r.event for r in caplog.records if hasattr(r, "event")]

        assert CeleryEvent.TASK_START in events
        assert CeleryEvent.TASK_FAILURE in events

        failure_record = next(
            r for r in caplog.records if getattr(r, "event", None) == CeleryEvent.TASK_FAILURE
        )
        assert failure_record.task_name == "cleanup_expired_swap_requests"
        assert "simulated cleanup failure" in failure_record.error
        assert failure_record.levelname == "ERROR"
