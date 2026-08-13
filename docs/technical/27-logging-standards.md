# 27. 日志规范与事件清单

> 适用版本:OmniDesk v0.7+
> 关联: PR-2 feat/key-path-logger

## 一、目标

生产环境排障时可通过 grep 关键事件快速定位问题,且不泄露 PII。

## 二、Logger 使用规范

### 2.1 统一获取方式

```python
from observability import get_logger

logger = get_logger(__name__)
```

**禁止**直接 `logging.getLogger(__name__)`,因为 `get_logger` 强制 `event` 字段。

### 2.2 必填 extra 字段

每条日志必须传 `event` 字段(枚举见 `observability/events.py`):

```python
logger.info("用户登录成功", extra={
    "event": AuthEvent.LOGIN_SUCCESS,
    "user_id": user.id,
    "ip": request.META.get("REMOTE_ADDR"),
})
```

未传 `event` 时,adapter 自动填 `"?"`。

此外,adapter 会自动注入 `request_id`(来自 `observability.context.request_id_var`,HTTP 请求 / Celery 任务生命周期内有效)与 `event`(默认 `"?"`);调用方通过 `extra` 显式传入的字段优先级更高,不会被覆盖。

## 三、Request ID 全链路追踪

自 2026-08 起,所有日志条目都携带 `request_id` 字段,贯穿 HTTP 请求与 Celery 任务。

### 3.1 来源与传播

1. **HTTP 入口**:`core.middleware.RequestIdMiddleware` 读 `X-Request-ID` header,缺失则生成 uuid4 hex(32 字符)
2. **响应同步返回** `X-Request-ID` header,前端 axios 拦截器可记录
3. **Celery 任务**:`omni_desk_backend.celery.RequestIdTask.apply_async` 自动把当前 request_id 写入 task headers;`task_prerun` signal 在 worker 端恢复 contextvar
4. **contextvars.ContextVar** 自动传递,跨 asyncio 无需手动 await

### 3.2 日志查询

ELK / Loki 中可用以下字段查询同一事务:

```
request_id:abc123
request_id:abc*
event:smart_assistant.*
```

### 3.3 关联追踪(代码层)

- DRF view: `request.request_id` 可在视图中显式使用
- Celery task: `(task.request.headers or {}).get("request_id")`
- 异步 Python: `from observability.context import request_id_var; request_id_var.get()`

### 3.4 强制规范(2026-08 起)

- 业务代码禁止 `from logging import getLogger`,统一用 `from observability import get_logger`
- **CI 守卫**:`omni_desk_backend/core/tests/test_observability_logger.py` AST/regex 守卫 + ruff LOG 规则(`extend-select = ["LOG"]`)。BASELINE 29 个未迁移文件(spec §11)允许保留,新文件用 stdlib `logging.getLogger` 直接红
- `except ...: pass` 必须有显式理由并加入 `smart_assistant/utils/silent_exceptions.py` 的 `ALLOWED_SILENT` 白名单(守卫 `core/tests/test_silent_exceptions.py` 计数)
- ruff 版本 CI 锁为 `>=0.16,<0.17`,确保 LOG 规则行为可复现

## 四、事件清单

| 事件 | 触发 | 字段 |
|------|------|------|
| `auth.login.success` | 登录成功 | user_id, ip |
| `auth.login.failure` | 登录失败 | username, reason, ip |
| `auth.jwt.refresh.success` | JWT 刷新成功 | user_id |
| `auth.jwt.refresh.failure` | JWT 刷新失败 | user_id, reason |
| `permission.denied` | 权限校验失败 | user_id, resource, action |
| `celery.task.start` | 任务开始 | task_name, task_id |
| `celery.task.success` | 任务成功 | task_name, task_id, duration_ms |
| `celery.task.failure` | 任务失败 | task_name, task_id, error |

## 五、脱敏规范(强制)

**永不记录**:
- 密码明文 / hash
- JWT access / refresh token
- Authorization header 完整值
- 请求 body 完整内容
- 用户 email / 手机号(用 `user_id` 替代)

**测试覆盖**: `caplog` fixture 验证字段不包含敏感词。

## 六、添加新事件流程

1. 在 `omni_desk_backend/observability/events.py` 加常量(命名 `<category>.<action>.<result>`)
2. 在使用处 `extra={"event": NewEvent.NAME, ...}`
3. 加 caplog 测试
4. 更新本文件 §四
