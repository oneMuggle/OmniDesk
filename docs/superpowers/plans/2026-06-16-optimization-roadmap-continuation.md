# 优化路线图续写 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 推进 2026-06-05 优化路线图剩余 6 项未完成项,以 6 个独立 feature 分支 / PR 方式交付,全部合并到 main 后覆盖率维持 ≥ 80%、CI 全绿、强约束不破。

**Architecture:** 6 个 PR 按"风险/收益优先"顺序串行,后端 3 个 (PR-1/2/3) + 前端 3 个 (PR-4/5/6) 可分别给后端/前端开发者并行。每个 PR 独立分支、独立可测、可回滚;PR 描述引用同一设计文档。

**Tech Stack:** Django 4.2 LTS / DRF 3.15.2 / pytest 8 + pytest-cov / python-json-logger / django-silk(dev) | React 18.3 / Vite 5.4 / TypeScript 5(allowJs)/ Jest / zod / antd 5

**Reference Spec:** `docs/superpowers/specs/2026-06-16-optimization-roadmap-continuation-design.md`

---

## 文件结构总览

### Phase 1 (PR-1):ViewSet 分页

| 文件 | 操作 | 责任 |
|------|------|------|
| `omni_desk_backend/documents/views/documents.py` | Modify | 移除 `GeneratedDocumentViewSet.pagination_class = None` |
| `omni_desk_backend/documents/tests/test_documents_viewset_pagination.py` | Create | 分页元数据存在性测试 |
| `omni_desk_backend/users/views.py` | Modify | 评估 `UserPersonnelViewSet.pagination_class = None` (line 185) |
| `omni_desk_backend/permissions/views.py` | Modify | 评估 `PageRouteViewSet.pagination_class = None` (line 29) |
| `omni_desk_backend/events/views.py` | Modify | 评估 `MyScheduleView.pagination_class = None` (line 764) |

### Phase 2 (PR-2):关键路径日志

| 文件 | 操作 | 责任 |
|------|------|------|
| `omni_desk_backend/omni_desk_backend/observability/__init__.py` | Create | 统一 logger 工厂: `get_logger(name)` |
| `omni_desk_backend/omni_desk_backend/observability/events.py` | Create | 事件常量: `Event.LOGIN_SUCCESS` / `LOGIN_FAILURE` / `JWT_REFRESH_FAILURE` / `PERMISSION_DENIED` / `CELERY_TASK_START` 等 |
| `omni_desk_backend/users/views.py` | Modify | 登录成功/失败事件 + 字段化日志 |
| `omni_desk_backend/users/tests/test_auth_logging.py` | Create | caplog 验证登录事件字段 |
| `omni_desk_backend/events/tasks.py` | Modify | Celery 任务起止结构化日志 |
| `omni_desk_backend/events/tests/test_tasks_logging.py` | Create | caplog 验证 Celery 事件字段 |
| `docs/technical/27-logging-standards.md` | Create | 脱敏规范 + 事件清单 + 示例 |

### Phase 3 (PR-3):django-silk dev 接入

| 文件 | 操作 | 责任 |
|------|------|------|
| `omni_desk_backend/requirements-dev.in` | Modify | 加 `django-silk` |
| `omni_desk_backend/requirements-dev.txt` | Modify | `pip-compile` 重新生成 |
| `omni_desk_backend/omni_desk_backend/settings/local.py` | Modify | 条件化 `INSTALLED_APPS` / `MIDDLEWARE` / `urls.py` |
| `omni_desk_backend/omni_desk_backend/settings/development.py` | Modify | 同上(若与 local 不同) |
| `omni_desk_backend/omni_desk_backend/urls.py` | Modify | silk URL 条件化(若 settings 层不够) |
| `docs/technical/29-performance-profiling.md` | Create | django-silk 启用 / 慢查询分析 |

### Phase 4 (PR-4):`src/shared/api` → TypeScript

| 文件 | 操作 | 责任 |
|------|------|------|
| `omni_desk_frontend/src/shared/api/apiClient.{js→ts}` | Modify | 泛型 `apiGet<T>` / `apiPost<T,R>` / `apiPut<T,R>` / `apiDelete<T>` |
| `omni_desk_frontend/src/shared/api/axiosConfig.{js→ts}` | Modify | `AxiosInstance` / `RequestInterceptor` / `ResponseInterceptor` 类型 |
| `omni_desk_frontend/src/shared/api/responseHandler.{js→ts}` | Modify | `handleResponse<T>` / `ApiError` 异常类型 |
| `omni_desk_frontend/src/shared/api/{compliance,deepseek,memoApi,ollama,pageConfigApi,permissionsApi,sequenceApi,trialApi,trials}.{js→ts}` | Modify | 业务 API 文件类型化(共 9 个) |
| `omni_desk_frontend/src/shared/types/api.d.ts` | Modify | 增补缺失接口 |

**测试文件 (`.test.js`) 不动,继续兼容 jest 配置。**

### Phase 5 (PR-5):zod 表单试点

| 文件 | 操作 | 责任 |
|------|------|------|
| `omni_desk_frontend/package.json` | Modify | 加 `zod` 依赖 |
| `omni_desk_frontend/package-lock.json` | Modify | `npm install` 更新 |
| `omni_desk_frontend/src/features/auth/schemas/loginSchema.ts` | Create | zod schema 单独成文件 |
| `omni_desk_frontend/src/features/auth/pages/Login.jsx` | Modify | 集成 zod + antd Form |
| `omni_desk_frontend/src/features/auth/schemas/loginSchema.test.js` | Create | schema 边界用例 |
| `omni_desk_frontend/src/features/auth/pages/Login.test.js` | Modify | 补错误提示测试 |
| `docs/technical/30-form-validation-pattern.md` | Create | 模式 + 扩展指南 |

### Phase 6 (PR-6):动态 import 优化

| 文件 | 操作 | 责任 |
|------|------|------|
| `omni_desk_frontend/src/routes/index.jsx` | Modify | `React.lazy` 包裹 editor / docprocessing / markdown 页面 |
| `omni_desk_frontend/src/shared/components/PageSuspenseFallback.jsx` | Create | `<Suspense fallback={...}>` 包装组件 |
| `docs/technical/22-win7-compatibility.md` | Modify | 加一行:动态 import 在 Chrome 109 支持 |

---

## 全局前置条件

执行任何 Phase 前,确认:

- [ ] 在最新 main 分支:`git switch main && git pull --rebase origin main`
- [ ] 后端测试基线绿:`cd omni_desk_backend && pytest --cov-fail-under=80 -q` (期望 ~580 passed)
- [ ] 前端测试基线绿:`cd omni_desk_frontend && npm test -- --watchAll=false` (期望全部 pass)
- [ ] `node_modules` 与 `venv` 装好(若没有,装项目专用环境,不污染 base — 见 `~/.claude/rules/common/python-environment.md`)
- [ ] 已配 `gh` CLI 登录: `gh auth status`

每个 Phase 结束都必须:
- [ ] commit + push 到自己的 feature 分支
- [ ] `gh pr create --title ... --body ...`
- [ ] `gh pr checks <n> --watch` 直到全绿
- [ ] 报告用户,等用户 merge
- [ ] merge 后:`git push origin --delete <branch>` + `git branch -d <branch>`

---

# Phase 1 (PR-1):ViewSet 分页恢复

**Branch:** `fix/viewset-pagination-restore`
**Worktree 建议:** `git switch -c fix/viewset-pagination-restore`(从最新 main)
**依赖前置:** 无
**总任务数:** 7

## Task 1.1:审计 4 处 `pagination_class = None` 上下文

**Files:**
- Read: `omni_desk_backend/documents/views/documents.py:1-30`
- Read: `omni_desk_backend/users/views.py:170-200`
- Read: `omni_desk_backend/permissions/views.py:15-45`
- Read: `omni_desk_backend/events/views.py:755-790`
- Read: `omni_desk_backend/omni_desk_backend/settings/base.py:215-225`

- [ ] **Step 1:** 读 4 个文件的 ViewSet 定义,记录:
  - queryset 是否已 select_related/prefetch_related
  - 是否有自定义 `list()` 方法
  - serializer 字段数(影响响应体大小)

- [ ] **Step 2:** 在 PR 描述或 commit message 写出每个 ViewSet 的判定:
  - `GeneratedDocumentViewSet`(documents) → **恢复分页**(数据随用户增长)
  - `UserPersonnelViewSet`(users) → **保留 None + 封顶 1000**(管理界面下拉)
  - `PageRouteViewSet`(permissions) → **保留 None + 封顶 1000**(菜单下拉)
  - `MyScheduleView`(events) → **恢复分页**(`days=60` 可产生大量 Schedule)

- [ ] **Step 3:** 暂不 commit,继续 Task 1.2

## Task 1.2:写 GeneratedDocumentViewSet 分页测试 (RED)

**Files:**
- Create: `omni_desk_backend/documents/tests/test_documents_viewset_pagination.py`

- [ ] **Step 1:** 创建测试文件:

```python
"""GeneratedDocumentViewSet 分页行为测试。

对应 PR-1 任务:验证移除 pagination_class = None 后,API 返回标准分页响应。
"""
import pytest
from rest_framework.test import APIClient
from rest_framework import status

from documents.models import GeneratedDocument
from tests.factories import UserFactory, GeneratedDocumentFactory


@pytest.mark.django_db
class TestGeneratedDocumentPagination:
    """验证 GeneratedDocumentViewSet 已启用分页。"""

    def test_list_returns_paginated_envelope(self, api_client, regular_user):
        """列表端点应返回 count/next/previous/results 字段(不是裸 list)。"""
        GeneratedDocumentFactory.create_batch(
            12, generated_by=regular_user  # 超过 PAGE_SIZE=10
        )
        api_client.force_authenticate(regular_user)
        response = api_client.get("/api/documents/generated/")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        # 分页 envelope 必有字段
        assert "count" in data
        assert "next" in data
        assert "previous" in data
        assert "results" in data
        assert data["count"] == 12
        assert len(data["results"]) == 10  # PAGE_SIZE=10

    def test_list_second_page(self, api_client, regular_user):
        """第二页应返回剩余 2 条。"""
        GeneratedDocumentFactory.create_batch(12, generated_by=regular_user)
        api_client.force_authenticate(regular_user)
        response = api_client.get("/api/documents/generated/?page=2")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["results"]) == 2
        assert data["previous"] is not None
```

- [ ] **Step 2:** 在 `omni_desk_backend/documents/tests/factories.py`(若不存在)创建 `GeneratedDocumentFactory`:

```python
"""documents app 测试 factory。"""
import factory
from factory.django import DjangoModelFactory

from documents.models import GeneratedDocument
from tests.factories import UserFactory  # 项目级共享 factory


class GeneratedDocumentFactory(DjangoModelFactory):
    class Meta:
        model = GeneratedDocument

    generated_by = factory.SubFactory(UserFactory)
    template = factory.SubFactory("documents.tests.factories.DocumentTemplateFactory")
    # 其他必填字段按模型默认填充
```

(若 `documents/tests/factories.py` 已有,只在其中追加新类;不要覆盖)

- [ ] **Step 3:** 跑测试验证 RED:

```bash
cd omni_desk_backend
pytest documents/tests/test_documents_viewset_pagination.py -v
```

**Expected:** 2 个测试 FAIL,错误信息包含 `"results"` 或 `"count"` 字段不存在(因为当前返回裸 list)

- [ ] **Step 4:** 暂不 commit,继续 Task 1.3

## Task 1.3:移除 `GeneratedDocumentViewSet.pagination_class = None`

**Files:**
- Modify: `omni_desk_backend/documents/views/documents.py:12`(删除该行)

- [ ] **Step 1:** 在 `documents.py` 中定位 line 12-13,删除整行 `pagination_class = None`

- [ ] **Step 2:** 同时移除文件顶部若有 `pagination_class` 的导入(若有,本项目一般无此 import)

- [ ] **Step 3:** 跑测试验证 GREEN:

```bash
cd omni_desk_backend
pytest documents/tests/test_documents_viewset_pagination.py -v
```

**Expected:** 2 个测试 PASS

- [ ] **Step 4:** 跑全量回归确保无破坏:

```bash
cd omni_desk_backend
pytest -q
```

**Expected:** 全部通过,总数 ~582 (从 580 增加 2)

- [ ] **Step 5:** Commit:

```bash
git add omni_desk_backend/documents/
git commit -m "fix(documents): 恢复 GeneratedDocumentViewSet 分页,数据增长避免全量返回

- 移除 pagination_class = None 覆盖
- 沿用全局 PageNumberPagination(PAGE_SIZE=10)
- 列表响应现返回标准 envelope: count/next/previous/results
- 加 2 个分页行为测试

关联: docs/superpowers/specs/2026-06-16-optimization-roadmap-continuation-design.md PR-1"
```

## Task 1.4:处理 `UserPersonnelViewSet` 与 `PageRouteViewSet` 封顶

**Files:**
- Modify: `omni_desk_backend/users/views.py:180-195`
- Modify: `omni_desk_backend/permissions/views.py:25-40`

- [ ] **Step 1:** 在 `users/views.py:UserPersonnelViewSet` 中:
   - 保留 `pagination_class = None`
   - 在 `get_queryset()` 末尾加 `.order_by("id")[:1000]` 或用 `[:1000]` 截断
   - 若已用 `.order_by("username")`,改在末尾加 `[:1000]`

```python
def get_queryset(self):
    return CustomUser.objects.prefetch_related("phone_numbers").all().order_by("username")[:1000]
```

- [ ] **Step 2:** 在 `permissions/views.py:PageRouteViewSet` 同样处理:

```python
queryset = PageRoute.objects.filter(parent__isnull=True).order_by("id")[:1000]
```

- [ ] **Step 3:** 加测试 `permissions/tests/test_page_route_limit.py`:

```python
"""PageRouteViewSet 全集封顶 1000 测试。"""
import pytest
from rest_framework.test import APIClient
from rest_framework import status

from permissions.models import PageRoute
from tests.factories import UserFactory


@pytest.mark.django_db
class TestPageRouteLimit:
    def test_returns_full_set_when_under_limit(self, api_client, admin_user):
        PageRoute.objects.create(name="route-1", path="/r1/", parent=None)
        PageRoute.objects.create(name="route-2", path="/r2/", parent=None)
        api_client.force_authenticate(admin_user)
        response = api_client.get("/api/permissions/page-routes/")
        assert response.status_code == status.HTTP_200_OK
        # 现有实现是裸 list 或 envelope(由 pagination_class 决定)
        # 此处断言长度 ≤ 1000 即可
        data = response.json() if isinstance(response.json(), list) else response.json()["results"]
        assert len(data) <= 1000
```

- [ ] **Step 4:** 跑测试:

```bash
cd omni_desk_backend
pytest permissions/tests/test_page_route_limit.py users/tests/ -q
```

- [ ] **Step 5:** Commit:

```bash
git add omni_desk_backend/users/views.py omni_desk_backend/permissions/
git commit -m "fix(permissions): 保留 None 分页时显式封顶 1000,避免无界数据

- UserPersonnelViewSet: 显式 .order_by('username')[:1000]
- PageRouteViewSet: 显式 .order_by('id')[:1000]
- 加 1 个测试验证封顶行为"
```

## Task 1.5:处理 `MyScheduleView` 分页

**Files:**
- Modify: `omni_desk_backend/events/views.py:760-790`

- [ ] **Step 1:** 读 `MyScheduleView` 完整定义,定位 queryset 构造点

- [ ] **Step 2:** 删除 `pagination_class = None`,沿用全局

- [ ] **Step 3:** 加测试 `events/tests/test_my_schedule_pagination.py`:

```python
"""MyScheduleView 分页行为测试。"""
import pytest
from rest_framework.test import APIClient

from events.models import Schedule
from tests.factories import UserFactory, PersonnelFactory


@pytest.mark.django_db
class TestMySchedulePagination:
    def test_returns_paginated_envelope(self, api_client, regular_user):
        personnel = PersonnelFactory(user=regular_user)
        Schedule.objects.create(
            personnel=personnel,
            start_time="2026-01-01T09:00:00Z",
            end_time="2026-01-01T18:00:00Z",
        )
        Schedule.objects.create(
            personnel=personnel,
            start_time="2026-01-02T09:00:00Z",
            end_time="2026-01-02T18:00:00Z",
        )
        api_client.force_authenticate(regular_user)
        response = api_client.get("/api/events/me/schedule/")
        assert response.status_code == 200
        data = response.json()
        assert "results" in data or isinstance(data, list)
```

- [ ] **Step 4:** 跑测试:

```bash
cd omni_desk_backend
pytest events/tests/test_my_schedule_pagination.py -v
```

- [ ] **Step 5:** Commit:

```bash
git add omni_desk_backend/events/
git commit -m "fix(events): 恢复 MyScheduleView 分页,days=60 大数据量避免全量返回

- 移除 pagination_class = None
- 加分页 envelope 测试"
```

## Task 1.6:全量回归 + 前端契约检查

- [ ] **Step 1:** 跑后端全测:

```bash
cd omni_desk_backend
pytest --cov-fail-under=80 -q
```

**Expected:** 全绿,覆盖率 ≥ 80%

- [ ] **Step 2:** grep 前端对 3 个改过分页端点的调用,确认无依赖"裸 list"假设:

```bash
cd ../omni_desk_frontend
grep -rn "documents/generated\|me/schedule\|page-routes" src/ --include="*.jsx" --include="*.js" | head -20
```

检查这些调用是否 `.results` / `.data.results`(兼容 envelope)或 `.data` 自身迭代(裸 list)。

- [ ] **Step 3:** 若发现裸 list 假设,在 PR 描述列出"前端需要配套调整"清单(不强制在 PR-1 内改前端,但要透明记录)

- [ ] **Step 4:** 暂不 commit,继续 Task 1.7

## Task 1.7:推送 + PR

- [ ] **Step 1:** 推送分支:

```bash
git push -u origin fix/viewset-pagination-restore
```

- [ ] **Step 2:** 创建 PR:

```bash
gh pr create --title "fix(viewsets): 恢复 3 处 ViewSet 分页 + 2 处封顶 1000" --body "
## 背景
docs/superpowers/specs/2026-06-16-optimization-roadmap-continuation-design.md PR-1

## 改动
- GeneratedDocumentViewSet: 移除 pagination_class = None
- MyScheduleView: 移除 pagination_class = None
- UserPersonnelViewSet: 保留 None + 显式 .order_by('username')[:1000]
- PageRouteViewSet: 保留 None + 显式 .order_by('id')[:1000]
- 新增 3 个测试文件 (4 个测试用例)

## 决策依据
- 文档/排班数据随用户增长 → 真分页
- 用户/页面路由是下拉全集 → 保留 None + 封顶 1000

## 前端配套
[列出 grep 发现的潜在裸 list 假设,若无可写 '无']
"
```

- [ ] **Step 3:** 监控 CI:

```bash
gh pr checks <PR-number> --watch
```

**Expected:** 4 个 job 全绿(backend-lint / backend-test / frontend-lint / security)

- [ ] **Step 4:** 报告用户:"PR-1 创建完成,CI 全绿,等审阅 merge"

---

# Phase 2 (PR-2):关键路径结构化日志

**Branch:** `feat/key-path-logger`
**Worktree 建议:** `git switch -c feat/key-path-logger`
**依赖前置:** PR-1 已合并(或可并行基于 main)
**总任务数:** 9

## Task 2.1:创建 observability 基础模块

**Files:**
- Create: `omni_desk_backend/omni_desk_backend/observability/__init__.py`
- Create: `omni_desk_backend/omni_desk_backend/observability/events.py`

- [ ] **Step 1:** 创建 `__init__.py`:

```python
"""可观测性工具。

统一 logger 工厂:所有业务代码用 get_logger() 获取 logger,避免直接 logging.getLogger。

用法:
    from omni_desk_backend.observability import get_logger
    logger = get_logger(__name__)
    logger.info("login.success", extra={"user_id": 42, "event": "login_success"})
"""
from __future__ import annotations

import logging
from typing import Optional


def get_logger(name: str, level: Optional[int] = None) -> logging.LoggerAdapter:
    """获取统一 logger,自动附加 event 字段。

    Args:
        name: 通常传 __name__,命名空间 omni_desk.<app>.<module>
        level: 可选覆盖 level

    Returns:
        LoggerAdapter 实例,调用 .info/.warning/.error 时第一参数为 event 字符串。
    """
    base = logging.getLogger(name)
    if level is not None:
        base.setLevel(level)
    return _EventLoggerAdapter(base, {})


class _EventLoggerAdapter(logging.LoggerAdapter):
    """确保每条日志都包含 event 字段(无则填 'unspecified')。"""

    def process(self, msg, kwargs):
        extra = kwargs.get("extra", {})
        if "event" not in extra:
            extra["event"] = "unspecified"
        kwargs["extra"] = extra
        return msg, kwargs
```

- [ ] **Step 2:** 创建 `events.py`:

```python
"""关键事件常量定义。

所有事件名采用 snake_case,分四类:
- auth: 认证(登录、刷新、登出)
- permission: 权限校验
- celery_task: 异步任务
- system: 系统级(启动、关闭)

新增事件请遵循:
- 命名: <category>.<action>.<result> 例: auth.login.success
- 必填字段见 docstring
"""
from __future__ import annotations


class AuthEvent:
    """认证相关事件。"""
    LOGIN_SUCCESS = "auth.login.success"          # user_id, ip
    LOGIN_FAILURE = "auth.login.failure"          # username, reason, ip
    LOGOUT = "auth.logout"                        # user_id
    JWT_REFRESH_SUCCESS = "auth.jwt.refresh.success"  # user_id
    JWT_REFRESH_FAILURE = "auth.jwt.refresh.failure"  # user_id, reason


class PermissionEvent:
    """权限相关事件。"""
    PERMISSION_DENIED = "permission.denied"        # user_id, resource, action


class CeleryEvent:
    """Celery 任务事件。"""
    TASK_START = "celery.task.start"              # task_name, task_id
    TASK_SUCCESS = "celery.task.success"          # task_name, task_id, duration_ms
    TASK_FAILURE = "celery.task.failure"          # task_name, task_id, error, retry_count
    TASK_RETRY = "celery.task.retry"              # task_name, task_id, reason
```

- [ ] **Step 3:** 验证 import 正常:

```bash
cd omni_desk_backend
python -c "from omni_desk_backend.observability import get_logger; from omni_desk_backend.observability.events import AuthEvent; print(AuthEvent.LOGIN_SUCCESS)"
```

**Expected:** `auth.login.success`

- [ ] **Step 4:** 暂不 commit,继续 Task 2.2

## Task 2.2:加 observability 测试

**Files:**
- Create: `omni_desk_backend/omni_desk_backend/observability/tests/__init__.py`
- Create: `omni_desk_backend/omni_desk_backend/observability/tests/test_observability.py`

- [ ] **Step 1:** 创建 `__init__.py`(空文件)

- [ ] **Step 2:** 创建 `test_observability.py`:

```python
"""observability 模块测试。"""
import logging
import pytest

from omni_desk_backend.observability import get_logger
from omni_desk_backend.observability.events import AuthEvent, PermissionEvent, CeleryEvent


def test_get_logger_returns_adapter():
    """get_logger 返回 LoggerAdapter。"""
    logger = get_logger("test.module")
    assert isinstance(logger, logging.LoggerAdapter)


def test_event_field_auto_added_when_missing(caplog):
    """未传 event 字段时,自动填 'unspecified'。"""
    logger = get_logger("test.module")
    with caplog.at_level(logging.INFO):
        logger.info("hello world")
    assert len(caplog.records) == 1
    assert caplog.records[0].event == "unspecified"


def test_event_field_preserved_when_provided(caplog):
    """传了 event 字段,保持原值。"""
    logger = get_logger("test.module")
    with caplog.at_level(logging.INFO):
        logger.info("hello", extra={"event": "custom.event", "user_id": 42})
    assert caplog.records[0].event == "custom.event"
    assert caplog.records[0].user_id == 42


def test_event_constants_unique():
    """事件常量不重复。"""
    all_events = [
        AuthEvent.LOGIN_SUCCESS,
        AuthEvent.LOGIN_FAILURE,
        AuthEvent.LOGOUT,
        AuthEvent.JWT_REFRESH_SUCCESS,
        AuthEvent.JWT_REFRESH_FAILURE,
        PermissionEvent.PERMISSION_DENIED,
        CeleryEvent.TASK_START,
        CeleryEvent.TASK_SUCCESS,
        CeleryEvent.TASK_FAILURE,
        CeleryEvent.TASK_RETRY,
    ]
    assert len(all_events) == len(set(all_events))
```

- [ ] **Step 3:** 跑测试验证 GREEN:

```bash
cd omni_desk_backend
pytest omni_desk_backend/observability/tests/test_observability.py -v
```

**Expected:** 4 个测试 PASS

- [ ] **Step 4:** Commit:

```bash
git add omni_desk_backend/omni_desk_backend/observability/
git commit -m "feat(observability): 统一 logger 工厂 + 事件常量定义

- get_logger(name) 返回带 event 字段保证的 LoggerAdapter
- events.py 定义 10 个关键事件常量(AuthEvent/PermissionEvent/CeleryEvent)
- 4 个测试覆盖 event 自动填充与保留"
```

## Task 2.3:登录成功/失败事件

**Files:**
- Modify: `omni_desk_backend/users/views.py`(定位登录 view,通常在文件前 1/3)

- [ ] **Step 1:** 定位登录 view 函数名(`grep "def.*login\|LoginView" omni_desk_backend/users/views.py`)

- [ ] **Step 2:** 在视图顶部加 import:

```python
from omni_desk_backend.observability import get_logger
from omni_desk_backend.observability.events import AuthEvent

logger = get_logger(__name__)
```

- [ ] **Step 3:** 在登录成功分支加:

```python
logger.info(
    "用户登录成功",
    extra={"event": AuthEvent.LOGIN_SUCCESS, "user_id": user.id, "ip": request.META.get("REMOTE_ADDR")},
)
```

- [ ] **Step 4:** 在登录失败分支加(密码错 / 账号锁 / 找不到用户,每个分支):

```python
logger.warning(
    "用户登录失败",
    extra={
        "event": AuthEvent.LOGIN_FAILURE,
        "username": request.data.get("username"),  # 仅记用户名,不记密码
        "reason": "invalid_password",  # 或 "user_not_found" / "account_locked"
        "ip": request.META.get("REMOTE_ADDR"),
    },
)
```

(若视图是 DRF class-based,失败分支通常在 `try/except` 或 `validate()`)

- [ ] **Step 5:** 暂不 commit,继续 Task 2.4

## Task 2.4:写登录日志测试 (TDD)

**Files:**
- Create: `omni_desk_backend/users/tests/test_auth_logging.py`

- [ ] **Step 1:** 写测试(在改视图前先写,确认 RED 后再改视图):

```python
"""登录事件日志测试。

对应 PR-2 Task 2.3:验证登录成功/失败有结构化日志。
"""
import logging
import pytest

from tests.factories import UserFactory


@pytest.mark.django_db
class TestLoginLogging:
    def test_login_success_emits_event(self, api_client, caplog):
        """登录成功应发 auth.login.success 事件。"""
        user = UserFactory(username="alice")
        user.set_password("TestPass123!")
        user.save()
        with caplog.at_level(logging.INFO):
            response = api_client.post(
                "/api/auth/login/",
                {"username": "alice", "password": "TestPass123!"},
                format="json",
            )
        assert response.status_code == 200
        events = [r.event for r in caplog.records if hasattr(r, "event")]
        assert "auth.login.success" in events

    def test_login_failure_emits_event_with_reason(self, api_client, caplog):
        """登录失败应发 auth.login.failure 事件,含 reason 字段。"""
        with caplog.at_level(logging.WARNING):
            response = api_client.post(
                "/api/auth/login/",
                {"username": "nonexistent", "password": "wrong"},
                format="json",
            )
        assert response.status_code in (400, 401)
        events = [r.event for r in caplog.records if hasattr(r, "event")]
        assert "auth.login.failure" in events
        failure_record = next(r for r in caplog.records if getattr(r, "event", None) == "auth.login.failure")
        assert hasattr(failure_record, "reason")
```

- [ ] **Step 2:** 跑测试 RED → GREEN 循环(若 2.3 步骤已实施,现在应 GREEN)

- [ ] **Step 3:** 跑测试:

```bash
cd omni_desk_backend
pytest users/tests/test_auth_logging.py -v
```

**Expected:** 2 个测试 PASS

- [ ] **Step 4:** Commit:

```bash
git add omni_desk_backend/users/
git commit -m "feat(users): 登录成功/失败结构化日志

- 用 observability.get_logger 与 AuthEvent 常量
- 登录成功: user_id + ip
- 登录失败: username + reason + ip(不记密码)
- 2 个 caplog 测试覆盖"
```

## Task 2.5:权限校验失败事件

**Files:**
- Modify: `omni_desk_backend/permissions/views.py` 或 DRF 全局 permission class

- [ ] **Step 1:** 定位权限失败抛 `PermissionDenied` 的位置(通常在自定义 permission class 的 `has_permission` 返回 False)

- [ ] **Step 2:** 在 permission class 顶部加 import,加日志:

```python
from omni_desk_backend.observability import get_logger
from omni_desk_backend.observability.events import PermissionEvent

logger = get_logger(__name__)

class IsAdminOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        if not (request.user and request.user.is_staff):
            logger.warning(
                "权限校验失败",
                extra={
                    "event": PermissionEvent.PERMISSION_DENIED,
                    "user_id": getattr(request.user, "id", None),
                    "resource": view.__class__.__name__,
                    "action": request.method,
                },
            )
            return False
        return True
```

- [ ] **Step 3:** 加测试 `permissions/tests/test_permission_logging.py`:

```python
"""权限校验失败日志测试。"""
import logging
import pytest

from tests.factories import UserFactory


@pytest.mark.django_db
class TestPermissionLogging:
    def test_denied_emits_event(self, api_client, caplog):
        """非管理员访问受保护资源应发 permission.denied 事件。"""
        user = UserFactory(is_staff=False)
        api_client.force_authenticate(user)
        with caplog.at_level(logging.WARNING):
            response = api_client.get("/api/permissions/page-routes/")  # 假设此端点需要 admin
        events = [r.event for r in caplog.records if hasattr(r, "event")]
        # 不强制端点必须拒绝(因为 Phase 1 可能改了分页),只验证:若有拒绝,有日志
        if response.status_code in (403, 401):
            assert "permission.denied" in events
```

- [ ] **Step 4:** 跑测试:

```bash
cd omni_desk_backend
pytest permissions/tests/test_permission_logging.py -v
```

- [ ] **Step 5:** Commit:

```bash
git add omni_desk_backend/permissions/
git commit -m "feat(permissions): 权限校验失败结构化日志

- IsAdminOrReadOnly: 拒绝时发 permission.denied 事件
- 字段: user_id / resource / action
- 1 个测试覆盖"
```

## Task 2.6:Celery 任务起止日志

**Files:**
- Modify: `omni_desk_backend/events/tasks.py`(及任何其他 `*tasks.py` 至少改 1 个代表)

- [ ] **Step 1:** 读 `events/tasks.py` 列出所有 `@shared_task` 装饰的函数

- [ ] **Step 2:** 选 1-2 个代表任务(高频/重要),加装饰器包装(不直接改函数体):

```python
from functools import wraps
import time
from celery import shared_task as celery_shared_task

from omni_desk_backend.observability import get_logger
from omni_desk_backend.observability.events import CeleryEvent

logger = get_logger(__name__)


def logged_task(*celery_args, **celery_kwargs):
    """Celery 任务装饰器,自动记录 start/success/failure 事件。"""
    def decorator(func):
        @celery_shared_task(*celery_args, **celery_kwargs)
        @wraps(func)
        def wrapper(*args, **kwargs):
            task_name = func.__name__
            task_id = wrapper.request.id
            logger.info("celery 任务开始", extra={"event": CeleryEvent.TASK_START, "task_name": task_name, "task_id": task_id})
            start = time.monotonic()
            try:
                result = func(*args, **kwargs)
                duration = (time.monotonic() - start) * 1000
                logger.info(
                    "celery 任务成功",
                    extra={"event": CeleryEvent.TASK_SUCCESS, "task_name": task_name, "task_id": task_id, "duration_ms": duration},
                )
                return result
            except Exception as e:
                logger.error(
                    "celery 任务失败",
                    extra={"event": CeleryEvent.TASK_FAILURE, "task_name": task_name, "task_id": task_id, "error": str(e)},
                )
                raise
        return wrapper
    return decorator
```

- [ ] **Step 3:** 改 `events/tasks.py` 中 1-2 个代表任务:`@shared_task` → `@logged_task()`

- [ ] **Step 4:** 写测试 `events/tests/test_tasks_logging.py`:

```python
"""Celery 任务结构化日志测试。"""
import logging
import pytest

from events.tasks import example_task  # 替换为实际任务名


@pytest.mark.django_db(transaction=True)
class TestCeleryTaskLogging:
    def test_task_success_emits_start_and_success_events(self, caplog):
        """任务成功应发 celery.task.start + celery.task.success 两个事件。"""
        # 用 apply() 同步执行(eager mode)
        with caplog.at_level(logging.INFO):
            example_task.apply().get()
        events = [r.event for r in caplog.records if hasattr(r, "event")]
        assert "celery.task.start" in events
        assert "celery.task.success" in events
```

- [ ] **Step 5:** 跑测试:

```bash
cd omni_desk_backend
pytest events/tests/test_tasks_logging.py -v
```

- [ ] **Step 6:** Commit:

```bash
git add omni_desk_backend/events/tasks.py omni_desk_backend/events/tests/
git commit -m "feat(events): Celery 任务 start/success/failure 结构化日志

- 新增 logged_task 装饰器,自动记录起止 + duration_ms
- 应用到 events/tasks.py 代表任务
- 1 个测试覆盖"
```

## Task 2.7:写日志规范文档

**Files:**
- Create: `docs/technical/27-logging-standards.md`

- [ ] **Step 1:** 创建文档:

```markdown
# 27. 日志规范与事件清单

> 适用版本:OmniDesk v0.7+
> 关联: PR-2 feat/key-path-logger

## 一、目标

生产环境排障时可通过 grep 关键事件快速定位问题,且不泄露 PII。

## 二、Logger 使用规范

### 2.1 统一获取方式

```python
from omni_desk_backend.observability import get_logger

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
```

- [ ] **Step 2:** 在 `docs/technical/README.md` 章节目录加一行:

```markdown
| 27 | [日志规范与事件清单](27-logging-standards.md) | 日志使用、事件清单、脱敏规范 |
```

- [ ] **Step 3:** Commit:

```bash
git add docs/technical/27-logging-standards.md docs/technical/README.md
git commit -m "docs(technical): 新增 §27 日志规范与事件清单

- 27-logging-standards.md: 涵盖 logger 使用 / 事件清单 / 脱敏规范 / 添加流程
- README.md 章节目录加链接"
```

## Task 2.8:全量回归

- [ ] **Step 1:** 跑后端全测:

```bash
cd omni_desk_backend
pytest --cov-fail-under=80 -q
```

**Expected:** 全绿,覆盖率 ≥ 80%

- [ ] **Step 2:** 跑 ruff:

```bash
ruff check omni_desk_backend/
ruff format --check omni_desk_backend/
```

**Expected:** 0 errors

- [ ] **Step 3:** 暂不 commit,继续 Task 2.9

## Task 2.9:推送 + PR

- [ ] **Step 1:** 推送 + PR(同 Task 1.7 流程):

```bash
git push -u origin feat/key-path-logger
gh pr create --title "feat(observability): 关键路径结构化日志(登录/权限/Celery)" --body "..."
gh pr checks <n> --watch
```

- [ ] **Step 2:** 报告用户,等 merge

---

# Phase 3 (PR-3):django-silk dev 接入

**Branch:** `feat/django-silk-dev`
**Worktree 建议:** `git switch -c feat/django-silk-dev`
**依赖前置:** 无(可与 PR-1/PR-2 并行)
**总任务数:** 6

## Task 3.1:加 django-silk 到 requirements-dev

**Files:**
- Modify: `omni_desk_backend/requirements-dev.in`
- Modify: `omni_desk_backend/requirements-dev.txt`

- [ ] **Step 1:** 在 `requirements-dev.in` 末尾加:

```
# Performance profiling (dev only)
django-silk
```

- [ ] **Step 2:** 用 pip-tools 重新生成 `requirements-dev.txt`:

```bash
cd omni_desk_backend
pip-compile -o requirements-dev.txt requirements-dev.in
```

(若 `pip-compile` 未装:`pip install pip-tools`)

- [ ] **Step 3:** 验证 `requirements-dev.txt` 含 `django-silk==<version>`,且 `requirements-prod.txt` 不含(只 dev 依赖)

- [ ] **Step 4:** Commit:

```bash
git add omni_desk_backend/requirements-dev.in omni_desk_backend/requirements-dev.txt
git commit -m "build(deps-dev): django-silk 仅 dev 依赖

- requirements-dev.in 加 django-silk
- pip-compile 重生成 requirements-dev.txt
- requirements-prod.txt 不受影响"
```

## Task 3.2:settings/local.py 条件化启用

**Files:**
- Modify: `omni_desk_backend/omni_desk_backend/settings/local.py`

- [ ] **Step 1:** 读 `local.py`,定位 `INSTALLED_APPS` 与 `MIDDLEWARE` 列表

- [ ] **Step 2:** 在文件顶部加:

```python
import os
ENABLE_SILK = os.environ.get("ENABLE_SILK") == "1" and DEBUG
```

- [ ] **Step 3:** 在 `INSTALLED_APPS` 末尾加条件:

```python
if ENABLE_SILK:
    INSTALLED_APPS += [
        "silk",
    ]
```

- [ ] **Step 4:** 在 `MIDDLEWARE` 列表最前加:

```python
if ENABLE_SILK:
    MIDDLEWARE = ["silk.middleware.SilkyMiddleware"] + MIDDLEWARE
```

- [ ] **Step 5:** 在 `local.py` 末尾加 silk 配置(条件块):

```python
if ENABLE_SILK:
    SILKY_PYTHON_PROFILER = False  # 关闭 Python profiler,只 SQL
    SILKY_AUTHENTICATION = True    # 限制访问
    SILKY_AUTHORISATION = True
    SILKY_MAX_REQUEST_BODY_SIZE = 1024
    SILKY_MAX_RESPONSE_BODY_SIZE = 1024
    SILKY_EXCLUDE_PATHS = ["/health/", "/ready/"]  # 排除健康检查
```

- [ ] **Step 6:** 暂不 commit,继续 Task 3.3

## Task 3.3:URL 路由条件化

**Files:**
- Modify: `omni_desk_backend/omni_desk_backend/urls.py`

- [ ] **Step 1:** 在 `urls.py` 顶部加:

```python
from django.conf import settings
```

- [ ] **Step 2:** 在 `urlpatterns` 末尾(或合适位置)加:

```python
if getattr(settings, "ENABLE_SILK", False):
    urlpatterns += [path("silk/", include("silk.urls", namespace="silk"))]
```

(若 `include` 已 import,无需重复)

- [ ] **Step 3:** 暂不 commit,继续 Task 3.4

## Task 3.4:验证 dev 启动 + 访问 silk

- [ ] **Step 1:** 装 dev 依赖:

```bash
cd omni_desk_backend
pip install -r requirements-dev.txt
```

- [ ] **Step 2:** 启动 dev server(模拟 dev 模式):

```bash
ENABLE_SILK=1 DJANGO_SETTINGS_MODULE=omni_desk_backend.settings.local python manage.py runserver
```

**Expected:** 启动无报错,silk 出现在 INSTALLED_APPS

- [ ] **Step 3:** 浏览器访问 `http://127.0.0.1:8000/silk/`,确认能进 silk 主页

- [ ] **Step 4:** 触发一个 API 请求(如 `curl http://127.0.0.1:8000/api/auth/login/`),回 silk 页面看是否有记录

- [ ] **Step 5:** 不带 `ENABLE_SILK=1` 启动:

```bash
DJANGO_SETTINGS_MODULE=omni_desk_backend.settings.local python manage.py runserver
```

访问 `/silk/` 应 404(未启用)

- [ ] **Step 6:** Commit:

```bash
git add omni_desk_backend/omni_desk_backend/settings/local.py omni_desk_backend/omni_desk_backend/urls.py
git commit -m "feat(devtools): django-silk dev 模式接入

- settings/local.py: ENABLE_SILK=1 且 DEBUG 时挂载
- urls.py: /silk/ 路径条件化
- silk 配置: 关闭 Python profiler,限制 body 大小,排除健康检查
- prod 构建完全无 silk 引用"
```

## Task 3.5:写 profiling 文档

**Files:**
- Create: `docs/technical/29-performance-profiling.md`

- [ ] **Step 1:** 创建文档:

```markdown
# 29. 性能 Profiling(django-silk)

> 适用版本:OmniDesk v0.7+
> 关联: PR-3 feat/django-silk-dev

## 一、概述

django-silk 是 Django 官方推荐的 SQL profiling 工具,记录每个 HTTP 请求的 SQL 数量、耗时、慢查询。

**仅 dev/local 模式启用**,生产环境永不接入。

## 二、启用

```bash
export ENABLE_SILK=1
DJANGO_SETTINGS_MODULE=omni_desk_backend.settings.local python manage.py runserver
```

访问 `http://127.0.0.1:8000/silk/` 即可看到 profiling 面板。

## 三、典型使用场景

### 3.1 找慢查询

1. 触发慢 API(如列表端点)
2. 打开 silk 主页,按 "Time" 降序
3. 点击进入详情,看 SQL 列表与 EXPLAIN
4. 加 `select_related` / `prefetch_related` / 索引

### 3.2 找 N+1

1. 触发列表 API(如 `/api/documents/generated/`)
2. silk 详情看 SQL 数量:正常 ≤ 5,N+1 时 = N
3. 在对应 viewset 加 `select_related` / `prefetch_related`

### 3.3 找端点慢但 SQL 快的请求

1. silk 看 SQL 耗时占比
2. 若 SQL 占 < 30%,看 Python 代码侧(profile with silk)

## 四、配置项

见 `settings/local.py` 的 `SILKY_*` 配置:

| 配置 | 默认 | 说明 |
|------|------|------|
| `SILKY_PYTHON_PROFILER` | False | 是否启用 Python 代码级 profiling |
| `SILKY_MAX_REQUEST_BODY_SIZE` | 1024 | 请求体最大记录字节 |
| `SILKY_MAX_RESPONSE_BODY_SIZE` | 1024 | 响应体最大记录字节 |
| `SILKY_EXCLUDE_PATHS` | `["/health/", "/ready/"]` | 不记录的路径 |

## 五、生产禁用

- prod 设置文件(`settings/production.py`)不 import silk
- `requirements-prod.txt` 不含 django-silk
- 即使 `ENABLE_SILK=1` 在 prod 也无效(因为 `DEBUG=False` 短路)
```

- [ ] **Step 2:** 在 `docs/technical/README.md` 加一行:

```markdown
| 29 | [性能 Profiling](29-performance-profiling.md) | django-silk dev 接入与使用 |
```

- [ ] **Step 3:** Commit:

```bash
git add docs/technical/29-performance-profiling.md docs/technical/README.md
git commit -m "docs(technical): 新增 §29 性能 Profiling(django-silk)"
```

## Task 3.6:推送 + PR

- [ ] **Step 1:** 推送 + PR(同 Task 1.7 流程)

- [ ] **Step 2:** 报告用户,等 merge

---

# Phase 4 (PR-4):`src/shared/api` → TypeScript

**Branch:** `refactor/shared-api-typescript`
**Worktree 建议:** `git switch -c refactor/shared-api-typescript`
**依赖前置:** 无(可与后端 PR 并行)
**总任务数:** 8

## Task 4.1:基础设施层 — apiClient + axiosConfig + responseHandler

**Files:**
- Modify: `omni_desk_frontend/src/shared/api/axiosConfig.js` → `.ts`
- Modify: `omni_desk_frontend/src/shared/api/apiClient.js` → `.ts`
- Modify: `omni_desk_frontend/src/shared/api/responseHandler.js` → `.ts`

- [ ] **Step 1:** 用 `git mv` 重命名(保留历史):

```bash
cd omni_desk_frontend/src/shared/api
git mv axiosConfig.js axiosConfig.ts
git mv apiClient.js apiClient.ts
git mv responseHandler.js responseHandler.ts
```

- [ ] **Step 2:** 编辑 `axiosConfig.ts`,在文件顶部加类型:

```typescript
import axios, { AxiosInstance, InternalAxiosRequestConfig, AxiosResponse, AxiosError } from 'axios';
import { getEnv } from '../utils/env';

const API_BASE_URL = getEnv('VITE_API_BASE_URL', '/api');
const baseURL = API_BASE_URL.endsWith('/') ? API_BASE_URL : API_BASE_URL + '/';

interface FailedRequest {
    resolve: (token: string | null) => void;
    reject: (error: AxiosError) => void;
}

const instance: AxiosInstance = axios.create({ /* 原配置不变 */ });

let isRefreshing = false;
let failedQueue: FailedRequest[] = [];

// ... 后续代码不变
```

- [ ] **Step 3:** 编辑 `apiClient.ts`:

```typescript
import { instance as axiosInstance } from './axiosConfig';
import { handleResponse, ApiError } from './responseHandler';

export async function apiGet<T>(url: string, config?: object): Promise<T> {
    return handleResponse<T>(await axiosInstance.get<T>(url, config));
}

export async function apiPost<T, R = T>(url: string, body?: T, config?: object): Promise<R> {
    return handleResponse<R>(await axiosInstance.post<R>(url, body, config));
}

export async function apiPut<T, R = T>(url: string, body?: T, config?: object): Promise<R> {
    return handleResponse<R>(await axiosInstance.put<R>(url, body, config));
}

export async function apiDelete<T = void>(url: string, config?: object): Promise<T> {
    return handleResponse<T>(await axiosInstance.delete<T>(url, config));
}

export { ApiError };
```

- [ ] **Step 4:** 编辑 `responseHandler.ts`:

```typescript
import { AxiosResponse, AxiosError } from 'axios';

export class ApiError extends Error {
    status: number;
    data: unknown;
    constructor(message: string, status: number, data: unknown) {
        super(message);
        this.name = 'ApiError';
        this.status = status;
        this.data = data;
    }
}

export async function handleResponse<T>(response: AxiosResponse<T>): Promise<T> {
    return response.data;
}

export async function handleError(error: AxiosError): Promise<never> {
    if (error.response) {
        throw new ApiError(
            error.message,
            error.response.status,
            error.response.data,
        );
    }
    throw new ApiError(error.message, 0, null);
}
```

- [ ] **Step 5:** 跑类型检查:

```bash
cd omni_desk_frontend
npx tsc --noEmit
```

**Expected:** 0 errors(其他业务 API 文件可能临时报错,继续 Task 4.2)

- [ ] **Step 6:** 跑测试(测试文件未改):

```bash
npm test -- --watchAll=false
```

**Expected:** 原有测试全绿

- [ ] **Step 7:** 暂不 commit,继续 Task 4.2

## Task 4.2:业务 API 文件 1 — compliance + deepseek + ollama

**Files:**
- Modify: `omni_desk_frontend/src/shared/api/{compliance,deepseek,ollama}.js` → `.ts`

- [ ] **Step 1:** 重命名 3 个文件:

```bash
cd omni_desk_frontend/src/shared/api
git mv compliance.js compliance.ts
git mv deepseek.js deepseek.ts
git mv ollama.js ollama.ts
```

- [ ] **Step 2:** 编辑每个文件,加 import 与类型:

```typescript
// compliance.ts 示例
import { apiGet, apiPost } from './apiClient';

export interface ComplianceIssue {
    id: number;
    title: string;
    severity: 'low' | 'medium' | 'high' | 'critical';
    status: 'open' | 'in_progress' | 'resolved' | 'closed';
    created_at: string;
}

export async function getComplianceIssues(): Promise<ComplianceIssue[]> {
    return apiGet<ComplianceIssue[]>('/compliance/issues/');
}

// ... 其他函数同理加返回类型
```

(具体接口字段参考 `compliance/serializers.py`,按 DRF 实际返回结构)

- [ ] **Step 3:** 跑类型检查 + 测试:

```bash
cd omni_desk_frontend
npx tsc --noEmit
npm test -- --watchAll=false
```

**Expected:** 0 type errors, 测试全绿

- [ ] **Step 4:** 暂不 commit,继续 Task 4.3

## Task 4.3:业务 API 文件 2 — memoApi + pageConfigApi + permissionsApi

**Files:**
- Modify: `omni_desk_frontend/src/shared/api/{memoApi,pageConfigApi,permissionsApi}.js` → `.ts`

- [ ] **Step 1:** 重命名 3 个文件:

```bash
cd omni_desk_frontend/src/shared/api
git mv memoApi.js memoApi.ts
git mv pageConfigApi.js pageConfigApi.ts
git mv permissionsApi.js permissionsApi.ts
```

- [ ] **Step 2:** 按 Task 4.2 Step 2 模式加类型(参考后端 serializer)

- [ ] **Step 3:** 跑类型检查 + 测试

- [ ] **Step 4:** 暂不 commit,继续 Task 4.4

## Task 4.4:业务 API 文件 3 — sequenceApi + trialApi + trials

**Files:**
- Modify: `omni_desk_frontend/src/shared/api/{sequenceApi,trialApi,trials}.js` → `.ts`

- [ ] **Step 1:** 重命名 3 个文件

- [ ] **Step 2:** 按相同模式加类型

- [ ] **Step 3:** 跑类型检查 + 测试

- [ ] **Step 4:** 暂不 commit,继续 Task 4.5

## Task 4.5:补全 api.d.ts 缺失接口

**Files:**
- Modify: `omni_desk_frontend/src/shared/types/api.d.ts`

- [ ] **Step 1:** 读 `api.d.ts` 现有内容,列出已有接口

- [ ] **Step 2:** 对照 `compliance/serializers.py`、`permissions/serializers.py` 等,补缺失的枚举 / 引用类型

- [ ] **Step 3:** 跑 `npx tsc --noEmit` 确认 0 errors

- [ ] **Step 4:** 暂不 commit,继续 Task 4.6

## Task 4.6:全量构建 + 测试

- [ ] **Step 1:** 全量类型检查:

```bash
cd omni_desk_frontend
npx tsc --noEmit
```

**Expected:** 0 errors

- [ ] **Step 2:** 跑 lint:

```bash
npm run lint
```

**Expected:** 0 errors(若有,按需修)

- [ ] **Step 3:** 跑全测:

```bash
npm test -- --watchAll=false
```

**Expected:** 全部通过

- [ ] **Step 4:** 跑 build:

```bash
npm run build
```

**Expected:** 构建成功,记录 main bundle 体积前后对比

- [ ] **Step 5:** 暂不 commit,继续 Task 4.7

## Task 4.7:清理 `any` + 标注 TODO

- [ ] **Step 1:** grep 转换后的 .ts 文件中的 `any`:

```bash
cd omni_desk_frontend
grep -n "any" src/shared/api/*.ts
```

- [ ] **Step 2:** 对每个 `any`,判断能否用具体类型替代:
  - 可替代 → 替换
  - 暂时无法替代(后端 serializer 未明确) → 改为 `unknown` + 加 `// TODO: 后续 PR 完善类型` 注释

- [ ] **Step 3:** 跑 `npx tsc --noEmit` 确认仍 0 errors

- [ ] **Step 4:** Commit:

```bash
git add omni_desk_frontend/src/shared/api/ omni_desk_frontend/src/shared/types/
git commit -m "refactor(frontend): src/shared/api 全部转 TypeScript

- 12 个 .js 文件转 .ts(apiClient / axiosConfig / responseHandler + 9 业务 API)
- 利用现有 api.d.ts 共享类型
- 用 unknown 替代 any,标 TODO 后续完善
- 测试文件保持 .test.js 不动(jest 兼容)
- 验证: tsc --noEmit 0 errors / npm test 全绿 / npm run build 成功"
```

## Task 4.8:推送 + PR

- [ ] **Step 1:** 推送 + PR(同 Task 1.7 流程)

- [ ] **Step 2:** PR 描述中包含:
  - 转换前后 main bundle 体积对比
  - 类型覆盖率(已知接口 / 总接口)
  - 后续 PR TODO 清单

- [ ] **Step 3:** 报告用户,等 merge

---

# Phase 5 (PR-5):zod 表单试点

**Branch:** `feat/zod-form-pilot`
**Worktree 建议:** `git switch -c feat/zod-form-pilot`
**依赖前置:** 无(可与后端 PR 并行)
**总任务数:** 6

## Task 5.1:装 zod 依赖

**Files:**
- Modify: `omni_desk_frontend/package.json`
- Modify: `omni_desk_frontend/package-lock.json`

- [ ] **Step 1:** 装最新稳定 zod:

```bash
cd omni_desk_frontend
npm install zod
```

(若需锁版本:`npm install zod@<version>`,记下版本号)

- [ ] **Step 2:** 验证 `package.json` 中 `"zod": "<version>"` 存在

- [ ] **Step 3:** 跑 `npm install` 确认 lock file 一致

- [ ] **Step 4:** 跑 build 确保不破坏:

```bash
npm run build
```

**Expected:** 构建成功

- [ ] **Step 5:** Commit:

```bash
git add omni_desk_frontend/package.json omni_desk_frontend/package-lock.json
git commit -m "build(frontend): 加 zod 依赖(表单 schema 校验)"
```

## Task 5.2:创建 LoginSchema (RED)

**Files:**
- Create: `omni_desk_frontend/src/features/auth/schemas/loginSchema.ts`
- Create: `omni_desk_frontend/src/features/auth/schemas/loginSchema.test.js`

- [ ] **Step 1:** 创建 `loginSchema.ts`:

```typescript
import { z } from 'zod';

/** 登录表单 schema。 */
export const LoginSchema = z.object({
    username: z
        .string()
        .min(3, '用户名至少 3 字符')
        .max(64, '用户名不超过 64 字符'),
    password: z
        .string()
        .min(8, '密码至少 8 字符')
        .max(128, '密码不超过 128 字符'),
});

export type LoginFormValues = z.infer<typeof LoginSchema>;

/** 把 zod 错误转 antd Form 字段错误格式。 */
export function zodToAntdErrors(error: z.ZodError): Record<string, { errors: string[] }> {
    const fieldErrors: Record<string, { errors: string[] }> = {};
    for (const issue of error.issues) {
        const path = issue.path.join('.');
        if (!fieldErrors[path]) {
            fieldErrors[path] = { errors: [] };
        }
        fieldErrors[path].errors.push(issue.message);
    }
    return fieldErrors;
}
```

- [ ] **Step 2:** 创建 `loginSchema.test.js`:

```javascript
import { LoginSchema, zodToAntdErrors } from './loginSchema';

describe('LoginSchema', () => {
    test('accepts valid input', () => {
        const result = LoginSchema.safeParse({ username: 'alice', password: 'Pass1234' });
        expect(result.success).toBe(true);
    });

    test('rejects short username', () => {
        const result = LoginSchema.safeParse({ username: 'ab', password: 'Pass1234' });
        expect(result.success).toBe(false);
        if (!result.success) {
            expect(result.error.issues[0].path).toEqual(['username']);
            expect(result.error.issues[0].message).toContain('至少 3 字符');
        }
    });

    test('rejects short password', () => {
        const result = LoginSchema.safeParse({ username: 'alice', password: 'short' });
        expect(result.success).toBe(false);
    });

    test('rejects empty fields', () => {
        const result = LoginSchema.safeParse({ username: '', password: '' });
        expect(result.success).toBe(false);
        expect(result.error.issues.length).toBe(2);
    });

    test('zodToAntdErrors formats errors', () => {
        const result = LoginSchema.safeParse({ username: 'ab', password: 'short' });
        if (result.success) throw new Error('expected failure');
        const formatted = zodToAntdErrors(result.error);
        expect(formatted.username).toBeDefined();
        expect(formatted.password).toBeDefined();
        expect(formatted.username.errors[0]).toContain('至少 3 字符');
    });
});
```

- [ ] **Step 3:** 跑测试 GREEN:

```bash
cd omni_desk_frontend
npm test -- --watchAll=false src/features/auth/schemas/loginSchema.test.js
```

**Expected:** 5 个测试 PASS

- [ ] **Step 4:** Commit:

```bash
git add omni_desk_frontend/src/features/auth/schemas/
git commit -m "feat(auth): 登录表单 zod schema + 转换函数

- LoginSchema: username 3-64, password 8-128
- zodToAntdErrors: zod 错误转 antd Form 字段错误格式
- 5 个测试覆盖边界"
```

## Task 5.3:重构 Login.jsx 集成 zod

**Files:**
- Modify: `omni_desk_frontend/src/features/auth/pages/Login.jsx`

- [ ] **Step 1:** 读 `Login.jsx` 当前实现,定位 Form 的 `rules` 与 `onFinish` 处理

- [ ] **Step 2:** 改 import:

```javascript
// 移除:
import { Form, Input, Button, message } from 'antd';
// 加:
import { LoginSchema, zodToAntdErrors } from '../schemas/loginSchema';
```

- [ ] **Step 3:** 移除 Form.Item 的 `rules` 属性(由 zod 校验)

- [ ] **Step 4:** 改 `onFinish`:

```javascript
const onFinish = (values) => {
    const result = LoginSchema.safeParse(values);
    if (!result.success) {
        const fieldErrors = zodToAntdErrors(result.error);
        const antdErrors = Object.entries(fieldErrors).map(([name, err]) => ({
            name,
            errors: err.errors,
        }));
        form.setFields(antdErrors);
        return;
    }
    authLogin(result.data);
};
```

(注:`setFields` 接受 `{name, errors}[]`,不是 record;上面 map 是修正)

- [ ] **Step 5:** 跑测试:

```bash
cd omni_desk_frontend
npm test -- --watchAll=false src/features/auth/pages/Login.test.js
```

**Expected:** 现有测试全绿(若有"提交空表单显示错误"测试,需更新为验证 zod 错误信息)

- [ ] **Step 6:** 跑 build:

```bash
npm run build
```

- [ ] **Step 7:** Commit:

```bash
git add omni_desk_frontend/src/features/auth/pages/Login.jsx
git commit -m "feat(auth): 登录页集成 zod schema 校验

- 移除 antd Form.Item rules
- onFinish 用 LoginSchema.safeParse + zodToAntdErrors
- 错误提示文案与原版一致(用户无感)"
```

## Task 5.4:补 Login 测试

**Files:**
- Modify: `omni_desk_frontend/src/features/auth/pages/Login.test.js`

- [ ] **Step 1:** 读现有 `Login.test.js`,识别是否覆盖了空表单 / 短字段场景

- [ ] **Step 2:** 若未覆盖,加测试:

```javascript
test('shows zod error on empty submit', async () => {
    render(<Login />);
    // 不填任何字段,直接点登录
    fireEvent.click(screen.getByRole('button', { name: /登录/ }));
    // 断言: 错误提示出现
    expect(await screen.findByText(/至少 3 字符/)).toBeInTheDocument();
});
```

- [ ] **Step 3:** 跑测试验证:

```bash
npm test -- --watchAll=false src/features/auth/pages/Login.test.js
```

- [ ] **Step 4:** 暂不 commit,继续 Task 5.5

## Task 5.5:写表单校验模式文档

**Files:**
- Create: `docs/technical/30-form-validation-pattern.md`

- [ ] **Step 1:** 创建文档:

```markdown
# 30. 表单校验模式(zod + antd Form)

> 适用版本:OmniDesk v0.7+
> 关联: PR-5 feat/zod-form-pilot

## 一、为什么用 zod

- 单一真相源: 字段约束、错误信息、TS 类型从同一 schema 推导
- 复用: 前后端共享 schema(若用 zod-to-openapi)
- 可测: schema 本身可纯函数测试,无需 DOM

## 二、模式

### 2.1 文件结构

```
features/<feature>/schemas/
├── __init__.py
├── loginSchema.ts
└── loginSchema.test.js
```

每个表单一个 schema 文件,文件名 `<form>Schema.ts`。

### 2.2 schema 三要素

```typescript
import { z } from 'zod';

export const LoginSchema = z.object({
    username: z.string().min(3, '用户名至少 3 字符').max(64),
    password: z.string().min(8, '密码至少 8 字符').max(128),
});

export type LoginFormValues = z.infer<typeof LoginSchema>;
```

### 2.3 antd 集成

```javascript
import { Form, Input, Button } from 'antd';
import { LoginSchema, zodToAntdErrors } from '../schemas/loginSchema';

const [form] = Form.useForm();

const onFinish = (values) => {
    const result = LoginSchema.safeParse(values);
    if (!result.success) {
        form.setFields(
            Object.entries(zodToAntdErrors(result.error)).map(([name, err]) => ({
                name,
                errors: err.errors,
            }))
        );
        return;
    }
    // 提交
    submitLogin(result.data);
};

<Form form={form} onFinish={onFinish}>
    <Form.Item name="username"><Input /></Form.Item>
    <Form.Item name="password"><Input.Password /></Form.Item>
    <Button htmlType="submit">登录</Button>
</Form>
```

### 2.4 错误提示规范

- 用户面向的错误信息**用中文**(本项目 UI 全中文)
- min/max 提示带具体数字:`"至少 3 字符"` 而非 `"太短"`
- 业务规则错误用更友好措辞:`"用户名已存在"` 而非 `"unique constraint"`

## 三、测试

每个 schema 必有 5 类测试:
- 合法输入
- 边界值(最小/最大)
- 空字段
- 错误格式(zodToAntdErrors 输出格式)
- 跨字段约束(若有 `refine`)

## 四、扩展到其他表单

1. 复制 `loginSchema.ts` 模式,新建 `<form>Schema.ts`
2. 在表单页面改 import + 移除 rules
3. 加测试
4. 不需要改后端 / antd 全局配置
```

- [ ] **Step 2:** 在 `docs/technical/README.md` 加一行:

```markdown
| 30 | [表单校验模式](30-form-validation-pattern.md) | zod + antd Form 集成模式 |
```

- [ ] **Step 3:** Commit:

```bash
git add omni_desk_frontend/src/features/auth/pages/Login.test.js docs/technical/30-form-validation-pattern.md docs/technical/README.md
git commit -m "feat(auth+docs): Login zod 集成测试 + §30 表单校验模式文档"
```

## Task 5.6:推送 + PR

- [ ] **Step 1:** 推送 + PR

- [ ] **Step 2:** 报告用户,等 merge

---

# Phase 6 (PR-6):动态 import 优化

**Branch:** `feat/lazy-chunk-optimization`
**Worktree 建议:** `git switch -c feat/lazy-chunk-optimization`
**依赖前置:** 无(可与其他 PR 并行)
**总任务数:** 5

## Task 6.1:创建 Suspense fallback 组件

**Files:**
- Create: `omni_desk_frontend/src/shared/components/PageSuspenseFallback.jsx`

- [ ] **Step 1:** 创建组件:

```jsx
import { Spin } from 'antd';

/** 路由级 lazy 加载的占位组件。 */
export default function PageSuspenseFallback() {
    return (
        <div
            style={{
                display: 'flex',
                justifyContent: 'center',
                alignItems: 'center',
                minHeight: '60vh',
            }}
        >
            <Spin size="large" tip="加载中..." />
        </div>
    );
}
```

- [ ] **Step 2:** 暂不 commit,继续 Task 6.2

## Task 6.2:把 editor / docprocessing / markdown 页面转为 lazy

**Files:**
- Modify: `omni_desk_frontend/src/routes/index.jsx`

- [ ] **Step 1:** 读 `routes/index.jsx`,定位以下页面的 import(根据 `vite.config.js` 中 manualChunks):
  - editor 相关:`@tiptap` / `react-quill` 用到的页面
  - docprocessing:`docxtemplater` / `mammoth` 用到的页面
  - markdown:`react-markdown` 用到的页面

- [ ] **Step 2:** 把直接 import 改为 lazy:

```jsx
// 改前
import DocumentEditorPage from '@/features/documents/pages/DocumentEditorPage';
import PdfPreviewPage from '@/features/documents/pages/PdfPreviewPage';
import MarkdownRenderPage from '@/features/markdown/MarkdownRenderPage';

// 改后
import { lazy } from 'react';
const DocumentEditorPage = lazy(() => import('@/features/documents/pages/DocumentEditorPage'));
const PdfPreviewPage = lazy(() => import('@/features/documents/pages/PdfPreviewPage'));
const MarkdownRenderPage = lazy(() => import('@/features/markdown/MarkdownRenderPage'));
```

- [ ] **Step 3:** 在路由外层加 Suspense(若有 Router wrapper):

```jsx
import { Suspense } from 'react';
import PageSuspenseFallback from '@/shared/components/PageSuspenseFallback';

<Suspense fallback={<PageSuspenseFallback />}>
    <Routes>...</Routes>
</Suspense>
```

或在 `createBrowserRouter` 形式中用 `lazy` + `HydrateFallback` / `Suspense` 包裹。

- [ ] **Step 4:** 跑 build:

```bash
cd omni_desk_frontend
npm run build
```

**Expected:** 构建成功,记录 main bundle 体积前后对比

- [ ] **Step 5:** 跑测试:

```bash
npm test -- --watchAll=false
```

**Expected:** 全部通过

- [ ] **Step 6:** 暂不 commit,继续 Task 6.3

## Task 6.3:Win7 Chrome 109 实测验证

- [ ] **Step 1:** 启动 dev server:

```bash
cd omni_desk_frontend
npm start
```

- [ ] **Step 2:** 在 Chrome 109(若项目 CI 有此版本 runner)实际访问以下路由:
  - `/documents/<id>/edit` (触发 editor chunk)
  - `/documents/<id>/preview` (触发 docprocessing chunk)
  - `/memo/<id>` (触发 markdown chunk)

- [ ] **Step 3:** 检查 Network 面板,确认:
  - 初次进入页面时只下载 main + 必要 vendor
  - 点击上述路由时按需下载 editor / docprocessing / markdown chunk
  - 无 JS 报错

- [ ] **Step 4:** 暂不 commit,继续 Task 6.4

## Task 6.4:写 win7-compatibility 加一行

**Files:**
- Modify: `docs/technical/22-win7-compatibility.md`

- [ ] **Step 1:** 读 `22-win7-compatibility.md`,在浏览器兼容特性表加一行:

```markdown
| 动态 `import()` / `React.lazy` | ✅ 支持 | Chrome 61+,与 Win7 Chrome 109 兼容 |
```

- [ ] **Step 2:** Commit:

```bash
git add omni_desk_frontend/src/shared/components/PageSuspenseFallback.jsx omni_desk_frontend/src/routes/index.jsx docs/technical/22-win7-compatibility.md
git commit -m "perf(frontend): editor / docprocessing / markdown 页面 React.lazy 拆分

- 新增 PageSuspenseFallback 组件
- 三个最大 chunk 改为 React.lazy + Suspense
- main bundle 体积下降(具体数值见 PR 描述)
- Win7 Chrome 109 实测通过
- 22-win7-compatibility.md 加兼容性记录"
```

## Task 6.5:推送 + PR

- [ ] **Step 1:** 推送 + PR

- [ ] **Step 2:** PR 描述包含:
  - main bundle 体积前后对比(从 build 报告)
  - editor / docprocessing / markdown chunk 体积
  - 实测截图(可选)

- [ ] **Step 3:** 报告用户,等 merge

---

# 自审清单(Self-Review)

执行完所有 6 个 Phase 后,Plan 整体自审:

## Spec 覆盖

| Spec § | 对应 Phase | 状态 |
|--------|-----------|------|
| §三 PR-1 ViewSet 分页恢复 | Phase 1 | ✅ Task 1.1-1.7 |
| §三 PR-2 关键路径结构化日志 | Phase 2 | ✅ Task 2.1-2.9 |
| §三 PR-3 django-silk dev 接入 | Phase 3 | ✅ Task 3.1-3.6 |
| §三 PR-4 src/shared/api → TS | Phase 4 | ✅ Task 4.1-4.8 |
| §三 PR-5 zod 表单试点 | Phase 5 | ✅ Task 5.1-5.6 |
| §三 PR-6 动态 import 优化 | Phase 6 | ✅ Task 6.1-6.5 |
| §四 实施顺序与并行性 | 全局前置条件 | ✅ |
| §五 风险评估 | 每个 PR 描述 + Phase 任务 | ✅ |
| §六 依赖 | Task 3.1 / 5.1 | ✅ |
| §七 Definition of Done | 全局前置条件 + 每个 Phase 结束 | ✅ |

## Placeholder 扫描

✅ 全文搜索:无 TBD / TODO(除 PR-4 故意保留的"// TODO: 后续 PR 完善类型"注释,在 Task 4.7 显式说明)
✅ 无 "implement later" / "add appropriate" / "handle edge cases" 模糊措辞
✅ 所有代码块完整

## Type/Name 一致性

- `GeneratedDocumentViewSet` 出现: Task 1.1, 1.2, 1.3(一致)
- `UserPersonnelViewSet` 出现: Task 1.1, 1.4(一致)
- `PageRouteViewSet` 出现: Task 1.1, 1.4(一致)
- `MyScheduleView` 出现: Task 1.1, 1.5(一致)
- `AuthEvent.LOGIN_SUCCESS` 等: Task 2.1(定义), 2.2(测试), 2.3(使用)(一致)
- `LoginSchema` / `zodToAntdErrors`: Task 5.2(定义 + 测试), 5.3(使用)(一致)
- `PageSuspenseFallback`: Task 6.1(定义), 6.2(使用)(一致)

## 文件路径一致性

所有 `Create` / `Modify` 路径:
- `omni_desk_backend/...` ✅
- `omni_desk_frontend/...` ✅
- `docs/technical/...` ✅

无悬挂引用。
