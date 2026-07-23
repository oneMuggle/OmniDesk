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

未传 `event` 时,adapter 自动填 `"unspecified"`,**测试会警告**。

## 三、事件清单

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

## 四、脱敏规范(强制)

**永不记录**:
- 密码明文 / hash
- JWT access / refresh token
- Authorization header 完整值
- 请求 body 完整内容
- 用户 email / 手机号(用 `user_id` 替代)

**测试覆盖**: `caplog` fixture 验证字段不包含敏感词。

## 五、添加新事件流程

1. 在 `omni_desk_backend/observability/events.py` 加常量(命名 `<category>.<action>.<result>`)
2. 在使用处 `extra={"event": NewEvent.NAME, ...}`
3. 加 caplog 测试
4. 更新本文件 §三
