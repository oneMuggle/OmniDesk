# OmniDesk 端 ↔ Sage 桌面端 集成 — 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 OmniDesk 后端新增 `sage_integration` Django app,提供通道 A(Sage 查业务:排班 / 人员)与通道 B(任务留痕)的双向 API,默认关闭,显式开启后生效。配套技术 / 用户文档 + CHANGELOG。

**Architecture:** 所有互通逻辑落到新 `sage_integration` app,不修改既有 16 个业务 app。账号模型用 `OneToOneField` 扩展 CustomUser(沿用 `PhoneNumber` 风格,不污染主表)。全局开关 `settings.SAGE_INTEGRATION_ENABLED`(默认 False)在 `urls.py` 守卫式挂载路由,**关闭时路由不存在**,返回 404。JWT 通过新建 `SageTokenObtainPairSerializer` 复用基类,加 `sage_user_id` / `sage_local_features` claim。通道 A 业务代理在 `proxy_views` 做字段裁剪,通道 B 任务模型 `SageTask` 由 Sage 自派,OmniDesk 仅留痕审计。

**Tech Stack:** Django 4.2 + DRF + djangorestframework-simplejwt + Python 3.10 + pytest + mypy strict。沿用既有 `pytest --ds=omni_desk_backend.settings.test` + `conftest.py` fixtures。

**Companion plan:** `sage/docs/superpowers/plans/2026-08-18-omnidesk-sage-integration-sage.md`(Sage 桌面端实施,跨仓引用)
**Cross-project contract:** `docs/superpowers/specs/2026-08-18-omnidesk-sage-integration-design.md`

---

## Global Constraints

源自 spec,所有 Task 必须遵守:

1. **默认关闭**:任何互通 API 在 `settings.SAGE_INTEGRATION_ENABLED=False`(默认)时**路由整体不挂载**,返回 404
2. **OmniDesk 不自建 AI 能力**:不修改 16 个业务 app 的现有视图;字段裁剪在 `sage_integration.proxy_views` 完成
3. **身份共享 ≠ 数据共享**:OmniDesk 业务数据仅"查",不"存";Sage 对话内容默认不同步
4. **JWT 含 sage_user_id claim**:`CustomTokenObtainPairSerializer` 不动,新建 `SageTokenObtainPairSerializer` 复用基类
5. **INSTALLED_APPS 写法**:必须写 `"sage_integration.apps.SageIntegrationConfig"`(全路径 app config)
6. **测试模式**:OmniDesk 统一用 `pytest --ds=omni_desk_backend.settings.test`,沿用 `conftest.py` fixtures
7. **mypy strict**:新增代码必须通过 mypy 严格类型检查
8. **测试覆盖率**:新增模块 ≥ 80%
9. **commit message**:遵循 conventional commits(`feat:` / `fix:` / `refactor:` / `test:` / `docs:` / `chore:`)
10. **feature 分支**:每个 Task 在独立 `feat/sage-*` 分支上,完成通过 CI 后合并到 main,不留脏分支
11. **降级完备**:任何通道 A 接口超时(5s)/不可达,Sage 端必须返回明确降级信息(本计划仅管 OmniDesk 后端,Sage 端降级由 Sage 端计划负责)

---

## File Structure

```
omni_desk_backend/
├── sage_integration/                          # 新增 app
│   ├── __init__.py
│   ├── apps.py                                # SageIntegrationConfig
│   ├── models.py                              # SageIntegrationFields, SageTask
│   ├── auth_serializers.py                    # SageTokenObtainPairSerializer
│   ├── auth_views.py                          # bind, whoami, enable-local-features
│   ├── proxy_views.py                         # schedule, personnel
│   ├── task_views.py                          # tasks CRUD, claim, result, pending
│   ├── serializers.py                         # 所有输入 / 输出序列化器
│   ├── permissions.py                         # IsSageIntegrationEnabled, IsSageAuthenticated
│   ├── throttles.py                           # SageBindThrottle / SageAuthThrottle /
│   │                                          # SageProxyThrottle / SageTaskThrottle
│   ├── urls.py                                # 路由汇总
│   ├── management/
│   │   ├── __init__.py
│   │   └── commands/
│   │       ├── __init__.py
│   │       └── cleanup_sage_tasks.py          # 过期任务清理命令
│   ├── migrations/
│   │   ├── __init__.py
│   │   ├── 0001_initial.py                    # 自动生成
│   │   └── 0002_sagetask.py                   # 自动生成
│   └── tests/
│       ├── __init__.py
│       ├── test_smoke.py                      # App 加载 + settings 关闭验证
│       ├── test_models.py                     # SageIntegrationFields 测试
│       ├── test_auth_serializers.py           # JWT claim 扩展测试
│       ├── test_auth_views.py                 # bind/whoami/enable-local-features 测试
│       ├── test_proxy.py                      # schedule/personnel 测试
│       ├── test_task_model.py                 # SageTask 模型测试
│       ├── test_tasks.py                      # 任务 API 测试
│       └── test_cleanup_command.py            # cleanup 命令测试
└── omni_desk_backend/
    ├── settings/
    │   ├── base.py                            # 修改:加 INSTALLED_APPS + SAGE_INTEGRATION_ENABLED
    │   │                                      + REST_FRAMEWORK throttle rates
    │   ├── test.py                            # 修改:加 SAGE_INTEGRATION_ENABLED=True
    │   └── local.py / development.py / production.py  # 默认 False
    └── urls.py                                # 修改:守卫式挂载路由

docs/
├── technical/
│   ├── README.md                              # 修改:加章节链接
│   └── 40-omnidesk-sage-integration.md        # 新增
└── user-manual/
    ├── README.md                              # 修改:加章节链接
    └── 40-sage-integration.md                 # 新增

deployment/docker/CHANGELOG.md                 # 修改:加条目
```

---

## 任务总览

| # | 任务 | 阶段 | 依赖 |
|---|---|---|---|
| T1 | 创建 sage_integration app 骨架 | Phase 1 | — |
| T2 | SageIntegrationFields 模型 + migration | Phase 1 | T1 |
| T3 | SageTokenObtainPairSerializer(JWT claim) | Phase 1 | T2 |
| T4 | 绑定 + whoami + enable-local-features API | Phase 1 | T3 |
| T5 | `/api/sage/proxy/schedule/` | Phase 2 | T4 |
| T6 | `/api/sage/proxy/personnel/` | Phase 2 | T5 |
| T7 | SageTask 模型 + migration | Phase 3 | T6 |
| T8 | 任务 API(create/detail/pending/claim/result) | Phase 3 | T7 |
| T9 | cleanup_sage_tasks 管理命令 | Phase 3 | T8 |
| T10 | 文档 + CHANGELOG | Phase 4 | T9 |

依赖链:`T1 → T2 → T3 → T4 → T5 → T6 → T7 → T8 → T9 → T10`。

---

# Phase 1: 后端基础

## Task 1: 创建 sage_integration app 骨架

**Files:**
- Create: `omni_desk_backend/sage_integration/__init__.py`
- Create: `omni_desk_backend/sage_integration/apps.py`
- Create: `omni_desk_backend/sage_integration/models.py`(空 stub)
- Create: `omni_desk_backend/sage_integration/urls.py`(空 stub)
- Create: `omni_desk_backend/sage_integration/tests/__init__.py`
- Create: `omni_desk_backend/sage_integration/tests/test_smoke.py`
- Modify: `omni_desk_backend/omni_desk_backend/settings/base.py:63-106`(INSTALLED_APPS)
- Modify: `omni_desk_backend/omni_desk_backend/settings/base.py:251-254`(REST_FRAMEWORK throttle rates)
- Modify: `omni_desk_backend/omni_desk_backend/settings/base.py`(末尾追加 SAGE_INTEGRATION_ENABLED)
- Modify: `omni_desk_backend/omni_desk_backend/settings/test.py`(启用开关)
- Modify: `omni_desk_backend/omni_desk_backend/urls.py`(守卫式挂载路由)

**Step 1.1: 写冒烟测试**

`omni_desk_backend/sage_integration/tests/test_smoke.py`:

```python
"""冒烟测试:验证 sage_integration app 已被 Django 加载并可通过 settings 关闭。"""


def test_app_is_loaded():
    from django.apps.apps import get_app_config

    config = get_app_config("sage_integration")
    assert config.name == "sage_integration"
    assert config.verbose_name == "Sage 桌面端集成"


def test_default_disabled_in_base_settings(settings):
    """base.py 默认 SAGE_INTEGRATION_ENABLED=False(必须显式开启)。"""
    assert hasattr(settings, "SAGE_INTEGRATION_ENABLED")
    assert settings.SAGE_INTEGRATION_ENABLED is False


def test_urls_not_mounted_when_disabled(client):
    """默认未启用时,请求 /api/sage/auth/whoami/ 应返回 404。"""
    from django.test import override_settings

    with override_settings(SAGE_INTEGRATION_ENABLED=False):
        response = client.get("/api/sage/auth/whoami/")
    assert response.status_code == 404
```

> 用 `override_settings` 显式覆盖(因 test settings 启用开关),避免与全局开关状态耦合。

**Step 1.2: 运行测试,确认失败**

Run:
```bash
cd /home/fz/project/OmniDesk
/home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest omni_desk_backend/sage_integration/tests/test_smoke.py -v 2>&1 | tail -20
```

Expected:FAIL,原因 `sage_integration` app 不存在。

**Step 1.3: 创建 app 骨架**

`omni_desk_backend/sage_integration/__init__.py`:
```python
"""OmniDesk ↔ Sage 桌面端互通集成 app。

详见 docs/superpowers/specs/2026-08-18-omnidesk-sage-integration-design.md。
"""
```

`omni_desk_backend/sage_integration/apps.py`:
```python
"""sage_integration Django app config。"""

from django.apps import AppConfig


class SageIntegrationConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "sage_integration"
    verbose_name = "Sage 桌面端集成"
```

`omni_desk_backend/sage_integration/models.py`:
```python
"""Models placeholder;后续 Task 2 / Task 7 填充。"""
```

`omni_desk_backend/sage_integration/urls.py`:
```python
"""URL routes placeholder;后续 Task 4 / 5 / 6 / 8 填充。"""

from django.urls import path

app_name = "sage_integration"

urlpatterns: list = []
```

`omni_desk_backend/sage_integration/tests/__init__.py`:
```python
```

**Step 1.4: 修改 settings**

`omni_desk_backend/omni_desk_backend/settings/base.py`,在 INSTALLED_APPS 列表末尾(`file_processing.apps.FileProcessingConfig` 之后,line 106)追加:

```python
    "file_processing.apps.FileProcessingConfig",
    "sage_integration.apps.SageIntegrationConfig",  # OmniDesk ↔ Sage 桌面端互通(默认关闭)
]
```

`omni_desk_backend/omni_desk_backend/settings/base.py`,在 `REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]`(line 251-254)中添加 sage_* 速率:

```python
    "DEFAULT_THROTTLE_RATES": {
        "anon": "60/min",
        "client_error": "10/min",
        # OmniDesk ↔ Sage 桌面端互通限流
        "sage_bind": "5/hour",
        "sage_auth": "30/min",
        "sage_proxy": "60/min",
        "sage_task": "20/hour",
    },
```

`omni_desk_backend/omni_desk_backend/settings/base.py`,在文件末尾追加:

```python
# OmniDesk ↔ Sage 桌面端互通总开关。
# 默认 False(全功能关闭);启用后 sage_integration 路由才生效。
# 关闭状态下所有 /api/sage/* 请求返回 404,业务侧零影响。
SAGE_INTEGRATION_ENABLED = False
```

`omni_desk_backend/omni_desk_backend/settings/test.py`,在文件末尾追加:

```python
from .base import *  # noqa: F401,F403

# 测试环境默认启用 sage_integration,便于测试路由可达性
SAGE_INTEGRATION_ENABLED = True
```

> 确认 `test.py` 已有 `from .base import *`(应有,沿用现有继承模式)。若没有,把它放在文件最顶。

**Step 1.5: 修改根 URL 守卫式挂载**

`omni_desk_backend/omni_desk_backend/urls.py`,找到 `urlpatterns` 列表(在文件后部),将挂载包在 `if settings.SAGE_INTEGRATION_ENABLED:` 守卫中。

如果文件顶部 imports 已有 `from django.conf import settings` 和 `from django.urls import include`,直接修改 `urlpatterns`;否则先补 imports。

`urlpatterns` 末尾追加(替换最后的 `]` 前一行):

```python
    # OmniDesk ↔ Sage 桌面端互通(默认关闭)
    # 详见 docs/superpowers/specs/2026-08-18-omnidesk-sage-integration-design.md
    *(
        [path("api/sage/", include("sage_integration.urls"))]
        if settings.SAGE_INTEGRATION_ENABLED
        else []
    ),
]
```

> **为什么用条件 spread**:`test_smoke.py` 要求关闭时路由完全消失(Django 返回 404)。直接 `include` 在关闭时仍可达,只是 Permission 403,不符合"零影响"设计目标。条件 spread 让关闭时路由不存在。

**Step 1.6: 运行测试,确认 PASS**

Run:
```bash
cd /home/fz/project/OmniDesk
/home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest omni_desk_backend/sage_integration/tests/test_smoke.py -v 2>&1 | tail -15
```

Expected:3 passed。

**Step 1.7: Commit**

```bash
cd /home/fz/project/OmniDesk
git checkout -b feat/sage-integration-scaffold
git add omni_desk_backend/sage_integration/ omni_desk_backend/omni_desk_backend/settings/ omni_desk_backend/omni_desk_backend/urls.py
git commit -m "feat(sage-integration): 新增 app 骨架与全局开关

- 创建 sage_integration Django app(空 stub)
- base.py 加 SAGE_INTEGRATION_ENABLED 默认 False(全功能关闭)
- test.py 启用开关以便测试
- base.py REST_FRAMEWORK 加 sage_*/hour 限流配置
- urls.py 守卫式挂载路由(关闭时路由不存在)

Refs: docs/superpowers/specs/2026-08-18-omnidesk-sage-integration-design.md"
```

---

## Task 2: SageIntegrationFields 模型

**Files:**
- Modify: `omni_desk_backend/sage_integration/models.py`
- Create: `omni_desk_backend/sage_integration/migrations/__init__.py`
- Create: `omni_desk_backend/sage_integration/migrations/0001_initial.py`(由 makemigrations 生成)
- Create: `omni_desk_backend/sage_integration/tests/test_models.py`

**Interfaces:**
- Produces: `sage_integration.models.SageIntegrationFields`(OneToOne 关联 CustomUser)
- 字段名:`sage_user_id`(UUIDField)、`sage_last_sync_at`(DateTimeField)、`sage_local_features_enabled`(BooleanField)、`sage_omnidesk_url`(URLField)、`created_at`、`updated_at`

**Step 2.1: 写失败测试**

`omni_desk_backend/sage_integration/tests/test_models.py`:

```python
"""SageIntegrationFields 模型测试。"""

import uuid

from sage_integration.models import SageIntegrationFields
from users.models import CustomUser


def test_sage_integration_fields_one_to_one_with_user(db):
    """OneToOne 关联 CustomUser,user 为 PK。"""
    user = CustomUser.objects.create_user(username="user1", password="pw12345!")
    integration = SageIntegrationFields.objects.create(user=user)
    assert integration.user == user
    assert integration._meta.pk.name == "user"


def test_sage_user_id_auto_generated_and_unique(db):
    """sage_user_id 自动生成 UUID 且唯一。"""
    user1 = CustomUser.objects.create_user(username="user2", password="pw12345!")
    user2 = CustomUser.objects.create_user(username="user3", password="pw12345!")
    i1 = SageIntegrationFields.objects.create(user=user1)
    i2 = SageIntegrationFields.objects.create(user=user2)
    assert i1.sage_user_id != i2.sage_user_id
    uuid.UUID(str(i1.sage_user_id))
    uuid.UUID(str(i2.sage_user_id))


def test_default_field_values(db):
    """默认 sage_local_features_enabled=False,sage_last_sync_at/sage_omnidesk_url 为空。"""
    user = CustomUser.objects.create_user(username="user4", password="pw12345!")
    integration = SageIntegrationFields.objects.create(user=user)
    assert integration.sage_local_features_enabled is False
    assert integration.sage_last_sync_at is None
    assert integration.sage_omnidesk_url in (None, "")


def test_user_cascade_delete(db):
    """删除 CustomUser 时,SageIntegrationFields 也被级联删除。"""
    user = CustomUser.objects.create_user(username="user5", password="pw12345!")
    SageIntegrationFields.objects.create(user=user)
    user.delete()
    assert SageIntegrationFields.objects.count() == 0
```

**Step 2.2: 运行测试,确认失败**

Run:
```bash
cd /home/fz/project/OmniDesk
/home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest omni_desk_backend/sage_integration/tests/test_models.py -v 2>&1 | tail -15
```

Expected:FAIL,模型类未定义。

**Step 2.3: 实现模型**

`omni_desk_backend/sage_integration/models.py`:

```python
"""Sage 集成扩展模型。

与 CustomUser 一对一关联,记录 Sage 桌面端集成所需的扩展字段。
不复用旧版 SageExtension,避免污染 CustomUser 主表。

字段语义详见 docs/superpowers/specs/2026-08-18-omnidesk-sage-integration-design.md §6.1.1。
"""

import uuid

from django.conf import settings
from django.db import models


class SageIntegrationFields(models.Model):
    """OmniDesk CustomUser 的 Sage 集成扩展字段。

    Why: Sage 不引入独立账号体系,身份统一来自 OmniDesk CustomUser。
    How: OneToOne 扩展模型而非直接加字段,便于整体回滚。
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sage_integration",
        primary_key=True,
    )
    sage_user_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        help_text="Sage 桌面端生成的稳定 UUID,标识 OmniDesk 用户",
    )
    sage_last_sync_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="最后一次通道 A/B 调用成功的时间戳",
    )
    sage_local_features_enabled = models.BooleanField(
        default=False,
        help_text="用户主动开启'接收 OmniDesk 任务'后的通道 B 开关",
    )
    sage_omnidesk_url = models.URLField(
        null=True,
        blank=True,
        help_text="Sage 上报的 OmniDesk 服务地址(冗余校验,防中间人)",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Sage 集成字段"
        verbose_name_plural = "Sage 集成字段"

    def __str__(self) -> str:
        return f"SageIntegration<user={self.user.username}>"
```

`omni_desk_backend/sage_integration/migrations/__init__.py`:
```python
```

**Step 2.4: 生成 migration**

Run:
```bash
cd /home/fz/project/OmniDesk
/home/fz/anaconda3/envs/OmniDesk/bin/python manage.py makemigrations sage_integration 2>&1 | tail -10
```

Expected:创建 `0001_initial.py`,包含 `SageIntegrationFields` 表。

**Step 2.5: 运行测试,确认 PASS**

Run:
```bash
cd /home/fz/project/OmniDesk
/home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest omni_desk_backend/sage_integration/tests/test_models.py -v 2>&1 | tail -15
```

Expected:4 passed。

**Step 2.6: Commit**

```bash
cd /home/fz/project/OmniDesk
git add omni_desk_backend/sage_integration/
git commit -m "feat(sage-integration): SageIntegrationFields 模型与初始 migration

- OneToOne 扩展 CustomUser,不污染主表
- 字段: sage_user_id(UUID)/ sage_last_sync_at/ sage_local_features_enabled/ sage_omnidesk_url
- 单元测试覆盖(4 个用例)"
```

---

## Task 3: SageTokenObtainPairSerializer(JWT claim 扩展)

**Files:**
- Create: `omni_desk_backend/sage_integration/auth_serializers.py`
- Create: `omni_desk_backend/sage_integration/tests/test_auth_serializers.py`

**Interfaces:**
- Produces: `sage_integration.auth_serializers.SageTokenObtainPairSerializer`
- 不修改 `users/auth_serializers.py` 现有 `CustomTokenObtainPairSerializer`
- Token payload claim 名:`sage_user_id`(UUID 字符串)、`sage_local_features`(bool)

**Step 3.1: 写失败测试**

`omni_desk_backend/sage_integration/tests/test_auth_serializers.py`:

```python
"""SageTokenObtainPairSerializer 测试。"""

from sage_integration.auth_serializers import SageTokenObtainPairSerializer
from sage_integration.models import SageIntegrationFields
from users.models import CustomUser


def test_token_contains_sage_user_id_claim(db):
    """绑定 Sage 后,JWT 中应包含 sage_user_id claim(字符串形式)。"""
    user = CustomUser.objects.create_user(username="user1", password="pw12345!")
    integration = SageIntegrationFields.objects.create(user=user)
    integration.sage_local_features_enabled = True
    integration.save()

    token = SageTokenObtainPairSerializer.get_token(user)

    assert "sage_user_id" in token
    assert token["sage_user_id"] == str(integration.sage_user_id)
    assert "sage_local_features" in token
    assert token["sage_local_features"] is True


def test_token_claim_reflects_disabled_state(db):
    """sage_local_features_enabled=False 时,claim 也为 False。"""
    user = CustomUser.objects.create_user(username="user2", password="pw12345!")
    SageIntegrationFields.objects.create(user=user)  # 默认 False

    token = SageTokenObtainPairSerializer.get_token(user)
    assert token["sage_local_features"] is False


def test_user_without_integration_still_gets_token(db):
    """未创建 SageIntegrationFields 的用户也能拿到 token,只是 claim 为 None/False。"""
    user = CustomUser.objects.create_user(username="user3", password="pw12345!")
    token = SageTokenObtainPairSerializer.get_token(user)
    assert "sage_user_id" in token
    assert token["sage_user_id"] is None
    assert token["sage_local_features"] is False
```

**Step 3.2: 运行测试,确认失败**

Run:
```bash
cd /home/fz/project/OmniDesk
/home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest omni_desk_backend/sage_integration/tests/test_auth_serializers.py -v 2>&1 | tail -15
```

Expected:FAIL,`SageTokenObtainPairSerializer` 不存在。

**Step 3.3: 实现 serializer**

`omni_desk_backend/sage_integration/auth_serializers.py`:

```python
"""Sage 集成专用的 JWT 序列化器。

继承 simplejwt 的 TokenObtainPairSerializer,在 token 中注入 Sage 集成 claim:
- sage_user_id: SageIntegrationFields.sage_user_id(UUID 转 str)
- sage_local_features: 是否开启通道 B

不修改 users/CustomTokenObtainPairSerializer,避免影响 OmniDesk 现有登录流程。
"""

from __future__ import annotations

from typing import Any

from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import SageIntegrationFields


class SageTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Sage 集成专用 JWT 序列化器。"""

    @classmethod
    def get_token(cls, user: Any) -> Any:
        token = super().get_token(user)

        # 默认值
        sage_user_id: str | None = None
        sage_local_features = False

        # 尝试获取 SageIntegrationFields
        try:
            integration = SageIntegrationFields.objects.get(user=user)
            sage_user_id = str(integration.sage_user_id)
            sage_local_features = integration.sage_local_features_enabled
        except SageIntegrationFields.DoesNotExist:
            # 用户尚未绑定 Sage,claim 为 None/False,token 仍可正常颁发
            pass

        token["sage_user_id"] = sage_user_id
        token["sage_local_features"] = sage_local_features
        return token
```

**Step 3.4: 运行测试,确认 PASS**

Run:
```bash
cd /home/fz/project/OmniDesk
/home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest omni_desk_backend/sage_integration/tests/test_auth_serializers.py -v 2>&1 | tail -15
```

Expected:3 passed。

**Step 3.5: Commit**

```bash
cd /home/fz/project/OmniDesk
git add omni_desk_backend/sage_integration/auth_serializers.py omni_desk_backend/sage_integration/tests/test_auth_serializers.py
git commit -m "feat(sage-integration): SageTokenObtainPairSerializer 含 sage_user_id claim

- 复用 simplejwt 基类,不修改 users/CustomTokenObtainPairSerializer
- token claim: sage_user_id (str UUID) / sage_local_features (bool)
- 未绑定 Sage 的用户也能拿到 token,claim 为 None/False
- 单元测试 3 用例覆盖"
```

---

## Task 4: 绑定 + whoami + enable-local-features 三个 auth API

**Files:**
- Create: `omni_desk_backend/sage_integration/permissions.py`
- Create: `omni_desk_backend/sage_integration/throttles.py`
- Create: `omni_desk_backend/sage_integration/serializers.py`
- Create: `omni_desk_backend/sage_integration/auth_views.py`
- Modify: `omni_desk_backend/sage_integration/urls.py`(挂载三个 endpoint)
- Create: `omni_desk_backend/sage_integration/tests/test_auth_views.py`

**Interfaces:**
- `POST /api/sage/auth/bind/`(Body:`{username, password, sage_user_id, omnidesk_url}` → `{access, refresh, user_profile}`)
- `GET /api/sage/auth/whoami/`(Header:`Authorization` → `{username, sage_user_id, sage_local_features, sage_last_sync_at}`)
- `POST /api/sage/auth/enable-local-features/`(Body:`{enable: bool}` → `{ok, sage_local_features}`)

**Step 4.1: 写失败测试**

`omni_desk_backend/sage_integration/tests/test_auth_views.py`:

```python
"""sage_integration auth views 测试。"""

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from sage_integration.models import SageIntegrationFields
from users.models import CustomUser


@pytest.fixture
def user_with_password(db):
    return CustomUser.objects.create_user(username="user1", password="pw12345!")


@pytest.fixture
def api_client():
    return APIClient()


def test_bind_creates_integration_and_returns_jwt(api_client, user_with_password):
    """绑定成功:创建 SageIntegrationFields,返回 JWT。"""
    payload = {
        "username": "user1",
        "password": "pw12345!",
        "sage_user_id": "11111111-1111-1111-1111-111111111111",
        "omnidesk_url": "http://omnidesk.local:8000",
    }
    response = api_client.post(reverse("sage_integration:auth-bind"), payload, format="json")

    assert response.status_code == 200
    data = response.json()
    assert "access" in data
    assert "refresh" in data
    assert data["user_profile"]["username"] == "user1"

    integration = SageIntegrationFields.objects.get(user=user_with_password)
    assert str(integration.sage_user_id) == payload["sage_user_id"]
    assert integration.sage_omnidesk_url == payload["omnidesk_url"]


def test_bind_rejects_invalid_credentials(api_client, user_with_password):
    """错误密码:返回 400。"""
    payload = {
        "username": "user1",
        "password": "wrong",
        "sage_user_id": "11111111-1111-1111-1111-111111111111",
        "omnidesk_url": "http://omnidesk.local:8000",
    }
    response = api_client.post(reverse("sage_integration:auth-bind"), payload, format="json")
    assert response.status_code == 400


def test_bind_rejects_duplicate_sage_user_id(api_client, user_with_password, db):
    """重复的 sage_user_id 拒绝。"""
    SageIntegrationFields.objects.create(
        user=user_with_password,
        sage_user_id="22222222-2222-2222-2222-222222222222",
    )
    other = CustomUser.objects.create_user(username="user2", password="pw12345!")
    payload = {
        "username": "user2",
        "password": "pw12345!",
        "sage_user_id": "22222222-2222-2222-2222-222222222222",
        "omnidesk_url": "http://omnidesk.local:8000",
    }
    response = api_client.post(reverse("sage_integration:auth-bind"), payload, format="json")
    assert response.status_code == 400


def test_whoami_returns_profile_when_authenticated(api_client, user_with_password):
    """whoami: 已登录返回档案。"""
    integration = SageIntegrationFields.objects.create(user=user_with_password)
    api_client.force_authenticate(user=user_with_password)
    response = api_client.get(reverse("sage_integration:auth-whoami"))
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "user1"
    assert data["sage_user_id"] == str(integration.sage_user_id)
    assert data["sage_local_features"] is False
    assert "sage_last_sync_at" in data


def test_whoami_requires_authentication(api_client):
    """whoami 未登录:401。"""
    response = api_client.get(reverse("sage_integration:auth-whoami"))
    assert response.status_code == 401


def test_enable_local_features_toggles_flag(api_client, user_with_password):
    """enable-local-features 切换 sage_local_features_enabled。"""
    SageIntegrationFields.objects.create(user=user_with_password)
    api_client.force_authenticate(user=user_with_password)

    response = api_client.post(
        reverse("sage_integration:auth-enable-local-features"),
        {"enable": True},
        format="json",
    )
    assert response.status_code == 200
    assert response.json()["sage_local_features"] is True

    user_with_password.refresh_from_db()
    assert user_with_password.sage_integration.sage_local_features_enabled is True
```

**Step 4.2: 运行测试,确认失败**

Run:
```bash
cd /home/fz/project/OmniDesk
/home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest omni_desk_backend/sage_integration/tests/test_auth_views.py -v 2>&1 | tail -15
```

Expected:FAIL,路由未定义。

**Step 4.3: 实现 permissions**

`omni_desk_backend/sage_integration/permissions.py`:

```python
"""sage_integration 权限类。

IsSageIntegrationEnabled:全局守卫,settings.SAGE_INTEGRATION_ENABLED=False 时一律 False。
由于 Task 1 Step 1.5 已用条件 spread 让路由在关闭时消失,此守卫在测试中是冗余防御;
在生产中若有人手动 include 路由,此守卫仍是最后一道防线。
"""

from __future__ import annotations

from typing import Any

from django.conf import settings
from rest_framework.permissions import IsAuthenticated


class IsSageIntegrationEnabled:
    """全局开关:settings.SAGE_INTEGRATION_ENABLED=False 时一律拒绝。"""

    def has_permission(self, request: Any, view: Any) -> bool:
        return bool(getattr(settings, "SAGE_INTEGRATION_ENABLED", False))


class IsSageAuthenticated(IsAuthenticated):
    """需要 JWT 认证(token 由 SageTokenObtainPairSerializer 颁发)。

    继承 IsAuthenticated(必须有有效 JWT)。
    """
```

**Step 4.4: 实现 throttles**

`omni_desk_backend/sage_integration/throttles.py`:

```python
"""sage_integration 限流。

scope 名称与 base.py REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] 中配置的
sage_bind / sage_auth / sage_proxy / sage_task 对应。
"""

from __future__ import annotations

from rest_framework.throttling import UserRateThrottle


class SageBindThrottle(UserRateThrottle):
    """绑定端点限流:每用户每小时最多 5 次。"""

    scope = "sage_bind"


class SageAuthThrottle(UserRateThrottle):
    """whoami / enable-local-features 限流:每用户每分钟 30 次。"""

    scope = "sage_auth"


class SageProxyThrottle(UserRateThrottle):
    """通道 A 业务代理端点限流:每用户每分钟 60 次。"""

    scope = "sage_proxy"


class SageTaskThrottle(UserRateThrottle):
    """通道 B 任务端点限流:每用户每小时最多 20 个任务。"""

    scope = "sage_task"
```

**Step 4.5: 实现 serializers**

`omni_desk_backend/sage_integration/serializers.py`:

```python
"""sage_integration 序列化器集合。"""

from __future__ import annotations

from typing import Any

from django.contrib.auth import authenticate
from rest_framework import serializers

from sage_integration.models import SageIntegrationFields
from users.models import CustomUser


class SageBindSerializer(serializers.Serializer):
    """Sage 账号绑定请求序列化器。"""

    username = serializers.CharField()
    password = serializers.CharField(write_only=True, style={"input_type": "password"})
    sage_user_id = serializers.UUIDField()
    omnidesk_url = serializers.URLField()

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        user = authenticate(
            request=self.context.get("request"),
            username=attrs["username"],
            password=attrs["password"],
        )
        if user is None or not user.is_active:
            raise serializers.ValidationError({"password": "用户名或密码不正确"})

        # 校验 sage_user_id 唯一性(防止两个 OmniDesk 用户绑同一个 Sage 标识)
        if SageIntegrationFields.objects.filter(sage_user_id=attrs["sage_user_id"]).exists():
            raise serializers.ValidationError(
                {"sage_user_id": "该 Sage 用户标识已被绑定,请联系管理员"}
            )

        attrs["user"] = user
        return attrs

    def create(self, validated_data: dict[str, Any]) -> SageIntegrationFields:
        user: CustomUser = validated_data["user"]
        integration, _ = SageIntegrationFields.objects.update_or_create(
            user=user,
            defaults={
                "sage_user_id": validated_data["sage_user_id"],
                "sage_omnidesk_url": validated_data["omnidesk_url"],
            },
        )
        return integration


class SageWhoamiSerializer(serializers.Serializer):
    """whoami 响应序列化器。"""

    username = serializers.CharField()
    sage_user_id = serializers.SerializerMethodField()
    sage_local_features = serializers.SerializerMethodField()
    sage_last_sync_at = serializers.SerializerMethodField()

    def get_sage_user_id(self, obj: CustomUser) -> str | None:
        integration = getattr(obj, "sage_integration", None)
        return str(integration.sage_user_id) if integration else None

    def get_sage_local_features(self, obj: CustomUser) -> bool:
        integration = getattr(obj, "sage_integration", None)
        return bool(integration.sage_local_features_enabled) if integration else False

    def get_sage_last_sync_at(self, obj: CustomUser) -> str | None:
        integration = getattr(obj, "sage_integration", None)
        return (
            integration.sage_last_sync_at.isoformat()
            if (integration and integration.sage_last_sync_at)
            else None
        )
```

> `update_or_create` 用于支持用户在新电脑重装 Sage 后复用同一 `sage_user_id` 重新绑定。

**Step 4.6: 实现 views**

`omni_desk_backend/sage_integration/auth_views.py`:

```python
"""sage_integration auth views。"""

from __future__ import annotations

import logging
from typing import Any

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from sage_integration.auth_serializers import SageTokenObtainPairSerializer
from sage_integration.models import SageIntegrationFields
from sage_integration.permissions import IsSageAuthenticated, IsSageIntegrationEnabled
from sage_integration.serializers import SageBindSerializer, SageWhoamiSerializer
from sage_integration.throttles import SageAuthThrottle, SageBindThrottle

logger = logging.getLogger(__name__)


class SageBindView(APIView):
    """POST /api/sage/auth/bind/

    Sage 桌面端首次绑定:用户名密码 + sage_user_id + omnidesk_url。
    返回 JWT(Sage 端用此 token 调后续通道 A/B API)。
    """

    permission_classes = [IsSageIntegrationEnabled]
    authentication_classes: list = []  # bind 端点本身允许未认证
    throttle_classes = [SageBindThrottle]

    def post(self, request: Any) -> Response:
        serializer = SageBindSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        integration = serializer.save()

        # 用 SageTokenObtainPairSerializer 颁发 token(自动注入 claim)
        token = SageTokenObtainPairSerializer.get_token(integration.user)

        return Response(
            {
                "access": str(token.access_token),
                "refresh": str(token),
                "user_profile": {
                    "username": integration.user.username,
                    "sage_user_id": str(integration.sage_user_id),
                    "sage_local_features": integration.sage_local_features_enabled,
                },
            },
            status=status.HTTP_200_OK,
        )


class SageWhoamiView(APIView):
    """GET /api/sage/auth/whoami/

    Sage 端启动后调用,验证 token 有效 + 返回当前用户档案。
    """

    permission_classes = [IsSageIntegrationEnabled, IsSageAuthenticated]
    throttle_classes = [SageAuthThrottle]

    def get(self, request: Any) -> Response:
        serializer = SageWhoamiSerializer(request.user)
        return Response(serializer.data)


class SageEnableLocalFeaturesView(APIView):
    """POST /api/sage/auth/enable-local-features/

    用户主动开启/关闭"接收 OmniDesk 任务"通道 B 开关。
    """

    permission_classes = [IsSageIntegrationEnabled, IsSageAuthenticated]
    throttle_classes = [SageAuthThrottle]

    def post(self, request: Any) -> Response:
        enable = bool(request.data.get("enable", False))
        try:
            integration = request.user.sage_integration
        except SageIntegrationFields.DoesNotExist:
            return Response(
                {"detail": "尚未绑定 Sage,请先调用 /api/sage/auth/bind/"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        integration.sage_local_features_enabled = enable
        integration.save(update_fields=["sage_local_features_enabled", "updated_at"])

        return Response({"ok": True, "sage_local_features": enable})
```

**Step 4.7: 挂载路由**

`omni_desk_backend/sage_integration/urls.py`(覆盖原 placeholder):

```python
"""sage_integration URL 路由。

仅 Phase 1 路由(Task 4);Task 5/6/8 后续追加。
"""

from __future__ import annotations

from django.urls import path

from sage_integration.auth_views import (
    SageBindView,
    SageEnableLocalFeaturesView,
    SageWhoamiView,
)

app_name = "sage_integration"

urlpatterns = [
    path("auth/bind/", SageBindView.as_view(), name="auth-bind"),
    path("auth/whoami/", SageWhoamiView.as_view(), name="auth-whoami"),
    path(
        "auth/enable-local-features/",
        SageEnableLocalFeaturesView.as_view(),
        name="auth-enable-local-features",
    ),
]
```

**Step 4.8: 运行测试,确认 PASS**

Run:
```bash
cd /home/fz/project/OmniDesk
/home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest omni_desk_backend/sage_integration/tests/test_auth_views.py -v 2>&1 | tail -20
```

Expected:6 passed。

若 404 出现,先确认 `omni_desk_backend/omni_desk_backend/urls.py` 已 include `sage_integration.urls`,并 `SAGE_INTEGRATION_ENABLED=True`(test settings 已设)。

**Step 4.9: mypy 检查**

Run:
```bash
cd /home/fz/project/OmniDesk
/home/fz/anaconda3/envs/OmniDesk/bin/python -m mypy omni_desk_backend/sage_integration/ 2>&1 | tail -15
```

Expected:无错误或仅有"未使用导入"提示(可加 `# noqa: F401` 或调整)。

**Step 4.10: Commit**

```bash
cd /home/fz/project/OmniDesk
git add omni_desk_backend/sage_integration/
git commit -m "feat(sage-integration): 账号绑定 + whoami + enable-local-features API

- POST /api/sage/auth/bind/ 用户名密码 + sage_user_id + omnidesk_url → JWT
- GET /api/sage/auth/whoami/ 返回当前用户档案
- POST /api/sage/auth/enable-local-features/ 切换通道 B 开关
- 限流: bind 5/h, auth 30/min
- 全局开关守卫(双重防御:路由守卫 + 权限类)
- 单元测试 6 用例覆盖"
```

---

# Phase 2: 通道 A 业务代理

## Task 5: 实现 `/api/sage/proxy/schedule/`

**Files:**
- Create: `omni_desk_backend/sage_integration/proxy_views.py`
- Modify: `omni_desk_backend/sage_integration/urls.py`(挂载)
- Create: `omni_desk_backend/sage_integration/tests/test_proxy.py`

**Interfaces:**
- Endpoint: `POST /api/sage/proxy/schedule/`(Body:`{date_from, date_to}` → `{schedule: [{date, role, location, leader}]}`)

> **实施前核对**:第一步去 `events/models.py` 实际核对 `Schedule` 模型字段名(`duty_date` / `duty_person` / `duty_leader` / `location` / `notes`),如有差异,测试与 view 同步调整。

**Step 5.1: 写失败测试**

`omni_desk_backend/sage_integration/tests/test_proxy.py`:

```python
"""通道 A 业务代理测试。"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from events.models import Schedule
from personnel.models import Personnel
from sage_integration.models import SageIntegrationFields
from users.models import CustomUser


@pytest.fixture
def personnel(db):
    return Personnel.objects.create(name="测试人员", employee_id="E001")


@pytest.fixture
def alice(db, personnel):
    return CustomUser.objects.create_user(
        username="user1",
        password="pw12345!",
        personnel=personnel,
    )


@pytest.fixture
def authed_client(alice):
    client = APIClient()
    client.force_authenticate(user=alice)
    return client


def test_schedule_proxy_returns_only_requesting_user_schedule(
    authed_client, alice, personnel
):
    """schedule 代理只返回当前用户相关排班,不返回他人。"""
    other_personnel = Personnel.objects.create(name="他人", employee_id="E002")
    CustomUser.objects.create_user(
        username="user2", password="pw12345!", personnel=other_personnel
    )
    Schedule.objects.create(
        duty_date=date.today() + timedelta(days=1),
        duty_person=personnel,
        duty_leader=personnel,
        location="A 区",
    )
    Schedule.objects.create(
        duty_date=date.today() + timedelta(days=1),
        duty_person=other_personnel,
        duty_leader=other_personnel,
        location="B 区",
    )
    SageIntegrationFields.objects.create(user=alice)

    response = authed_client.post(
        reverse("sage_integration:proxy-schedule"),
        {
            "date_from": date.today().isoformat(),
            "date_to": (date.today() + timedelta(days=7)).isoformat(),
        },
        format="json",
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["schedule"]) == 1
    assert data["schedule"][0]["location"] == "A 区"


def test_schedule_proxy_fields_are_trimmed(authed_client, alice, personnel):
    """schedule 返回字段裁剪:不含内部备注/创建人等敏感字段。"""
    Schedule.objects.create(
        duty_date=date.today() + timedelta(days=1),
        duty_person=personnel,
        duty_leader=personnel,
        location="A 区",
        notes="内部敏感备注",
    )
    SageIntegrationFields.objects.create(user=alice)

    response = authed_client.post(
        reverse("sage_integration:proxy-schedule"),
        {
            "date_from": date.today().isoformat(),
            "date_to": (date.today() + timedelta(days=7)).isoformat(),
        },
        format="json",
    )
    assert response.status_code == 200
    item = response.json()["schedule"][0]
    assert "date" in item
    assert "location" in item
    assert "notes" not in item
    assert "internal_id" not in item


def test_schedule_proxy_updates_last_sync_at(authed_client, alice, personnel):
    """成功调用后 sage_last_sync_at 更新。"""
    Schedule.objects.create(
        duty_date=date.today() + timedelta(days=1),
        duty_person=personnel,
        duty_leader=personnel,
        location="A 区",
    )
    integration = SageIntegrationFields.objects.create(user=alice)
    assert integration.sage_last_sync_at is None

    authed_client.post(
        reverse("sage_integration:proxy-schedule"),
        {
            "date_from": date.today().isoformat(),
            "date_to": (date.today() + timedelta(days=7)).isoformat(),
        },
        format="json",
    )

    integration.refresh_from_db()
    assert integration.sage_last_sync_at is not None


def test_schedule_proxy_rejects_when_sage_integration_disabled(alice, personnel):
    """全局开关关闭时 403。"""
    Schedule.objects.create(
        duty_date=date.today(),
        duty_person=personnel,
        duty_leader=personnel,
        location="A 区",
    )
    SageIntegrationFields.objects.create(user=alice)

    client = APIClient()
    client.force_authenticate(user=alice)
    with override_settings(SAGE_INTEGRATION_ENABLED=False):
        response = client.post(
            reverse("sage_integration:proxy-schedule"),
            {"date_from": date.today().isoformat(), "date_to": date.today().isoformat()},
            format="json",
        )
    assert response.status_code == 403
```

**Step 5.2: 运行测试,确认失败**

Run:
```bash
cd /home/fz/project/OmniDesk
/home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest omni_desk_backend/sage_integration/tests/test_proxy.py::test_schedule_proxy_returns_only_requesting_user_schedule -v 2>&1 | tail -15
```

Expected:FAIL,路由未定义。

**Step 5.3: 实现 schedule 代理 view**

`omni_desk_backend/sage_integration/proxy_views.py`:

```python
"""通道 A 业务代理 views。

从 OmniDesk 业务 app 的 view 中安全地暴露数据给 Sage 桌面端。
字段裁剪在本层完成,不修改原业务 view。
"""

from __future__ import annotations

from datetime import date
from typing import Any

from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from events.models import Schedule
from sage_integration.models import SageIntegrationFields
from sage_integration.permissions import IsSageAuthenticated, IsSageIntegrationEnabled
from sage_integration.throttles import SageProxyThrottle


class ScheduleQuerySerializer(serializers.Serializer):
    """schedule 代理入参。"""

    date_from = serializers.DateField()
    date_to = serializers.DateField()

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if attrs["date_from"] > attrs["date_to"]:
            raise serializers.ValidationError({"date_to": "date_to 不能早于 date_from"})
        if (attrs["date_to"] - attrs["date_from"]).days > 90:
            raise serializers.ValidationError({"date_to": "查询范围不能超过 90 天"})
        return attrs


class SageScheduleProxyView(APIView):
    """POST /api/sage/proxy/schedule/

    返回当前用户(及其 personnel)未来 N 天的排班。
    字段裁剪:只暴露 {date, role, location, leader},不返回 notes / created_by 等敏感字段。
    """

    permission_classes = [IsSageIntegrationEnabled, IsSageAuthenticated]
    throttle_classes = [SageProxyThrottle]

    def post(self, request: Any) -> Response:
        serializer = ScheduleQuerySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        date_from: date = serializer.validated_data["date_from"]
        date_to: date = serializer.validated_data["date_to"]

        user = request.user
        personnel = getattr(user, "personnel", None)
        if personnel is None:
            return Response({"schedule": []})

        schedules = (
            Schedule.objects.filter(
                duty_person=personnel,
                duty_date__gte=date_from,
                duty_date__lte=date_to,
            )
            .order_by("duty_date")
            .only("duty_date", "location", "duty_leader__name")
        )

        items: list[dict[str, Any]] = [
            {
                "date": s.duty_date.isoformat(),
                "role": "值班员",
                "location": s.location,
                "leader": s.duty_leader.name if s.duty_leader else None,
            }
            for s in schedules
        ]

        # 更新 last_sync_at(成功调用时)
        try:
            integration = user.sage_integration
            integration.sage_last_sync_at = timezone.now()
            integration.save(update_fields=["sage_last_sync_at", "updated_at"])
        except SageIntegrationFields.DoesNotExist:
            pass

        return Response({"schedule": items})
```

**Step 5.4: 挂载路由**

`omni_desk_backend/sage_integration/urls.py`,在 `urlpatterns` 列表中追加(在 `auth-enable-local-features` 后):

```python
    # 通道 A 业务代理(Task 5/6)
    path("proxy/schedule/", SageScheduleProxyView.as_view(), name="proxy-schedule"),
```

并在文件顶部 imports 加:

```python
from sage_integration.proxy_views import SageScheduleProxyView
```

**Step 5.5: 运行测试,确认 PASS**

Run:
```bash
cd /home/fz/project/OmniDesk
/home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest omni_desk_backend/sage_integration/tests/test_proxy.py -v -k schedule 2>&1 | tail -20
```

Expected:4 passed。

**Step 5.6: Commit**

```bash
cd /home/fz/project/OmniDesk
git add omni_desk_backend/sage_integration/
git commit -m "feat(sage-integration): 通道 A schedule 代理

- POST /api/sage/proxy/schedule/ 返回当前用户排班(限定本人 personnel)
- 字段裁剪:{date, role, location, leader},不返回 notes/created_by
- 入参校验:date_from <= date_to,范围 <= 90 天
- 全局开关关闭 → 403(双重防御)
- 成功调用更新 sage_last_sync_at
- 单元测试 4 用例覆盖"
```

---

## Task 6: 实现 `/api/sage/proxy/personnel/`

**Files:**
- Modify: `omni_desk_backend/sage_integration/proxy_views.py`
- Modify: `omni_desk_backend/sage_integration/urls.py`
- Modify: `omni_desk_backend/sage_integration/tests/test_proxy.py`

**Interfaces:**
- Endpoint: `GET /api/sage/proxy/personnel/?query=<name_or_dept>&limit=<int>` → `{personnel: [{id, name, department, position, phone}]}`

> **实施前核对**:`personnel/models.py` 的 Personnel 模型实际字段(phone / department / id_card 等)。如有差异,测试与 view 同步调整。

**Step 6.1: 追加失败测试**

在 `omni_desk_backend/sage_integration/tests/test_proxy.py` 末尾追加:

```python
def test_personnel_proxy_returns_search_results(db, alice):
    """personnel 代理按姓名/部门查询。"""
    Personnel.objects.create(name="张三", employee_id="E010", department="研发部")
    Personnel.objects.create(name="李四", employee_id="E011", department="行政部")

    client = APIClient()
    client.force_authenticate(user=alice)
    SageIntegrationFields.objects.create(user=alice)

    response = client.get(
        reverse("sage_integration:proxy-personnel"),
        {"query": "张", "limit": 10},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["personnel"]) == 1
    assert data["personnel"][0]["name"] == "张三"


def test_personnel_proxy_trims_sensitive_fields(db, alice):
    """personnel 不返回身份证 / 银行账号等敏感字段。"""
    Personnel.objects.create(
        name="王五",
        employee_id="E020",
        department="财务部",
        id_card="110101199001011234",  # 假设模型有该字段;无则跳过此字段验证
    )

    client = APIClient()
    client.force_authenticate(user=alice)
    SageIntegrationFields.objects.create(user=alice)

    response = client.get(
        reverse("sage_integration:proxy-personnel"),
        {"query": "王", "limit": 10},
    )
    assert response.status_code == 200
    item = response.json()["personnel"][0]
    assert "id_card" not in item
    assert "id" in item
    assert "name" in item
    assert "department" in item
```

**Step 6.2: 实现 personnel 代理 view**

在 `omni_desk_backend/sage_integration/proxy_views.py` 追加:

```python
from django.db import models
from personnel.models import Personnel


class SagePersonnelProxyView(APIView):
    """GET /api/sage/proxy/personnel/

    按姓名 / 部门查询人员。字段裁剪:不返回身份证 / 银行账号 / 详细地址等敏感字段。
    """

    permission_classes = [IsSageIntegrationEnabled, IsSageAuthenticated]
    throttle_classes = [SageProxyThrottle]

    ALLOWED_FIELDS = ("id", "name", "department", "position", "phone")
    DEFAULT_LIMIT = 20
    MAX_LIMIT = 100

    def get(self, request: Any) -> Response:
        query = (request.query_params.get("query") or "").strip()
        if not query:
            return Response({"personnel": []})

        try:
            limit = min(int(request.query_params.get("limit", self.DEFAULT_LIMIT)), self.MAX_LIMIT)
        except (TypeError, ValueError):
            limit = self.DEFAULT_LIMIT

        qs = Personnel.objects.filter(
            models.Q(name__icontains=query) | models.Q(department__icontains=query)
        ).only(*self.ALLOWED_FIELDS)[:limit]

        items: list[dict[str, Any]] = [
            {
                "id": p.pk,
                "name": p.name,
                "department": getattr(p, "department", None),
                "position": getattr(p, "position", None),
                "phone": getattr(p, "phone", None),
            }
            for p in qs
        ]
        return Response({"personnel": items})
```

并在文件顶部 imports 加:

```python
from django.db import models
from personnel.models import Personnel
```

**Step 6.3: 挂载路由**

`omni_desk_backend/sage_integration/urls.py` 在 urlpatterns 追加:

```python
    path("proxy/personnel/", SagePersonnelProxyView.as_view(), name="proxy-personnel"),
```

并在 imports 加:

```python
from sage_integration.proxy_views import SagePersonnelProxyView, SageScheduleProxyView
```

**Step 6.4: 运行测试,确认 PASS**

Run:
```bash
cd /home/fz/project/OmniDesk
/home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest omni_desk_backend/sage_integration/tests/test_proxy.py -v 2>&1 | tail -20
```

Expected:6 passed。

若失败:`Personnel` 字段名不匹配(`phone` / `department` 不存在),按实际字段调整测试断言。

**Step 6.5: Commit**

```bash
cd /home/fz/project/OmniDesk
git add omni_desk_backend/sage_integration/
git commit -m "feat(sage-integration): 通道 A personnel 代理

- GET /api/sage/proxy/personnel/?query=&limit=
- 字段裁剪白名单: id / name / department / position / phone
- 不返回身份证 / 银行账号 / 详细地址
- 限流 60/min,默认 20 条上限 100 条
- 单元测试覆盖(含敏感字段剔除)"
```

---

# Phase 3: 通道 B 任务模型与 API

## Task 7: SageTask 模型与 migration

**Files:**
- Modify: `omni_desk_backend/sage_integration/models.py`
- Create: `omni_desk_backend/sage_integration/migrations/0002_sagetask.py`(由 makemigrations 生成)
- Create: `omni_desk_backend/sage_integration/tests/test_task_model.py`

**Interfaces:**
- Produces: `sage_integration.models.SageTask`
- 字段:`id`(UUID PK)、`user`(FK)、`kind`(枚举)、`params`(JSON)、`status`(枚举)、`result`(JSON)、`error`(Text)、`created_at`、`claimed_at`、`completed_at`、`expires_at`

**Step 7.1: 写失败测试**

`omni_desk_backend/sage_integration/tests/test_task_model.py`:

```python
"""SageTask 模型测试。"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone

from sage_integration.models import SageTask
from users.models import CustomUser


def test_sage_task_creation_defaults(db):
    """创建任务时 status=pending,expires_at=created_at+1h。"""
    user = CustomUser.objects.create_user(username="user1", password="pw12345!")
    task = SageTask.objects.create(
        user=user,
        kind="local_file_scan",
        params={"directory": "/tmp", "pattern": "*.txt"},
    )
    assert task.status == "pending"
    delta = task.expires_at - task.created_at
    assert timedelta(minutes=59, seconds=59) < delta < timedelta(minutes=60, seconds=1)


def test_sage_task_kind_choices(db):
    """kind 必须是 local_file_scan / local_kb_search 之一。"""
    user = CustomUser.objects.create_user(username="user2", password="pw12345!")
    with pytest.raises(Exception):
        SageTask.objects.create(user=user, kind="invalid_kind", params={})


def test_sage_task_user_cascade_delete(db):
    """删除 CustomUser 时关联任务级联删除。"""
    user = CustomUser.objects.create_user(username="user3", password="pw12345!")
    SageTask.objects.create(user=user, kind="local_file_scan", params={})
    user.delete()
    assert SageTask.objects.count() == 0


def test_sage_task_index_for_pending_query(db):
    """(user, status, created_at) 索引存在以便 pending 查询高效。"""
    from sage_integration.models import SageTask as Model

    indexes = Model._meta.indexes
    assert any(
        {f.name for f in idx.fields} == {"user", "status", "created_at"}
        for idx in indexes
    )
```

**Step 7.2: 运行测试,确认失败**

Run:
```bash
cd /home/fz/project/OmniDesk
/home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest omni_desk_backend/sage_integration/tests/test_task_model.py -v 2>&1 | tail -15
```

Expected:FAIL,`SageTask` 未定义。

**Step 7.3: 实现 SageTask**

`omni_desk_backend/sage_integration/models.py` 追加(原 SageIntegrationFields 之后):

```python
from datetime import timedelta
from typing import Any


class SageTask(models.Model):
    """Sage 桌面端发起、OmniDesk 留痕的本地任务。

    Why: 不让 OmniDesk 自建 AI 触发能力(违反非目标),仅作审计/留痕/限流。
    """

    TASK_KIND_CHOICES = [
        ("local_file_scan", "本地文件扫描"),
        ("local_kb_search", "本地知识库查询"),
    ]
    STATUS_CHOICES = [
        ("pending", "等待 Sage 认领"),
        ("claimed", "Sage 已认领,执行中"),
        ("done", "完成"),
        ("failed", "失败"),
        ("timeout", "超时"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sage_tasks",
        help_text="任务归属用户(只能本人发起/查询)",
    )
    kind = models.CharField(max_length=64, choices=TASK_KIND_CHOICES)
    params = models.JSONField(default=dict, help_text="任务参数")
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="pending")
    result = models.JSONField(null=True, blank=True, help_text="执行结果")
    error = models.TextField(blank=True, help_text="失败原因")
    created_at = models.DateTimeField(auto_now_add=True)
    claimed_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(help_text="任务过期时间,默认 1 小时后")

    class Meta:
        verbose_name = "Sage 任务"
        verbose_name_plural = "Sage 任务"
        indexes = [
            models.Index(fields=["user", "status", "created_at"]),
        ]

    def save(self, *args: Any, **kwargs: Any) -> None:
        # 默认 expires_at = created_at + 1h(创建时设置,后续不再更新)
        if not self.expires_at:
            now = timezone.now()
            self.expires_at = now + timedelta(hours=1)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"SageTask<{self.kind} user={self.user.username} status={self.status}>"
```

并在文件顶部 imports 加:

```python
from django.utils import timezone
```

**Step 7.4: 生成 migration**

Run:
```bash
cd /home/fz/project/OmniDesk
/home/fz/anaconda3/envs/OmniDesk/bin/python manage.py makemigrations sage_integration 2>&1 | tail -10
```

Expected:创建 `0002_sagetask.py`。

**Step 7.5: 运行测试,确认 PASS**

Run:
```bash
cd /home/fz/project/OmniDesk
/home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest omni_desk_backend/sage_integration/tests/test_task_model.py -v 2>&1 | tail -15
```

Expected:4 passed。

**Step 7.6: Commit**

```bash
cd /home/fz/project/OmniDesk
git add omni_desk_backend/sage_integration/
git commit -m "feat(sage-integration): SageTask 模型与 migration

- 字段: id(UUID)/ user(FK)/ kind/ params/ status/ result/ error/ 时间戳
- 复合索引 (user, status, created_at)
- 默认 expires_at = created_at + 1h
- 单元测试 4 用例覆盖"
```

---

## Task 8: 通道 B 五个任务 API

**Files:**
- Create: `omni_desk_backend/sage_integration/task_views.py`
- Modify: `omni_desk_backend/sage_integration/urls.py`
- Create: `omni_desk_backend/sage_integration/tests/test_tasks.py`

**Interfaces:**
- `POST /api/sage/tasks/` → 创建任务,要求 `user.sage_integration.sage_local_features_enabled=True`
- `GET /api/sage/tasks/<uuid:id>/` → 单任务查询
- `GET /api/sage/tasks/pending/` → 当前用户待办任务
- `POST /api/sage/tasks/<uuid:id>/claim/` → 认领(更新 status=claimed,claimed_at=now)
- `POST /api/sage/tasks/<uuid:id>/result/` → 回写结果(body: `{status, result?, error?}`)

**Step 8.1: 写失败测试**

`omni_desk_backend/sage_integration/tests/test_tasks.py`:

```python
"""通道 B 任务 API 测试。"""

from __future__ import annotations

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from sage_integration.models import SageIntegrationFields, SageTask
from users.models import CustomUser


@pytest.fixture
def alice_with_local_enabled(db):
    user = CustomUser.objects.create_user(username="user1", password="pw12345!")
    SageIntegrationFields.objects.create(user=user, sage_local_features_enabled=True)
    return user


@pytest.fixture
def alice_without_local(db):
    user = CustomUser.objects.create_user(username="user2", password="pw12345!")
    SageIntegrationFields.objects.create(user=user, sage_local_features_enabled=False)
    return user


@pytest.fixture
def authed_client():
    return APIClient()


def test_create_task_requires_local_features_enabled(authed_client, alice_without_local):
    """未启用本地功能时,创建任务 403。"""
    authed_client.force_authenticate(user=alice_without_local)
    response = authed_client.post(
        reverse("sage_integration:task-create"),
        {"kind": "local_file_scan", "params": {"directory": "/tmp"}},
        format="json",
    )
    assert response.status_code == 403


def test_create_task_succeeds_when_enabled(authed_client, alice_with_local_enabled):
    """启用本地功能 + 未超限 → 创建成功。"""
    authed_client.force_authenticate(user=alice_with_local_enabled)
    response = authed_client.post(
        reverse("sage_integration:task-create"),
        {"kind": "local_file_scan", "params": {"directory": "/tmp", "pattern": "*.txt"}},
        format="json",
    )
    assert response.status_code == 201
    data = response.json()
    assert data["kind"] == "local_file_scan"
    assert data["status"] == "pending"
    assert SageTask.objects.filter(user=alice_with_local_enabled).count() == 1


def test_pending_returns_only_user_own_pending(authed_client, alice_with_local_enabled):
    """pending 只返回当前用户的待办,不返回他人。"""
    other_user = CustomUser.objects.create_user(username="user3", password="pw12345!")
    SageIntegrationFields.objects.create(user=other_user, sage_local_features_enabled=True)

    SageTask.objects.create(user=alice_with_local_enabled, kind="local_file_scan", params={})
    SageTask.objects.create(user=other_user, kind="local_file_scan", params={})

    authed_client.force_authenticate(user=alice_with_local_enabled)
    response = authed_client.get(reverse("sage_integration:task-pending"))
    assert response.status_code == 200
    tasks = response.json()["tasks"]
    assert len(tasks) == 1
    assert tasks[0]["user_id"] == alice_with_local_enabled.id


def test_claim_transitions_status(authed_client, alice_with_local_enabled):
    """claim 把 status 从 pending → claimed,设置 claimed_at。"""
    task = SageTask.objects.create(
        user=alice_with_local_enabled, kind="local_file_scan", params={}
    )
    authed_client.force_authenticate(user=alice_with_local_enabled)
    response = authed_client.post(reverse("sage_integration:task-claim", args=[task.id]))
    assert response.status_code == 200

    task.refresh_from_db()
    assert task.status == "claimed"
    assert task.claimed_at is not None


def test_claim_rejects_already_claimed(authed_client, alice_with_local_enabled):
    """已认领的任务再次 claim → 409。"""
    task = SageTask.objects.create(
        user=alice_with_local_enabled, kind="local_file_scan", params={}
    )
    authed_client.force_authenticate(user=alice_with_local_enabled)
    authed_client.post(reverse("sage_integration:task-claim", args=[task.id]))
    response = authed_client.post(reverse("sage_integration:task-claim", args=[task.id]))
    assert response.status_code == 409


def test_result_records_status_and_result(authed_client, alice_with_local_enabled):
    """result 把 claimed → done,并存 result。"""
    task = SageTask.objects.create(
        user=alice_with_local_enabled, kind="local_file_scan", params={}
    )
    authed_client.force_authenticate(user=alice_with_local_enabled)
    authed_client.post(reverse("sage_integration:task-claim", args=[task.id]))

    response = authed_client.post(
        reverse("sage_integration:task-result", args=[task.id]),
        {"status": "done", "result": {"files": ["a.txt", "b.txt"]}},
        format="json",
    )
    assert response.status_code == 200

    task.refresh_from_db()
    assert task.status == "done"
    assert task.completed_at is not None
    assert task.result == {"files": ["a.txt", "b.txt"]}


def test_detail_returns_404_for_other_user_task(authed_client, alice_with_local_enabled):
    """他人的任务返回 404(不暴露存在性)。"""
    other = CustomUser.objects.create_user(username="user4", password="pw12345!")
    SageIntegrationFields.objects.create(user=other, sage_local_features_enabled=True)
    task = SageTask.objects.create(user=other, kind="local_file_scan", params={})

    authed_client.force_authenticate(user=alice_with_local_enabled)
    response = authed_client.get(reverse("sage_integration:task-detail", args=[task.id]))
    assert response.status_code == 404
```

**Step 8.2: 运行测试,确认失败**

Run:
```bash
cd /home/fz/project/OmniDesk
/home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest omni_desk_backend/sage_integration/tests/test_tasks.py -v 2>&1 | tail -15
```

Expected:FAIL,路由未定义。

**Step 8.3: 实现 task views**

`omni_desk_backend/sage_integration/task_views.py`:

```python
"""通道 B 任务 views。

Sage 桌面端发起本地任务到 OmniDesk 留痕。OmniDesk 不主动派发。
"""

from __future__ import annotations

from typing import Any

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from sage_integration.models import SageIntegrationFields, SageTask
from sage_integration.permissions import IsSageAuthenticated, IsSageIntegrationEnabled
from sage_integration.throttles import SageTaskThrottle


class SageTaskCreateSerializer(serializers.Serializer):
    """创建任务入参。"""

    kind = serializers.ChoiceField(choices=[c[0] for c in SageTask.TASK_KIND_CHOICES])
    params = serializers.JSONField()


class SageTaskResultSerializer(serializers.Serializer):
    """回写结果入参。"""

    status = serializers.ChoiceField(choices=["done", "failed"])
    result = serializers.JSONField(required=False, allow_null=True)
    error = serializers.CharField(required=False, allow_blank=True)


def _user_has_local_enabled(user: Any) -> bool:
    try:
        return bool(user.sage_integration.sage_local_features_enabled)
    except SageIntegrationFields.DoesNotExist:
        return False


class SageTaskCreateView(APIView):
    """POST /api/sage/tasks/

    Sage 桌面端自派任务。要求用户已开启通道 B。
    """

    permission_classes = [IsSageIntegrationEnabled, IsSageAuthenticated]
    throttle_classes = [SageTaskThrottle]

    def post(self, request: Any) -> Response:
        if not _user_has_local_enabled(request.user):
            return Response(
                {"detail": "请先在 Sage 桌面端启用'接收 OmniDesk 任务'开关"},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = SageTaskCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        task = SageTask.objects.create(
            user=request.user,
            kind=serializer.validated_data["kind"],
            params=serializer.validated_data["params"],
        )
        return Response(
            {
                "id": str(task.id),
                "kind": task.kind,
                "status": task.status,
                "created_at": task.created_at.isoformat(),
                "expires_at": task.expires_at.isoformat(),
            },
            status=status.HTTP_201_CREATED,
        )


class SageTaskDetailView(APIView):
    """GET /api/sage/tasks/<uuid:id>/"""

    permission_classes = [IsSageIntegrationEnabled, IsSageAuthenticated]

    def get(self, request: Any, pk: Any) -> Response:
        task = get_object_or_404(SageTask, pk=pk, user=request.user)
        return Response(
            {
                "id": str(task.id),
                "kind": task.kind,
                "status": task.status,
                "params": task.params,
                "result": task.result,
                "error": task.error,
                "created_at": task.created_at.isoformat(),
                "claimed_at": task.claimed_at.isoformat() if task.claimed_at else None,
                "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                "expires_at": task.expires_at.isoformat(),
            }
        )


class SagePendingTasksView(APIView):
    """GET /api/sage/tasks/pending/

    返回当前用户的 pending 任务(同一 OmniDesk 用户多端场景)。
    """

    permission_classes = [IsSageIntegrationEnabled, IsSageAuthenticated]

    def get(self, request: Any) -> Response:
        if not _user_has_local_enabled(request.user):
            return Response({"tasks": []})

        pending = (
            SageTask.objects.filter(
                user=request.user,
                status="pending",
                expires_at__gt=timezone.now(),
            )
            .order_by("created_at")
            .only("id", "kind", "params", "created_at", "expires_at", "user_id")
        )

        items: list[dict[str, Any]] = [
            {
                "id": str(t.id),
                "user_id": t.user_id,
                "kind": t.kind,
                "params": t.params,
                "created_at": t.created_at.isoformat(),
                "expires_at": t.expires_at.isoformat(),
            }
            for t in pending
        ]
        return Response({"tasks": items})


class SageTaskClaimView(APIView):
    """POST /api/sage/tasks/<uuid:id>/claim/"""

    permission_classes = [IsSageIntegrationEnabled, IsSageAuthenticated]

    def post(self, request: Any, pk: Any) -> Response:
        task = get_object_or_404(SageTask, pk=pk, user=request.user)
        if task.status != "pending":
            return Response(
                {"detail": f"任务状态为 {task.status},不可认领"},
                status=status.HTTP_409_CONFLICT,
            )
        if task.expires_at <= timezone.now():
            task.status = "timeout"
            task.save(update_fields=["status"])
            return Response(
                {"detail": "任务已过期"},
                status=status.HTTP_409_CONFLICT,
            )

        task.status = "claimed"
        task.claimed_at = timezone.now()
        task.save(update_fields=["status", "claimed_at"])
        return Response({"ok": True, "status": task.status, "claimed_at": task.claimed_at.isoformat()})


class SageTaskResultView(APIView):
    """POST /api/sage/tasks/<uuid:id>/result/"""

    permission_classes = [IsSageIntegrationEnabled, IsSageAuthenticated]

    def post(self, request: Any, pk: Any) -> Response:
        task = get_object_or_404(SageTask, pk=pk, user=request.user)
        if task.status not in ("claimed", "pending"):
            return Response(
                {"detail": f"任务状态 {task.status},不能回写结果"},
                status=status.HTTP_409_CONFLICT,
            )

        serializer = SageTaskResultSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_status = serializer.validated_data["status"]

        task.status = new_status
        task.completed_at = timezone.now()
        if "result" in serializer.validated_data:
            task.result = serializer.validated_data["result"]
        if "error" in serializer.validated_data:
            task.error = serializer.validated_data["error"]
        task.save(update_fields=["status", "completed_at", "result", "error"])

        return Response({"ok": True, "status": task.status})
```

**Step 8.4: 挂载路由**

`omni_desk_backend/sage_integration/urls.py` 在 urlpatterns 追加:

```python
    # 通道 B 任务(Task 8)
    path("tasks/", SageTaskCreateView.as_view(), name="task-create"),
    path("tasks/pending/", SagePendingTasksView.as_view(), name="task-pending"),
    path("tasks/<uuid:pk>/", SageTaskDetailView.as_view(), name="task-detail"),
    path("tasks/<uuid:pk>/claim/", SageTaskClaimView.as_view(), name="task-claim"),
    path("tasks/<uuid:pk>/result/", SageTaskResultView.as_view(), name="task-result"),
```

并在文件顶部 imports 加:

```python
from sage_integration.task_views import (
    SagePendingTasksView,
    SageTaskClaimView,
    SageTaskCreateView,
    SageTaskDetailView,
    SageTaskResultView,
)
```

**Step 8.5: 运行测试,确认 PASS**

Run:
```bash
cd /home/fz/project/OmniDesk
/home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest omni_desk_backend/sage_integration/tests/test_tasks.py -v 2>&1 | tail -20
```

Expected:7 passed。

**Step 8.6: Commit**

```bash
cd /home/fz/project/OmniDesk
git add omni_desk_backend/sage_integration/
git commit -m "feat(sage-integration): 通道 B 任务 API

- POST /api/sage/tasks/ 创建任务(要求 sage_local_features_enabled=True)
- GET /api/sage/tasks/<id>/ 单任务查询
- GET /api/sage/tasks/pending/ 当前用户待办
- POST /api/sage/tasks/<id>/claim/ 认领(pending→claimed,设 claimed_at)
- POST /api/sage/tasks/<id>/result/ 回写结果(claimed→done/failed,设 completed_at)
- 状态机: pending → claimed → done/failed;claim 二次 → 409;过期 → timeout
- 限流: 20/hour(每用户)
- 单元测试 7 用例覆盖"
```

---

## Task 9: cleanup_sage_tasks 管理命令

**Files:**
- Create: `omni_desk_backend/sage_integration/management/__init__.py`
- Create: `omni_desk_backend/sage_integration/management/commands/__init__.py`
- Create: `omni_desk_backend/sage_integration/management/commands/cleanup_sage_tasks.py`
- Create: `omni_desk_backend/sage_integration/tests/test_cleanup_command.py`

> `SageTaskThrottle` 已在 Task 4 Step 4.4 实现,rate 在 Task 1 Step 1.4 的 `sage_task: "20/hour"` 配置,无需重复。

**Step 9.1: 写失败测试**

`omni_desk_backend/sage_integration/tests/test_cleanup_command.py`:

```python
"""cleanup_sage_tasks 管理命令测试。"""

from __future__ import annotations

from datetime import timedelta

from django.core.management import call_command
from django.utils import timezone

from sage_integration.models import SageTask
from users.models import CustomUser


def test_cleanup_marks_expired_pending_as_timeout(db):
    """过期且 pending 的任务标记为 timeout。"""
    user = CustomUser.objects.create_user(username="user1", password="pw12345!")
    expired_task = SageTask.objects.create(
        user=user,
        kind="local_file_scan",
        params={},
    )
    expired_task.expires_at = timezone.now() - timedelta(minutes=5)
    expired_task.save(update_fields=["expires_at"])

    call_command("cleanup_sage_tasks")

    expired_task.refresh_from_db()
    assert expired_task.status == "timeout"


def test_cleanup_skips_recent_tasks(db):
    """未过期任务不动。"""
    user = CustomUser.objects.create_user(username="user2", password="pw12345!")
    task = SageTask.objects.create(user=user, kind="local_file_scan", params={})
    call_command("cleanup_sage_tasks")

    task.refresh_from_db()
    assert task.status == "pending"


def test_cleanup_skips_already_done_tasks(db):
    """已完成任务不被 cleanup 重新标记。"""
    user = CustomUser.objects.create_user(username="user3", password="pw12345!")
    task = SageTask.objects.create(
        user=user,
        kind="local_file_scan",
        params={},
        status="done",
    )
    task.expires_at = timezone.now() - timedelta(minutes=5)
    task.save(update_fields=["expires_at"])

    call_command("cleanup_sage_tasks")

    task.refresh_from_db()
    assert task.status == "done"


def test_cleanup_dry_run_does_not_modify(db):
    """--dry-run 不修改数据。"""
    user = CustomUser.objects.create_user(username="user4", password="pw12345!")
    task = SageTask.objects.create(user=user, kind="local_file_scan", params={})
    task.expires_at = timezone.now() - timedelta(minutes=5)
    task.save(update_fields=["expires_at"])

    call_command("cleanup_sage_tasks", "--dry-run")

    task.refresh_from_db()
    assert task.status == "pending"
```

**Step 9.2: 运行测试,确认失败**

Run:
```bash
cd /home/fz/project/OmniDesk
/home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest omni_desk_backend/sage_integration/tests/test_cleanup_command.py -v 2>&1 | tail -15
```

Expected:FAIL,命令不存在。

**Step 9.3: 实现 cleanup 命令**

`omni_desk_backend/sage_integration/management/__init__.py`:
```python
```

`omni_desk_backend/sage_integration/management/commands/__init__.py`:
```python
```

`omni_desk_backend/sage_integration/management/commands/cleanup_sage_tasks.py`:

```python
"""清理过期的 SageTask。

典型用途:cron 每日执行一次,把 expires_at < now 且 status=pending 的任务
标记为 timeout,防止任务队列堆积。

用法:
    python manage.py cleanup_sage_tasks [--dry-run]
"""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand
from django.utils import timezone

from sage_integration.models import SageTask


class Command(BaseCommand):
    help = "把过期的 pending SageTask 标记为 timeout"

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="只统计,不修改",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        dry_run: bool = bool(options.get("dry_run", False))
        now = timezone.now()
        expired_qs = SageTask.objects.filter(status="pending", expires_at__lte=now)
        count = expired_qs.count()

        if dry_run:
            self.stdout.write(self.style.WARNING(f"[dry-run] 将标记 {count} 个任务为 timeout"))
            return

        updated = expired_qs.update(status="timeout")
        self.stdout.write(self.style.SUCCESS(f"已标记 {updated} 个任务为 timeout"))
```

**Step 9.4: 运行测试,确认 PASS**

Run:
```bash
cd /home/fz/project/OmniDesk
/home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest omni_desk_backend/sage_integration/tests/test_cleanup_command.py -v 2>&1 | tail -15
```

Expected:4 passed。

**Step 9.5: Commit**

```bash
cd /home/fz/project/OmniDesk
git add omni_desk_backend/sage_integration/
git commit -m "feat(sage-integration): cleanup_sage_tasks 管理命令

- 把 expired pending 任务 → timeout
- 支持 --dry-run
- 单元测试 4 用例覆盖(含 dry-run / 已完成保护)"
```

---

# Phase 4: 文档与 CHANGELOG

## Task 10: 文档 + CHANGELOG(OmniDesk 端部分)

> **Sage 端文档由 Sage 端计划(`*-sage.md`)负责,本 Task 仅写 OmniDesk 端文档。**

**Files:**
- Create: `docs/technical/40-omnidesk-sage-integration.md`
- Create: `docs/user-manual/40-sage-integration.md`
- Modify: `docs/technical/README.md`
- Modify: `docs/user-manual/README.md`
- Modify: `deployment/docker/CHANGELOG.md`

**Step 10.1: 写技术文档**

`docs/technical/40-omnidesk-sage-integration.md`:

```markdown
# OmniDesk ↔ Sage 桌面端 集成

## 概述
- 设计稿:`docs/superpowers/specs/2026-08-18-omnidesk-sage-integration-design.md`
- MVP 范围:通道 A(查业务) + 通道 B(Sage 自派本地任务)
- 配套 Sage 端计划:`2026-08-18-omnidesk-sage-integration-sage.md`

## 架构

```
[ Sage 桌面端 ]
       │  HTTPS + JWT (sage_user_id claim)
       ▼
[ OmniDesk sage_integration app ]
       │  本地代理调用
       ▼
[ events / personnel / ... 既有业务 app ]
```

## OmniDesk 端模块

### app 配置
- `INSTALLED_APPS`:`sage_integration.apps.SageIntegrationConfig`
- 全局开关:`settings.SAGE_INTEGRATION_ENABLED`(默认 False)
- 关闭时路由整体不挂载,`/api/sage/*` 返回 404

### 数据模型
| Model | 关键字段 |
|---|---|
| `SageIntegrationFields` | user(OneToOne)/ sage_user_id(UUID unique)/ sage_last_sync_at/ sage_local_features_enabled/ sage_omnidesk_url |
| `SageTask` | id(UUID PK)/ user(FK)/ kind/ params(JSON)/ status/ result(JSON)/ error/ expires_at |

### JWT claim 扩展
- 不修改 `users/CustomTokenObtainPairSerializer`
- 新建 `SageTokenObtainPairSerializer` 复用基类,在 token 中加:
  - `sage_user_id`(str UUID,无集成时 None)
  - `sage_local_features`(bool)

### API 列表

| 端点 | 方法 | 限流 | 鉴权 |
|---|---|---|---|
| `/api/sage/auth/bind/` | POST | 5/h | 允许未认证 |
| `/api/sage/auth/whoami/` | GET | 30/min | JWT |
| `/api/sage/auth/enable-local-features/` | POST | 30/min | JWT |
| `/api/sage/proxy/schedule/` | POST | 60/min | JWT |
| `/api/sage/proxy/personnel/` | GET | 60/min | JWT |
| `/api/sage/tasks/` | POST | 20/h | JWT + 本地功能开关 |
| `/api/sage/tasks/pending/` | GET | (无) | JWT + 本地功能开关 |
| `/api/sage/tasks/<id>/` | GET | (无) | JWT |
| `/api/sage/tasks/<id>/claim/` | POST | (无) | JWT |
| `/api/sage/tasks/<id>/result/` | POST | (无) | JWT |

### 管理命令
```bash
python manage.py cleanup_sage_tasks [--dry-run]
```

## 部署

1. `settings.SAGE_INTEGRATION_ENABLED=True` 显式开启
2. `python manage.py migrate sage_integration`
3. 重启服务

## 故障排查

| 现象 | 原因 | 排查 |
|---|---|---|
| 所有 `/api/sage/*` 404 | SAGE_INTEGRATION_ENABLED=False 或路由未挂载 | 检查 settings |
| bind 返回 400 "用户名或密码不正确" | 凭据错或账号 inactive | OmniDesk admin 查账号 |
| 401 on whoami | JWT 过期或无效 | Sage 端重新 bind |
| 409 on 二次 claim | 任务已认领 | 任务状态机查询 |
| 任务卡在 pending | Sage 没拉 / worker 挂了 | 查 Sage 端 worker 日志 |

## 测试

```bash
pytest omni_desk_backend/sage_integration/tests/ --cov=omni_desk_backend/sage_integration
mypy omni_desk_backend/sage_integration/
```

## 已知限制(均见 spec)

- 记忆同步、Skill 互通、事件推送不在 MVP
- JWT revoke 机制未实现(依赖 simplejwt 自带 blacklist,有效期 7 天)
- `safeStorage` Win7 兼容性验证由 Sage 端负责
```

**Step 10.2: 写用户手册**

`docs/user-manual/40-sage-integration.md`:

```markdown
# 连接到 OmniDesk(Sage 用户视角)

## 适用对象
- Sage 桌面端用户,需要查询 OmniDesk 业务数据
- 内网用户,OmniDesk 部署在内网可访问

## 前置条件
- 有 OmniDesk 账号
- Sage 版本含 OmniDesk 集成

## 步骤
1. 打开 Sage 设置 → "连接到 OmniDesk"
2. 输入 OmniDesk URL(如 http://omnidesk.company.local:8000)
3. 输入用户名 / 密码
4. 点"绑定"
5. (可选)勾选"启用接收 OmniDesk 任务"

## 使用示例
- "我明天上什么班" → 查排班
- "研发部有哪些人" → 查人员

## 隐私说明
- Sage 不会把对话内容同步到 OmniDesk
- 业务数据只用于查询,不会下载到本地
- 密码不会持久化(JWT 用 OS 密钥加密存储)

## 解除绑定
在 OmniDesk 集成设置页底部点"解除绑定",所有本地 token 立即清除。

## 常见问题

**Q: 绑定后多久生效?**
A: 立即生效。OmniDesk 端状态会立刻写入。

**Q: 换了电脑需要重新绑定吗?**
A: 需要。但使用相同 sage_user_id 可以复用之前的绑定记录。

**Q: 报错"OmniDesk 当前不可达"怎么办?**
A: 检查 URL 配置、内网连通性、OmniDesk 是否开启 sage 集成开关。
```

**Step 10.3: 更新 README 章节目录**

`docs/technical/README.md` 在目录表格中追加一行(序号 40):

```markdown
| 40 | [OmniDesk ↔ Sage 集成](40-omnidesk-sage-integration.md) | Sage 桌面端集成架构、API、部署、故障排查 |
```

`docs/user-manual/README.md` 类似追加:

```markdown
| 40 | [Sage 桌面集成](40-sage-integration.md) | Sage 用户连接 OmniDesk 的步骤与隐私说明 |
```

**Step 10.4: 更新 CHANGELOG**

`deployment/docker/CHANGELOG.md`(OmniDesk 端),在 `[Unreleased]` 段(若不存在则创建)下追加:

```markdown
## [Unreleased]

### Added
- feat: OmniDesk ↔ Sage 桌面端集成(sage_integration app)
  - 通道 A:Sage 查询 OmniDesk 业务数据(排班 / 人员)
  - 通道 B:Sage 自派本地任务,OmniDesk 留痕审计
  - JWT 扩展 sage_user_id / sage_local_features claim
  - 全局开关 `settings.SAGE_INTEGRATION_ENABLED`(默认 False)
  - 管理命令 `cleanup_sage_tasks [--dry-run]`
```

**Step 10.5: Commit**

```bash
cd /home/fz/project/OmniDesk
git add docs/ deployment/docker/CHANGELOG.md
git commit -m "docs(sage-integration): 技术文档 + 用户手册 + CHANGELOG

- docs/technical/40-omnidesk-sage-integration.md: 架构 / API / 部署 / 故障排查
- docs/user-manual/40-sage-integration.md: 用户视角操作步骤
- 更新 README 章节目录
- CHANGELOG.md 加条目

Refs: docs/superpowers/specs/2026-08-18-omnidesk-sage-integration-design.md"
```

---

# 完成检查清单

执行完成后,逐项勾选(spec §10 验收标准):

- [ ] **单元测试覆盖率 ≥ 80%**

  Run:
  ```bash
  cd /home/fz/project/OmniDesk
  /home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest omni_desk_backend/sage_integration/tests/ --cov=omni_desk_backend/sage_integration --cov-report=term-missing 2>&1 | tail -30
  ```

- [ ] **OmniDesk CI 全绿**(`pytest --ds=omni_desk_backend.settings.test` + mypy)

  Run:
  ```bash
  cd /home/fz/project/OmniDesk
  /home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest omni_desk_backend/ -q 2>&1 | tail -10
  /home/fz/anaconda3/envs/OmniDesk/bin/python -m mypy omni_desk_backend/sage_integration/ 2>&1 | tail -10
  ```

- [ ] **关闭开关后路由全部 404**

  临时关闭测试:
  ```bash
  SAGE_INTEGRATION_ENABLED=False /home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest omni_desk_backend/sage_integration/tests/test_smoke.py::test_urls_not_mounted_when_disabled -v
  ```

- [ ] **CHANGELOG 双端更新**(本仓 `deployment/docker/CHANGELOG.md` + Sage 仓 `CHANGELOG.md`)

- [ ] **文档齐备**:`docs/technical/40-omnidesk-sage-integration.md` + `docs/user-manual/40-sage-integration.md`

- [ ] **与 Sage 端计划同步**:Sage 端实施完成后,实测两边端到端

---

# 执行模式选择

**1. Subagent-Driven (推荐)** — 每个 Task 派一个独立子 agent 执行,正确性 + 设计意图两阶段评审。高吞吐、上下文隔离。

**2. Inline Execution** — 在当前会话按 Task 顺序执行,定期 checkpoint 让你 review。

直接说"开始执行"默认走 1。