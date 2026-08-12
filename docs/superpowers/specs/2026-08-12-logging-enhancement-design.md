# 2026-08-12 日志增强设计（排查效率导向）

> **核心目标**:把 OmniDesk 当前"零散、各模块各自一套"的日志,打通为"按 request_id 全链路串联"的可观测链路,出问题能从一个请求 ID 串起 DRF 视图 → Celery 任务 → 异常栈 → smart_assistant hook 等所有事件。
>
> **不在范围内(YAGNI)**:Sentry/ELK 接入、前端错误监控、其他 14 个 app 的批量重构、全量 360 处 except:pass 整治、nginx access_log。

---

## 1. 背景与目标

### 1.1 现状(来自 2026-08-12 扫描报告)

| 维度 | 现状 |
|---|---|
| 生产 JSON 日志 | ✅ `settings/production.py:106-138` 已配置 |
| 开发文本日志 | ✅ `settings/base.py:188-214` 已配置 |
| `observability/` 工具包 | ✅ 已存在,含 `get_logger`、`AuthEvent/PermissionEvent/CeleryEvent` |
| 日志规范文档 | ✅ `docs/technical/27-logging-standards.md` 已存在 |
| 规范落地率 | ❌ 仅 3/57 个文件用 `observability.get_logger`,54 个绕过 |
| `request_id` | ❌ 仅有 smart_assistant 局部 `ToolContext.request_id`,未注入到日志 |
| Sentry/前端监控 | ❌ 完全没有 |
| 0% logger 覆盖的 app | 9 个:`office_assistant`、`meeting_rooms`、`dify_apps`、`projects`、`memos`、`communication`、`news`、`ebooks`、`config` |
| 静默 `except: pass` | ⚠️ 360 处,smart_assistant 一家占 168 处 |
| `print()` 调试残留 | ⚠️ 12 处,其中 `celery.py:24`、`executor.py:164` 是生产代码 |

### 1.2 目标(4 项验收)

1. **同一 `request_id` 能从 HTTP 入口串联到所有 logger 调用**,跨 DRF view / Celery task / smart_assistant hook / 异常栈
2. **get_logger 规范 CI 拦截**:ruff 检查在 CI 失败时拒绝合并
3. **含 request_id 的集成测试通过**:`pytest -k request_id` 全绿,smart_assistant 至少 3 个 caplog 用例
4. **except:pass 计数不增长**:pytest 收集计数与 baseline 比较(smart_assistant baseline = 168)

---

## 2. 架构

```
┌─────────────────────────────────────────────────────────────┐
│  HTTP Request (X-Request-ID: <uuid4>)                       │
└──────────────────────────┬──────────────────────────────────┘
                           ▼
        ┌──────────────────────────────────────┐
        │ RequestIdMiddleware (Django)         │
        │  - 读 X-Request-ID header / 生成 fallback │
        │  - request.request_id = <id>         │
        │  - contextvars.set(request_id)       │
        └──────────────────────────────────────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
          DRF View    Celery .delay()    smart_assistant hook
              │            │            │
              ▼            ▼            ▼
        logger.info(extra={"event": ...})  ─── contextvars 自动注入 request_id
              │            │            │
              ▼            ▼            ▼
            JsonFormatter (production)   text formatter (local)
              │            │            │
              ▼            ▼            ▼
              stdout (json)  ───→  ELK / Loki / 临时 docker logs
```

---

## 3. 组件接口

### 3.1 `RequestIdMiddleware`(`core/middleware.py`,新增)

```python
class RequestIdMiddleware:
    HEADER = "HTTP_X_REQUEST_ID"
    FALLBACK_ATTR = "request_id"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        rid = request.META.get(self.HEADER) or uuid.uuid4().hex
        request.request_id = rid
        token = request_id_var.set(rid)
        try:
            response = self.get_response(request)
            response["X-Request-ID"] = rid
            return response
        finally:
            request_id_var.reset(token)
```

### 3.2 `observability/context.py`(新增)

```python
from contextvars import ContextVar
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
```

### 3.3 `_EventLoggerAdapter` 增强(`observability/__init__.py`,改)

```python
class _EventLoggerAdapter(LoggerAdapter):
    def process(self, msg, kwargs):
        rid = request_id_var.get()
        extra = kwargs.setdefault("extra", {})
        if rid:
            extra.setdefault("request_id", rid)
        extra.setdefault("event", "?")
        return msg, kwargs
```

### 3.4 Celery 任务基类与中间件(`omni_desk_backend/celery.py`,改)

```python
class RequestIdTask(Task):
    """所有任务继承,自动序列化/反序列化 request_id"""
    def apply_async(self, args=None, kwargs=None, **options):
        options.setdefault("headers", {})
        rid = request_id_var.get()
        if rid and "request_id" not in options["headers"]:
            options["headers"]["request_id"] = rid
        return super().apply_async(args, kwargs, **options)

class RequestIdTaskMiddleware:
    def before_task_publish(self, sender, headers=None, body=None, **kwargs):
        rid = request_id_var.get()
        if rid and headers is not None:
            headers.setdefault("request_id", rid)

    def process_task(self, task, args, kwargs):
        rid = (task.request.headers or {}).get("request_id")
        if rid:
            token = request_id_var.set(rid)
            task._request_id_token = token
        return task.run(args, kwargs)

    def process_after_return(self, state=None, task=None, **kwargs):
        token = getattr(task, "_request_id_token", None)
        if token is not None:
            request_id_var.reset(token)

# 在 celery.py 中:
#   app.Task = RequestIdTask
#   app.conf.task_inherit_parent_headers = True
# 注册中间件
```

### 3.5 Formatter 改动

```python
# settings/production.py JsonFormatter
"format": "%(asctime)s %(levelname)s %(name)s %(message)s %(request_id)s %(event)s"
"rename_fields": {"asctime": "timestamp", "levelname": "level",
                  "name": "logger", "request_id": "request_id", "event": "event"}

# settings/base.py 文本 formatter
"format": "%(asctime)s [%(levelname)s] %(name)s [req=%(request_id)s evt=%(event)s]: %(message)s"
```

### 3.6 ruff 规则(`pyproject.toml`,改)

```toml
[tool.ruff.lint]
extend-select = ["LOG", "G"]
"LOG001"  # logger = logging.getLogger(__name__) 而非模块顶层赋值

# 自定义 flake8 plugin: forbid_logging_import_in_business
# 在 omni_desk_backend/<business_app>/ 路径下禁止 from logging import getLogger
# 但保留 observability 包内、tests/ 内、migrations/ 内的豁免
```

实现方式:`pyproject.toml` 中配置 `flake8-forbid-modules` 或写一个最小 flake8 plugin(`flake8_observability.py`)。

---

## 4. 示范重构(smart_assistant)

### 4.1 21 个文件的重构原则

| 文件类型 | 处理 |
|---|---|
| 含 `logging.getLogger(__name__)` 且为模块顶层 | `from observability import get_logger` + `logger = get_logger(__name__, "smart_assistant")` |
| 含 except 但无 logger 的关键路径 | 加 `logger.exception(...)` + event 常量 |
| 已有 logger 但绕过 observability 的 | 切换为 `observability.get_logger`,**不修改调用逻辑**(最小风险) |
| `print(result.final_output)` 等调试残留 | 删除 + 加 `logger.debug(...)` |

### 4.2 关键改动示例

```python
# omni_desk_backend/smart_assistant/agents/executor.py:164
# 现状:
print(result.final_output)

# 重构后:
logger.debug("smart_assistant.agent.final_output",
             extra={"output_preview": str(result.final_output)[:200]})

# 关键路径异常:
# 现状:
try:
    agent.run()
except Exception:
    pass

# 重构后(默认):
try:
    agent.run()
except Exception:
    logger.exception("smart_assistant.agent.run.failed",
                     extra={"event": "smart_assistant.run.failed",
                            "agent_id": agent.id})
```

### 4.3 已知可忽略白名单

```python
# smart_assistant/utils/silent_exceptions.py
ALLOWED_SILENT = {
    ("agent.run", "rate_limit_retry"),  # 重试策略已知
    ("tool.invoke", "deprecated_call"),  # 老工具兼容
}
```

使用方式:在 except 块中显式 import 并声明,让 ruff 不报警。

### 4.4 删除调试残留

| 文件 | 行 | 现状 | 处理 |
|---|---|---|---|
| `omni_desk_backend/celery.py` | 24 | `print(self.request)` | 删除,加 `logger.debug("celery.task.received", ...)` |
| `omni_desk_backend/smart_assistant/agents/executor.py` | 164 | `print(result.final_output)` | 删除,改 `logger.debug(...)` |

---

## 5. 9 个 0% app 的基线补全

| app | 改动文件 | 加什么 |
|---|---|---|
| office_assistant | views.py | `logger = get_logger(__name__, "office_assistant")` + 视图入口 1 处 `logger.info(...)` |
| meeting_rooms | views.py | 同上 |
| dify_apps | views.py + tasks.py | 视图入口 + 任务入口 |
| projects | views.py | 同上 |
| memos | views.py | 同上 |
| communication | views.py + tasks.py | 同上 |
| news | views.py | 同上 |
| ebooks | views.py | 同上 |
| config | views.py | 同上 |

**基线定义**:每个 app 至少有 1 个文件包含 `from observability import get_logger`,且至少有 1 处 `logger.info(...)` 调用。不深入 except:pass 治理。

---

## 6. 关键文件改动清单

| 文件 | 类型 | 改动 |
|---|---|---|
| `core/middleware.py` | 新增 | `RequestIdMiddleware` |
| `core/tests/test_middleware.py` | 新增 | middleware 单元测试 |
| `observability/context.py` | 新增 | `request_id_var` contextvar |
| `observability/__init__.py` | 改 | `_EventLoggerAdapter` 自动注入 request_id / event |
| `omni_desk_backend/settings/base.py` | 改 | MIDDLEWARE 顶部插入;文本 formatter 加 request_id/event |
| `omni_desk_backend/settings/production.py` | 改 | JsonFormatter 加 request_id/event 字段 |
| `omni_desk_backend/celery.py` | 改 | `Task = RequestIdTask`;注册中间件;删除 print 残留 |
| `pyproject.toml` | 改 | ruff LOG 规则 + 自定义 observability 强制规则 |
| `.github/workflows/ci.yml` | 改 | 加 `ruff check` 步骤(若未集成) |
| `smart_assistant/**/*.py` | 改 | 21 个文件批量替换为 `observability.get_logger`;删除 print 残留;关键路径加 logger.exception |
| `smart_assistant/utils/silent_exceptions.py` | 新增 | 已知可忽略白名单 |
| 9 个 0% app 的 views/tasks.py | 改 | 基线 logger |
| `docs/technical/27-logging-standards.md` | 改 | 新增 request_id 章节,记录 contextvars + middleware 模式 |
| `deployment/docker/CHANGELOG.md` | 改 | 加一条"日志可观测性增强" |

---

## 7. 测试

### 7.1 middleware 单元测试

```python
# core/tests/test_middleware.py
def test_request_id_from_header():
    response = client.get("/api/users/me/", HTTP_X_REQUEST_ID="deadbeef")
    assert response["X-Request-ID"] == "deadbeef"

def test_request_id_generated_when_missing():
    response = client.get("/api/users/me/")
    assert re.match(r"^[0-9a-f]{32}$", response["X-Request-ID"])

def test_request_id_unique_per_request():
    r1 = client.get("/api/users/me/")
    r2 = client.get("/api/users/me/")
    assert r1["X-Request-ID"] != r2["X-Request-ID"]
```

### 7.2 caplog 集成测试(smart_assistant)

```python
# smart_assistant/tests/test_request_id.py
def test_request_id_persists_through_view(caplog):
    caplog.set_level(logging.INFO, logger="smart_assistant")
    client.post("/api/smart-assistant/chat/", {...},
                HTTP_X_REQUEST_ID="abc123")
    smart_logs = [r for r in caplog.records if r.name.startswith("smart_assistant")]
    assert smart_logs, "no smart_assistant logs captured"
    assert all(r.request_id == "abc123" for r in smart_logs)

def test_celery_task_inherits_request_id(caplog):
    caplog.set_level(logging.INFO, logger="smart_assistant")
    rid = "task-trace-001"
    result = some_task.apply_async(args=[...], headers={"request_id": rid})
    result.get()
    records = [r for r in caplog.records
               if getattr(r, "request_id", None) == rid]
    assert records
```

### 7.3 except:pass 计数测试

```python
# core/tests/test_silent_exceptions.py
import ast, pathlib, json

def test_except_pass_count_does_not_grow():
    baseline_path = pathlib.Path("tests/baselines/except_pass_count.json")
    baseline = json.loads(baseline_path.read_text())

    repo = pathlib.Path("omni_desk_backend")
    actual = {}
    for app_dir in repo.iterdir():
        if not app_dir.is_dir() or app_dir.name.startswith("."):
            continue
        count = 0
        for py_file in app_dir.rglob("*.py"):
            if "migrations" in py_file.parts:
                continue
            tree = ast.parse(py_file.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.ExceptHandler):
                    if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
                        count += 1
        actual[app_dir.name] = count

    for app, base_count in baseline.items():
        assert actual.get(app, 0) <= base_count, \
            f"{app}: {actual[app]} except:pass > baseline {base_count}"
```

baseline 文件:`tests/baselines/except_pass_count.json` 包含每个 app 的当前计数(smart_assistant: 168 等)。`{"smart_assistant": 168, "llm_service": 12, "ragflow_service": 10, ...}` 是合成 baseline 示例,实施时由脚本统计生成。

---

## 8. 回滚计划

| 触发条件 | 回滚动作 |
|---|---|
| middleware 顺序错位,request_id 未注入 | `MIDDLEWARE` 注释 `RequestIdMiddleware` 行,保留代码可快速恢复 |
| Celery 任务基类与其他中间件冲突 | `app.Task = celery.Task` 切回默认基类 |
| ruff 误报阻断 CI | `extend-select = []` 关闭 LOG 规则;或加 `per-file-ignores` |
| smart_assistant 重构引入 bug | 每个文件单独 commit,git revert 单个 commit |

---

## 9. 风险评估

| 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|
| middleware 顺序错位,request_id 未注入到 logger | 中 | 高 | 写集成测试;放在 MIDDLEWARE 列表第一位 |
| Celery 任务继承 Task 基类后与第三方中间件冲突 | 低 | 中 | 注册顺序:先第三方再 `RequestIdTaskMiddleware` |
| ruff 规则过严阻断不相关 PR | 中 | 中 | `per-file-ignores` 排除 migrations/tests |
| smart_assistant 重构出现 import 循环 | 低 | 中 | observability 不依赖任何业务 app |
| 9 个 0% app 加 logger 时引入语法错误 | 低 | 低 | 加 logger 行用纯机械插入,pytest 全跑 |

---

## 10. 实施顺序

```
Phase 1: 基础设施(无破坏)
  1.1 core/middleware.py + observability/context.py + 注册到 MIDDLEWARE
  1.2 celery.py + RequestIdTask + RequestIdTaskMiddleware
  1.3 _EventLoggerAdapter 增强 + production formatter
  1.4 ruff 规则启用 + ci.yml 集成
  1.5 测试:middleware 单元 + caplog 集成

Phase 2: 示范重构(smart_assistant)
  2.1 sed 重构 21 个文件:logging.getLogger → observability.get_logger
  2.2 删除 print() 调试残留(celery.py:24, executor.py:164)
  2.3 写一份示范性集成测试

Phase 3: 基线补全(9 个 0% app)
  3.1 每个 app 加 logger + 1 处 logger.info(...)

Phase 4: 验收与文档
  4.1 pytest 全跑
  4.2 ruff 全跑
  4.3 docs/technical/27-logging-standards.md 增量更新(新增 request_id 章节)
  4.4 deployment/docker/CHANGELOG.md 写一笔
```

每阶段独立 commit、独立可测、可回滚。

---

## 11. 不在范围内(YAGNI)

- ❌ Sentry / Prometheus 接入
- ❌ ELK / Loki 部署配置(生产 JSON 已可消费)
- ❌ 前端 sentry 接入
- ❌ 54 个其他 app 的批量重构(示范 smart_assistant 后分批推)
- ❌ 全量 360 处 except:pass 整治(只保证"不增长",整治留 follow-up)
- ❌ nginx access_log 配置(不在本仓)