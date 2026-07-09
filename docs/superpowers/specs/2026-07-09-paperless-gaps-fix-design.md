# paperless_proxy 集成后续缺口修复 设计规范

**日期:** 2026-07-09
**项目:** OmniDesk
**作者:** Claude
**状态:** 待用户审阅
**前置 PR:** #54(已合并,094af0e)

---

## 1. 背景与目标

### 1.1 问题

PR #54 将 paperless-ngx 集成合并到 main,但合并后的代码留下 **7 个已知缺口**(5 个合并时识别 + 2 个 deferred):

| # | 缺口 | 严重度 | 类型 |
|---|---|---|---|
| 1 | 缺少 `POST /api/paperless/upload/` 视图(`PaperlessUploadService` 已实现,未暴露 HTTP) | HIGH | API 缺失 |
| 2 | 缺少 `GET /api/paperless/documents/` 列表视图(`DocumentBindingSerializer` 已存在但未使用) | HIGH | API 缺失 |
| 3 | 缺少 `admin.py`,4 个 paperless 模型未注册 Django admin | MEDIUM | 运维缺失 |
| 4 | `DELETE /api/paperless/outbox/{id}/` 返回 405(`OutboxViewSet` 是 `ReadOnlyModelViewSet`,不支持 DELETE) | MEDIUM | API 缺陷 |
| 5 | `update_metadata` / `delete` 操作 `tasks.py` 中是 `raise PaperlessError("not implemented in v1")` placeholder | HIGH | 功能缺失 |
| 6(原 deferred #1,已变 critical bug) | `DocumentBinding.paperless_id` 模型约束为 `unique=True`,但 `services/upload.py` 用 `paperless_id=0` 作临时占位 → 同一 `source_type+source_id` 第二次上传触发 `IntegrityError`,transaction 回滚 | **CRITICAL** | 数据完整性 bug |
| 7(原 deferred #2) | `compliance/views.py` 和 `personnel/views.py` 没有 paperless upload action | HIGH | 模块缺失 |

### 1.2 目标

一次合并修复全部 7 个缺口,使 paperless_proxy app **生产可用**:

- 暴露缺失的 upload / documents 视图,前端可正常调通
- admin 可管理 4 个模型
- outbox 可删 dead 项
- update_metadata / delete 操作真正调 paperless API
- 修 critical bug:paperless_id 占位冲突
- compliance / personnel 模块支持上传到 paperless

### 1.3 范围(明确做与不做)

| 做 | 不做 |
|---|---|
| 新增 upload / documents 视图,扩 OutboxViewSet 支持 DELETE | 重写现有 upload 流程(沿用 outbox 异步语义) |
| `DocumentBindingViewSet` 暴露 update_metadata / delete action | 软删除(默认硬删,paperless 端删除 + 本地 binding 删除) |
| `PaperlessClient` 扩 `update_metadata()` / `delete()` 方法 | 重写 PaperlessClient 的 auth / 重试逻辑 |
| `tasks.py` 实现 `_process_update_metadata` / `_process_delete` 真正调 paperless API | 把所有 outbox 操作改成同步 |
| 迁移 `paperless_id` → `null=True`(标准 AlterField) | 数据回填 migration(0 占位保留,worker 自然会重试覆盖) |
| 注册 4 个 paperless 模型到 Django admin | 自定义 admin actions(后续可加) |
| compliance / personnel view 加 upload action(复用对象级权限) | 抽象统一的 `IsPaperlessUploader` 权限类(YAGNI) |
| 写/扩测试覆盖新 API 与 critical bug 修复 | 前端 E2E 测试(已有覆盖,本次不动) |
| 不动现有 `projects/views.py` 的 upload action(已是参考实现) | 改前端 upload 组件 |

---

## 2. 设计方案

### 2.1 架构

```
omni_desk_backend/paperless_proxy/
├── models.py            # ✏️ DocumentBinding.paperless_id: null=True
├── migrations/0005_*.py # 🆕 AlterField paperless_id → nullable
├── services/
│   ├── upload.py        # ✏️ paperless_id 占位 0 → None
│   ├── outbox.py        # ✏️ 加 queue_update_metadata / queue_delete 静态方法
│   └── client.py        # ✏️ 加 update_metadata(paperless_id, fields) / delete(paperless_id)
├── views.py             # ✏️ 新增 UploadView / DocumentBindingViewSet
│                        #     OutboxViewSet 改 ModelViewSet(支持 DELETE)
├── urls.py              # ✏️ 注册新路由
├── admin.py             # 🆕 注册 4 个模型
└── tasks.py             # ✏️ _process_upload: not paperless_id → is None
                         #     实现 _process_update_metadata / _process_delete

omni_desk_backend/
├── projects/views.py    # (不动,已有 upload action)
├── compliance/views.py  # ✏️ 加 upload action(复用对象级权限)
└── personnel/views.py   # ✏️ 加 upload action(复用对象级权限)
```

**架构原则:** 不引入新的抽象类;`upload/update_metadata/delete` 三类操作统一通过 outbox 通道,`PaperlessClient` 扩 3 个方法,`tasks.py` 填充实际 paperless API 调用。

### 2.2 接口设计

| 方法 | 路径 | 鉴权 | 行为 | 状态码 |
|---|---|---|---|---|
| `POST` | `/api/paperless/upload/` | IsAuthenticated | 接收 multipart/form-data:`file`, `title`, `source_type`, `source_id`, 可选 `correspondent`/`document_type`/`tags` → 入 outbox | 201 / 400 |
| `GET` | `/api/paperless/documents/` | IsAuthenticated | 列表查询 `DocumentBinding`,过滤:`source_type`/`source_id`/`owner`/`paperless_id`,分页 20/page | 200 |
| `GET` | `/api/paperless/documents/{id}/` | IsAuthenticated + IsBindingOwnerOrAdmin | 单个 binding 详情(含 `outbox_status`) | 200 / 404 |
| `PATCH` | `/api/paperless/documents/{id}/` | IsAuthenticated + IsBindingOwnerOrAdmin | 部分更新 metadata → 入 `update_metadata` outbox | 202 |
| `DELETE` | `/api/paperless/documents/{id}/` | IsAuthenticated + IsBindingOwnerOrAdmin | 删除 → 入 `delete` outbox,worker 异步调 paperless DELETE + 删 binding 行 | 202 |
| `DELETE` | `/api/paperless/outbox/{id}/` | IsAdmin | 删 outbox 项(仅 `status=dead`) | 204 / 400 |
| `GET` | `/api/paperless/outbox/{id}/` | IsAdmin | 单个 outbox 详情 | 200 |

**Serializer 复用:**
- `DocumentBindingSerializer`(已有 line 25-48,本次启用)
- `OutboxItemSerializer`(已有)

**新增 OutboxService 方法(在 `services/outbox.py`):**

```python
@staticmethod
@transaction.atomic
def queue_update_metadata(binding: DocumentBinding, fields: dict, created_by) -> OutboxItem:
    return OutboxItem.objects.create(
        operation="update_metadata",
        status="pending",
        payload=fields,
        binding=binding,
        created_by=created_by,
    )

@staticmethod
@transaction.atomic
def queue_delete(binding: DocumentBinding, created_by) -> OutboxItem:
    return OutboxItem.objects.create(
        operation="delete",
        status="pending",
        payload={"paperless_id": binding.paperless_id},
        binding=binding,
        created_by=created_by,
    )
```

### 2.3 数据流

**Upload 流(POST /upload/):**

```
multipart → PaperlessUploadService.queue_upload()
  ├─ 保存到 MEDIA_ROOT/paperless_pending/<uuid>_<name>(0o600)
  ├─ transaction.atomic:
  │   ├─ DocumentBinding.objects.create(paperless_id=None, paperless_checksum="", ...)
  │   └─ OutboxService.enqueue(operation="upload", payload={...}, binding, created_by)
  └─ return {binding_id, outbox_id, status: "pending"}
```

**Celery worker(`process_paperless_outbox`):**

```
fetch_pending → for item:
  if upload → _process_upload(item, client):
    client.upload(file, ...) → result.id, result.checksum
    binding.paperless_id = result.id       # None → 真实 ID
    binding.paperless_checksum = result.checksum
    binding.save()
    os.remove(pending file)
```

**Update_metadata 流(PATCH /documents/{id}/):**

```
view → OutboxService.queue_update_metadata(binding, fields={title?, correspondent_id?, tags?, extra_metadata?})
  ├─ OutboxItem.objects.create(operation="update_metadata", payload=fields, binding)
  └─ return 202 + {outbox_id, status}
```

**Celery worker:**

```
_process_update_metadata(item, client):
  if item.binding.paperless_id is None: raise PaperlessError("binding not yet synced")
  client.update_metadata(paperless_id, item.payload)
  binding.title = item.payload.get("title", binding.title)
  binding.save(update_fields=["title", "extra_metadata", "updated_at"])
```

**Delete 流(DELETE /documents/{id}/):**

```
view → OutboxService.queue_delete(binding)
  ├─ OutboxItem.objects.create(operation="delete", payload={paperless_id}, binding)
  └─ return 202 + {outbox_id, status}
```

**Celery worker:**

```
_process_delete(item, client):
  if item.binding.paperless_id is None: raise PaperlessError("binding not yet synced")
  client.delete(item.binding.paperless_id)
  item.binding.delete()  # CASCADE 删 outbox
```

**outbox DELETE 流(DELETE /outbox/{id}/):**

```
view → 检查 status == "dead" → outbox.delete()
status != "dead" → 400 + detail
```

**compliance / personnel upload 流:** 复用 `projects/views.py:60-93` 的同款 `upload` action pattern,绑定 `source_type=compliance_report` / `personnel_file`。

### 2.4 错误处理

| 场景 | 错误源 | 处理 |
|---|---|---|
| `paperless_id` 旧数据 `0` 占位冲突 | migration 后 | 保留 0(语义"未同步"),worker 看到 0 仍重试,同步成功后改写为真实 ID |
| `_process_upload` 调 `client.upload` 失败 | paperless 不可用 / auth 失败 | `OutboxService.mark_failed` → 指数退避(30s * 2^retry),10 次后转 `dead` |
| `_process_upload` 文件丢失 | pending 文件被外部清掉 | `raise PaperlessError("pending file not found")` → mark_failed(已有 line 59) |
| `_process_update_metadata` / `_process_delete` 时 `paperless_id is None` | binding 还在 pending | `raise PaperlessError("binding not yet synced")` → mark_failed |
| `_process_delete` 调 `client.delete` 失败 | paperless 文档已被别人删 | mark_failed 走指数退避 |
| `DELETE /api/paperless/outbox/{id}/` 非 dead | 误操作 | 400 + `detail: "只能删除死信(当前 status=...)"` |
| `POST /api/paperless/upload/` 缺 file 字段 | 客户端没传 | 400 `{"detail": "缺少 file 字段"}` |
| `POST /api/paperless/upload/` 非法 source_type | 客户端传错 | `PaperlessUploadService.queue_upload` 抛 `ValueError` → view catch → 400 |
| admin.py 注册遗漏 | 运维需要管理界面 | 一次性注册 4 个模型 + list_display + list_filter + search_fields |

**安全相关:**

- 仍走 IsAuthenticated;`DocumentBindingViewSet` / delete_documents / update_metadata 走 `IsBindingOwnerOrAdmin`
- upload action 中 paperless owner 由 `payload["owner"]` 注入,owner 由 `request.user` 决定(view 层校验,不能伪造)
- `_save_pending_file` 用 `O_EXCL` + 0o600 + uuid,防 TOCTOU 与路径外溢(已有 line 71-78)

---

## 3. 实施步骤(占位 — writing-plans 阶段细化)

1. `models.py` 改 `paperless_id` 为 `null=True` + 生成 `0005_*.py` migration
2. `services/upload.py` 把占位 `paperless_id=0` 改 `paperless_id=None`
3. `services/client.py` 加 `update_metadata()` 和 `delete()` 方法(参考 paperless-ngx REST API)
4. `services/outbox.py` 加 `queue_update_metadata()` 和 `queue_delete()` 静态方法
5. `tasks.py`:
   - `_process_upload` 把 `not item.binding.paperless_id` 改 `is None`
   - `_process_update_metadata` 调 `client.update_metadata` + 回写 binding
   - `_process_delete` 调 `client.delete` + 删 binding
6. `views.py`:
   - 新增 `UploadView`(APIView,POST)
   - 新增 `DocumentBindingViewSet`(ModelViewSet,过滤 + 分页 + update_metadata/delete action)
   - `OutboxViewSet` 改 `ModelViewSet`,加 GET retrieve + DELETE destroy
7. `urls.py` 注册新路由
8. `admin.py` 新建,注册 4 个模型
9. `compliance/views.py` 加 `upload` action
10. `personnel/views.py` 加 `upload` action
11. 写测试 + 跑全部 paperless_proxy tests
12. `python manage.py makemigrations --check` + `pytest` 全绿后 commit + push + PR

---

## 4. 风险与依赖

| 风险 | 缓解 |
|---|---|
| migration 改 nullable 在大数据表上慢 | paperless_proxy 数据量极小(刚上线),秒级完成 |
| `tasks.py` 改 `_process_upload` truthy 检查 → `is None` 后,旧 outbox 项(已有 `paperless_id=0`)不再被回写 | 旧 0 占位语义是"未同步",worker 看到 0 仍会调 client.upload 重新同步,符合预期 |
| paperless-ngx DELETE / PATCH API 行为差异 | 实施前先在 staging paperless 跑一次手动验证,文档化到 `docs/technical/31-paperless-integration.md` |
| admin 注册后字段名 verbose_name 中文显示乱码 | Django admin 自动支持 i18n,确保 `LANGUAGE_CODE='zh-hans'`(已配置) |
| compliance / personnel 已有 upload 视图(非 paperless)会被本次覆盖 | 实施前 grep 确认无同名 `upload` action |

---

## 5. 测试策略

**新增/扩展测试:**

| 测试文件 | 覆盖范围 | 关键 case |
|---|---|---|
| `test_views.py` (扩) | `POST /upload/` | (1) 缺 file→400 (2) 正常创建→201 + binding/outbox (3) 非法 source_type→400 (4) `paperless_id is None`(nullable 验证) |
| `test_views.py` (扩) | `GET /documents/` | (1) 未登录→401 (2) 列表分页 (3) 过滤 source_type/source_id/owner |
| `test_views.py` (扩) | `GET/PATCH/DELETE /documents/{id}/` | (1) owner 可访问 (2) 非 owner 非 admin→403 (3) admin 可访问 (4) PATCH 创建 update_metadata outbox (5) DELETE 创建 delete outbox (6) 不存在→404 |
| `test_views.py` (扩) | `OutboxViewSet` DELETE | (1) 非 admin→403 (2) 删非 dead→400 (3) 删 dead→204 + 行消失 |
| `test_views.py` (扩) | `OutboxViewSet` GET 单个 | (1) admin→200 (2) 非 admin→403 |
| `test_tasks.py` (扩) | `_process_upload/update_metadata/delete` | mock `PaperlessClient`,验证调用参数与 binding 回写 |
| `test_admin.py` 🆕 | 4 个 model 在 admin 可注册 | 验证 `admin.site._registry` 包含 4 个 model 类 |
| `test_views.py` (扩) | compliance / personnel upload action | 复用 projects 测试结构:owner 可传 / 非 owner 不可传 / admin 可传 |

**目标覆盖率:** ≥ 87.6%(上次合并时的基线)

**TDD 顺序(写入时):**

1. 改 models.py + migration → 跑 `test_models.py` 验证 nullable
2. 改 services/upload.py + tasks.py _process_upload → 跑 `test_tasks.py`
3. 写/扩 `test_views.py` 测试 → 实现 views + urls → 红绿循环
4. 写 `test_admin.py` → 实现 admin.py
5. compliance/personnel upload action 测试 + 实现
6. 跑全部 paperless_proxy tests,目标 ≥ 87.6%

---

## 6. 相关文件清单

**修改:**

- `omni_desk_backend/paperless_proxy/models.py`
- `omni_desk_backend/paperless_proxy/services/upload.py`
- `omni_desk_backend/paperless_proxy/services/outbox.py`
- `omni_desk_backend/paperless_proxy/services/client.py`
- `omni_desk_backend/paperless_proxy/tasks.py`
- `omni_desk_backend/paperless_proxy/views.py`
- `omni_desk_backend/paperless_proxy/urls.py`
- `omni_desk_backend/paperless_proxy/tests/test_views.py`
- `omni_desk_backend/paperless_proxy/tests/test_tasks.py`
- `omni_desk_backend/compliance/views.py`
- `omni_desk_backend/personnel/views.py`

**新增:**

- `omni_desk_backend/paperless_proxy/admin.py`
- `omni_desk_backend/paperless_proxy/migrations/0005_*.py`
- `omni_desk_backend/paperless_proxy/tests/test_admin.py`

**不改:**

- `omni_desk_backend/projects/views.py`(已是参考实现)
- 前端代码(已能用 paperless 上传)

---

## 7. 验收标准

- [ ] `GET /api/paperless/documents/` 返回 200 + 分页数据
- [ ] `POST /api/paperless/upload/` 返回 201 + binding/outbox ID,且 binding.paperless_id 为 None
- [ ] `PATCH /api/paperless/documents/{id}/` 返回 202 + 创建 update_metadata outbox
- [ ] `DELETE /api/paperless/documents/{id}/` 返回 202 + 创建 delete outbox
- [ ] `DELETE /api/paperless/outbox/{id}/` 仅当 status=dead 返回 204
- [ ] Django admin 4 个 paperless 模型可访问
- [ ] `compliance/{id}/upload/` 与 `personnel/{id}/upload/` 鉴权与 projects 一致
- [ ] paperless_proxy 测试覆盖率 ≥ 87.6%
- [ ] `python manage.py makemigrations --check` 报告 no changes
- [ ] `python manage.py migrate --check` 无未应用 migration
- [ ] 全套 pytest 通过,无 warning