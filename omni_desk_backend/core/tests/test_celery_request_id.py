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

    mw.process_task(fake_task, (), {})
    assert request_id_var.get() == "exec-rid"
    # 中间件只管理 context,不执行任务(worker 负责执行,否则双重执行)
    fake_task.run.assert_not_called()
    mw.process_after_return(state="SUCCESS", task=fake_task)
    assert request_id_var.get() is None
