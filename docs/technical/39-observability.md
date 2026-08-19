# 39. 可观测性 (observability)

> 适用版本:OmniDesk v0.7+
> 关联:[27-logging-standards.md](27-logging-standards.md)(日志格式规范)、omni_desk_backend/celery.py(request_id 传播)

## 一、概述

`observability` 应用提供统一的可观测性基础设施:标准化的 logger 工厂、事件常量、`request_id` 的 HTTP / Celery 全链路传播,以及容错 formatter。目标是让每条日志都能回答三个问题:**谁发起的**(request_id)、**发生了什么事件**(event)、**何时何地**(时间戳 + 模块)。

## 二、统一 logger(get_logger)

```python
from observability import get_logger

logger = get_logger(__name__)  # 命名空间 omni_desk.<app>.<module>
logger.info("auth.login.success", extra={"user_id": 42, "event": "auth.login.success"})
```

`get_logger(name, event_default="?")` 返回 `logging.LoggerAdapter`(`_EventLoggerAdapter`),在每条 LogRecord 的 extra 中**自动注入**:

- `request_id`:来自 `observability.context.request_id_var`(HTTP 请求 / Celery 任务生命周期内有效)。
- `event`:logger 初始化时指定的 `event_default`(默认 `"?"`)。

调用方通过 `extra` 显式传入的 `request_id` / `event` **优先级最高**,不会被覆盖。

## 三、事件常量(observability/events.py)

所有事件名采用 snake_case,**命名规范:`<category>.<action>.<result>`**,四类:

| 类别 | 事件常量 | 必填字段 |
|------|----------|----------|
| auth | `auth.login.success` / `auth.login.failure` / `auth.logout` / `auth.jwt.refresh.success` / `auth.jwt.refresh.failure` | user_id / ip;username, reason, ip;… |
| permission | `permission.denied` | user_id, resource, action |
| celery_task | `celery.task.start` / `celery.task.success` / `celery.task.failure` / `celery.task.retry` | task_name, task_id;…;error, retry_count;reason |
| system | 系统级(启动、关闭) | — |

新增事件时遵循:命名 `<category>.<action>.<result>`,字段见各常量 docstring。

## 四、request_id 全链路传播

### 4.1 HTTP 侧:RequestIdMiddleware(core/middleware.py)

- 读取 `X-Request-ID` 请求头;缺失时生成 `uuid4().hex`。
- 写入 `request.request_id`,并 `request_id_var.set(rid)` 注入 ContextVar → 请求生命周期内所有 `get_logger()` 日志自动携带。
- 响应头回写 `X-Request-ID`(`RESPONSE_HEADER`),方便与前端/网关侧对账。
- `finally` 中 `request_id_var.reset(token)`,避免污染线程池复用。

### 4.2 Celery 侧:RequestIdTask + RequestIdTaskMiddleware(omni_desk_backend/celery.py)

```
HTTP 请求(rid=A) ──apply_async──▶ task headers.request_id=A
                                    │
Celery worker ──task_prerun──▶ request_id_var.set(A)
                                    │
                                执行任务,子任务 publish 自动携带 A
                                    │
                              task_postrun ──▶ reset token
```

- `app.Task = RequestIdTask`:`apply_async` 快照当前 `request_id_var` 到 task headers。
- `RequestIdTaskMiddleware` 通过 Celery 信号注册:
  - `before_task_publish`:headers 无 request_id 时注入当前上下文值。
  - `task_prerun`(process_task):从 `task.request.headers` 取出 rid 并 set 到 ContextVar;**token 存 `task.request` 而非共享 task 实例**(否则 `--pool=threads/eventlet/gevent` 下并发执行互相覆盖)。
  - `task_postrun`(process_after_return):reset token。
- **链式任务**(chain/group)的 request_id 继承由 `RequestIdTask.apply_async` 承担:worker 内父任务执行时 ContextVar 已持有 rid,子任务 publish 自动注入。

## 五、容错 formatter(SafeTextFormatter)

dev 文本 formatter 引用 `{request_id}/{event}`,但部分 LogRecord 缺这些字段:

- 未走 `observability.get_logger` 的直接 `logging.getLogger` 日志。
- 走 adapter 但无请求上下文(管理命令、Celery 无传播时)的日志。

裸 `logging.Formatter` 的 `{}-style` 对缺字段抛 `ValueError`,导致整条日志丢失。`SafeTextFormatter` 在格式化前给 record 临时补缺键(`"?"`),格式化后恢复,**不污染 record**。

## 六、与其他模块的关系

- `smart_assistant`、`office_assistant`、`file_processing` 等业务模块统一用 `get_logger(__name__)` 打日志。
- 文件处理的异步任务(`process_file_task`)在 Celery 中自动继承调用方 request_id,便于端到端追踪"哪个用户上传的文件在哪步失败"。
