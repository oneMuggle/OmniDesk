# paperless_proxy 集成后续缺口修复 — 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 PR #54 合并后遗留的 7 个 paperless 缺口(API 视图缺失 + outbox DELETE 405 + update_metadata/delete placeholder + paperless_id=0 与 unique 冲突的 critical bug + 合规/人事 upload action + Django admin 注册),使 paperless_proxy 生产可用。

**Architecture:** 不引入新抽象类,扩展 `PaperlessClient.update_metadata/delete`,扩展 `OutboxService.queue_update_metadata/queue_delete`,`tasks.py` 真正调 paperless API,扩 `OutboxViewSet → ModelViewSet`,新增 `UploadView` + `DocumentBindingViewSet`,迁移 `paperless_id → null=True`(数据 0 占位保留,worker 重试覆盖),compliance/personnel view 复用 `PaperlessUploadService` 加 upload action。

**Tech Stack:** Django 4.2 + DRF, Python 3.10, pytest + pytest-django + pytest-cov, MySQL/PostgreSQL, Celery + Redis, paperless-ngx REST API。

## Global Constraints

- Python 3.10(项目统一,见 CLAUDE.md §8)
- 测试在 `omni_desk` conda 环境运行:`/home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest`
- 所有 commit 必须用 conventional commits(`feat:` / `refactor:` / `test:` / `chore:` / `fix:` / `docs:`)
- paperless_proxy 覆盖率门槛:87.6%(上次合并基线)
- 项目硬约束:纯内网离线;Windows 7 浏览器兼容(Chrome 109)
- 所有对话和文档使用中文(CLAUDE.md §Language)
- Django settings:测试用 `--ds=omni_desk_backend.settings.test`(内存 SQLite)
- 所有 Python 文件保持 ≤ 800 行
- 不引入新的 permission 类;沿用 `IsAdmin` / `IsBindingOwnerOrAdmin`
- **必读 spec 文档:** `docs/superpowers/specs/2026-07-09-paperless-gaps-fix-design.md`

## File Structure(本次改动)

**修改:**
- `omni_desk_backend/paperless_proxy/models.py` — `paperless_id: null=True`
- `omni_desk_backend/paperless_proxy/services/upload.py` — 占位 0 → None
- `omni_desk_backend/paperless_proxy/services/outbox.py` — 加 `queue_update_metadata` / `queue_delete`
- `omni_desk_backend/paperless_proxy/services/client.py` — 加 `update_metadata` / `delete`
- `omni_desk_backend/paperless_proxy/tasks.py` — 实现 `_process_update_metadata` / `_process_delete`,修 `_process_upload` `is None`
- `omni_desk_backend/paperless_proxy/views.py` — 加 `UploadView` / `DocumentBindingViewSet`,`OutboxViewSet → ModelViewSet`
- `omni_desk_backend/paperless_proxy/urls.py` — 注册新路由
- `omni_desk_backend/paperless_proxy/tests/test_views.py` — 扩测试
- `omni_desk_backend/paperless_proxy/tests/test_tasks.py` — 扩测试
- `omni_desk_backend/compliance/views.py` — `ComplianceIssueViewSet.upload` action
- `omni_desk_backend/personnel/views.py` — `PersonnelViewSet.upload` action

**新增:**
- `omni_desk_backend/paperless_proxy/admin.py` — 注册 4 个模型
- `omni_desk_backend/paperless_proxy/migrations/0005_paperless_id_nullable.py` — AlterField
- `omni_desk_backend/paperless_proxy/tests/test_admin.py` — admin 注册测试

---

## Task 1: Model 迁移 paperless_id → null=True

**Files:**
- Modify: `omni_desk_backend/paperless_proxy/models.py:20`
- Create: `omni_desk_backend/paperless_proxy/migrations/0005_paperless_id_nullable.py` (auto-generated)

**Interfaces:**
- Produces: `DocumentBinding.paperless_id` 允许 `NULL`(缺省占位)

- [ ] **Step 1: 写失败测试**

`omni_desk_backend/paperless_proxy/tests/test_models.py` 末尾添加:

```python
@pytest.mark.django_db
def test_paperless_id_nullable():
    """DocumentBinding.paperless_id 必须允许 NULL,避免二次上传 unique 冲突"""
    from django.contrib.auth import get_user_model
    CustomUser = get_user_model()
    user = CustomUser.objects.create_user(username='u_null', password='p')
    binding = DocumentBinding.objects.create(
        source_type='contract', source_id=1,
        paperless_id=None, paperless_checksum='',
        owner=user, title='No paperless yet',
    )
    binding.refresh_from_db()
    assert binding.paperless_id is None
```

- [ ] **Step 2: 跑测试,确认 FAIL**

Run: `cd omni_desk_backend && /home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest paperless_proxy/tests/test_models.py::test_paperless_id_nullable -v`
Expected: `IntegrityError: NOT NULL constraint failed: paperless_proxy_documentbinding.paperless_id`

- [ ] **Step 3: 改 models.py**

`omni_desk_backend/paperless_proxy/models.py` line 20:

```python
# before:
    paperless_id = models.PositiveIntegerField(unique=True, verbose_name="paperless 文档 ID")
# after:
    paperless_id = models.PositiveIntegerField(
        unique=True, null=True, blank=True, verbose_name="paperless 文档 ID"
    )
```

- [ ] **Step 4: 生成 migration 并应用**

Run: `cd omni_desk_backend && /home/fz/anaconda3/envs/OmniDesk/bin/python manage.py makemigrations paperless_proxy`
Expected: 创建 `0005_paperless_id_nullable.py`,内容包含 `AlterField` 把 `paperless_id` 改 `null=True`。

Run: `cd omni_desk_backend && /home/fz/anaconda3/envs/OmniDesk/bin/python manage.py migrate --ds=omni_desk_backend.settings.test`
Expected: 迁移成功,无错误。

- [ ] **Step 5: 跑测试,确认 PASS**

Run: `cd omni_desk_backend && /home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest paperless_proxy/tests/test_models.py -v`
Expected: 全部 PASS

- [ ] **Step 6: Commit**

```bash
git add omni_desk_backend/paperless_proxy/models.py omni_desk_backend/paperless_proxy/migrations/0005_paperless_id_nullable.py omni_desk_backend/paperless_proxy/tests/test_models.py
git commit -m "fix(paperless): allow paperless_id null for async upload placeholder"
```

---

## Task 2: services/upload.py 占位 0 → None

**Files:**
- Modify: `omni_desk_backend/paperless_proxy/services/upload.py:43`

- [ ] **Step 1: 写失败测试**

`omni_desk_backend/paperless_proxy/tests/test_business_integration.py` 末尾追加:

```python
@pytest.mark.django_db
def test_queue_upload_paperless_id_is_none(user, tmp_path):
    """queue_upload 创建的 binding paperless_id 必须为 None,不是 0"""
    from django.core.files.uploadedfile import SimpleUploadedFile
    from ..services.upload import PaperlessUploadService
    file = SimpleUploadedFile('test.pdf', b'hello', content_type='application/pdf')
    result = PaperlessUploadService.queue_upload(
        file=file, filename='test.pdf', title='T',
        source_type='contract', source_id=99, owner=user,
    )
    from ..models import DocumentBinding
    binding = DocumentBinding.objects.get(pk=result['binding_id'])
    assert binding.paperless_id is None
    assert binding.paperless_checksum == ""
```

- [ ] **Step 2: 跑测试,确认 FAIL**

Run: `cd omni_desk_backend && /home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest paperless_proxy/tests/test_business_integration.py::test_queue_upload_paperless_id_is_none -v`
Expected: FAIL,binding.paperless_id 是 0 而非 None

- [ ] **Step 3: 改 services/upload.py**

`omni_desk_backend/paperless_proxy/services/upload.py` line 40-48 区块:

```python
                binding = DocumentBinding.objects.create(
                    source_type=source_type,
                    source_id=source_id,
                    paperless_id=None,  # 异步填充,worker 同步成功后回写
                    paperless_checksum="",
                    owner=owner,
                    title=title,
                    correspondent_id=correspondent,
                )
```

- [ ] **Step 4: 跑测试,确认 PASS**

Run: `cd omni_desk_backend && /home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest paperless_proxy/tests/test_business_integration.py -v`
Expected: 全部 PASS

- [ ] **Step 5: Commit**

```bash
git add omni_desk_backend/paperless_proxy/services/upload.py omni_desk_backend/paperless_proxy/tests/test_business_integration.py
git commit -m "refactor(paperless): use None as upload placeholder instead of 0"
```

---

## Task 3: PaperlessClient.update_metadata + delete

**Files:**
- Modify: `omni_desk_backend/paperless_proxy/services/client.py`(在 `preview` 之后,`search` 之前)
- Modify: `omni_desk_backend/paperless_proxy/tests/test_client.py`(末尾追加)

**Interfaces:**
- Produces:
  - `PaperlessClient.update_metadata(paperless_id: int, fields: dict) -> dict`
  - `PaperlessClient.delete(paperless_id: int) -> None`

- [ ] **Step 1: 写失败测试**

`omni_desk_backend/paperless_proxy/tests/test_client.py` 末尾追加:

```python
from unittest.mock import patch, MagicMock


def test_update_metadata_calls_patch():
    """update_metadata 必须 PATCH /api/documents/{id}/,payload 仅含非空字段"""
    from ..services.client import PaperlessClient
    client = PaperlessClient()
    mock_resp = MagicMock(status_code=200, ok=True)
    mock_resp.json.return_value = {"id": 42, "title": "new"}
    with patch.object(client.session, "request", return_value=mock_resp) as req:
        result = client.update_metadata(42, {"title": "new", "correspondent": None, "tags": [1, 2]})
    assert result == {"id": 42, "title": "new"}
    args, kwargs = req.call_args
    assert args[0] == "PATCH"
    assert "/api/documents/42/" in args[1]
    assert kwargs["json"] == {"title": "new", "tags": [1, 2]}  # None 被过滤


def test_delete_calls_delete():
    """delete 必须 DELETE /api/documents/{id}/"""
    from ..services.client import PaperlessClient
    client = PaperlessClient()
    mock_resp = MagicMock(status_code=204, ok=True)
    with patch.object(client.session, "request", return_value=mock_resp) as req:
        client.delete(42)
    args, kwargs = req.call_args
    assert args[0] == "DELETE"
    assert "/api/documents/42/" in args[1]


def test_delete_404_raises_not_found():
    """delete 时 404 → PaperlessNotFoundError"""
    from ..services.client import PaperlessClient
    from ..exceptions import PaperlessNotFoundError
    client = PaperlessClient()
    mock_resp = MagicMock(status_code=404, ok=False)
    with patch.object(client.session, "request", return_value=mock_resp):
        with pytest.raises(PaperlessNotFoundError):
            client.delete(99)
```

(若 `test_client.py` 顶部还没 import `pytest`,加上 `import pytest`)

- [ ] **Step 2: 跑测试,确认 FAIL**

Run: `cd omni_desk_backend && /home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest paperless_proxy/tests/test_client.py -v`
Expected: `AttributeError: 'PaperlessClient' object has no attribute 'update_metadata'`

- [ ] **Step 3: 在 client.py 添加方法**

`omni_desk_backend/paperless_proxy/services/client.py` line 108 之后(`preview` 之后,`search` 之前),插入:

```python
    def update_metadata(self, paperless_id: int, fields: dict[str, Any]) -> dict[str, Any]:
        """调用 paperless-ngx PATCH /api/documents/{id}/,过滤 None 字段"""
        payload = {k: v for k, v in fields.items() if v is not None}
        resp = self._request("PATCH", f"/api/documents/{paperless_id}/", json=payload)
        return resp.json()

    def delete(self, paperless_id: int) -> None:
        """调用 paperless-ngx DELETE /api/documents/{id}/"""
        self._request("DELETE", f"/api/documents/{paperless_id}/")
```

- [ ] **Step 4: 跑测试,确认 PASS**

Run: `cd omni_desk/backend && /home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest paperless_proxy/tests/test_client.py -v`
Expected: 全部 PASS(含原有测试)

- [ ] **Step 5: Commit**

```bash
git add omni_desk_backend/paperless_proxy/services/client.py omni_desk_backend/paperless_proxy/tests/test_client.py
git commit -m "feat(paperless): add client.update_metadata and client.delete"
```

---

## Task 4: OutboxService.queue_update_metadata + queue_delete

**Files:**
- Modify: `omni_desk_backend/paperless_proxy/services/outbox.py`(末尾追加)
- Modify: `omni_desk_backend/paperless_proxy/tests/test_outbox.py`(末尾追加)

**Interfaces:**
- Produces:
  - `OutboxService.queue_update_metadata(binding, fields, created_by) -> OutboxItem`
  - `OutboxService.queue_delete(binding, created_by) -> OutboxItem`

- [ ] **Step 1: 写失败测试**

`omni_desk_backend/paperless_proxy/tests/test_outbox.py` 末尾追加:

```python
from ..services.outbox import OutboxService


@pytest.mark.django_db
def test_queue_update_metadata_creates_outbox(db, user, binding):
    """queue_update_metadata 创建 operation=update_metadata 的 OutboxItem,payload 含 fields"""
    item = OutboxService.queue_update_metadata(
        binding, fields={"title": "new", "tags": [1]}, created_by=user
    )
    assert item.operation == "update_metadata"
    assert item.status == "pending"
    assert item.payload == {"title": "new", "tags": [1]}
    assert item.binding_id == binding.id
    assert item.created_by_id == user.id


@pytest.mark.django_db
def test_queue_delete_creates_outbox(db, user, binding):
    """queue_delete 创建 operation=delete 的 OutboxItem,payload 含 paperless_id"""
    item = OutboxService.queue_delete(binding, created_by=user)
    assert item.operation == "delete"
    assert item.status == "pending"
    assert item.payload == {"paperless_id": binding.paperless_id}
    assert item.binding_id == binding.id
```

- [ ] **Step 2: 跑测试,确认 FAIL**

Run: `cd omni_desk_backend && /home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest paperless_proxy/tests/test_outbox.py -v`
Expected: `AttributeError: type object 'OutboxService' has no attribute 'queue_update_metadata'`

- [ ] **Step 3: 在 outbox.py 添加方法**

`omni_desk_backend/paperless_proxy/services/outbox.py` line 95 之后(`retry_dead` 之后)添加:

```python
    @staticmethod
    @transaction.atomic
    def queue_update_metadata(binding, fields: dict, created_by) -> OutboxItem:
        """入队 update_metadata 操作,worker 异步调 paperless PATCH"""
        return OutboxItem.objects.create(
            operation="update_metadata",
            status="pending",
            payload=fields,
            binding=binding,
            created_by=created_by,
        )

    @staticmethod
    @transaction.atomic
    def queue_delete(binding, created_by) -> OutboxItem:
        """入队 delete 操作,worker 异步调 paperless DELETE + 删 binding"""
        return OutboxItem.objects.create(
            operation="delete",
            status="pending",
            payload={"paperless_id": binding.paperless_id},
            binding=binding,
            created_by=created_by,
        )
```

- [ ] **Step 4: 跑测试,确认 PASS**

Run: `cd omni_desk_backend && /home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest paperless_proxy/tests/test_outbox.py -v`
Expected: 全部 PASS

- [ ] **Step 5: Commit**

```bash
git add omni_desk_backend/paperless_proxy/services/outbox.py omni_desk_backend/paperless_proxy/tests/test_outbox.py
git commit -m "feat(paperless): outbox queue_update_metadata and queue_delete"
```

---

## Task 5: tasks.py 实现 _process_update_metadata / _process_delete + 修 _process_upload

**Files:**
- Modify: `omni_desk_backend/paperless_proxy/tasks.py`(line 70, 81-88)
- Modify: `omni_desk_backend/paperless_proxy/tests/test_tasks.py`(末尾追加)

**Interfaces:**
- Consumes: `OutboxItem.operation == "upload"/"update_metadata"/"delete"`,`PaperlessClient.update_metadata/delete`
- Produces: `binding.paperless_id` 被回写(binding 已同步)/`binding` 被删除(delete 成功)

- [ ] **Step 1: 写失败测试**

`omni_desk_backend/paperless_proxy/tests/test_tasks.py` 末尾追加:

```python
@pytest.mark.django_db
def test_process_upload_writes_real_paperless_id(user, binding, outbox_item):
    """worker 调 client.upload 后,binding.paperless_id 必须从 None 变为真实 ID"""
    fake_result = {"id": 12345, "checksum": "abc123"}
    with patch.object(PaperlessClient, "upload", return_value=fake_result):
        process_paperless_outbox.apply().get()
    binding.refresh_from_db()
    assert binding.paperless_id == 12345
    assert binding.paperless_checksum == "abc123"


@pytest.mark.django_db
def test_process_update_metadata_calls_client_and_writes_back(user, binding, monkeypatch):
    """update_metadata 调 client.update_metadata 并回写 binding.title"""
    binding.paperless_id = 999  # 已同步
    binding.save()
    OutboxItem.objects.create(
        operation="update_metadata",
        status="pending",
        payload={"title": "updated"},
        binding=binding,
        created_by=user,
    )
    fake_result = {"id": 999, "title": "updated"}
    with patch.object(PaperlessClient, "update_metadata", return_value=fake_result) as m:
        process_paperless_outbox.apply().get()
    m.assert_called_once_with(999, {"title": "updated"})
    binding.refresh_from_db()
    assert binding.title == "updated"


@pytest.mark.django_db
def test_process_update_metadata_skips_when_paperless_id_is_none(user, binding):
    """binding 未同步(paperless_id is None)时 update_metadata 走 mark_failed,不入 client"""
    binding.paperless_id = None
    binding.save()
    OutboxItem.objects.create(
        operation="update_metadata",
        status="pending",
        payload={"title": "x"},
        binding=binding,
        created_by=user,
    )
    with patch.object(PaperlessClient, "update_metadata") as m:
        process_paperless_outbox.apply().get()
    m.assert_not_called()
    failed = OutboxItem.objects.filter(operation="update_metadata").first()
    assert failed.status in ("failed", "dead")


@pytest.mark.django_db
def test_process_delete_calls_client_and_removes_binding(user, binding):
    """delete 调 client.delete 并删 binding(CASCADE 删 outbox)"""
    binding.paperless_id = 888
    binding.save()
    OutboxItem.objects.create(
        operation="delete",
        status="pending",
        payload={"paperless_id": 888},
        binding=binding,
        created_by=user,
    )
    with patch.object(PaperlessClient, "delete") as m:
        process_paperless_outbox.apply().get()
    m.assert_called_once_with(888)
    assert not DocumentBinding.objects.filter(pk=binding.pk).exists()
```

(若 `test_tasks.py` 顶部未 import `PaperlessClient`,加上:`from ..services.client import PaperlessClient`)

- [ ] **Step 2: 跑测试,确认 FAIL**

Run: `cd omni_desk_backend && /home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest paperless_proxy/tests/test_tasks.py -v`
Expected: `test_process_update_metadata_calls_client_and_writes_back` 等 3 个 FAIL

- [ ] **Step 3: 修 tasks.py**

`omni_desk_backend/paperless_proxy/tasks.py` 改三处:

(a) line 70(`_process_upload` 中条件):

```python
    # before:
    if item.binding and not item.binding.paperless_id:
    # after:
    if item.binding and item.binding.paperless_id is None:
```

(b) line 81-83(`_process_delete`),替换:

```python
def _process_delete(item, client: PaperlessClient) -> None:
    paperless_id = item.binding.paperless_id if item.binding else item.payload.get("paperless_id")
    if paperless_id is None:
        raise PaperlessError("binding not yet synced, cannot delete")
    client.delete(paperless_id)
    if item.binding:
        item.binding.delete()  # CASCADE 删 outbox
```

(c) line 86-88(`_process_update_metadata`),替换:

```python
def _process_update_metadata(item, client: PaperlessClient) -> None:
    binding = item.binding
    if not binding or binding.paperless_id is None:
        raise PaperlessError("binding not yet synced, cannot update_metadata")
    client.update_metadata(binding.paperless_id, item.payload)
    # 回写本地 binding
    fields_to_save = []
    if "title" in item.payload:
        binding.title = item.payload["title"]
        fields_to_save.append("title")
    if "extra_metadata" in item.payload:
        binding.extra_metadata = item.payload["extra_metadata"]
        fields_to_save.append("extra_metadata")
    if fields_to_save:
        fields_to_save.append("updated_at")
        binding.save(update_fields=fields_to_save)
```

- [ ] **Step 4: 跑测试,确认 PASS**

Run: `cd omni_desk_backend && /home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest paperless_proxy/tests/test_tasks.py -v`
Expected: 全部 PASS(含原有)

- [ ] **Step 5: Commit**

```bash
git add omni_desk_backend/paperless_proxy/tasks.py omni_desk_backend/paperless_proxy/tests/test_tasks.py
git commit -m "feat(paperless): implement update_metadata and delete workers"
```

---

## Task 6: views.UploadView(POST /api/paperless/upload/)

**Files:**
- Modify: `omni_desk_backend/paperless_proxy/views.py`(在 `OutboxViewSet` 之前插入)
- Modify: `omni_desk_backend/paperless_proxy/urls.py`(注册路由)
- Modify: `omni_desk_backend/paperless_proxy/tests/test_views.py`(追加)

**Interfaces:**
- Produces: `POST /api/paperless/upload/` → `{binding_id, outbox_id, status}` 201,400

- [ ] **Step 1: 写失败测试**

`omni_desk_backend/paperless_proxy/tests/test_views.py` 末尾追加:

```python
from django.core.files.uploadedfile import SimpleUploadedFile


@pytest.mark.django_db
class TestUploadAPI:
    def test_upload_requires_auth(self, db):
        client = APIClient()
        resp = client.post('/api/paperless/upload/', {})
        assert resp.status_code == 401

    def test_upload_missing_file_returns_400(self, user):
        client = APIClient()
        client.force_authenticate(user)
        resp = client.post('/api/paperless/upload/', {'title': 't', 'source_type': 'contract', 'source_id': 1}, format='multipart')
        assert resp.status_code == 400
        assert 'file' in resp.data['detail']

    def test_upload_invalid_source_type_returns_400(self, user):
        client = APIClient()
        client.force_authenticate(user)
        f = SimpleUploadedFile('test.pdf', b'x', content_type='application/pdf')
        resp = client.post('/api/paperless/upload/', {
            'file': f, 'title': 't', 'source_type': 'invalid', 'source_id': 1,
        }, format='multipart')
        assert resp.status_code == 400

    def test_upload_creates_binding_and_outbox(self, user, monkeypatch):
        from ..services.upload import PaperlessUploadService
        monkeypatch.setattr(
            PaperlessUploadService, 'queue_upload',
            staticmethod(lambda **kw: {'binding_id': 1, 'outbox_id': 1, 'status': 'pending'}),
        )
        client = APIClient()
        client.force_authenticate(user)
        f = SimpleUploadedFile('test.pdf', b'x', content_type='application/pdf')
        resp = client.post('/api/paperless/upload/', {
            'file': f, 'title': 't', 'source_type': 'contract', 'source_id': 1,
        }, format='multipart')
        assert resp.status_code == 201
        assert resp.data['status'] == 'pending'
        assert 'binding_id' in resp.data
        assert 'outbox_id' in resp.data
```

- [ ] **Step 2: 跑测试,确认 FAIL**

Run: `cd omni_desk_backend && /home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest paperless_proxy/tests/test_views.py::TestUploadAPI -v`
Expected: 404 Not Found(路由未注册)

- [ ] **Step 3: 加 UploadView**

`omni_desk_backend/paperless_proxy/views.py` line 19 后(`from` 区块后,`OutboxViewSet` 前)插入:

```python
class UploadView(APIView):
    """POST /api/paperless/upload/ — multipart 上传,入 outbox"""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        from .services.upload import PaperlessUploadService
        file = request.FILES.get("file")
        if not file:
            return Response(
                {"detail": "缺少 file 字段"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            result = PaperlessUploadService.queue_upload(
                file=file,
                filename=file.name,
                title=request.data.get("title") or file.name,
                source_type=request.data.get("source_type", "project_document"),
                source_id=int(request.data.get("source_id", 0)),
                owner=request.user,
                correspondent=request.data.get("correspondent"),
                document_type=request.data.get("document_type"),
                tags=request.data.get("tags"),
            )
        except (ValueError, TypeError) as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(result, status=status.HTTP_201_CREATED)
```

- [ ] **Step 4: 注册路由**

`omni_desk_backend/paperless_proxy/urls.py` line 2-11 区块更新:

```python
from .views import (
    OutboxViewSet,
    HealthView,
    BindView,
    BindStatusView,
    DocumentDownloadView,
    DocumentPreviewView,
    BindingSyncStatusView,
    UploadView,
)
```

line 17 前(`urlpatterns` 中,`health` 之前)添加:

```python
    path("upload/", UploadView.as_view(), name="upload"),
```

- [ ] **Step 5: 跑测试,确认 PASS**

Run: `cd omni_desk_backend && /home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest paperless_proxy/tests/test_views.py::TestUploadAPI -v`
Expected: 全部 PASS

- [ ] **Step 6: Commit**

```bash
git add omni_desk_backend/paperless_proxy/views.py omni_desk_backend/paperless_proxy/urls.py omni_desk_backend/paperless_proxy/tests/test_views.py
git commit -m "feat(paperless): expose POST /api/paperless/upload/"
```

---

## Task 7: views.DocumentBindingViewSet(GET list + GET/PATCH/DELETE detail)

**Files:**
- Modify: `omni_desk_backend/paperless_proxy/views.py`(末尾追加)
- Modify: `omni_desk_backend/paperless_proxy/urls.py`(注册 router)
- Modify: `omni_desk_backend/paperless_proxy/tests/test_views.py`(追加)

**Interfaces:**
- Produces: `GET/PATCH/DELETE /api/paperless/documents/{id}/`,`GET /api/paperless/documents/`(分页 + 过滤)

- [ ] **Step 1: 写失败测试**

`omni_desk_backend/paperless_proxy/tests/test_views.py` 末尾追加:

```python
@pytest.mark.django_db
class TestDocumentBindingAPI:
    def test_list_requires_auth(self, db):
        client = APIClient()
        resp = client.get('/api/paperless/documents/')
        assert resp.status_code == 401

    def test_list_returns_paginated_results(self, user, binding):
        client = APIClient()
        client.force_authenticate(user)
        resp = client.get('/api/paperless/documents/')
        assert resp.status_code == 200
        assert 'results' in resp.data
        assert len(resp.data['results']) >= 1

    def test_list_filter_by_source_type(self, user, binding):
        client = APIClient()
        client.force_authenticate(user)
        resp = client.get('/api/paperless/documents/?source_type=contract')
        assert resp.status_code == 200
        for item in resp.data['results']:
            assert item['source_type'] == 'contract'

    def test_detail_owner_can_access(self, user, binding):
        client = APIClient()
        client.force_authenticate(user)
        resp = client.get(f'/api/paperless/documents/{binding.id}/')
        assert resp.status_code == 200
        assert resp.data['title'] == 'X'

    def test_detail_non_owner_non_admin_forbidden(self, db, binding):
        other = CustomUser.objects.create_user(username='other', password='p')
        client = APIClient()
        client.force_authenticate(other)
        resp = client.get(f'/api/paperless/documents/{binding.id}/')
        assert resp.status_code == 403

    def test_detail_admin_can_access(self, admin, binding):
        client = APIClient()
        client.force_authenticate(admin)
        resp = client.get(f'/api/paperless/documents/{binding.id}/')
        assert resp.status_code == 200

    def test_patch_creates_update_metadata_outbox(self, user, binding):
        client = APIClient()
        client.force_authenticate(user)
        resp = client.patch(
            f'/api/paperless/documents/{binding.id}/',
            {'title': 'new'},
            format='json',
        )
        assert resp.status_code == 202
        assert OutboxItem.objects.filter(operation='update_metadata', binding=binding).exists()

    def test_delete_creates_delete_outbox(self, user, binding):
        client = APIClient()
        client.force_authenticate(user)
        resp = client.delete(f'/api/paperless/documents/{binding.id}/')
        assert resp.status_code == 202
        assert OutboxItem.objects.filter(operation='delete', binding=binding).exists()
```

- [ ] **Step 2: 跑测试,确认 FAIL**

Run: `cd omni_desk_backend && /home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest paperless_proxy/tests/test_views.py::TestDocumentBindingAPI -v`
Expected: 404 Not Found(路由未注册)

- [ ] **Step 3: 加 DocumentBindingViewSet**

`omni_desk_backend/paperless_proxy/views.py` line 171 末尾追加:

```python
class DocumentBindingViewSet(viewsets.ModelViewSet):
    """DocumentBinding CRUD + 异步 update_metadata/delete"""

    queryset = DocumentBinding.objects.all()
    serializer_class = DocumentBindingSerializer
    permission_classes = [IsAuthenticated, IsBindingOwnerOrAdmin]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["source_type", "source_id", "owner", "paperless_id"]

    def update(self, request, *args, **kwargs):
        """PATCH → 入 update_metadata outbox(不直接改 binding)"""
        binding = self.get_object()
        fields = {k: v for k, v in request.data.items() if k in ("title", "correspondent_id", "extra_metadata", "tags")}
        outbox = OutboxService.queue_update_metadata(binding, fields, created_by=request.user)
        return Response(
            {"binding_id": binding.id, "outbox_id": outbox.id, "status": outbox.status},
            status=status.HTTP_202_ACCEPTED,
        )

    def partial_update(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        """DELETE → 入 delete outbox(worker 异步删 binding + paperless)"""
        binding = self.get_object()
        outbox = OutboxService.queue_delete(binding, created_by=request.user)
        return Response(
            {"binding_id": binding.id, "outbox_id": outbox.id, "status": outbox.status},
            status=status.HTTP_202_ACCEPTED,
        )
```

- [ ] **Step 4: 注册路由**

`omni_desk_backend/paperless_proxy/urls.py` line 13-15 区块更新:

```python
router = DefaultRouter()
router.register(r"outbox", OutboxViewSet, basename="outbox")
router.register(r"documents", DocumentBindingViewSet, basename="documents")
```

- [ ] **Step 5: 跑测试,确认 PASS**

Run: `cd omni_desk_backend && /home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest paperless_proxy/tests/test_views.py::TestDocumentBindingAPI -v`
Expected: 全部 PASS

- [ ] **Step 6: Commit**

```bash
git add omni_desk_backend/paperless_proxy/views.py omni_desk_backend/paperless_proxy/urls.py omni_desk_backend/paperless_proxy/tests/test_views.py
git commit -m "feat(paperless): expose DocumentBinding CRUD with async outbox"
```

---

## Task 8: OutboxViewSet 改 ModelViewSet(支持 DELETE + GET single)

**Files:**
- Modify: `omni_desk_backend/paperless_proxy/views.py:21-39`
- Modify: `omni_desk_backend/paperless_proxy/tests/test_views.py`(扩 `TestOutboxListAPI` + 新增 `TestOutboxDeleteAPI`)

**Interfaces:**
- Produces: `GET /api/paperless/outbox/{id}/` → 200/403;`DELETE /api/paperless/outbox/{id}/` → 204(仅 dead)/400/403

- [ ] **Step 1: 写失败测试**

`omni_desk_backend/paperless_proxy/tests/test_views.py` 在 `TestOutboxListAPI` 类内末尾追加:

```python
    def test_retrieve_requires_admin(self, user, dead_outbox):
        client = APIClient()
        client.force_authenticate(user)
        resp = client.get(f'/api/paperless/outbox/{dead_outbox.id}/')
        assert resp.status_code == 403

    def test_admin_can_retrieve(self, admin, dead_outbox):
        client = APIClient()
        client.force_authenticate(admin)
        resp = client.get(f'/api/paperless/outbox/{dead_outbox.id}/')
        assert resp.status_code == 200
        assert resp.data['id'] == dead_outbox.id


@pytest.mark.django_db
class TestOutboxDeleteAPI:
    def test_delete_requires_admin(self, user, dead_outbox):
        client = APIClient()
        client.force_authenticate(user)
        resp = client.delete(f'/api/paperless/outbox/{dead_outbox.id}/')
        assert resp.status_code == 403

    def test_delete_non_dead_returns_400(self, admin, user, binding):
        pending = OutboxItem.objects.create(
            operation='upload', status='pending', payload={}, binding=binding, created_by=user,
        )
        client = APIClient()
        client.force_authenticate(admin)
        resp = client.delete(f'/api/paperless/outbox/{pending.id}/')
        assert resp.status_code == 400

    def test_delete_dead_returns_204_and_removes(self, admin, dead_outbox):
        client = APIClient()
        client.force_authenticate(admin)
        resp = client.delete(f'/api/paperless/outbox/{dead_outbox.id}/')
        assert resp.status_code == 204
        assert not OutboxItem.objects.filter(pk=dead_outbox.id).exists()
```

- [ ] **Step 2: 跑测试,确认 FAIL**

Run: `cd omni_desk_backend && /home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest paperless_proxy/tests/test_views.py::TestOutboxDeleteAPI -v`
Expected: 405 Method Not Allowed(ReadOnlyModelViewSet 不支持 DELETE)

- [ ] **Step 3: 改 OutboxViewSet**

`omni_desk_backend/paperless_proxy/views.py` line 21-39 区块替换:

```python
class OutboxViewSet(viewsets.ModelViewSet):
    """Outbox 管理(admin 限定)"""

    queryset = OutboxItem.objects.all()
    serializer_class = OutboxItemSerializer
    permission_classes = [IsAdmin]
    http_method_names = ["get", "post", "delete", "head", "options"]  # 禁 PUT/PATCH
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["status", "operation"]

    def destroy(self, request, *args, **kwargs):
        """仅 dead 状态可删除,避免误删正在处理的项"""
        outbox = self.get_object()
        if outbox.status != "dead":
            return Response(
                {"detail": f"只能删除死信(当前 status={outbox.status})"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=["post"])
    def retry(self, request, pk=None):
        outbox = self.get_object()
        if outbox.status != "dead":
            return Response(
                {"detail": f"只能重试死信(当前 status={outbox.status})"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        OutboxService.retry_dead(outbox)
        return Response(OutboxItemSerializer(outbox).data)
```

- [ ] **Step 4: 跑测试,确认 PASS**

Run: `cd omni_desk_backend && /home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest paperless_proxy/tests/test_views.py -v`
Expected: 全部 PASS(含原有 `TestOutboxListAPI`)

- [ ] **Step 5: Commit**

```bash
git add omni_desk_backend/paperless_proxy/views.py omni_desk_backend/paperless_proxy/tests/test_views.py
git commit -m "feat(paperless): OutboxViewSet support DELETE and GET single"
```

---

## Task 9: admin.py 注册 4 个 paperless 模型

**Files:**
- Create: `omni_desk_backend/paperless_proxy/admin.py`
- Create: `omni_desk_backend/paperless_proxy/tests/test_admin.py`

**Interfaces:**
- Produces: Django admin 可访问 `DocumentBinding` / `OutboxItem` / `UserPaperlessBinding` / `PaperlessHealth`

- [ ] **Step 1: 写失败测试**

`omni_desk_backend/paperless_proxy/tests/test_admin.py`:

```python
from django.contrib import admin
from ..models import DocumentBinding, OutboxItem, UserPaperlessBinding, PaperlessHealth


def test_all_paperless_models_registered_in_admin():
    """4 个 paperless 模型必须在 Django admin 中已注册"""
    registered = set(admin.site._registry.keys())
    for model in (DocumentBinding, OutboxItem, UserPaperlessBinding, PaperlessHealth):
        assert model in registered, f"{model.__name__} 未注册到 Django admin"


def test_document_binding_admin_has_list_display():
    from ..models import DocumentBinding
    ma = admin.site._registry[DocumentBinding]
    display = ma.list_display
    assert 'owner' in display or any('owner' in str(c) for c in display)
```

- [ ] **Step 2: 跑测试,确认 FAIL**

Run: `cd omni_desk_backend && /home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest paperless_proxy/tests/test_admin.py -v`
Expected: `AssertionError: DocumentBinding 未注册到 Django admin`

- [ ] **Step 3: 创建 admin.py**

`omni_desk_backend/paperless_proxy/admin.py`:

```python
"""paperless_proxy Django admin 注册"""

from django.contrib import admin
from .models import DocumentBinding, OutboxItem, UserPaperlessBinding, PaperlessHealth


@admin.register(DocumentBinding)
class DocumentBindingAdmin(admin.ModelAdmin):
    list_display = ("__str__", "owner", "paperless_id", "source_type", "created_at")
    list_filter = ("source_type",)
    search_fields = ("title", "source_id")
    raw_id_fields = ("owner",)
    readonly_fields = ("paperless_checksum", "created_at", "updated_at")


@admin.register(OutboxItem)
class OutboxItemAdmin(admin.ModelAdmin):
    list_display = ("id", "operation", "status", "binding", "retry_count", "next_retry_at", "created_at")
    list_filter = ("operation", "status")
    search_fields = ("binding__title",)
    raw_id_fields = ("binding", "created_by")
    readonly_fields = ("payload", "last_error", "created_at", "updated_at")


@admin.register(UserPaperlessBinding)
class UserPaperlessBindingAdmin(admin.ModelAdmin):
    list_display = ("user", "paperless_username", "is_active", "bound_at")
    search_fields = ("user__username", "paperless_username")
    raw_id_fields = ("user",)


@admin.register(PaperlessHealth)
class PaperlessHealthAdmin(admin.ModelAdmin):
    list_display = ("is_healthy", "consecutive_failures", "last_check_at")
    readonly_fields = ("last_check_at",)
```

- [ ] **Step 4: 跑测试,确认 PASS**

Run: `cd omni_desk_backend && /home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest paperless_proxy/tests/test_admin.py -v`
Expected: 全部 PASS

- [ ] **Step 5: Commit**

```bash
git add omni_desk_backend/paperless_proxy/admin.py omni_desk_backend/paperless_proxy/tests/test_admin.py
git commit -m "feat(paperless): register 4 models in Django admin"
```

---

## Task 10: ComplianceIssueViewSet.upload action

**Files:**
- Modify: `omni_desk_backend/compliance/views.py`(`ComplianceIssueViewSet` 内添加 `@action`)
- Modify: `omni_desk_backend/compliance/tests/test_views.py`(追加 upload 测试)

**Interfaces:**
- Produces: `POST /api/compliance/issues/{id}/upload/` → 201/400

- [ ] **Step 1: 写失败测试**

`omni_desk_backend/compliance/tests/test_views.py` 末尾追加:

```python
import pytest
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

CustomUser = get_user_model()


@pytest.fixture
def issue(db):
    from compliance.models import ComplianceIssue
    user = CustomUser.objects.create_user(username='owner', password='p')
    return ComplianceIssue.objects.create(
        title='Test Issue',
        description='d',
        severity='medium',
        status='open',
        reporter=user,
    )


@pytest.mark.django_db
class TestComplianceUpload:
    def test_owner_can_upload(self, issue, monkeypatch):
        from paperless_proxy.services.upload import PaperlessUploadService
        monkeypatch.setattr(
            PaperlessUploadService, 'queue_upload',
            staticmethod(lambda **kw: {'binding_id': 1, 'outbox_id': 1, 'status': 'pending'}),
        )
        owner = issue.reporter
        client = APIClient()
        client.force_authenticate(owner)
        f = SimpleUploadedFile('r.pdf', b'x', content_type='application/pdf')
        resp = client.post(
            f'/api/compliance/issues/{issue.id}/upload/',
            {'file': f, 'title': 'report'},
            format='multipart',
        )
        assert resp.status_code == 201

    def test_non_owner_non_admin_forbidden(self, issue):
        other = CustomUser.objects.create_user(username='other', password='p')
        client = APIClient()
        client.force_authenticate(other)
        f = SimpleUploadedFile('r.pdf', b'x', content_type='application/pdf')
        resp = client.post(
            f'/api/compliance/issues/{issue.id}/upload/',
            {'file': f, 'title': 'report'},
            format='multipart',
        )
        assert resp.status_code == 403

    def test_admin_can_upload(self, issue, monkeypatch):
        from paperless_proxy.services.upload import PaperlessUploadService
        monkeypatch.setattr(
            PaperlessUploadService, 'queue_upload',
            staticmethod(lambda **kw: {'binding_id': 1, 'outbox_id': 1, 'status': 'pending'}),
        )
        admin = CustomUser.objects.create_superuser(username='adm', password='a', email='a@a')
        client = APIClient()
        client.force_authenticate(admin)
        f = SimpleUploadedFile('r.pdf', b'x', content_type='application/pdf')
        resp = client.post(
            f'/api/compliance/issues/{issue.id}/upload/',
            {'file': f, 'title': 'report'},
            format='multipart',
        )
        assert resp.status_code == 201
```

- [ ] **Step 2: 跑测试,确认 FAIL**

Run: `cd omni_desk_backend && /home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest compliance/tests/test_views.py::TestComplianceUpload -v`
Expected: 404 Not Found(路由未注册)

- [ ] **Step 3: 加 upload action**

`omni_desk_backend/compliance/views.py` `ComplianceIssueViewSet` 类内(任何方法前)插入:

```python
    @action(detail=True, methods=["post"])
    def upload(self, request, pk=None):
        """上传合规报告,通过 paperless_proxy 异步投递到 paperless-ngx"""
        from paperless_proxy.services.upload import PaperlessUploadService
        issue = self.get_object()
        file = request.FILES.get("file")
        if not file:
            return Response({"detail": "缺少 file 字段"}, status=400)
        try:
            result = PaperlessUploadService.queue_upload(
                file=file,
                filename=file.name,
                title=request.data.get("title") or file.name,
                source_type="compliance_report",
                source_id=issue.id,
                owner=request.user,
                tags=request.data.get("tags"),
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response(result, status=201)
```

- [ ] **Step 4: 跑测试,确认 PASS**

Run: `cd omni_desk_backend && /home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest compliance/tests/test_views.py -v`
Expected: 全部 PASS

- [ ] **Step 5: Commit**

```bash
git add omni_desk_backend/compliance/views.py omni_desk_backend/compliance/tests/test_views.py
git commit -m "feat(compliance): expose issue upload action to paperless"
```

---

## Task 11: PersonnelViewSet.upload action

**Files:**
- Modify: `omni_desk_backend/personnel/views.py`(`PersonnelViewSet` 内添加 `@action`)
- Modify: `omni_desk_backend/personnel/tests/test_views.py`(追加 upload 测试)

**Interfaces:**
- Produces: `POST /api/personnel/personnels/{id}/upload/` → 201/400/403

- [ ] **Step 1: 写失败测试**

`omni_desk_backend/personnel/tests/test_views.py` 末尾追加:

```python
@pytest.fixture
def personnel(db):
    from personnel.models import Personnel
    user = CustomUser.objects.create_user(username='hr', password='p')
    return Personnel.objects.create(
        name='Test Person',
        employee_id='E001',
        id_card='110101199001011234',
        created_by=user,
    )


@pytest.mark.django_db
class TestPersonnelUpload:
    def test_admin_can_upload(self, personnel, monkeypatch):
        from paperless_proxy.services.upload import PaperlessUploadService
        monkeypatch.setattr(
            PaperlessUploadService, 'queue_upload',
            staticmethod(lambda **kw: {'binding_id': 1, 'outbox_id': 1, 'status': 'pending'}),
        )
        admin = CustomUser.objects.create_superuser(username='adm2', password='a', email='a2@a')
        client = APIClient()
        client.force_authenticate(admin)
        f = SimpleUploadedFile('p.pdf', b'x', content_type='application/pdf')
        resp = client.post(
            f'/api/personnel/personnels/{personnel.id}/upload/',
            {'file': f, 'title': '档案'},
            format='multipart',
        )
        assert resp.status_code == 201

    def test_unauthenticated_forbidden(self, personnel):
        client = APIClient()
        f = SimpleUploadedFile('p.pdf', b'x', content_type='application/pdf')
        resp = client.post(
            f'/api/personnel/personnels/{personnel.id}/upload/',
            {'file': f, 'title': '档案'},
            format='multipart',
        )
        assert resp.status_code in (401, 403)
```

- [ ] **Step 2: 跑测试,确认 FAIL**

Run: `cd omni_desk_backend && /home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest personnel/tests/test_views.py::TestPersonnelUpload -v`
Expected: 404 / 405(路由未注册或方法不允许)

- [ ] **Step 3: 加 upload action**

`omni_desk_backend/personnel/views.py` `PersonnelViewSet` 类内插入:

```python
    @action(detail=True, methods=["post"])
    def upload(self, request, pk=None):
        """上传人事档案,通过 paperless_proxy 异步投递到 paperless-ngx"""
        from paperless_proxy.services.upload import PaperlessUploadService
        personnel = self.get_object()
        file = request.FILES.get("file")
        if not file:
            return Response({"detail": "缺少 file 字段"}, status=400)
        try:
            result = PaperlessUploadService.queue_upload(
                file=file,
                filename=file.name,
                title=request.data.get("title") or file.name,
                source_type="personnel_file",
                source_id=personnel.id,
                owner=request.user,
                tags=request.data.get("tags"),
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response(result, status=201)
```

- [ ] **Step 4: 跑测试,确认 PASS**

Run: `cd omni_desk_backend && /home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest personnel/tests/test_views.py -v`
Expected: 全部 PASS

- [ ] **Step 5: Commit**

```bash
git add omni_desk_backend/personnel/views.py omni_desk_backend/personnel/tests/test_views.py
git commit -m "feat(personnel): expose personnel upload action to paperless"
```

---

## Task 12: 全套 paperless_proxy + compliance/personnel 测试 + 覆盖率验证

**Files:** 无(只跑测试)

- [ ] **Step 1: 跑 paperless_proxy 全套测试**

Run: `cd omni_desk_backend && /home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest paperless_proxy/ -v --cov=paperless_proxy --cov-report=term-missing`
Expected: 全部 PASS,覆盖率 ≥ 87%

- [ ] **Step 2: 跑 compliance/personnel 集成测试**

Run: `cd omni_desk_backend && /home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest compliance/tests/test_views.py personnel/tests/test_views.py -v`
Expected: 全部 PASS

- [ ] **Step 3: 跑 makemigrations 检查**

Run: `cd omni_desk_backend && /home/fz/anaconda3/envs/OmniDesk/bin/python manage.py makemigrations --check --dry-run --ds=omni_desk_backend.settings.test`
Expected: `No changes detected`

- [ ] **Step 4: 跑 lint**

Run: `cd omni_desk_backend && /home/fz/anaconda3/envs/OmniDesk/bin/python -m ruff check paperless_proxy compliance/views.py personnel/views.py`
Expected: `All checks passed!`(若有警告,按项目惯例修复或忽略)

- [ ] **Step 5: 跑 mypy(若项目配置)**

Run: `cd omni_desk_backend && /home/fz/anaconda3/envs/OmniDesk/bin/python -m mypy paperless_proxy 2>&1 | head -20`
Expected: 无新增 error(若有,修复)

- [ ] **Step 6: 跑全项目 pytest 短测试**

Run: `cd omni_desk_backend && /home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest -x --timeout=60 2>&1 | tail -30`
Expected: 全部 PASS(或仅已知 slow test skip)

- [ ] **Step 7: 最终 commit(若有 fix)**

```bash
git status
# 若有未提交的 fix:
git add -A && git commit -m "fix(paperless): post-test cleanup"
```

---

## 验收清单

- [ ] Task 1: `DocumentBinding.paperless_id` 可 NULL
- [ ] Task 2: `queue_upload` 用 None 占位
- [ ] Task 3: `PaperlessClient.update_metadata/delete` 实现
- [ ] Task 4: `OutboxService.queue_update_metadata/queue_delete` 实现
- [ ] Task 5: worker 真正调 paperless API,binding 同步回写
- [ ] Task 6: `POST /api/paperless/upload/` 暴露
- [ ] Task 7: `DocumentBindingViewSet` 列表 + GET/PATCH/DELETE detail
- [ ] Task 8: `OutboxViewSet` 支持 GET single + DELETE dead
- [ ] Task 9: 4 个模型注册 Django admin
- [ ] Task 10: compliance issue upload action
- [ ] Task 11: personnel upload action
- [ ] Task 12: 全部测试 PASS,覆盖率 ≥ 87%,无 lint/mypy 错误

## 自检结果(写作时)

| 检查项 | 结果 |
|---|---|
| Spec 覆盖 | 7 个 gap 全部覆盖:Task 1 (paperless_id null) / Task 2 (None 占位) / Task 3-5 (client+outbox+worker) / Task 6 (upload view) / Task 7 (documents view) / Task 8 (outbox DELETE) / Task 9 (admin) / Task 10-11 (compliance/personnel) |
| 占位符扫描 | 无 TBD/TODO;所有代码块完整 |
| 类型一致性 | `OutboxService.queue_update_metadata(binding, fields, created_by)` / `queue_delete(binding, created_by)` 在 Task 4 定义,Task 7 使用,签名一致;`PaperlessClient.update_metadata(id, fields)` / `delete(id)` 在 Task 3 定义,Task 5 使用,签名一致 |
| DRY | upload action pattern 在 Task 6(UploadView)/Task 10(ComplianceIssue)/Task 11(Personnel)重复 3 次,但因 view 不同(APIView / @action)需独立展示 |