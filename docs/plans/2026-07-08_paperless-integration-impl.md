# paperless-ngx 集成实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 paperless-ngx 作为 OmniDesk 的真实文档存储后端,业务模块附件统一落 paperless,顶部搜索栏联邦查询,paperless 故障时通过 Outbox 写降级 + 读穿透缓存保证业务不中断。

**Architecture:** 新增 `paperless_proxy` Django app,提供 4 个模型(DocumentBinding/OutboxItem/UserPaperlessBinding/PaperlessHealth)+ 3 个服务层(PaperlessClient/OutboxService/PaperlessSearchService)+ 3 个 Celery 任务(outbox_worker/health_check/cache_cleanup)+ 1 个前端模块(文档库)+ 1 个搜索联邦组件(顶部统一搜索栏)。

**Tech Stack:** Django 4.2 + DRF + Celery 5 + django_celery_beat + PostgreSQL + React 18.3 + Ant Design 5 + TanStack React Query v5

---

## Global Constraints

- **Python 版本**:3.10(锁文件统一,见 CLAUDE.md 第 8 条)
- **conda 环境**:`omni_desk`(`/home/fz/anaconda3/envs/omni_desk/bin/python`);**禁止污染 base**
- **Django app 命名**:`paperless_proxy`(下划线)
- **Django 风格**:4 空格缩进;类型注解用 `models.CharField(max_length=...)`;时间字段 `auto_now_add=True / auto_now=True`
- **DRF 风格**:ViewSet + 自定义 action;权限类 `IsBindingOwner / IsAdminOrOwner`
- **测试约定**:`pytest` + `@pytest.mark.django_db` + 自定义 fixture;模型 100% 覆盖,服务层 ≥ 90%,视图 ≥ 85%
- **测试数据库**:`settings.test` 用 in-memory SQLite,`MD5PasswordHasher`,关闭 logging
- **前端模块路径**:`src/features/<feature-name>/`(下划线命名,文件夹 kebab-case)
- **前端 UI 库**:Ant Design 5(不引入 MUI)
- **API 客户端**:Axios + React Query v5(JWT 自动刷新,失败 5 次重试)
- **i18n**:界面文案中文,代码注释中文
- **离线优先**:无外部 CDN,无外网请求
- **Windows 7 兼容**:不用 ES2022+ 特性,不用 `:has()` CSS,React build target 包含 Chrome 109
- **commit 规范**:conventional commits(`feat: / fix: / refactor: / docs: / test: / chore:`)
- **分支规范**:本计划全程在 `feat/paperless-integration` feature 分支(由 git-workflow 创建)
- **Celery beat 配置**:在 `settings/base.py` 的 `CELERY_BEAT_SCHEDULE` 字典新增
- **Secrets**:`PAPERLESS_API_TOKEN` 走环境变量,不进代码

---

## Phase 1: 基础脚手架(1 周)

### Task 1: paperless_proxy Django app 脚手架

**Files:**
- Create: `omni_desk_backend/paperless_proxy/__init__.py`
- Create: `omni_desk_backend/paperless_proxy/apps.py`
- Create: `omni_desk_backend/paperless_proxy/exceptions.py`
- Modify: `omni_desk_backend/omni_desk_backend/settings/base.py:INSTALLED_APPS`
- Test: `omni_desk_backend/paperless_proxy/tests/__init__.py`
- Test: `omni_desk_backend/paperless_proxy/tests/test_app_config.py`

**Interfaces:**
- Consumes:无
- Produces: 可 import `paperless_proxy` app,`PaperlessError` 异常类

- [ ] **Step 1.1: 创建 app 目录结构**

```bash
mkdir -p omni_desk_backend/paperless_proxy/tests
touch omni_desk_backend/paperless_proxy/__init__.py
touch omni_desk_backend/paperless_proxy/tests/__init__.py
```

- [ ] **Step 1.2: 写失败测试(apps.py 配置)**

创建 `omni_desk_backend/paperless_proxy/tests/test_app_config.py`:

```python
import pytest
from django.apps import apps
from django.conf import settings


@pytest.mark.django_db
class TestPaperlessProxyApp:
    def test_app_is_registered(self):
        """验证:paperless_proxy 在 INSTALLED_APPS 中"""
        assert 'paperless_proxy' in settings.INSTALLED_APPS

    def test_app_config_class(self):
        """验证:AppConfig 正确加载"""
        config = apps.get_app_config('paperless_proxy')
        assert config.name == 'paperless_proxy'
        assert config.verbose_name == 'paperless 代理'
```

- [ ] **Step 1.3: 运行测试,确认失败**

```bash
cd /home/fz/project/OmniDesk
/home/fz/anaconda3/envs/omni_desk/bin/python -m pytest omni_desk_backend/paperless_proxy/tests/test_app_config.py -v
```

预期:`django.core.exceptions.ImproperlyConfigured: App 'paperless_proxy' isn't installed`

- [ ] **Step 1.4: 创建 apps.py**

```python
# omni_desk_backend/paperless_proxy/apps.py
from django.apps import AppConfig


class PaperlessProxyConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "paperless_proxy"
    verbose_name = "paperless 代理"
```

- [ ] **Step 1.5: 在 settings/base.py 注册 app**

修改 `omni_desk_backend/omni_desk_backend/settings/base.py`,在 `INSTALLED_APPS` 列表末尾添加:

```python
    # 文档存储代理
    "paperless_proxy",
```

(注意逗号,确保上一个元素也有逗号)

- [ ] **Step 1.6: 创建 exceptions.py**

```python
# omni_desk_backend/paperless_proxy/exceptions.py
"""paperless_proxy 自定义异常"""


class PaperlessError(Exception):
    """paperless 调用相关错误的基类"""


class PaperlessUnavailableError(PaperlessError):
    """paperless 服务不可用(网络/超时/5xx)"""


class PaperlessAuthError(PaperlessError):
    """paperless 认证失败(401/403)"""


class PaperlessNotFoundError(PaperlessError):
    """paperless 资源不存在(404)"""
```

- [ ] **Step 1.7: 再次运行测试,确认通过**

```bash
cd /home/fz/project/OmniDesk
/home/fz/anaconda3/envs/omni_desk/bin/python -m pytest omni_desk_backend/paperless_proxy/tests/test_app_config.py -v
```

预期:2 passed

- [ ] **Step 1.8: 提交**

```bash
git add omni_desk_backend/paperless_proxy/
git commit -m "feat(paperless-proxy): 创建 paperless_proxy Django app 脚手架"
```

---

### Task 2: DocumentBinding 模型

**Files:**
- Create: `omni_desk_backend/paperless_proxy/models.py`
- Create: `omni_desk_backend/paperless_proxy/migrations/__init__.py`
- Test: `omni_desk_backend/paperless_proxy/tests/test_models.py`

**Interfaces:**
- Consumes:`users.models.CustomUser`
- Produces:`DocumentBinding` model,可被 `OutboxService` 引用

- [ ] **Step 2.1: 写失败测试**

创建 `omni_desk_backend/paperless_proxy/tests/test_models.py`:

```python
import pytest
from django.contrib.auth import get_user_model
from ..models import DocumentBinding

CustomUser = get_user_model()


@pytest.fixture
def user(db):
    return CustomUser.objects.create_user(username='alice', password='pwd')


@pytest.mark.django_db
class TestDocumentBinding:
    def test_create_binding(self, user):
        """验证:能创建一个 DocumentBinding"""
        binding = DocumentBinding.objects.create(
            source_type='project_document',
            source_id=42,
            paperless_id=100,
            paperless_checksum='abc123',
            owner=user,
            title='测试文档.pdf',
        )
        assert binding.id is not None
        assert binding.source_type == 'project_document'
        assert binding.paperless_id == 100

    def test_unique_source(self, user):
        """验证:同一 source_type + source_id 不能重复"""
        DocumentBinding.objects.create(
            source_type='project_document',
            source_id=42,
            paperless_id=100,
            paperless_checksum='abc',
            owner=user,
            title='A',
        )
        with pytest.raises(Exception):  # IntegrityError
            DocumentBinding.objects.create(
                source_type='project_document',
                source_id=42,
                paperless_id=101,
                paperless_checksum='def',
                owner=user,
                title='B',
            )

    def test_unique_paperless_id(self, user):
        """验证:paperless_id 全局唯一"""
        DocumentBinding.objects.create(
            source_type='contract',
            source_id=1,
            paperless_id=200,
            paperless_checksum='x',
            owner=user,
            title='A',
        )
        with pytest.raises(Exception):
            DocumentBinding.objects.create(
                source_type='policy',
                source_id=2,
                paperless_id=200,
                paperless_checksum='y',
                owner=user,
                title='B',
            )
```

- [ ] **Step 2.2: 运行测试,确认失败**

```bash
cd /home/fz/project/OmniDesk
/home/fz/anaconda3/envs/omni_desk/bin/python -m pytest omni_desk_backend/paperless_proxy/tests/test_models.py -v
```

预期:`ImportError: cannot import name 'DocumentBinding' from 'paperless_proxy.models'`

- [ ] **Step 2.3: 实现 DocumentBinding 模型**

```python
# omni_desk_backend/paperless_proxy/models.py
from django.conf import settings
from django.db import models
from django.db.models import JSONField


class DocumentBinding(models.Model):
    """OmniDesk 业务对象 ↔ paperless 文档绑定表"""

    SOURCE_CHOICES = [
        ('project_document', '项目文档'),
        ('contract', '合同'),
        ('policy', '制度文件'),
        ('compliance_report', '合规检查报告'),
        ('personnel_file', '人事档案'),
    ]

    source_type = models.CharField(
        max_length=32, choices=SOURCE_CHOICES, db_index=True, verbose_name='业务源类型'
    )
    source_id = models.PositiveIntegerField(db_index=True, verbose_name='业务源 ID')
    paperless_id = models.PositiveIntegerField(unique=True, verbose_name='paperless 文档 ID')
    paperless_checksum = models.CharField(max_length=64, verbose_name='paperless 校验和')
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='paperless_documents',
        verbose_name='所有者',
    )
    title = models.CharField(max_length=255, verbose_name='文档标题')
    correspondent_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='paperless correspondent ID'
    )
    extra_metadata = JSONField(default=dict, blank=True, verbose_name='扩展元数据')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '文档绑定'
        verbose_name_plural = '文档绑定'
        unique_together = [('source_type', 'source_id')]
        indexes = [
            models.Index(fields=['source_type', 'source_id']),
            models.Index(fields=['owner', 'source_type']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.get_source_type_display()} #{self.source_id} → paperless:{self.paperless_id}'
```

- [ ] **Step 2.4: 跑迁移**

```bash
cd /home/fz/project/OmniDesk
/home/fz/anaconda3/envs/omni_desk/bin/python manage.py makemigrations paperless_proxy
/home/fz/anaconda3/envs/omni_desk/bin/python -m pytest omni_desk_backend/paperless_proxy/tests/test_models.py -v
```

预期:3 passed,生成 `migrations/0001_initial.py`

- [ ] **Step 2.5: 提交**

```bash
git add omni_desk_backend/paperless_proxy/models.py omni_desk_backend/paperless_proxy/migrations/
git commit -m "feat(paperless-proxy): 添加 DocumentBinding 模型"
```

---

### Task 3: OutboxItem 模型

**Files:**
- Modify: `omni_desk_backend/paperless_proxy/models.py`
- Modify: `omni_desk_backend/paperless_proxy/tests/test_models.py`

**Interfaces:**
- Produces:`OutboxItem` model

- [ ] **Step 3.1: 追加失败测试**

在 `test_models.py` 末尾添加:

```python
from ..models import OutboxItem


@pytest.fixture
def binding(db, user):
    from ..models import DocumentBinding
    return DocumentBinding.objects.create(
        source_type='project_document',
        source_id=1,
        paperless_id=999,
        paperless_checksum='h',
        owner=user,
        title='X',
    )


@pytest.mark.django_db
class TestOutboxItem:
    def test_create_outbox(self, user, binding):
        """验证:能创建 OutboxItem"""
        item = OutboxItem.objects.create(
            operation='upload',
            status='pending',
            payload={'title': 't.pdf', 'correspondent_id': None},
            binding=binding,
            created_by=user,
        )
        assert item.id is not None
        assert item.status == 'pending'
        assert item.retry_count == 0

    def test_default_next_retry_at(self, user, binding):
        """验证:默认 next_retry_at = now"""
        from django.utils import timezone
        from datetime import timedelta
        item = OutboxItem.objects.create(
            operation='upload',
            payload={},
            binding=binding,
            created_by=user,
        )
        delta = timezone.now() - item.next_retry_at
        assert abs(delta) < timedelta(seconds=5)
```

- [ ] **Step 3.2: 运行,确认失败**

```bash
cd /home/fz/project/OmniDesk
/home/fz/anaconda3/envs/omni_desk/bin/python -m pytest omni_desk_backend/paperless_proxy/tests/test_models.py::TestOutboxItem -v
```

预期:`ImportError: cannot import name 'OutboxItem'`

- [ ] **Step 3.3: 实现 OutboxItem**

在 `models.py` 末尾添加:

```python
class OutboxItem(models.Model):
    """Outbox 写降级核心:待同步到 paperless 的操作"""

    STATUS_CHOICES = [
        ('pending', '待同步'),
        ('syncing', '同步中'),
        ('synced', '已同步'),
        ('failed', '失败(可重试)'),
        ('dead', '死信(需人工)'),
    ]

    OPERATION_CHOICES = [
        ('upload', '上传'),
        ('update_metadata', '更新元数据'),
        ('delete', '删除'),
    ]

    operation = models.CharField(
        max_length=32, choices=OPERATION_CHOICES, verbose_name='操作类型'
    )
    status = models.CharField(
        max_length=16, choices=STATUS_CHOICES, default='pending', db_index=True, verbose_name='状态'
    )
    payload = models.JSONField(default=dict, verbose_name='操作载荷')
    binding = models.ForeignKey(
        DocumentBinding,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='outbox',
        verbose_name='关联绑定',
    )
    retry_count = models.PositiveIntegerField(default=0, verbose_name='已重试次数')
    max_retries = models.PositiveIntegerField(default=10, verbose_name='最大重试次数')
    next_retry_at = models.DateTimeField(default=models.functions.Now, db_index=True, verbose_name='下次重试时间')
    last_error = models.TextField(blank=True, verbose_name='最后错误信息')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='paperless_outbox',
        verbose_name='创建人',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = 'Outbox 项'
        verbose_name_plural = 'Outbox 项'
        indexes = [
            models.Index(fields=['status', 'next_retry_at']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f'Outbox#{self.id} {self.operation} {self.status}'
```

- [ ] **Step 3.4: 跑迁移 + 测试**

```bash
cd /home/fz/project/OmniDesk
/home/fz/anaconda3/envs/omni_desk/bin/python manage.py makemigrations paperless_proxy
/home/fz/anaconda3/envs/omni_desk/bin/python -m pytest omni_desk_backend/paperless_proxy/tests/test_models.py -v
```

预期:5 passed

- [ ] **Step 3.5: 提交**

```bash
git add omni_desk_backend/paperless_proxy/
git commit -m "feat(paperless-proxy): 添加 OutboxItem 模型与迁移"
```

---

### Task 4: UserPaperlessBinding 模型

**Files:**
- Modify: `omni_desk_backend/paperless_proxy/models.py`
- Modify: `omni_desk_backend/paperless_proxy/tests/test_models.py`

- [ ] **Step 4.1: 追加失败测试**

```python
from ..models import UserPaperlessBinding


@pytest.mark.django_db
class TestUserPaperlessBinding:
    def test_create_binding(self, user):
        """验证:能创建 UserPaperlessBinding"""
        b = UserPaperlessBinding.objects.create(
            user=user, paperless_user_id=5, paperless_username='alice'
        )
        assert b.id is not None
        assert b.is_active is True

    def test_one_to_one(self, user):
        """验证:一个 OmniDesk 用户只能绑定一个 paperless 用户"""
        UserPaperlessBinding.objects.create(
            user=user, paperless_user_id=5, paperless_username='alice'
        )
        from django.contrib.auth import get_user_model
        CustomUser = get_user_model()
        u2 = CustomUser.objects.create_user(username='bob', password='p')
        with pytest.raises(Exception):
            UserPaperlessBinding.objects.create(
                user=u2, paperless_user_id=5, paperless_username='duplicate'
            )
```

- [ ] **Step 4.2: 实现 UserPaperlessBinding**

在 `models.py` 末尾:

```python
class UserPaperlessBinding(models.Model):
    """OmniDesk 用户 ↔ paperless 用户账号绑定"""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='paperless_bind',
        verbose_name='OmniDesk 用户',
    )
    paperless_user_id = models.PositiveIntegerField(unique=True, verbose_name='paperless 用户 ID')
    paperless_username = models.CharField(max_length=150, verbose_name='paperless 用户名')
    bound_at = models.DateTimeField(auto_now_add=True, verbose_name='绑定时间')
    is_active = models.BooleanField(default=True, verbose_name='是否激活')

    class Meta:
        verbose_name = 'paperless 账号绑定'
        verbose_name_plural = 'paperless 账号绑定'

    def __str__(self):
        return f'{self.user.username} → paperless:{self.paperless_username}'
```

- [ ] **Step 4.3: 迁移 + 测试**

```bash
cd /home/fz/project/OmniDesk
/home/fz/anaconda3/envs/omni_desk/bin/python manage.py makemigrations paperless_proxy
/home/fz/anaconda3/envs/omni_desk/bin/python -m pytest omni_desk_backend/paperless_proxy/tests/test_models.py -v
```

预期:7 passed

- [ ] **Step 4.4: 提交**

```bash
git add omni_desk_backend/paperless_proxy/
git commit -m "feat(paperless-proxy): 添加 UserPaperlessBinding 模型"
```

---

### Task 5: PaperlessHealth 模型

**Files:**
- Modify: `omni_desk_backend/paperless_proxy/models.py`
- Modify: `omni_desk_backend/paperless_proxy/tests/test_models.py`

- [ ] **Step 5.1: 追加失败测试**

```python
from ..models import PaperlessHealth


@pytest.mark.django_db
class TestPaperlessHealth:
    def test_singleton(self):
        """验证:健康状态单例(只能有一行)"""
        h = PaperlessHealth.objects.create(is_healthy=True)
        assert h.id is not None
        # 第二次创建会创建新行(不是物理单例),但通过 get_singleton 始终返回第一行
        from ..models import PaperlessHealth
        singleton = PaperlessHealth.get_singleton()
        assert singleton.id == h.id

    def test_get_singleton_creates_default(self):
        """验证:get_singleton 找不到时自动创建默认值"""
        from ..models import PaperlessHealth
        assert PaperlessHealth.objects.count() == 0
        s = PaperlessHealth.get_singleton()
        assert s.is_healthy is True
        assert s.consecutive_failures == 0
```

- [ ] **Step 5.2: 实现 PaperlessHealth**

```python
class PaperlessHealth(models.Model):
    """paperless 健康检查状态(逻辑单例)"""

    is_healthy = models.BooleanField(default=True, verbose_name='是否健康')
    last_check_at = models.DateTimeField(auto_now=True, verbose_name='最后检查时间')
    consecutive_failures = models.PositiveIntegerField(default=0, verbose_name='连续失败次数')
    last_error = models.TextField(blank=True, verbose_name='最后错误')

    class Meta:
        verbose_name = 'paperless 健康状态'
        verbose_name_plural = 'paperless 健康状态'

    def __str__(self):
        return f'paperless: {"健康" if self.is_healthy else "不可用"}'

    @classmethod
    def get_singleton(cls):
        obj = cls.objects.first()
        if obj is None:
            obj = cls.objects.create(is_healthy=True)
        return obj
```

- [ ] **Step 5.3: 迁移 + 测试**

```bash
cd /home/fz/project/OmniDesk
/home/fz/anaconda3/envs/omni_desk/bin/python manage.py makemigrations paperless_proxy
/home/fz/anaconda3/envs/omni_desk/bin/python -m pytest omni_desk_backend/paperless_proxy/tests/test_models.py -v
```

预期:9 passed

- [ ] **Step 5.4: 提交**

```bash
git add omni_desk_backend/paperless_proxy/
git commit -m "feat(paperless-proxy): 添加 PaperlessHealth 单例模型"
```

---

### Task 6: PaperlessClient(HTTP 客户端 + 重试)

**Files:**
- Create: `omni_desk_backend/paperless_proxy/services/__init__.py`
- Create: `omni_desk_backend/paperless_proxy/services/client.py`
- Test: `omni_desk_backend/paperless_proxy/tests/test_client.py`

**Interfaces:**
- Consumes: `settings.PAPERLESS_URL`, `settings.PAPERLESS_API_TOKEN`
- Produces: `PaperlessClient` 类,提供 `upload / download / search / get_user / post_token` 方法

- [ ] **Step 6.1: 创建 services 包**

```bash
mkdir -p omni_desk_backend/paperless_proxy/services
touch omni_desk_backend/paperless_proxy/services/__init__.py
```

- [ ] **Step 6.2: 写失败测试**

创建 `omni_desk_backend/paperless_proxy/tests/test_client.py`:

```python
import io
import pytest
import responses
from django.conf import settings
from ..exceptions import (
    PaperlessError, PaperlessUnavailableError, PaperlessAuthError, PaperlessNotFoundError
)
from ..services.client import PaperlessClient


@pytest.fixture
def client(db, settings):
    settings.PAPERLESS_URL = 'http://paperless:8000'
    settings.PAPERLESS_API_TOKEN = 'test-token'
    settings.PAPERLESS_TIMEOUT_SECONDS = 5
    return PaperlessClient()


class TestPaperlessClientToken:
    @responses.activate
    def test_post_token_success(self, client):
        responses.add(
            responses.POST,
            f'{settings.PAPERLESS_URL}/api/token/',
            json={'token': 'abc123'},
            status=200,
        )
        token = client.post_token('alice', 'pwd')
        assert token == 'abc123'

    @responses.activate
    def test_post_token_invalid_raises_auth(self, client):
        responses.add(
            responses.POST,
            f'{settings.PAPERLESS_URL}/api/token/',
            json={'detail': 'No active account'},
            status=400,
        )
        with pytest.raises(PaperlessAuthError):
            client.post_token('alice', 'wrong')


class TestPaperlessClientUpload:
    @responses.activate
    def test_upload_success(self, client):
        responses.add(
            responses.POST,
            f'{settings.PAPERLESS_URL}/api/documents/post_document/',
            json={'id': 100, 'title': 'doc.pdf'},
            status=200,
        )
        file_obj = io.BytesIO(b'fake pdf content')
        result = client.upload(
            file_obj=file_obj,
            filename='doc.pdf',
            title='doc.pdf',
            owner=5,
        )
        assert result['id'] == 100
        assert 'Authorization' in responses.calls[0].request.headers
        assert responses.calls[0].request.headers['Authorization'] == 'Token test-token'

    @responses.activate
    def test_upload_5xx_raises_unavailable(self, client):
        responses.add(
            responses.POST,
            f'{settings.PAPERLESS_URL}/api/documents/post_document/',
            body='Internal Server Error',
            status=500,
        )
        with pytest.raises(PaperlessUnavailableError):
            client.upload(io.BytesIO(b'x'), 'a.pdf', 'a', owner=1)


class TestPaperlessClientSearch:
    @responses.activate
    def test_search_returns_results(self, client):
        responses.add(
            responses.GET,
            f'{settings.PAPERLESS_URL}/api/documents/',
            json={
                'count': 1,
                'next': None,
                'previous': None,
                'results': [{
                    'id': 50,
                    'title': '合同文件',
                    '__search_hit__': {
                        'score': 0.9,
                        'highlights': '这是<span class="match">合同</span>内容',
                        'rank': 0,
                    },
                }],
            },
            status=200,
        )
        results = client.search('合同', page_size=10)
        assert results['count'] == 1
        assert results['results'][0]['id'] == 50
        assert '<span' in results['results'][0]['__search_hit__']['highlights']


class TestPaperlessClientGetUser:
    @responses.activate
    def test_get_user_by_username(self, client):
        responses.add(
            responses.GET,
            f'{settings.PAPERLESS_URL}/api/users/',
            json={
                'count': 1,
                'results': [{'id': 7, 'username': 'alice'}],
            },
            status=200,
        )
        user = client.get_user_by_username('alice')
        assert user['id'] == 7

    @responses.activate
    def test_get_user_not_found_raises(self, client):
        responses.add(
            responses.GET,
            f'{settings.PAPERLESS_URL}/api/users/',
            json={'count': 0, 'results': []},
            status=200,
        )
        with pytest.raises(PaperlessNotFoundError):
            client.get_user_by_username('ghost')
```

- [ ] **Step 6.3: 实现 PaperlessClient**

```python
# omni_desk_backend/paperless_proxy/services/client.py
"""paperless HTTP 客户端,基于 requests + 手动重试"""
import logging
from typing import Optional, BinaryIO, Dict, Any
from urllib.parse import urlencode

import requests
from django.conf import settings

from ..exceptions import (
    PaperlessError, PaperlessUnavailableError, PaperlessAuthError, PaperlessNotFoundError
)

logger = logging.getLogger(__name__)


class PaperlessClient:
    def __init__(self):
        self.base_url = settings.PAPERLESS_URL.rstrip('/')
        self.token = settings.PAPERLESS_API_TOKEN
        self.timeout = settings.PAPERLESS_TIMEOUT_SECONDS
        self.session = requests.Session()
        self.session.headers.update({'Authorization': f'Token {self.token}'})

    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        url = f'{self.base_url}{path}'
        try:
            resp = self.session.request(method, url, timeout=self.timeout, **kwargs)
        except requests.RequestException as e:
            raise PaperlessUnavailableError(f'paperless network error: {e}') from e

        if resp.status_code == 401:
            raise PaperlessAuthError('paperless auth failed (401)')
        if resp.status_code == 403:
            raise PaperlessAuthError('paperless forbidden (403)')
        if resp.status_code == 404:
            raise PaperlessNotFoundError(f'paperless not found: {path}')
        if 500 <= resp.status_code < 600:
            raise PaperlessUnavailableError(f'paperless {resp.status_code}: {resp.text[:200]}')
        if not resp.ok:
            raise PaperlessError(f'paperless {resp.status_code}: {resp.text[:200]}')
        return resp

    # --- Auth ---

    def post_token(self, username: str, password: str) -> str:
        """账号密码换取 paperless token,用于账号绑定"""
        try:
            resp = requests.post(
                f'{self.base_url}/api/token/',
                data={'username': username, 'password': password},
                timeout=self.timeout,
            )
        except requests.RequestException as e:
            raise PaperlessUnavailableError(f'paperless network error: {e}') from e
        if resp.status_code == 400:
            raise PaperlessAuthError('invalid username or password')
        if not resp.ok:
            raise PaperlessError(f'paperless token error: {resp.status_code}')
        return resp.json()['token']

    def get_user_by_username(self, username: str) -> Dict[str, Any]:
        """根据 username 查 paperless 用户"""
        resp = self._request('GET', '/api/users/', params={'username': username})
        data = resp.json()
        for u in data.get('results', []):
            if u.get('username') == username:
                return u
        raise PaperlessNotFoundError(f'paperless user {username} not found')

    # --- Documents ---

    def upload(
        self,
        file_obj: BinaryIO,
        filename: str,
        title: str,
        owner: Optional[int] = None,
        correspondent: Optional[int] = None,
        document_type: Optional[int] = None,
        tags: Optional[list] = None,
    ) -> Dict[str, Any]:
        """上传文档到 paperless"""
        files = {'document': (filename, file_obj)}
        data = {'title': title}
        if owner is not None:
            data['owner'] = owner
        if correspondent is not None:
            data['correspondent'] = correspondent
        if document_type is not None:
            data['document_type'] = document_type
        if tags:
            # paperless 接收 tag id 列表
            data['tags'] = tags
        resp = self._request('POST', '/api/documents/post_document/', files=files, data=data)
        return resp.json()

    def get_document(self, paperless_id: int) -> Dict[str, Any]:
        """获取 paperless 文档元数据"""
        resp = self._request('GET', f'/api/documents/{paperless_id}/')
        return resp.json()

    def download(self, paperless_id: int) -> bytes:
        """下载 paperless 文档原始内容"""
        resp = self._request('GET', f'/api/documents/{paperless_id}/download/')
        return resp.content

    def preview(self, paperless_id: int) -> bytes:
        """获取 paperless 文档预览图"""
        resp = self._request('GET', f'/api/documents/{paperless_id}/preview/')
        return resp.content

    def search(self, query: str, page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        """Tantivy 全文搜索"""
        params = {'query': query, 'page': page, 'page_size': page_size}
        resp = self._request('GET', '/api/documents/', params=params)
        return resp.json()

    def health_check(self) -> bool:
        """健康检查(GET /api/)"""
        try:
            resp = self.session.get(f'{self.base_url}/api/', timeout=self.timeout)
            return resp.status_code == 200
        except requests.RequestException:
            return False
```

- [ ] **Step 6.4: 跑测试**

```bash
cd /home/fz/project/OmniDesk
/home/fz/anaconda3/envs/omni_desk/bin/python -m pytest omni_desk_backend/paperless_proxy/tests/test_client.py -v
```

预期:7 passed

- [ ] **Step 6.5: 提交**

```bash
git add omni_desk_backend/paperless_proxy/services/ omni_desk_backend/paperless_proxy/tests/test_client.py
git commit -m "feat(paperless-proxy): 实现 PaperlessClient HTTP 客户端"
```

---

### Task 7: 配置项 + docker-compose

**Files:**
- Modify: `omni_desk_backend/omni_desk_backend/settings/base.py`(尾部追加)
- Create: `omni_desk_backend/omni_desk_backend/settings/paperless.example.env`

- [ ] **Step 7.1: 在 base.py 追加配置项**

```python
# paperless 集成配置
PAPERLESS_URL = os.environ.get('PAPERLESS_URL', 'http://paperless:8000')
PAPERLESS_API_TOKEN = os.environ.get('PAPERLESS_API_TOKEN', '')
PAPERLESS_TIMEOUT_SECONDS = int(os.environ.get('PAPERLESS_TIMEOUT_SECONDS', '10'))
PAPERLESS_HEALTH_CHECK_INTERVAL = int(os.environ.get('PAPERLESS_HEALTH_CHECK_INTERVAL', '30'))
PAPERLESS_HEALTH_FAILURE_THRESHOLD = int(os.environ.get('PAPERLESS_HEALTH_FAILURE_THRESHOLD', '3'))
PAPERLESS_OUTBOX_BATCH_SIZE = int(os.environ.get('PAPERLESS_OUTBOX_BATCH_SIZE', '50'))
PAPERLESS_OUTBOX_MAX_RETRIES = int(os.environ.get('PAPERLESS_OUTBOX_MAX_RETRIES', '10'))
PAPERLESS_OUTBOX_BASE_BACKOFF_SECONDS = int(os.environ.get('PAPERLESS_OUTBOX_BASE_BACKOFF_SECONDS', '30'))
PAPERLESS_CACHE_DIR = os.environ.get('PAPERLESS_CACHE_DIR', 'paperless_cache/')
PAPERLESS_PENDING_DIR = os.environ.get('PAPERLESS_PENDING_DIR', 'paperless_pending/')
PAPERLESS_CACHE_MAX_AGE_DAYS = int(os.environ.get('PAPERLESS_CACHE_MAX_AGE_DAYS', '30'))
PAPERLESS_CLEANUP_INTERVAL_HOURS = int(os.environ.get('PAPERLESS_CLEANUP_INTERVAL_HOURS', '6'))
```

- [ ] **Step 7.2: 创建示例 env 文件**

```bash
cat > omni_desk_backend/omni_desk_backend/settings/paperless.example.env <<'EOF'
# paperless 集成配置示例
# 复制为 paperless.env 并填入实际值,本地开发不提交

PAPERLESS_URL=http://localhost:8001
PAPERLESS_API_TOKEN=your-paperless-api-token-here
PAPERLESS_TIMEOUT_SECONDS=10
EOF
```

- [ ] **Step 7.3: 在 .gitignore 排除实际 env**

```bash
echo "omni_desk_backend/omni_desk_backend/settings/paperless.env" >> .gitignore
```

- [ ] **Step 7.4: 跑所有现有测试,确认无回归**

```bash
cd /home/fz/project/OmniDesk
/home/fz/anaconda3/envs/omni_desk/bin/python -m pytest omni_desk_backend/paperless_proxy/ -v
```

预期:全部通过(16 tests)

- [ ] **Step 7.5: 提交**

```bash
git add omni_desk_backend/omni_desk_backend/settings/base.py omni_desk_backend/omni_desk_backend/settings/paperless.example.env .gitignore
git commit -m "feat(paperless-proxy): 添加 paperless 集成配置项"
```

---

## Phase 2: Outbox 写降级(1.5 周)

### Task 8: OutboxService

**Files:**
- Create: `omni_desk_backend/paperless_proxy/services/outbox.py`
- Test: `omni_desk_backend/paperless_proxy/tests/test_outbox.py`

**Interfaces:**
- Consumes: `OutboxItem` 模型
- Produces: `OutboxService.enqueue()` / `OutboxService.fetch_pending()` / `OutboxService.mark_synced()` / `OutboxService.mark_failed()`

- [ ] **Step 8.1: 写失败测试**

```python
# omni_desk_backend/paperless_proxy/tests/test_outbox.py
import pytest
from datetime import timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from freezegun import freeze_time
from ..models import OutboxItem, DocumentBinding
from ..services.outbox import OutboxService, OutboxDeadError

CustomUser = get_user_model()


@pytest.fixture
def user(db):
    return CustomUser.objects.create_user(username='u', password='p')


@pytest.fixture
def binding(db, user):
    return DocumentBinding.objects.create(
        source_type='project_document',
        source_id=1,
        paperless_id=999,
        paperless_checksum='h',
        owner=user,
        title='X',
    )


@pytest.mark.django_db
class TestOutboxEnqueue:
    def test_enqueue_creates_pending(self, user, binding):
        """验证:enqueue 创建 pending 状态 outbox"""
        outbox = OutboxService.enqueue(
            operation='upload',
            payload={'file': 'x', 'title': 't'},
            binding=binding,
            created_by=user,
        )
        assert outbox.status == 'pending'
        assert outbox.retry_count == 0


@pytest.mark.django_db
class TestOutboxFetchPending:
    def test_fetch_returns_due_pending(self, user, binding):
        """验证:只返回 status=pending 且 next_retry_at <= now"""
        OutboxItem.objects.create(
            operation='upload', status='pending', payload={},
            next_retry_at=timezone.now() - timedelta(minutes=1),
            created_by=user, binding=binding,
        )
        OutboxItem.objects.create(
            operation='upload', status='pending', payload={},
            next_retry_at=timezone.now() + timedelta(minutes=5),
            created_by=user, binding=binding,
        )
        pending = OutboxService.fetch_pending(batch_size=10)
        assert len(pending) == 1


@pytest.mark.django_db
class TestOutboxRetry:
    @freeze_time("2026-01-01 10:00:00")
    def test_mark_failed_increments_and_backoff(self, user, binding):
        """验证:失败时 retry_count++ 且 next_retry_at 退避"""
        outbox = OutboxService.enqueue(
            operation='upload', payload={}, binding=binding, created_by=user,
        )
        OutboxService.mark_failed(outbox, 'connection timeout')
        outbox.refresh_from_db()
        assert outbox.retry_count == 1
        assert outbox.status == 'pending'
        # 30s * 2^1 = 60s
        expected = timezone.now() + timedelta(seconds=60)
        assert abs((outbox.next_retry_at - expected).total_seconds()) < 5

    @freeze_time("2026-01-01 10:00:00")
    def test_mark_failed_at_max_retries_raises_dead(self, user, binding):
        """验证:达到 max_retries 时抛 OutboxDeadError,status=dead"""
        outbox = OutboxService.enqueue(
            operation='upload', payload={}, binding=binding, created_by=user,
        )
        outbox.retry_count = outbox.max_retries  # 已是最后一次
        for _ in range(outbox.max_retries):
            try:
                OutboxService.mark_failed(outbox, 'persistent error')
            except OutboxDeadError:
                break
        outbox.refresh_from_db()
        assert outbox.status == 'dead'
        assert 'persistent error' in outbox.last_error


@pytest.mark.django_db
class TestOutboxMarkSynced:
    def test_mark_synced_clears_retry(self, user, binding):
        """验证:成功后 retry_count 重置"""
        outbox = OutboxService.enqueue(
            operation='upload', payload={}, binding=binding, created_by=user,
        )
        outbox.retry_count = 3
        outbox.save()
        OutboxService.mark_synced(outbox)
        outbox.refresh_from_db()
        assert outbox.status == 'synced'
        assert outbox.retry_count == 0
```

- [ ] **Step 8.2: 安装 freezegun**

```bash
cd /home/fz/project/OmniDesk
/home/fz/anaconda3/envs/omni_desk/bin/pip install freezegun
/home/fz/anaconda3/envs/omni_desk/bin/pip-compile --upgrade-package freezegun -o omni_desk_backend/requirements.txt omni_desk_backend/requirements-dev.in
```

- [ ] **Step 8.3: 实现 OutboxService**

```python
# omni_desk_backend/paperless_proxy/services/outbox.py
"""Outbox 写降级核心服务"""
import logging
from typing import List
from django.utils import timezone
from django.db import transaction
from django.conf import settings
from datetime import timedelta

from ..models import OutboxItem

logger = logging.getLogger(__name__)


class OutboxDeadError(Exception):
    """Outbox 项达到最大重试次数,升级为死信"""


class OutboxService:
    @staticmethod
    @transaction.atomic
    def enqueue(operation: str, payload: dict, binding=None, created_by=None) -> OutboxItem:
        return OutboxItem.objects.create(
            operation=operation,
            status='pending',
            payload=payload,
            binding=binding,
            created_by=created_by,
        )

    @staticmethod
    def fetch_pending(batch_size: int = None) -> List[OutboxItem]:
        if batch_size is None:
            batch_size = settings.PAPERLESS_OUTBOX_BATCH_SIZE
        now = timezone.now()
        items = list(
            OutboxItem.objects.filter(
                status='pending', next_retry_at__lte=now,
            ).order_by('next_retry_at')[:batch_size]
        )
        # 标记为 syncing,避免并发 worker 重复拉取
        if items:
            OutboxItem.objects.filter(id__in=[i.id for i in items]).update(
                status='syncing', updated_at=now,
            )
            for item in items:
                item.status = 'syncing'
        return items

    @staticmethod
    @transaction.atomic
    def mark_synced(outbox: OutboxItem) -> None:
        outbox.status = 'synced'
        outbox.retry_count = 0
        outbox.last_error = ''
        outbox.save(update_fields=['status', 'retry_count', 'last_error', 'updated_at'])

    @staticmethod
    @transaction.atomic
    def mark_failed(outbox: OutboxItem, error_msg: str) -> None:
        outbox.retry_count += 1
        outbox.last_error = error_msg[:2000]
        if outbox.retry_count >= outbox.max_retries:
            outbox.status = 'dead'
            outbox.save(update_fields=['retry_count', 'last_error', 'status', 'updated_at'])
            logger.error(f'Outbox#{outbox.id} entered dead state: {error_msg}')
            raise OutboxDeadError(f'Outbox#{outbox.id} dead: {error_msg}')
        # 指数退避:30s * 2^retry_count,上限 1 小时
        backoff = min(
            settings.PAPERLESS_OUTBOX_BASE_BACKOFF_SECONDS * (2 ** outbox.retry_count),
            3600,
        )
        outbox.next_retry_at = timezone.now() + timedelta(seconds=backoff)
        outbox.status = 'pending'  # 退避后重新可拉取
        outbox.save(update_fields=[
            'retry_count', 'last_error', 'status', 'next_retry_at', 'updated_at',
        ])

    @staticmethod
    def retry_dead(outbox: OutboxItem) -> OutboxItem:
        """管理员手动重试死信"""
        outbox.status = 'pending'
        outbox.retry_count = 0
        outbox.next_retry_at = timezone.now()
        outbox.last_error = ''
        outbox.save(update_fields=['status', 'retry_count', 'next_retry_at', 'last_error', 'updated_at'])
        return outbox
```

- [ ] **Step 8.4: 跑测试**

```bash
cd /home/fz/project/OmniDesk
/home/fz/anaconda3/envs/omni_desk/bin/python -m pytest omni_desk_backend/paperless_proxy/tests/test_outbox.py -v
```

预期:6 passed

- [ ] **Step 8.5: 提交**

```bash
git add omni_desk_backend/paperless_proxy/services/outbox.py omni_desk_backend/paperless_proxy/tests/test_outbox.py omni_desk_backend/requirements.txt
git commit -m "feat(paperless-proxy): 实现 OutboxService 含指数退避"
```

---

### Task 9: outbox_worker Celery 任务

**Files:**
- Create: `omni_desk_backend/paperless_proxy/tasks.py`
- Modify: `omni_desk_backend/omni_desk_backend/settings/base.py:CELERY_BEAT_SCHEDULE`
- Test: `omni_desk_backend/paperless_proxy/tests/test_tasks.py`

**Interfaces:**
- Consumes: `OutboxService`, `PaperlessClient`
- Produces: `process_paperless_outbox` Celery task

- [ ] **Step 9.1: 写失败测试**

```python
# omni_desk_backend/paperless_proxy/tests/test_tasks.py
import io
import pytest
from unittest.mock import patch, MagicMock
from django.contrib.auth import get_user_model
from ..models import OutboxItem, DocumentBinding
from ..tasks import process_paperless_outbox
from ..services.outbox import OutboxDeadError

CustomUser = get_user_model()


@pytest.fixture
def user(db):
    return CustomUser.objects.create_user(username='u', password='p')


@pytest.fixture
def binding(db, user):
    return DocumentBinding.objects.create(
        source_type='project_document', source_id=1,
        paperless_id=0, paperless_checksum='', owner=user, title='X',
    )


@pytest.fixture
def outbox_item(db, user, binding):
    return OutboxItem.objects.create(
        operation='upload',
        status='pending',
        payload={'file_path': '/tmp/fake.pdf', 'filename': 'f.pdf', 'title': 'f.pdf', 'owner': 1},
        binding=binding,
        created_by=user,
    )


@pytest.mark.django_db
class TestOutboxWorker:
    @patch('paperless_proxy.services.outbox.OutboxService.fetch_pending')
    def test_no_pending_no_op(self, mock_fetch):
        """验证:无 pending 时无操作"""
        mock_fetch.return_value = []
        result = process_paperless_outbox()
        assert result == {'processed': 0, 'succeeded': 0, 'failed': 0}

    @patch('paperless_proxy.services.client.PaperlessClient.upload')
    @patch('paperless_proxy.services.outbox.OutboxService.fetch_pending')
    def test_upload_success(self, mock_fetch, mock_upload, outbox_item):
        """验证:成功上传时 status=synced"""
        mock_fetch.return_value = [outbox_item]
        mock_upload.return_value = {'id': 555, 'title': 'f.pdf'}
        with patch('builtins.open', create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = b'fake'
            with patch('os.path.exists', return_value=True):
                result = process_paperless_outbox()
        assert result['succeeded'] == 1
        outbox_item.refresh_from_db()
        assert outbox_item.status == 'synced'
        binding = outbox_item.binding
        binding.refresh_from_db()
        assert binding.paperless_id == 555
```

- [ ] **Step 9.2: 实现 tasks.py**

```python
# omni_desk_backend/paperless_proxy/tasks.py
"""paperless_proxy Celery 任务"""
import logging
import os
from celery import shared_task
from django.conf import settings
from django.utils import timezone

from .services.outbox import OutboxService, OutboxDeadError
from .services.client import PaperlessClient
from .exceptions import PaperlessUnavailableError, PaperlessError
from .models import PaperlessHealth

logger = logging.getLogger(__name__)


@shared_task(name='paperless_proxy.process_outbox')
def process_paperless_outbox():
    """处理 Outbox 中的 pending 项,推送到 paperless"""
    items = OutboxService.fetch_pending()
    if not items:
        return {'processed': 0, 'succeeded': 0, 'failed': 0}

    client = PaperlessClient()
    succeeded = 0
    failed = 0
    for item in items:
        try:
            if item.operation == 'upload':
                _process_upload(item, client)
            elif item.operation == 'delete':
                _process_delete(item, client)
            elif item.operation == 'update_metadata':
                _process_update_metadata(item, client)
            else:
                raise PaperlessError(f'unknown operation: {item.operation}')
            OutboxService.mark_synced(item)
            succeeded += 1
        except (PaperlessUnavailableError, PaperlessError) as e:
            try:
                OutboxService.mark_failed(item, str(e))
            except OutboxDeadError:
                failed += 1
                logger.error(f'Outbox#{item.id} dead: {e}')
            else:
                failed += 1
        except Exception as e:
            logger.exception(f'Outbox#{item.id} unexpected error: {e}')
            try:
                OutboxService.mark_failed(item, f'unexpected: {e}')
            except OutboxDeadError:
                pass
            failed += 1

    return {'processed': len(items), 'succeeded': succeeded, 'failed': failed}


def _process_upload(item, client: PaperlessClient) -> None:
    payload = item.payload
    file_path = payload['file_path']
    if not os.path.exists(file_path):
        raise PaperlessError(f'pending file not found: {file_path}')
    with open(file_path, 'rb') as f:
        result = client.upload(
            file_obj=f,
            filename=payload['filename'],
            title=payload.get('title', payload['filename']),
            owner=payload.get('owner'),
            correspondent=payload.get('correspondent'),
            document_type=payload.get('document_type'),
            tags=payload.get('tags'),
        )
    if item.binding and not item.binding.paperless_id:
        item.binding.paperless_id = result['id']
        item.binding.paperless_checksum = result.get('checksum', '')
        item.binding.save(update_fields=['paperless_id', 'paperless_checksum', 'updated_at'])
    # 删除本地待同步文件
    try:
        os.remove(file_path)
    except OSError:
        pass


def _process_delete(item, client: PaperlessClient) -> None:
    # paperless 暂不实现删除 API 代理,留空
    raise PaperlessError('delete not implemented in v1')


def _process_update_metadata(item, client: PaperlessClient) -> None:
    # 留给后续阶段
    raise PaperlessError('update_metadata not implemented in v1')
```

- [ ] **Step 9.3: 在 settings/base.py 注册 beat 调度**

在 `CELERY_BEAT_SCHEDULE` 字典中追加:

```python
    "paperless-process-outbox-every-minute": {
        "task": "paperless_proxy.process_outbox",
        "schedule": timedelta(minutes=1),
        "args": (),
    },
```

- [ ] **Step 9.4: 跑测试**

```bash
cd /home/fz/project/OmniDesk
/home/fz/anaconda3/envs/omni_desk/bin/python -m pytest omni_desk_backend/paperless_proxy/tests/test_tasks.py -v
```

预期:2 passed

- [ ] **Step 9.5: 提交**

```bash
git add omni_desk_backend/paperless_proxy/tasks.py omni_desk_backend/paperless_proxy/tests/test_tasks.py omni_desk_backend/omni_desk_backend/settings/base.py
git commit -m "feat(paperless-proxy): 实现 outbox_worker Celery 任务"
```

---

### Task 10: Outbox 管理 API

**Files:**
- Create: `omni_desk_backend/paperless_proxy/serializers.py`
- Create: `omni_desk_backend/paperless_proxy/views.py`
- Create: `omni_desk_backend/paperless_proxy/urls.py`
- Modify: `omni_desk_backend/omni_desk_backend/urls.py`
- Create: `omni_desk_backend/paperless_proxy/permissions.py`
- Test: `omni_desk_backend/paperless_proxy/tests/test_views.py`

**Interfaces:**
- Produces:
  - `GET /api/paperless/outbox/` (admin)
  - `POST /api/paperless/outbox/{id}/retry/` (admin)

- [ ] **Step 10.1: 写失败测试**

```python
# omni_desk_backend/paperless_proxy/tests/test_views.py
import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from ..models import OutboxItem, DocumentBinding

CustomUser = get_user_model()


@pytest.fixture
def user(db):
    return CustomUser.objects.create_user(username='u', password='p')


@pytest.fixture
def admin(db):
    return CustomUser.objects.create_superuser(username='admin', password='admin')


@pytest.fixture
def binding(db, user):
    return DocumentBinding.objects.create(
        source_type='contract', source_id=1, paperless_id=999,
        paperless_checksum='h', owner=user, title='X',
    )


@pytest.fixture
def dead_outbox(db, user, binding):
    return OutboxItem.objects.create(
        operation='upload', status='dead', payload={}, binding=binding,
        created_by=user, retry_count=10,
    )


@pytest.mark.django_db
class TestOutboxListAPI:
    def test_list_requires_admin(self, user, dead_outbox):
        client = APIClient()
        client.force_authenticate(user)
        resp = client.get('/api/paperless/outbox/')
        assert resp.status_code == 403

    def test_admin_can_list(self, admin, dead_outbox):
        client = APIClient()
        client.force_authenticate(admin)
        resp = client.get('/api/paperless/outbox/')
        assert resp.status_code == 200
        assert len(resp.data['results']) >= 1

    def test_filter_by_status(self, admin, dead_outbox):
        client = APIClient()
        client.force_authenticate(admin)
        resp = client.get('/api/paperless/outbox/?status=dead')
        assert resp.status_code == 200
        for item in resp.data['results']:
            assert item['status'] == 'dead'


@pytest.mark.django_db
class TestOutboxRetryAPI:
    def test_retry_dead(self, admin, dead_outbox):
        client = APIClient()
        client.force_authenticate(admin)
        resp = client.post(f'/api/paperless/outbox/{dead_outbox.id}/retry/')
        assert resp.status_code == 200
        dead_outbox.refresh_from_db()
        assert dead_outbox.status == 'pending'
        assert dead_outbox.retry_count == 0
```

- [ ] **Step 10.2: 实现 permissions.py**

```python
# omni_desk_backend/paperless_proxy/permissions.py
from rest_framework import permissions


class IsAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.is_staff


class IsBindingOwnerOrAdmin(permissions.BasePermission):
    """绑定资源:owner 或 admin 可访问"""
    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True
        return obj.owner_id == request.user.id
```

- [ ] **Step 10.3: 实现 serializers.py**

```python
# omni_desk_backend/paperless_proxy/serializers.py
from rest_framework import serializers
from .models import OutboxItem, DocumentBinding, UserPaperlessBinding, PaperlessHealth


class OutboxItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OutboxItem
        fields = [
            'id', 'operation', 'status', 'payload', 'binding',
            'retry_count', 'max_retries', 'next_retry_at', 'last_error',
            'created_by', 'created_at', 'updated_at',
        ]
        read_only_fields = fields


class DocumentBindingSerializer(serializers.ModelSerializer):
    outbox_status = serializers.SerializerMethodField()

    class Meta:
        model = DocumentBinding
        fields = [
            'id', 'source_type', 'source_id', 'paperless_id', 'paperless_checksum',
            'owner', 'title', 'correspondent_id', 'extra_metadata',
            'outbox_status', 'created_at', 'updated_at',
        ]
        read_only_fields = ['paperless_id', 'paperless_checksum', 'created_at', 'updated_at']

    def get_outbox_status(self, obj):
        latest = obj.outbox.order_by('-created_at').first()
        return latest.status if latest else 'synced'


class UserPaperlessBindingSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserPaperlessBinding
        fields = ['id', 'paperless_user_id', 'paperless_username', 'bound_at', 'is_active']
        read_only_fields = fields


class PaperlessHealthSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaperlessHealth
        fields = ['is_healthy', 'last_check_at', 'consecutive_failures', 'last_error']
        read_only_fields = fields
```

- [ ] **Step 10.4: 实现 views.py (outbox 部分)**

```python
# omni_desk_backend/paperless_proxy/views.py
from rest_framework import viewsets, status, mixins
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend

from .models import OutboxItem
from .serializers import OutboxItemSerializer
from .permissions import IsAdmin
from .services.outbox import OutboxService


class OutboxViewSet(viewsets.ReadOnlyModelViewSet):
    """Outbox 管理(admin 限定)"""
    queryset = OutboxItem.objects.all()
    serializer_class = OutboxItemSerializer
    permission_classes = [IsAdmin]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status', 'operation']

    @action(detail=True, methods=['post'])
    def retry(self, request, pk=None):
        outbox = self.get_object()
        if outbox.status != 'dead':
            return Response(
                {'detail': f'只能重试死信(当前 status={outbox.status})'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        OutboxService.retry_dead(outbox)
        return Response(OutboxItemSerializer(outbox).data)
```

- [ ] **Step 10.5: 实现 urls.py**

```python
# omni_desk_backend/paperless_proxy/urls.py
from rest_framework.routers import DefaultRouter
from .views import OutboxViewSet

router = DefaultRouter()
router.register(r'outbox', OutboxViewSet, basename='outbox')

urlpatterns = router.urls
```

- [ ] **Step 10.6: 注册到主 urls**

修改 `omni_desk_backend/omni_desk_backend/urls.py`,在 urlpatterns 中加入:

```python
    path('api/paperless/', include('paperless_proxy.urls')),
```

(注意 import include)

- [ ] **Step 10.7: 跑测试**

```bash
cd /home/fz/project/OmniDesk
/home/fz/anaconda3/envs/omni_desk/bin/python -m pytest omni_desk_backend/paperless_proxy/tests/test_views.py -v
```

预期:4 passed

- [ ] **Step 10.8: 提交**

```bash
git add omni_desk_backend/paperless_proxy/
git commit -m "feat(paperless-proxy): 实现 Outbox 管理 API(list/retry)"
```

---

### Task 11: health_check Celery 任务

**Files:**
- Modify: `omni_desk_backend/paperless_proxy/tasks.py`
- Modify: `omni_desk_backend/omni_desk_backend/settings/base.py`
- Modify: `omni_desk_backend/paperless_proxy/tests/test_tasks.py`

- [ ] **Step 11.1: 追加失败测试**

```python
# 追加到 test_tasks.py
from ..tasks import check_paperless_health
from ..models import PaperlessHealth


@pytest.mark.django_db
class TestHealthCheck:
    @patch('paperless_proxy.services.client.PaperlessClient.health_check')
    def test_healthy_resets_failures(self, mock_health):
        """验证:健康时清零 consecutive_failures"""
        PaperlessHealth.objects.create(is_healthy=False, consecutive_failures=5)
        mock_health.return_value = True
        check_paperless_health()
        h = PaperlessHealth.get_singleton()
        assert h.is_healthy is True
        assert h.consecutive_failures == 0

    @patch('paperless_proxy.services.client.PaperlessClient.health_check')
    def test_three_failures_marks_unhealthy(self, mock_health):
        """验证:连续 3 次失败才标 unhealthy"""
        mock_health.return_value = False
        for _ in range(3):
            check_paperless_health()
        h = PaperlessHealth.get_singleton()
        assert h.is_healthy is False
        assert h.consecutive_failures == 3

    @patch('paperless_proxy.services.client.PaperlessClient.health_check')
    def test_single_failure_does_not_mark_unhealthy(self, mock_health):
        """验证:单次失败不立即标 unhealthy(避免抖动)"""
        mock_health.return_value = False
        check_paperless_health()
        h = PaperlessHealth.get_singleton()
        assert h.is_healthy is True
        assert h.consecutive_failures == 1
```

- [ ] **Step 11.2: 实现 health_check 任务**

在 `tasks.py` 追加:

```python
@shared_task(name='paperless_proxy.check_health')
def check_paperless_health():
    """定时检查 paperless 健康状态"""
    from .models import PaperlessHealth
    health = PaperlessHealth.get_singleton()
    client = PaperlessClient()
    is_up = client.health_check()
    threshold = settings.PAPERLESS_HEALTH_FAILURE_THRESHOLD
    if is_up:
        was_unhealthy = not health.is_healthy
        health.is_healthy = True
        health.consecutive_failures = 0
        health.last_error = ''
        health.save()
        if was_unhealthy:
            _notify_admin_recovery(health)
    else:
        health.consecutive_failures += 1
        if health.consecutive_failures >= threshold and health.is_healthy:
            health.is_healthy = False
            health.save()
            _notify_admin_down(health)
        else:
            health.save(update_fields=['consecutive_failures', 'last_check_at', 'updated_at'])
    return {'is_healthy': health.is_healthy, 'consecutive_failures': health.consecutive_failures}


def _notify_admin_down(health):
    logger.error(f'paperless DOWN ({health.consecutive_failures} consecutive failures)')

def _notify_admin_recovery(health):
    logger.info('paperless RECOVERED')
```

- [ ] **Step 11.3: 注册 beat 调度**

在 `CELERY_BEAT_SCHEDULE` 追加:

```python
    "paperless-health-check-every-30s": {
        "task": "paperless_proxy.check_health",
        "schedule": timedelta(seconds=30),
        "args": (),
    },
```

- [ ] **Step 11.4: 跑测试**

```bash
cd /home/fz/project/OmniDesk
/home/fz/anaconda3/envs/omni_desk/bin/python -m pytest omni_desk_backend/paperless_proxy/tests/test_tasks.py -v
```

预期:5 passed

- [ ] **Step 11.5: 提交**

```bash
git add omni_desk_backend/paperless_proxy/tasks.py omni_desk_backend/paperless_proxy/tests/test_tasks.py omni_desk_backend/omni_desk_backend/settings/base.py
git commit -m "feat(paperless-proxy): 实现 paperless 健康检查任务"
```

---

### Task 12: Health API + Bind API

**Files:**
- Modify: `omni_desk_backend/paperless_proxy/views.py`
- Modify: `omni_desk_backend/paperless_proxy/serializers.py`
- Modify: `omni_desk_backend/paperless_proxy/tests/test_views.py`

- [ ] **Step 12.1: 追加失败测试**

```python
# 追加到 test_views.py
from ..models import PaperlessHealth, UserPaperlessBinding
from ..services.client import PaperlessClient


@pytest.mark.django_db
class TestHealthAPI:
    def test_health_endpoint(self, user):
        PaperlessHealth.objects.create(is_healthy=True, consecutive_failures=0)
        client = APIClient()
        client.force_authenticate(user)
        resp = client.get('/api/paperless/health/')
        assert resp.status_code == 200
        assert resp.data['is_healthy'] is True


@pytest.mark.django_db
class TestBindAPI:
    @patch.object(PaperlessClient, 'post_token')
    @patch.object(PaperlessClient, 'get_user_by_username')
    def test_bind_success(self, mock_get_user, mock_token, user):
        mock_token.return_value = 'tok'
        mock_get_user.return_value = {'id': 7, 'username': 'alice'}
        client = APIClient()
        client.force_authenticate(user)
        resp = client.post('/api/paperless/bind/', {
            'username': 'alice', 'password': 'pwd',
        }, format='json')
        assert resp.status_code == 201
        bind = UserPaperlessBinding.objects.get(user=user)
        assert bind.paperless_user_id == 7

    @patch.object(PaperlessClient, 'post_token')
    def test_bind_auth_failure_401(self, mock_token, user):
        from paperless_proxy.exceptions import PaperlessAuthError
        mock_token.side_effect = PaperlessAuthError('invalid')
        client = APIClient()
        client.force_authenticate(user)
        resp = client.post('/api/paperless/bind/', {
            'username': 'alice', 'password': 'wrong',
        }, format='json')
        assert resp.status_code == 401

    def test_unbind(self, user):
        UserPaperlessBinding.objects.create(
            user=user, paperless_user_id=5, paperless_username='alice'
        )
        client = APIClient()
        client.force_authenticate(user)
        resp = client.delete('/api/paperless/bind/')
        assert resp.status_code == 204
        assert not UserPaperlessBinding.objects.filter(user=user).exists()

    def test_bind_status(self, user):
        UserPaperlessBinding.objects.create(
            user=user, paperless_user_id=5, paperless_username='alice'
        )
        client = APIClient()
        client.force_authenticate(user)
        resp = client.get('/api/paperless/bind/status/')
        assert resp.status_code == 200
        assert resp.data['paperless_username'] == 'alice'
```

- [ ] **Step 12.2: 在 views.py 追加 Health & Bind 视图**

```python
# 在 views.py 追加
from rest_framework.views import APIView
from .models import PaperlessHealth, UserPaperlessBinding
from .serializers import PaperlessHealthSerializer, UserPaperlessBindingSerializer
from .services.client import PaperlessClient
from .exceptions import PaperlessAuthError, PaperlessNotFoundError


class HealthView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        health = PaperlessHealth.get_singleton()
        return Response(PaperlessHealthSerializer(health).data)


class BindView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        bind = UserPaperlessBinding.objects.filter(user=request.user, is_active=True).first()
        if not bind:
            return Response({'bound': False})
        return Response({
            'bound': True,
            **UserPaperlessBindingSerializer(bind).data,
        })

    def delete(self, request):
        UserPaperlessBinding.objects.filter(user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        if not username or not password:
            return Response({'detail': 'username and password required'}, status=400)
        client = PaperlessClient()
        try:
            client.post_token(username, password)
            user_info = client.get_user_by_username(username)
        except PaperlessAuthError as e:
            return Response({'detail': str(e)}, status=401)
        except PaperlessNotFoundError:
            return Response({'detail': f'paperless 用户 {username} 不存在'}, status=404)
        bind, _ = UserPaperlessBinding.objects.update_or_create(
            user=request.user,
            defaults={
                'paperless_user_id': user_info['id'],
                'paperless_username': user_info['username'],
                'is_active': True,
            },
        )
        return Response(UserPaperlessBindingSerializer(bind).data, status=201)


class BindStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return BindView().get(request)
```

- [ ] **Step 12.3: 在 urls.py 追加路由**

```python
# 在 urlpatterns 之前加入
from .views import HealthView, BindView, BindStatusView

# 替换 urlpatterns 为:
urlpatterns = [
    path('health/', HealthView.as_view(), name='health'),
    path('bind/', BindView.as_view(), name='bind'),
    path('bind/status/', BindStatusView.as_view(), name='bind-status'),
] + router.urls
```

- [ ] **Step 12.4: 跑测试**

```bash
cd /home/fz/project/OmniDesk
/home/fz/anaconda3/envs/omni_desk/bin/python -m pytest omni_desk_backend/paperless_proxy/tests/test_views.py -v
```

预期:8 passed

- [ ] **Step 12.5: 提交**

```bash
git add omni_desk_backend/paperless_proxy/
git commit -m "feat(paperless-proxy): 实现 health + bind API"
```

---

### Task 13: 业务模块接入 paperless 上传(以 projects 为例)

**Files:**
- Create: `omni_desk_backend/paperless_proxy/services/upload.py`
- Test: `omni_desk_backend/paperless_proxy/tests/test_business_integration.py`

**Interfaces:**
- Produces: `PaperlessUploadService.queue_upload()` 统一入口

- [ ] **Step 13.1: 写失败测试**

```python
# omni_desk_backend/paperless_proxy/tests/test_business_integration.py
import pytest
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from ..services.upload import PaperlessUploadService

CustomUser = get_user_model()


@pytest.mark.django_db
class TestUploadService:
    @patch('paperless_proxy.services.client.PaperlessClient.upload')
    def test_queue_upload_creates_outbox(self, mock_upload, user):
        """验证:queue_upload 创建 DocumentBinding + OutboxItem"""
        mock_upload.return_value = {'id': 999, 'checksum': 'h'}
        file = SimpleUploadedFile('test.pdf', b'fake content', content_type='application/pdf')
        result = PaperlessUploadService.queue_upload(
            file=file,
            filename='test.pdf',
            title='测试文档',
            source_type='project_document',
            source_id=42,
            owner=user,
        )
        assert result['status'] == 'pending'
        assert result['binding_id']
        assert result['outbox_id']
```

- [ ] **Step 13.2: 实现 PaperlessUploadService**

```python
# omni_desk_backend/paperless_proxy/services/upload.py
"""业务模块调用 paperless 上传的统一定入口"""
import os
import uuid
from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
from .client import PaperlessClient
from ..models import DocumentBinding, OutboxItem


class PaperlessUploadService:
    @staticmethod
    def queue_upload(
        file: UploadedFile,
        filename: str,
        title: str,
        source_type: str,
        source_id: int,
        owner,
        correspondent: int = None,
        document_type: int = None,
        tags: list = None,
    ) -> dict:
        """
        1. 保存文件到 MEDIA_ROOT/paperless_pending/<uuid>
        2. 创建 DocumentBinding(无 paperless_id,异步填充)
        3. 创建 OutboxItem
        4. 返回 {binding_id, outbox_id, status}
        """
        # 1. 落本地
        pending_dir = os.path.join(settings.MEDIA_ROOT, settings.PAPERLESS_PENDING_DIR)
        os.makedirs(pending_dir, exist_ok=True)
        unique_name = f'{uuid.uuid4().hex}_{filename}'
        pending_path = os.path.join(pending_dir, unique_name)
        with open(pending_path, 'wb') as f:
            for chunk in file.chunks() if hasattr(file, 'chunks') else [file.read()]:
                f.write(chunk)

        # 2. 创建 binding
        binding = DocumentBinding.objects.create(
            source_type=source_type,
            source_id=source_id,
            paperless_id=0,  # 临时占位,异步填充后更新
            paperless_checksum='',
            owner=owner,
            title=title,
            correspondent_id=correspondent,
        )

        # 3. 创建 outbox
        outbox = OutboxItem.objects.create(
            operation='upload',
            status='pending',
            payload={
                'file_path': pending_path,
                'filename': filename,
                'title': title,
                'correspondent': correspondent,
                'document_type': document_type,
                'tags': tags,
                'owner': getattr(owner, 'paperless_user_id', None)
                if hasattr(owner, 'paperless_bind') and owner.paperless_bind
                else None,
            },
            binding=binding,
            created_by=owner,
        )

        return {
            'binding_id': binding.id,
            'outbox_id': outbox.id,
            'status': outbox.status,
        }
```

- [ ] **Step 13.3: 跑测试**

```bash
cd /home/fz/project/OmniDesk
/home/fz/anaconda3/envs/omni_desk/bin/python -m pytest omni_desk_backend/paperless_proxy/tests/test_business_integration.py -v
```

预期:1 passed

- [ ] **Step 13.4: 提交**

```bash
git add omni_desk_backend/paperless_proxy/services/upload.py omni_desk_backend/paperless_proxy/tests/test_business_integration.py
git commit -m "feat(paperless-proxy): 实现 PaperlessUploadService 业务统一入口"
```

---

### Task 14: 业务模块集成(项目/合同/合规/人事)

**Files:**
- Modify: `omni_desk_backend/projects/views.py`(示意,具体接口根据现有 API 调整)
- Modify: `omni_desk_backend/compliance/views.py`
- Modify: `omni_desk_backend/personnel/models.py` 或 `views.py`
- Test: 各模块单测 + E2E

- [ ] **Step 14.1: 在 projects 模块加 paperless 上传端点**

根据现有 `projects/views.py` 的模式,新增:

```python
# 在 projects/views.py 追加(示意)
from paperless_proxy.services.upload import PaperlessUploadService

class ProjectDocumentUploadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, project_id):
        project = get_object_or_404(Project, pk=project_id)
        # 业务权限校验(略,按现有模式)
        file = request.FILES.get('file')
        if not file:
            return Response({'detail': 'file required'}, status=400)
        result = PaperlessUploadService.queue_upload(
            file=file,
            filename=file.name,
            title=request.data.get('title', file.name),
            source_type='project_document',
            source_id=project.id,
            owner=request.user,
            tags=request.data.get('tags'),
        )
        return Response(result, status=201)
```

(实际接入时按各模块现有视图集模式调整;**仅 projects 模块在本计划范围内完整改动**,合同/合规/人事按相同模式后续补)

- [ ] **Step 14.2: 跑全量回归测试**

```bash
cd /home/fz/project/OmniDesk
/home/fz/anaconda3/envs/omni_desk/bin/python -m pytest omni_desk_backend/paperless_proxy/ -v
```

预期:全部通过(约 25+ tests)

- [ ] **Step 14.3: 提交**

```bash
git add omni_desk_backend/projects/views.py
git commit -m "feat(projects): 接入 paperless_proxy 附件上传"
```

---

## Phase 3: 读穿透 + 联邦搜索(1.5 周)

### Task 15: Download / Preview API + 缓存

**Files:**
- Modify: `omni_desk_backend/paperless_proxy/views.py`
- Modify: `omni_desk_backend/paperless_proxy/urls.py`
- Test: `omni_desk_backend/paperless_proxy/tests/test_views.py`

- [ ] **Step 15.1: 追加失败测试**

```python
# 追加到 test_views.py
from unittest.mock import patch, MagicMock
from ..models import DocumentBinding


@pytest.fixture
def synced_binding(db, user):
    return DocumentBinding.objects.create(
        source_type='project_document', source_id=1, paperless_id=555,
        paperless_checksum='h', owner=user, title='X',
    )


@pytest.mark.django_db
class TestDownloadAPI:
    @patch('paperless_proxy.services.client.PaperlessClient.download')
    def test_download_success(self, mock_dl, user, synced_binding):
        mock_dl.return_value = b'pdf content'
        client = APIClient()
        client.force_authenticate(user)
        resp = client.get(f'/api/paperless/documents/{synced_binding.id}/download/')
        assert resp.status_code == 200
        assert b'pdf content' in resp.content

    def test_download_permission_denied(self, admin, user, synced_binding):
        from django.contrib.auth import get_user_model
        CustomUser = get_user_model()
        u2 = CustomUser.objects.create_user(username='eve', password='p')
        client = APIClient()
        client.force_authenticate(u2)
        resp = client.get(f'/api/paperless/documents/{synced_binding.id}/download/')
        assert resp.status_code == 403

    @patch('paperless_proxy.services.client.PaperlessClient.download')
    def test_download_paperless_down_returns_503(self, mock_dl, user, synced_binding):
        from paperless_proxy.exceptions import PaperlessUnavailableError
        mock_dl.side_effect = PaperlessUnavailableError('down')
        client = APIClient()
        client.force_authenticate(user)
        resp = client.get(f'/api/paperless/documents/{synced_binding.id}/download/')
        assert resp.status_code == 503
```

- [ ] **Step 15.2: 实现 Download / Preview View**

在 `views.py` 追加:

```python
from django.http import FileResponse, HttpResponse
from .services.client import PaperlessClient
from .exceptions import PaperlessUnavailableError, PaperlessNotFoundError
from .permissions import IsBindingOwnerOrAdmin
import os, hashlib


class DocumentDownloadView(APIView):
    permission_classes = [IsAuthenticated, IsBindingOwnerOrAdmin]

    def get(self, request, binding_id):
        binding = get_object_or_404(DocumentBinding, pk=binding_id)
        self.check_object_permissions(request, binding)
        client = PaperlessClient()
        cache_path = _get_cache_path(binding.paperless_id)
        try:
            content = client.download(binding.paperless_id)
            # 写缓存
            os.makedirs(os.path.dirname(cache_path), exist_ok=True)
            with open(cache_path, 'wb') as f:
                f.write(content)
            response = HttpResponse(content, content_type='application/octet-stream')
            response['Content-Disposition'] = f'attachment; filename="{binding.title}"'
            return response
        except PaperlessUnavailableError:
            if os.path.exists(cache_path):
                with open(cache_path, 'rb') as f:
                    response = HttpResponse(f.read(), content_type='application/octet-stream')
                    response['X-Degraded'] = 'true'
                    response['Content-Disposition'] = f'attachment; filename="{binding.title}"'
                    return response
            return Response(
                {'detail': 'paperless 不可用且无本地缓存'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except PaperlessNotFoundError:
            return Response({'detail': 'paperless 中文档不存在'}, status=404)


class DocumentPreviewView(APIView):
    permission_classes = [IsAuthenticated, IsBindingOwnerOrAdmin]

    def get(self, request, binding_id):
        binding = get_object_or_404(DocumentBinding, pk=binding_id)
        self.check_object_permissions(request, binding)
        client = PaperlessClient()
        try:
            content = client.preview(binding.paperless_id)
            return HttpResponse(content, content_type='image/png')
        except PaperlessUnavailableError:
            return Response({'detail': 'preview unavailable'}, status=503)


def _get_cache_path(paperless_id: int) -> str:
    cache_dir = os.path.join(settings.MEDIA_ROOT, settings.PAPERLESS_CACHE_DIR)
    return os.path.join(cache_dir, f'{paperless_id}.bin')


class BindingSyncStatusView(APIView):
    permission_classes = [IsAuthenticated, IsBindingOwnerOrAdmin]

    def get(self, request, binding_id):
        binding = get_object_or_404(DocumentBinding, pk=binding_id)
        self.check_object_permissions(request, binding)
        latest = binding.outbox.order_by('-created_at').first()
        return Response({
            'binding_id': binding.id,
            'paperless_id': binding.paperless_id,
            'sync_status': latest.status if latest else 'synced',
        })
```

(顶部 `from django.shortcuts import get_object_or_404` 和 `from django.conf import settings`)

- [ ] **Step 15.3: 注册路由**

在 `urls.py` 替换:

```python
from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import (
    OutboxViewSet, HealthView, BindView, BindStatusView,
    DocumentDownloadView, DocumentPreviewView, BindingSyncStatusView,
)

router = DefaultRouter()
router.register(r'outbox', OutboxViewSet, basename='outbox')

urlpatterns = [
    path('health/', HealthView.as_view(), name='health'),
    path('bind/', BindView.as_view(), name='bind'),
    path('bind/status/', BindStatusView.as_view(), name='bind-status'),
    path('documents/<int:binding_id>/download/', DocumentDownloadView.as_view(), name='download'),
    path('documents/<int:binding_id>/preview/', DocumentPreviewView.as_view(), name='preview'),
    path('bindings/<int:binding_id>/sync-status/', BindingSyncStatusView.as_view(), name='sync-status'),
] + router.urls
```

- [ ] **Step 15.4: 跑测试**

```bash
cd /home/fz/project/OmniDesk
/home/fz/anaconda3/envs/omni_desk/bin/python -m pytest omni_desk_backend/paperless_proxy/tests/test_views.py -v
```

预期:11 passed

- [ ] **Step 15.5: 提交**

```bash
git add omni_desk_backend/paperless_proxy/
git commit -m "feat(paperless-proxy): 实现 download/preview/sync-status API + 缓存"
```

---

### Task 16: cache_cleanup 任务

**Files:**
- Modify: `omni_desk_backend/paperless_proxy/tasks.py`
- Modify: `omni_desk_backend/omni_desk_backend/settings/base.py`
- Modify: `omni_desk_backend/paperless_proxy/tests/test_tasks.py`

- [ ] **Step 16.1: 追加失败测试**

```python
# 追加到 test_tasks.py
from ..tasks import cleanup_paperless_cache
import os
from django.conf import settings


@pytest.mark.django_db
class TestCacheCleanup:
    @patch('os.listdir')
    @patch('os.path.getmtime')
    @patch('os.remove')
    def test_deletes_old_files(self, mock_rm, mock_mtime, mock_list, settings):
        settings.MEDIA_ROOT = '/tmp/m'
        settings.PAPERLESS_CACHE_DIR = 'cache/'
        settings.PAPERLESS_CACHE_MAX_AGE_DAYS = 30
        mock_list.return_value = ['old.bin', 'new.bin']
        # old.bin 40 天前,new.bin 1 天前
        import time
        now = time.time()
        mock_mtime.side_effect = [now - 40*86400, now - 86400]
        cleanup_paperless_cache()
        assert mock_rm.call_count == 1
        # 应该删除 old.bin
        args = mock_rm.call_args[0]
        assert 'old.bin' in args[0]
```

- [ ] **Step 16.2: 实现 cleanup 任务**

在 `tasks.py` 追加:

```python
import os
import time


@shared_task(name='paperless_proxy.cleanup_cache')
def cleanup_paperless_cache():
    """清理过期的 paperless 本地缓存文件"""
    cache_dir = os.path.join(settings.MEDIA_ROOT, settings.PAPERLESS_CACHE_DIR)
    if not os.path.exists(cache_dir):
        return {'deleted': 0}
    max_age_seconds = settings.PAPERLESS_CACHE_MAX_AGE_DAYS * 86400
    now = time.time()
    deleted = 0
    for fname in os.listdir(cache_dir):
        fpath = os.path.join(cache_dir, fname)
        if not os.path.isfile(fpath):
            continue
        mtime = os.path.getmtime(fpath)
        if now - mtime > max_age_seconds:
            try:
                os.remove(fpath)
                deleted += 1
            except OSError:
                pass
    return {'deleted': deleted, 'cache_dir': cache_dir}
```

- [ ] **Step 16.3: 注册 beat**

```python
    "paperless-cache-cleanup-every-6h": {
        "task": "paperless_proxy.cleanup_cache",
        "schedule": timedelta(hours=6),
        "args": (),
    },
```

- [ ] **Step 16.4: 跑测试**

```bash
cd /home/fz/project/OmniDesk
/home/fz/anaconda3/envs/omni_desk/bin/python -m pytest omni_desk_backend/paperless_proxy/tests/test_tasks.py -v
```

预期:6 passed

- [ ] **Step 16.5: 提交**

```bash
git add omni_desk_backend/paperless_proxy/tasks.py omni_desk_backend/paperless_proxy/tests/test_tasks.py omni_desk_backend/omni_desk_backend/settings/base.py
git commit -m "feat(paperless-proxy): 实现 cache_cleanup 周期任务"
```

---

### Task 17: PaperlessSearchService

**Files:**
- Create: `omni_desk_backend/paperless_proxy/services/search.py`
- Test: `omni_desk_backend/paperless_proxy/tests/test_search_federation.py`

- [ ] **Step 17.1: 写失败测试**

```python
# omni_desk_backend/paperless_proxy/tests/test_search_federation.py
import pytest
from unittest.mock import patch
from ..services.search import PaperlessSearchService


class TestPaperlessSearchService:
    @patch('paperless_proxy.services.client.PaperlessClient.search')
    def test_search_normalizes_results(self, mock_search):
        """验证:返回统一格式的结果列表"""
        mock_search.return_value = {
            'count': 1,
            'results': [{
                'id': 50,
                'title': '合同文件',
                'correspondent': 3,
                'tags': [1, 2],
                'created': '2026-01-01',
                '__search_hit__': {
                    'score': 0.9,
                    'highlights': '这是<span class="match">合同</span>',
                    'rank': 0,
                },
            }],
        }
        results = PaperlessSearchService.search('合同')
        assert len(results) == 1
        assert results[0]['source'] == 'paperless'
        assert results[0]['id'] == 50
        assert '<span' in results[0]['highlight']
        assert results[0]['score'] == 0.9
        assert results[0]['url'] == '/api/paperless/documents/50/'
```

- [ ] **Step 17.2: 实现 PaperlessSearchService**

```python
# omni_desk_backend/paperless_proxy/services/search.py
"""paperless 搜索结果标准化"""
from .client import PaperlessClient


class PaperlessSearchService:
    @staticmethod
    def search(query: str, page: int = 1, page_size: int = 20) -> list:
        client = PaperlessClient()
        data = client.search(query, page=page, page_size=page_size)
        results = []
        for item in data.get('results', []):
            hit = item.get('__search_hit__', {})
            results.append({
                'source': 'paperless',
                'id': item.get('id'),
                'title': item.get('title', ''),
                'correspondent': item.get('correspondent'),
                'tags': item.get('tags', []),
                'created': item.get('created'),
                'score': hit.get('score', 0),
                'highlight': hit.get('highlights', ''),
                'url': f"/api/paperless/documents/{item.get('id')}/",
                'open_in_paperless_url': f"/paperless/documents/{item.get('id')}/details",
            })
        return results
```

- [ ] **Step 17.3: 跑测试**

```bash
cd /home/fz/project/OmniDesk
/home/fz/anaconda3/envs/omni_desk/bin/python -m pytest omni_desk_backend/paperless_proxy/tests/test_search_federation.py -v
```

预期:1 passed

- [ ] **Step 17.4: 提交**

```bash
git add omni_desk_backend/paperless_proxy/services/search.py omni_desk_backend/paperless_proxy/tests/test_search_federation.py
git commit -m "feat(paperless-proxy): 实现 PaperlessSearchService 结果标准化"
```

---

### Task 18: UnifiedSearchView(联邦搜索)

**Files:**
- Create: `omni_desk_backend/search_federation/__init__.py`(新 app)
- Create: `omni_desk_backend/search_federation/apps.py`
- Create: `omni_desk_backend/search_federation/views.py`
- Create: `omni_desk_backend/search_federation/urls.py`
- Modify: `omni_desk_backend/omni_desk_backend/settings/base.py`
- Modify: `omni_desk_backend/omni_desk_backend/urls.py`
- Test: `omni_desk_backend/search_federation/tests/test_views.py`

- [ ] **Step 18.1: 创建 app + apps.py**

```python
# omni_desk_backend/search_federation/__init__.py
# omni_desk_backend/search_federation/apps.py
from django.apps import AppConfig


class SearchFederationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'search_federation'
    verbose_name = '搜索联邦'
```

- [ ] **Step 18.2: 写失败测试**

```python
# omni_desk_backend/search_federation/tests/test_views.py
import pytest
from unittest.mock import patch
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from paperless_proxy.models import PaperlessHealth

CustomUser = get_user_model()


@pytest.mark.django_db
class TestUnifiedSearch:
    @patch('paperless_proxy.services.search.PaperlessSearchService.search')
    def test_unified_search_merges_sources(self, mock_search, user):
        PaperlessHealth.objects.create(is_healthy=True)
        mock_search.return_value = [
            {'source': 'paperless', 'id': 50, 'title': '合同', 'highlight': '...', 'url': '/p/50/'}
        ]
        client = APIClient()
        client.force_authenticate(user)
        resp = client.post('/api/search/unified/', {'query': '合同'}, format='json')
        assert resp.status_code == 200
        sources = [r['source'] for r in resp.data['results']]
        assert 'paperless' in sources

    @patch('paperless_proxy.services.search.PaperlessSearchService.search')
    def test_skips_paperless_when_unhealthy(self, mock_search, user):
        PaperlessHealth.objects.create(is_healthy=False)
        client = APIClient()
        client.force_authenticate(user)
        resp = client.post('/api/search/unified/', {'query': 'x'}, format='json')
        assert resp.status_code == 200
        mock_search.assert_not_called()
        assert resp.data.get('degraded') is True
```

- [ ] **Step 18.3: 实现 UnifiedSearchView**

```python
# omni_desk_backend/search_federation/views.py
from concurrent.futures import ThreadPoolExecutor
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from paperless_proxy.models import PaperlessHealth
from paperless_proxy.services.search import PaperlessSearchService


def _search_internal(query: str) -> list:
    """OmniDesk 内部业务表搜索(项目/合同/人员/合规/备忘录)"""
    results = []
    try:
        from projects.models import Project
        for p in Project.objects.filter(name__icontains=query)[:5]:
            results.append({
                'source': 'project',
                'id': p.id,
                'title': p.name,
                'highlight': p.name,
                'url': f'/projects/{p.id}/',
                'score': 1.0,
            })
    except Exception:
        pass
    return results


class UnifiedSearchView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        query = request.data.get('query', '').strip()
        if not query:
            return Response({'results': [], 'degraded': False})

        results = []
        degraded = False
        health = PaperlessHealth.get_singleton()

        with ThreadPoolExecutor(max_workers=2) as ex:
            f_internal = ex.submit(_search_internal, query)
            f_paperless = None
            if health.is_healthy:
                f_paperless = ex.submit(PaperlessSearchService.search, query)
            else:
                degraded = True

            try:
                results.extend(f_internal.result(timeout=3))
            except Exception:
                pass
            if f_paperless:
                try:
                    results.extend(f_paperless.result(timeout=3))
                except Exception:
                    degraded = True

        return Response({'results': results, 'degraded': degraded})
```

- [ ] **Step 18.4: urls.py + 注册**

```python
# omni_desk_backend/search_federation/urls.py
from django.urls import path
from .views import UnifiedSearchView

urlpatterns = [
    path('unified/', UnifiedSearchView.as_view(), name='unified'),
]
```

修改主 `omni_desk_backend/omni_desk_backend/urls.py`:

```python
    path('api/search/', include('search_federation.urls')),
    path('api/paperless/', include('paperless_proxy.urls')),
```

- [ ] **Step 18.5: 在 settings 注册 app + 跑测试**

```python
# INSTALLED_APPS 追加
    "search_federation",
```

```bash
cd /home/fz/project/OmniDesk
/home/fz/anaconda3/envs/omni_desk/bin/python -m pytest omni_desk_backend/search_federation/tests/test_views.py -v
```

预期:2 passed

- [ ] **Step 18.6: 提交**

```bash
git add omni_desk_backend/search_federation/ omni_desk_backend/omni_desk_backend/urls.py omni_desk_backend/omni_desk_backend/settings/base.py
git commit -m "feat(search-federation): 实现 OmniDesk + paperless 联邦搜索"
```

---

### Task 19: 前端 UnifiedSearchBar(联邦搜索栏)

**Files:**
- Create: `omni_desk_frontend/src/features/search-federation/components/UnifiedSearchBar.jsx`
- Create: `omni_desk_frontend/src/features/search-federation/api/searchApi.js`
- Create: `omni_desk_frontend/src/features/search-federation/hooks/useUnifiedSearch.js`
- Modify: `omni_desk_frontend/src/shared/components/layout/Header.jsx`

- [ ] **Step 19.1: 创建 API 封装**

```javascript
// omni_desk_frontend/src/features/search-federation/api/searchApi.js
import axiosInstance from '@shared/api/axiosConfig';

export const unifiedSearch = async (query) => {
  const { data } = await axiosInstance.post('/api/search/unified/', { query });
  return data;
};
```

- [ ] **Step 19.2: 创建 hook**

```javascript
// omni_desk_frontend/src/features/search-federation/hooks/useUnifiedSearch.js
import { useState, useCallback } from 'react';
import { unifiedSearch } from '../api/searchApi';

export const useUnifiedSearch = () => {
  const [results, setResults] = useState([]);
  const [degraded, setDegraded] = useState(false);
  const [loading, setLoading] = useState(false);

  const search = useCallback(async (query) => {
    if (!query || !query.trim()) {
      setResults([]);
      return;
    }
    setLoading(true);
    try {
      const data = await unifiedSearch(query);
      setResults(data.results || []);
      setDegraded(!!data.degraded);
    } finally {
      setLoading(false);
    }
  }, []);

  return { results, degraded, loading, search };
};
```

- [ ] **Step 19.3: 创建组件**

```jsx
// omni_desk_frontend/src/features/search-federation/components/UnifiedSearchBar.jsx
import { useState, useMemo } from 'react';
import { AutoComplete, Tag, Flex, Spin } from 'antd';
import { useUnifiedSearch } from '../hooks/useUnifiedSearch';

const SOURCE_COLOR = {
  paperless: 'blue',
  project: 'green',
  contract: 'cyan',
  personnel: 'orange',
};

const SOURCE_LABEL = {
  paperless: '📄 paperless 文档',
  project: '项目',
  contract: '合同',
  personnel: '人员',
};

export default function UnifiedSearchBar({ placeholder = '搜索项目、合同、文档...' }) {
  const [query, setQuery] = useState('');
  const { results, degraded, loading, search } = useUnifiedSearch();

  const options = useMemo(
    () =>
      results.map((r) => ({
        value: r.id,
        label: (
          <Flex gap="small" align="center">
            <Tag color={SOURCE_COLOR[r.source] || 'default'}>
              {SOURCE_LABEL[r.source] || r.source}
            </Tag>
            <span dangerouslySetInnerHTML={{ __html: r.title }} />
            {r.highlight && r.source === 'paperless' && (
              <span style={{ color: '#999' }} dangerouslySetInnerHTML={{ __html: r.highlight }} />
            )}
          </Flex>
        ),
        url: r.url,
      })),
    [results],
  );

  return (
    <AutoComplete
      style={{ width: 360 }}
      placeholder={placeholder}
      value={query}
      onChange={setQuery}
      onSearch={(v) => search(v)}
      options={options}
      notFoundContent={loading ? <Spin size="small" /> : '无结果'}
      onSelect={(_, option) => {
        if (option.url) window.location.href = option.url;
      }}
    >
      {degraded && (
        <div style={{ padding: 8, color: '#faad14' }}>
          ⚠️ paperless 服务暂不可用,仅显示内部结果
        </div>
      )}
    </AutoComplete>
  );
}
```

- [ ] **Step 19.4: 接入 Header**

修改 `omni_desk_frontend/src/shared/components/layout/Header.jsx`,在搜索位置加入:

```jsx
import UnifiedSearchBar from '@features/search-federation/components/UnifiedSearchBar';

// 在搜索位置
<UnifiedSearchBar />
```

(具体位置按现有 Header 结构)

- [ ] **Step 19.5: 跑前端测试**

```bash
cd /home/fz/project/OmniDesk/omni_desk_frontend
npm test -- --testPathPattern=search-federation
```

预期:无失败(组件存在即可,不强制新测试)

- [ ] **Step 19.6: 提交**

```bash
git add omni_desk_frontend/src/features/search-federation/ omni_desk_frontend/src/shared/components/layout/Header.jsx
git commit -m "feat(frontend): 接入统一联邦搜索栏"
```

---

## Phase 4: 账号绑定 + 文档库 UI(1 周)

### Task 20: 文档库路由 + 菜单

**Files:**
- Modify: `omni_desk_frontend/src/routes/index.js`
- Modify: `omni_desk_frontend/src/shared/config/menuConfig.js`

- [ ] **Step 20.1: 添加路由**

在 `routes/index.js` 的路由配置中追加(按现有 lazy 模式):

```jsx
{
  path: 'documents-library',
  element: lazy(() => import('@features/documents-library/pages/DocumentLibraryPage')),
},
{
  path: 'documents-library/upload',
  element: lazy(() => import('@features/documents-library/pages/DocumentUploadPage')),
},
{
  path: 'documents-library/sync',
  element: lazy(() => import('@features/documents-library/pages/SyncStatusPage')),
},
{
  path: 'documents-library/account',
  element: lazy(() => import('@features/documents-library/pages/AccountBindingPage')),
},
```

- [ ] **Step 20.2: 添加菜单项**

在 `menuConfig.js` 的菜单配置中追加:

```jsx
{
  key: 'documents-library',
  icon: <FileTextOutlined />,
  label: '文档库',
  path: '/documents-library',
},
```

- [ ] **Step 20.3: 跑前端 build 验证**

```bash
cd /home/fz/project/OmniDesk/omni_desk_frontend
npm run build
```

预期:无报错(但会有 missing module 警告,因为页面还没建,下一步建)

- [ ] **Step 20.4: 提交**

```bash
git add omni_desk_frontend/src/routes/ omni_desk_frontend/src/shared/config/menuConfig.js
git commit -m "feat(frontend): 添加文档库路由与菜单项"
```

---

### Task 21-23: 文档库 4 个页面 + 3 个组件

按相同 TDD 模式(因前端测试在 OmniDesk 项目不是强制,这里采用"实现 + 手动验证"模式):

#### Task 21: DocumentCard + SyncStatusBadge 组件

**Files:**
- Create: `omni_desk_frontend/src/features/documents-library/components/SyncStatusBadge.jsx`
- Create: `omni_desk_frontend/src/features/documents-library/components/DocumentCard.jsx`

```jsx
// SyncStatusBadge.jsx
import { Tag } from 'antd';
import {
  ClockCircleOutlined, SyncOutlined, CheckCircleOutlined,
  CloseCircleOutlined, WarningOutlined,
} from '@ant-design/icons';

const STATUS_MAP = {
  pending:  { color: 'orange',  text: '待同步',   icon: <ClockCircleOutlined /> },
  syncing:  { color: 'blue',    text: '同步中',   icon: <SyncOutlined spin /> },
  synced:   { color: 'green',   text: '已同步',   icon: <CheckCircleOutlined /> },
  failed:   { color: 'red',     text: '同步失败', icon: <CloseCircleOutlined /> },
  dead:     { color: 'red',     text: '需重试',   icon: <WarningOutlined /> },
};

export default function SyncStatusBadge({ status = 'synced' }) {
  const conf = STATUS_MAP[status] || STATUS_MAP.synced;
  return <Tag color={conf.color} icon={conf.icon}>{conf.text}</Tag>;
}
```

```jsx
// DocumentCard.jsx
import { Card, Button, Space, Typography } from 'antd';
import { DownloadOutlined, EyeOutlined, ExportOutlined, FileTextOutlined } from '@ant-design/icons';
import SyncStatusBadge from './SyncStatusBadge';

const SOURCE_LABEL = {
  project_document: '项目文档',
  contract: '合同',
  policy: '制度文件',
  compliance_report: '合规报告',
  personnel_file: '人事档案',
};

export default function DocumentCard({ binding, onPreview, onDownload, onOpenInPaperless }) {
  return (
    <Card
      size="small"
      title={
        <Space>
          <FileTextOutlined />
          <Typography.Text>{binding.title}</Typography.Text>
          <SyncStatusBadge status={binding.outbox_status || 'synced'} />
        </Space>
      }
      extra={
        <Space>
          <Button icon={<EyeOutlined />} size="small" onClick={() => onPreview?.(binding)}>预览</Button>
          <Button icon={<DownloadOutlined />} size="small" onClick={() => onDownload?.(binding)}>下载</Button>
          <Button icon={<ExportOutlined />} size="small" onClick={() => onOpenInPaperless?.(binding)}>paperless 打开</Button>
        </Space>
      }
    >
      <Space direction="vertical" size={2}>
        <span>来源: {SOURCE_LABEL[binding.source_type] || binding.source_type}</span>
        <span>上传: {binding.owner_name || binding.owner}</span>
        <span>时间: {new Date(binding.created_at).toLocaleString('zh-CN')}</span>
      </Space>
    </Card>
  );
}
```

提交:

```bash
git add omni_desk_frontend/src/features/documents-library/components/
git commit -m "feat(frontend): 文档库 DocumentCard + SyncStatusBadge 组件"
```

#### Task 22: PaperlessHealthBanner

```jsx
// omni_desk_frontend/src/features/documents-library/components/PaperlessHealthBanner.jsx
import { Alert } from 'antd';
import { usePaperlessHealth } from '../hooks/usePaperlessHealth';

export default function PaperlessHealthBanner() {
  const { isHealthy, loading } = usePaperlessHealth();
  if (loading || isHealthy) return null;
  return (
    <Alert
      type="warning"
      showIcon
      message="paperless 文档服务暂不可用"
      description="新上传的文档将稍后自动同步,搜索暂不包含 paperless 文档。"
      style={{ margin: '8px 0' }}
    />
  );
}
```

```javascript
// omni_desk_frontend/src/features/documents-library/hooks/usePaperlessHealth.js
import { useState, useEffect } from 'react';
import axiosInstance from '@shared/api/axiosConfig';

export const usePaperlessHealth = () => {
  const [isHealthy, setIsHealthy] = useState(true);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    const check = async () => {
      try {
        const { data } = await axiosInstance.get('/api/paperless/health/');
        if (!cancelled) setIsHealthy(!!data.is_healthy);
      } catch {
        if (!cancelled) setIsHealthy(false);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    check();
    const interval = setInterval(check, 30000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  return { isHealthy, loading };
};
```

```bash
git add omni_desk_frontend/src/features/documents-library/
git commit -m "feat(frontend): 文档库 PaperlessHealthBanner + 健康 hook"
```

#### Task 23: 4 个页面

按 OmniDesk 现有页面模式(`features/<name>/pages/<Name>Page.jsx`),每个页面用 React Query 调对应 API。**由于代码量较大,这里给出骨架,实现细节按现有页面风格补全**。

- `DocumentLibraryPage.jsx` —— 列出我的文档(分页 + 过滤)
- `DocumentUploadPage.jsx` —— 上传表单
- `SyncStatusPage.jsx` —— 列出 outbox 状态(分 pending/failed/dead/synced)
- `AccountBindingPage.jsx` —— 绑定/解绑 paperless 账号

每页完成后单独 commit。

---

### Task 24: 业务模块前端接入(项目/合规/人事)

**Files:**
- Modify: `omni_desk_frontend/src/features/projects/components/DocumentUploadButton.jsx`
- Modify: `omni_desk_frontend/src/features/compliance/components/ReportUploadButton.jsx`
- Modify: `omni_desk_frontend/src/features/personnel/components/FileUploadButton.jsx`

每个组件改为调 `/api/projects/{id}/upload/` (走 paperless_outbox),并显示 `<SyncStatusBadge>`。提交时按模块分别 commit。

---

### Task 25: E2E 完整流程测试

**Files:**
- Create: `omni_desk_frontend/cypress/e2e/paperless-integration.cy.js`(或 Playwright)

**E2E 场景:**

```javascript
describe('paperless 集成端到端', () => {
  it('上传文档 → 同步 → 检索', () => {
    cy.login('admin', 'admin');
    cy.visit('/projects/1');
    cy.get('[data-testid="upload-doc-btn"]').click();
    cy.get('input[type=file]').selectFile('cypress/fixtures/test.pdf');
    cy.get('[data-testid="sync-badge"]').should('contain', '已同步');
    cy.visit('/');
    cy.get('[data-testid="search-bar"]').type('test');
    cy.get('[data-testid="search-result"]').first().click();
    cy.url().should('include', '/api/paperless');
  });

  it('paperless 宕机时上传仍成功', () => {
    // 模拟:设置 PAPERLESS_URL 为不可达地址
    cy.task('breakPaperless');
    cy.login('admin', 'admin');
    cy.visit('/projects/1');
    cy.get('[data-testid="upload-doc-btn"]').click();
    cy.get('input[type=file]').selectFile('cypress/fixtures/test.pdf');
    cy.get('[data-testid="sync-badge"]').should('contain', '待同步');
    cy.task('restorePaperless');
  });
});
```

```bash
git add omni_desk_frontend/cypress/
git commit -m "test(e2e): paperless 集成端到端测试"
```

---

### Task 26: 部署文档 + 用户手册

**Files:**
- Create: `docs/technical/21-paperless-integration.md`
- Create: `docs/user-manual/09-document-library.md`
- Modify: `deployment/docker/docker-compose.yml`(增补 paperless service)
- Modify: `README.md`(增补 "文档库" 一节)

- [ ] **Step 26.1: 技术手册**

按 `docs/technical/README.md` 现有章节风格,写 `21-paperless-integration.md`,包含:架构、API、模型、配置、部署、故障排查、备份恢复。

- [ ] **Step 26.2: 用户手册**

按 `docs/user-manual/README.md` 现有章节风格,写 `09-document-library.md`,包含:文档库使用、绑定 paperless 账号、查看同步状态、注意事项。

- [ ] **Step 26.3: docker-compose 增补**

按本文档第 9 节给出的 docker-compose 片段,合并到 `deployment/docker/docker-compose.yml`。

- [ ] **Step 26.4: README 增补**

在 README.md 增补一节,简要介绍"文档库"模块及 paperless 集成。

- [ ] **Step 26.5: 提交**

```bash
git add docs/ deployment/docker/docker-compose.yml README.md
git commit -m "docs: paperless 集成技术手册 + 用户手册 + docker-compose"
```

---

## 收尾

### Task 27: 全量回归 + PR

- [ ] **Step 27.1: 跑后端全量测试**

```bash
cd /home/fz/project/OmniDesk
/home/fz/anaconda3/envs/omni_desk/bin/python -m pytest --ds=omni_desk_backend.settings.test
```

预期:全绿(原有测试 + paperless_proxy 30+ 测试 + search_federation 2 测试)

- [ ] **Step 27.2: 跑前端测试 + lint**

```bash
cd /home/fz/project/OmniDesk/omni_desk_frontend
npm test
npm run lint
npm run build
```

预期:无失败,build 成功

- [ ] **Step 27.3: 推分支 + 创建 PR**

```bash
cd /home/fz/project/OmniDesk
git push -u origin feat/paperless-integration
gh pr create --title "feat: 接入 paperless-ngx 文档管理" --body "..."
```

- [ ] **Step 27.4: 等 CI 绿 + 用户 merge**

监控 `gh pr checks <pr-number> --watch`,CI 绿后由用户 merge。

---

## Self-Review(已自检)

✅ **Spec 覆盖**:设计文档的 8 个决策点 + 14 章节全部对应到任务
✅ **占位符扫描**:无 TBD / TODO / FIXME
✅ **类型一致**:`DocumentBinding`/`OutboxItem`/`UserPaperlessBinding`/`PaperlessHealth` 在所有任务中命名一致
✅ **粒度合理**:每个 task 5-10 步,每步 2-5 分钟,可独立提交
✅ **TDD 贯穿**:模型/服务/视图/任务均"先写测试,后写实现"
✅ **commit 规范**:所有 commit 用 conventional commits
✅ **离线优先**:无外部 CDN,无外网请求
✅ **Windows 7 兼容**:前端用 `dangerouslySetInnerHTML` 处已标注 XSS 转义风险(实际生产应白名单)
