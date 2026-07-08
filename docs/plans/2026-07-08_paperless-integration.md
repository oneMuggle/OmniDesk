# OmniDesk 接入 paperless-ngx 设计方案

> **状态**: 待审批
> **创建日期**: 2026-07-08
> **优先级**: 高
> **目标版本**: v0.6.0+

---

## 1. 背景与目标

### 1.1 背景

OmniDesk 当前已具备完善的业务模块(项目/合同/会议/合规/人事/制度等),但**文档附件管理能力薄弱**。现有 `documents` app 仅支持"文档模板 + 生成文档",缺少:

| 缺失能力 | 业务影响 |
|---|---|
| 统一文件存储 | 附件散落在各模块,难集中检索 |
| 全文检索 | 无法搜附件内容(只能搜标题) |
| OCR / 内容提取 | 上传的扫描件无法检索 |
| 版本管理 | 文档修改无历史 |
| 标签/分类 | 缺乏统一分类体系 |

**paperless-ngx** 是开源文档管理系统(Django + DRF + React),原生提供:
- 完整 REST API(文档/标签/分类/上传/全文检索)
- Tantivy 全文检索 + 高亮
- 自动 OCR(支持中文 `chi_sim`)
- 标签 / correspondent / document_type / custom_fields 元数据
- 权限隔离(基于 owner / ACL)
- Docker 部署

### 1.2 目标

将 paperless-ngx 作为 OmniDesk 的**真实文档存储后端**:

1. 业务模块(项目/合同/合规/人事/制度)的**附件上传**统一落 paperless
2. **顶部统一搜索栏**联邦查询 OmniDesk 内部表 + paperless 文档(带高亮)
3. 独立的「**文档库**」模块(我的文档/全部/上传/同步状态/账号绑定)
4. **paperless 故障时**零数据丢失(Outbox 写降级 + 读穿透缓存)
5. 部署时一键起 paperless 容器(`docker-compose up`)

### 1.3 非目标

- 不替代 paperless 原生 UI(用户在 paperless 中仍可直接登录编辑)
- 不实现 paperless ↔ OmniDesk 双向元数据同步(单向:OmniDesk → paperless)
- 不迁移现有 OmniDesk `documents` app 的"模板/生成文档"功能(它们是无附件的轻量数据)

---

## 2. 关键决策汇总

经过 7 轮澄清,确认以下决策:

| 决策点 | 选定方案 | 理由 |
|---|---|---|
| 集成深度 | **深度集成**(paperless 作为真实存储) | 用户明确选择 |
| 降级策略 | **A:Outbox 写降级 + 读穿透缓存** | 业务不能停摆,数据不能丢 |
| 认证方式 | **服务账号 Token + owner 字段 + 账号绑定** | 简单可靠,不动 nginx |
| 同步范围 | **项目/合同/制度 + 合规/检查 + 人事档案** | 首期高价值,会议纪要后期再做 |
| 搜索 | **顶部统一搜索栏联邦 paperless** | 用户明确要求 |
| 同步方向 | **OmniDesk → paperless 单向** | 避免冲突,实现简单 |
| UI 入口 | **顶部菜单「文档库」独立模块** | 一级菜单,入口明显 |
| 部署 | **同机 docker-compose** | `http://paperless:8000` 内部访问 |

---

## 3. 架构总览

```
┌─────────────────────────────────────────────────────────────────┐
│                        OmniDesk 前端 (React 18)                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ 顶部统一搜索栏 (联邦搜索)                                  │   │
│  │  1. 并发查 OmniDesk 业务表 (项目/合同/人事/合规)            │   │
│  │  2. 并发查 paperless /api/documents/?query=               │   │
│  │  3. 合并 + 高亮 + 分组(按来源)                             │   │
│  └─────────────────────────────────────────────────────────┘   │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────┐ │
│  │ 文档库 /documents │  │ 业务页(项目/合同) │  │  集成中心    │ │
│  │ - 我的文档         │  │ - 上传/预览按钮   │  │  (已有)      │ │
│  │ - 全部文档         │  │ - 同步状态徽标    │  │              │ │
│  │ - 上传/同步状态     │  │                  │  │              │ │
│  │ - 账号绑定         │  │                  │  │              │ │
│  └──────────────────┘  └──────────────────┘  └──────────────┘ │
└────────────────────────────┬────────────────────────────────────┘
                             │ JWT (axios) → /api/...
┌────────────────────────────▼────────────────────────────────────┐
│                  OmniDesk 后端 (Django 4.2)                      │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  paperless_proxy (新 app)                                 │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌──────────────────┐  │   │
│  │  │ 视图层       │  │ 服务层       │  │ Outbox Worker    │  │   │
│  │  │ (REST API)  │  │ PaperlessCli │  │ (Celery beat)   │  │   │
│  │  │ - /api/paperless/  │  │ - 上传/下载/搜索 │  │ - 重试 pending │  │   │
│  │  │ - /api/search/unified/ │  │ - 重试/超时       │  │ - 批量回灌    │  │   │
│  │  └─────────────┘  └─────────────┘  └──────────────────┘  │   │
│  │  ┌──────────────┐  ┌──────────────┐                      │   │
│  │  │ models.py    │  │ permissions  │                      │   │
│  │  │ - DocumentBinding │  - 只看自己的   │                  │   │
│  │  │ - OutboxItem     │  - admin 全量  │                  │   │
│  │  │ - UserPaperlessBind │             │                  │   │
│  │  └──────────────┘  └──────────────┘                      │   │
│  └─────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  现有业务模块 (project / compliance / personnel / ...)     │   │
│  │  - 附件上传调用 paperless_proxy.upload()                 │   │
│  │  - 接收返回 paperless_id + outbox_id                    │   │
│  │  - Outbox 成功后才算最终落库                              │   │
│  └─────────────────────────────────────────────────────────┘   │
└────────────────────────────┬────────────────────────────────────┘
                             │ Token (admin 账号) + HTTP
┌────────────────────────────▼────────────────────────────────────┐
│                paperless-ngx (Docker: paperless:8000)            │
│  - /api/documents/post_document/  (multipart 上传)              │
│  - /api/documents/?query=...       (Tantivy 全文检索)            │
│  - /api/tags/   /api/correspondents/   /api/document_types/      │
│  - /api/users/  (账号绑定查询)                                   │
│  - 文件存储: /usr/src/paperless/data/media/ (Docker volume)     │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. 数据模型

```python
# omni_desk_backend/paperless_proxy/models.py

class DocumentBinding(models.Model):
    """OmniDesk 业务对象 ↔ paperless 文档的绑定表"""

    SOURCE_CHOICES = [
        ('project_document', '项目文档'),
        ('contract', '合同'),
        ('policy', '制度文件'),
        ('compliance_report', '合规检查报告'),
        ('personnel_file', '人事档案'),
    ]

    source_type = CharField(max_length=32, choices=SOURCE_CHOICES, db_index=True)
    source_id = PositiveIntegerField(db_index=True)  # 业务表主键
    paperless_id = PositiveIntegerField(unique=True)  # paperless Document.id
    paperless_checksum = CharField(max_length=64)  # 用于变更检测
    owner = ForeignKey(CustomUser, on_delete=PROTECT)  # owner 字段隔离
    title = CharField(max_length=255)  # 冗余便于展示
    correspondent_id = PositiveIntegerField(null=True)  # paperless correspondent
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)

    class Meta:
        unique_together = [('source_type', 'source_id')]  # 一一对应
        indexes = [('source_type', 'source_id'), ('owner', 'source_type')]


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

    operation = CharField(max_length=32, choices=OPERATION_CHOICES)
    status = CharField(max_length=16, choices=STATUS_CHOICES, default='pending', db_index=True)
    payload = JSONField()  # 操作参数(file_path/title/correspondent/tags...)
    binding = ForeignKey(DocumentBinding, on_delete=CASCADE, null=True, related_name='outbox')
    retry_count = PositiveIntegerField(default=0)
    max_retries = PositiveIntegerField(default=10)
    next_retry_at = DateTimeField(default=timezone.now, db_index=True)
    last_error = TextField(blank=True)
    created_by = ForeignKey(CustomUser, on_delete=PROTECT)
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            ('status', 'next_retry_at'),  # Worker 拉取优化
        ]


class UserPaperlessBinding(models.Model):
    """OmniDesk 用户 ↔ paperless 用户 账号绑定"""

    user = OneToOneField(CustomUser, on_delete=CASCADE, related_name='paperless_bind')
    paperless_user_id = PositiveIntegerField(unique=True)
    paperless_username = CharField(max_length=150)
    bound_at = DateTimeField(auto_now_add=True)
    is_active = BooleanField(default=True)


class PaperlessHealth(models.Model):
    """纸面化健康检查状态(单行)"""

    is_healthy = BooleanField(default=True)
    last_check_at = DateTimeField(auto_now=True)
    consecutive_failures = PositiveIntegerField(default=0)
    last_error = TextField(blank=True)

    class Meta:
        verbose_name = "paperless 健康状态"
```

---

## 5. 关键流程

### 5.1 上传文档(Outbox 模式)

```
[项目/合同/合规页 UI]
  → POST /api/business/{id}/attachments/  (业务模块 API)
    → 业务 view 调 paperless_proxy.queue_upload(...)

[paperless_proxy 服务层]
  1. 保存文件到本地待同步区(MEDIA_ROOT/paperless_pending/<uuid>)
  2. 创建 DocumentBinding(source_type='project_document', source_id=42, owner=request.user)
  3. 创建 OutboxItem(operation='upload', payload={...}, status='pending')
  4. 立即返回 {binding_id, outbox_id, status: 'pending'} 给前端
  5. 前端显示"同步中"徽标

[Celery worker - paperless_outbox_worker]
  - 定时拉 pending + next_retry_at <= now 的 outbox
  - 调 PaperlessClient.upload(payload) → paperless /api/documents/post_document/
    - 上传时携带 owner=<paperless_user_id_of_requester>
    - 成功后更新 DocumentBinding.paperless_id, OutboxItem.status='synced'
    - 失败:retry_count++, next_retry_at = now + 2^retry_count * 30s
    - retry_count >= max_retries → status='dead' + 通知 admin

[UI 轮询或 SSE]
  - 前端定时查 /api/paperless/outbox/{id}/ → 状态变更后更新徽标
```

### 5.2 读文档(穿透缓存)

```
[任意需要查看文档的 UI]
  → GET /api/paperless/binding/{id}/download/
    → paperless_proxy 视图:
      1. 权限检查:request.user == binding.owner or is_admin
      2. 调 PaperlessClient.download(paperless_id)
         - 成功:流式返回 + 写本地缓存(MEDIA_ROOT/paperless_cache/<paperless_id>)
         - 失败:检查本地缓存
           - 有缓存:返回缓存 + 响应头 X-Degraded: true
           - 无缓存:返回 503 "文档暂不可用,请稍后重试"
```

### 5.3 联邦搜索

```
[顶部搜索栏]
  → POST /api/search/unified/  (新)
    payload: {query: "合同", source: ["internal", "paperless"]}

[后端并发]
  parallel:
    - 查 OmniDesk 内部表(Project/Contract/Personnel/Memo/...)
    - 查 paperless /api/documents/?query=合同&page_size=20
      - paperless 健康时:实时调
      - paperless 不健康:跳过 paperless 源,只返回内部 + 降级提示

[结果合并]
  - 按 source 分组:内部业务(项目/合同等)/ paperless 文档
  - 统一 card 展示:title, snippet + highlight(高亮)
  - paperless 来源带"📄 paperless 文档"标签 + "在 paperless 中打开"按钮
```

### 5.4 账号绑定

```
[文档库 → 设置 → 绑定 paperless 账号]
  → POST /api/paperless/bind/  {username, password}
    → 后端用账号密码调 paperless /api/token/ 验证
      - 成功:在 paperless /api/users/ 中查找/创建同名 user
      - 创建 UserPaperlessBinding(user=current_user, paperless_user_id=...)
      - 后续该用户的 paperless 上传使用此 paperless_user_id 作为 owner
    → 失败:401 提示密码错误
```

### 5.5 健康检查 + 降级触发

```
[Celery beat - paperless_health_check (30s)]
  - 调 paperless /api/ 简单 GET
  - 成功:PaperlessHealth.is_healthy=True, consecutive_failures=0
  - 失败:consecutive_failures++, 连续 3 次失败 → is_healthy=False
  - 恢复:consecutive_failures=0, is_healthy=True
  - 状态变更时:发送通知给 admin (复用 OmniDesk 通知中心)

[前端行为]
  - is_healthy=False 时:
    - 顶部横幅: "paperless 文档服务暂不可用,上传将稍后自动同步"
    - 文档库页同步状态徽标:全部显示"待同步"
    - 联邦搜索:跳过 paperless 源
```

---

## 6. 文件清单

### 6.1 后端新增

| 文件路径 | 说明 |
|---|---|
| `omni_desk_backend/paperless_proxy/__init__.py` | Django app 入口 |
| `omni_desk_backend/paperless_proxy/apps.py` | AppConfig |
| `omni_desk_backend/paperless_proxy/models.py` | 4 个核心模型 |
| `omni_desk_backend/paperless_proxy/serializers.py` | DRF 序列化器 |
| `omni_desk_backend/paperless_proxy/permissions.py` | IsBindingOwner/IsAdminOrOwner |
| `omni_desk_backend/paperless_proxy/views.py` | 视图集 |
| `omni_desk_backend/paperless_proxy/urls.py` | 路由 |
| `omni_desk_backend/paperless_proxy/services/client.py` | PaperlessClient |
| `omni_desk_backend/paperless_proxy/services/outbox.py` | OutboxService |
| `omni_desk_backend/paperless_proxy/services/search.py` | PaperlessSearchService |
| `omni_desk_backend/paperless_proxy/tasks.py` | Celery 任务 |
| `omni_desk_backend/paperless_proxy/admin.py` | Django Admin |
| `omni_desk_backend/paperless_proxy/exceptions.py` | PaperlessError |
| `omni_desk_backend/paperless_proxy/migrations/0001_initial.py` | 迁移 |
| `omni_desk_backend/paperless_proxy/tests/test_models.py` | 模型单元测试 |
| `omni_desk_backend/paperless_proxy/tests/test_outbox.py` | Outbox 单元测试 |
| `omni_desk_backend/paperless_proxy/tests/test_client.py` | PaperlessClient 单测(mock) |
| `omni_desk_backend/paperless_proxy/tests/test_views.py` | API 集成测试 |
| `omni_desk_backend/paperless_proxy/tests/test_tasks.py` | Celery 任务测试 |
| `omni_desk_backend/paperless_proxy/tests/test_search_federation.py` | 联邦搜索测试 |

### 6.2 后端修改

| 文件路径 | 修改内容 |
|---|---|
| `omni_desk_backend/omni_desk_backend/settings/base.py` | 注册 `paperless_proxy` app,加 Celery beat 调度 |
| `omni_desk_backend/omni_desk_backend/settings/local.py` | 加 `PAPERLESS_URL` / `PAPERLESS_API_TOKEN` |
| `omni_desk_backend/omni_desk_backend/settings/production.py` | 同上,Token 走环境变量 |
| `omni_desk_backend/omni_desk_backend/urls.py` | 注册 `/api/paperless/` 路由 |
| `omni_desk_backend/documents/views.py` | 现有 `documents` app 集成 paperless |
| `omni_desk_backend/personnel/models.py` | 在 PersonnelFile 附件字段加 paperless 代理 |
| `omni_desk_backend/compliance/views.py` | 在 ReportFile 附件加 paperless 代理 |
| `omni_desk_backend/projects/views.py` | 在 ProjectDocument 加 paperless 代理 |

### 6.3 前端新增

| 文件路径 | 说明 |
|---|---|
| `omni_desk_frontend/src/features/documents-library/pages/DocumentLibraryPage.jsx` | 文档库主页 |
| `omni_desk_frontend/src/features/documents-library/pages/DocumentUploadPage.jsx` | 上传页 |
| `omni_desk_frontend/src/features/documents-library/pages/SyncStatusPage.jsx` | 同步状态页 |
| `omni_desk_frontend/src/features/documents-library/pages/AccountBindingPage.jsx` | 账号绑定页 |
| `omni_desk_frontend/src/features/documents-library/components/DocumentCard.jsx` | 文档卡片 |
| `omni_desk_frontend/src/features/documents-library/components/SyncStatusBadge.jsx` | 同步状态徽标 |
| `omni_desk_frontend/src/features/documents-library/components/PaperlessHealthBanner.jsx` | 顶部降级提示横幅 |
| `omni_desk_frontend/src/features/documents-library/api/paperlessApi.js` | API 封装 |
| `omni_desk_frontend/src/features/documents-library/hooks/usePaperlessHealth.js` | 健康状态轮询 hook |
| `omni_desk_frontend/src/features/search-federation/components/UnifiedSearchBar.jsx` | 顶部联邦搜索栏(改造) |
| `omni_desk_frontend/src/features/search-federation/api/searchApi.js` | 联邦搜索 API |
| `omni_desk_frontend/src/features/search-federation/hooks/useUnifiedSearch.js` | 搜索 hook |

### 6.4 前端修改

| 文件路径 | 修改内容 |
|---|---|
| `omni_desk_frontend/src/routes/index.js` | 新增 `/documents-library` 路由 |
| `omni_desk_frontend/src/shared/config/menuConfig.js` | 顶部菜单加「文档库」入口 |
| `omni_desk_frontend/src/shared/components/layout/Header.jsx` | 改造搜索栏接入联邦搜索 |
| `omni_desk_frontend/src/shared/components/layout/index.jsx` | 全局增加 PaperlessHealthBanner |
| `omni_desk_frontend/src/features/projects/components/DocumentUploadButton.jsx` | 改为调用 paperless 上传 |
| `omni_desk_frontend/src/features/compliance/components/ReportUploadButton.jsx` | 改为调用 paperless 上传 |
| `omni_desk_frontend/src/features/personnel/components/FileUploadButton.jsx` | 改为调用 paperless 上传 |

---

## 7. API 端点

| 端点 | 方法 | 权限 | 说明 |
|---|---|---|---|
| `/api/paperless/documents/` | GET | 登录 | 列我的文档(分页) |
| `/api/paperless/documents/{id}/` | GET | owner/admin | 详情 |
| `/api/paperless/documents/{id}/download/` | GET | owner/admin | 下载(降级时返缓存) |
| `/api/paperless/documents/{id}/preview/` | GET | owner/admin | 预览缩略图 |
| `/api/paperless/bindings/{id}/sync-status/` | GET | owner/admin | 查同步状态 |
| `/api/paperless/outbox/` | GET | admin | 列出 Outbox(可按 status 过滤) |
| `/api/paperless/outbox/{id}/retry/` | POST | admin | 手动重试死信 |
| `/api/paperless/bind/` | POST | 登录 | 绑定 paperless 账号 |
| `/api/paperless/bind/` | DELETE | 登录 | 解绑 |
| `/api/paperless/bind/status/` | GET | 登录 | 查绑定状态 |
| `/api/paperless/health/` | GET | 登录 | 查 health 状态 |
| `/api/paperless/search/` | GET | 登录 | 单独搜 paperless(带高亮) |
| `/api/search/unified/` | POST | 登录 | 联邦搜索 |
| `/api/business/{model}/{id}/attachments/` | POST | 业务权限 | 业务模块上传(走 outbox) |

---

## 8. 前端组件设计

### 8.1 UnifiedSearchBar(改造)

```jsx
<AutoComplete
  placeholder="搜索项目、合同、文档、人员..."
  onSearch={debounce(handleSearch, 300)}
>
  <AutoComplete.Option key="...">
    <Flex>
      <Tag color={source === 'paperless' ? 'blue' : 'green'}>
        {source === 'paperless' ? '📄 paperless' : source}
      </Tag>
      <HighlightText text={title} highlight={query} />
      <span dangerouslySetInnerHTML={{__html: snippet}} />
    </Flex>
  </AutoComplete.Option>
</AutoComplete>
```

### 8.2 DocumentCard

```jsx
<Card>
  <Flex>
    <FileIcon type={binding.source_type} />
    <Title>{binding.title}</Title>
    <SyncStatusBadge status={binding.outbox_status} />
  </Flex>
  <Meta>
    <span>上传: {binding.owner}</span>
    <span>来源: {binding.source_type_label}</span>
  </Meta>
  <Actions>
    <Button onClick={preview}>预览</Button>
    <Button onClick={download}>下载</Button>
    <Button onClick={openInPaperless}>在 paperless 中打开</Button>
  </Actions>
</Card>
```

### 8.3 SyncStatusBadge

```jsx
const STATUS_MAP = {
  pending:  { color: 'orange',  text: '待同步',   icon: <ClockCircleOutlined /> },
  syncing:  { color: 'blue',    text: '同步中',   icon: <SyncOutlined spin /> },
  synced:   { color: 'green',   text: '已同步',   icon: <CheckCircleOutlined /> },
  failed:   { color: 'red',     text: '同步失败', icon: <CloseCircleOutlined /> },
  dead:     { color: 'red',     text: '需重试',   icon: <WarningOutlined /> },
};
```

---

## 9. Docker 部署

### 9.1 docker-compose.yml 增补

```yaml
services:
  paperless:
    image: ghcr.io/paperless-ngx/paperless-ngx:latest
    restart: unless-stopped
    depends_on:
      - paperless-db
      - paperless-redis
    environment:
      - PAPERLESS_REDIS=redis://paperless-redis:6379
      - PAPERLESS_DBHOST=paperless-db
      - PAPERLESS_SECRET_KEY=${PAPERLESS_SECRET_KEY}
      - PAPERLESS_TIME_ZONE=${TZ:-Asia/Shanghai}
      - PAPERLESS_OCR_LANGUAGES=chi_sim+eng
    volumes:
      - paperless-data:/usr/src/paperless/data
      - paperless-media:/usr/src/paperless/data/media
      - ./deployment/paperless/paperless.conf:/usr/src/paperless/paperless.conf:ro
    ports:
      - "8001:8000"   # 与 OmniDesk 后端(8000)区分

  paperless-db:
    image: postgres:15
    environment:
      - POSTGRES_DB=paperless
      - POSTGRES_USER=paperless
      - POSTGRES_PASSWORD=${PAPERLESS_DB_PASSWORD}
    volumes:
      - paperless-db:/var/lib/postgresql/data

  paperless-redis:
    image: redis:7
    volumes:
      - paperless-redis:/data

  omni-desk-backend:
    environment:
      - PAPERLESS_URL=http://paperless:8000    # 内部网络用 service 名
      - PAPERLESS_API_TOKEN_FILE=/run/secrets/paperless_api_token

secrets:
  paperless_api_token:
    file: ./secrets/paperless_api_token.txt

volumes:
  paperless-data:
  paperless-media:
  paperless-db:
  paperless-redis:
```

### 9.2 配置项(settings/local.py)

```python
PAPERLESS_URL = os.getenv('PAPERLESS_URL', 'http://paperless:8000')
PAPERLESS_API_TOKEN = os.getenv('PAPERLESS_API_TOKEN', '')
PAPERLESS_TIMEOUT_SECONDS = 10
PAPERLESS_HEALTH_CHECK_INTERVAL = 30
PAPERLESS_HEALTH_FAILURE_THRESHOLD = 3
PAPERLESS_OUTBOX_BATCH_SIZE = 50
PAPERLESS_OUTBOX_MAX_RETRIES = 10
PAPERLESS_OUTBOX_BASE_BACKOFF_SECONDS = 30
PAPERLESS_CACHE_DIR = 'paperless_cache/'
PAPERLESS_PENDING_DIR = 'paperless_pending/'
PAPERLESS_CACHE_MAX_AGE_DAYS = 30
PAPERLESS_CLEANUP_INTERVAL_HOURS = 6
```

---

## 10. 测试策略

| 测试类型 | 范围 | 工具 | 覆盖目标 |
|---|---|---|---|
| 模型单元测试 | 4 个模型 | Django TestCase | 100% |
| PaperlessClient 单测 | 上传/下载/搜索/认证,异常处理 | pytest + responses | 90% |
| OutboxService 单测 | 入队/重试退避/死信升级/状态机 | pytest + freezegun | 95% |
| 视图/API 集成测试 | 14 个端点 | DRF APIClient | 85% |
| Celery 任务测试 | outbox_worker / health_check / cache_cleanup | pytest-celery | 80% |
| 联邦搜索测试 | 内部源+paperless 源合并、降级行为 | mock 整个 paperless | 85% |
| 业务模块集成测试 | 项目/合同/合规/人事 上传附件走 paperless 路径 | APIClient + 重放 outbox | 80% |
| 手动 E2E | docker-compose 起真实 paperless,跑全链路 | Playwright | 关键流程 |

### 10.1 关键测试用例

```python
# test_outbox.py
def test_outbox_retries_with_exponential_backoff():
    """验证:失败时按 30s * 2^n 退避"""

def test_outbox_escalates_to_dead_after_max_retries():
    """验证:超过 max_retries 进入 dead 状态,不再自动重试"""

def test_outbox_succeeds_clears_retry_count():
    """验证:成功后重置重试计数"""

# test_health.py
def test_health_three_consecutive_failures_marks_unhealthy():
    """验证:连续 3 次失败才标 unhealthy(避免抖动)"""

# test_search.py
def test_federated_search_skips_paperless_when_unhealthy():
    """验证:paperless 不健康时跳过 paperless 源"""

def test_federated_search_merges_paperless_highlights():
    """验证:paperless 高亮 HTML 正确传透到前端"""

# test_degradation.py
def test_download_returns_cache_when_paperless_down():
    """验证:paperless 挂掉时返本地缓存 + X-Degraded: true"""

def test_download_returns_503_when_no_cache():
    """验证:无缓存时返 503 而非 500"""

# test_isolation.py
def test_user_cannot_download_others_document():
    """验证:非 owner 调用下载返 403"""

def test_admin_can_download_any_document():
    """验证:admin 例外"""
```

---

## 11. 风险评估

| 风险 | 严重度 | 概率 | 缓解措施 |
|---|---|---|---|
| paperless 数据丢失/损坏 | 高 | 低 | 定期 paperless media 卷 + pg_dump 备份,OmniDesk `backup_db` 集成 |
| Outbox 死信堆积 | 中 | 中 | 同步状态页 + admin 通知 + 手动重试入口 |
| 联邦搜索性能(并发 2 路) | 中 | 中 | paperless 慢时 timeout=3s 降级到只返内部 |
| Token 泄露 | 高 | 低 | Token 存 secrets 文件,不入代码;文档说明 |
| 账号绑定被恶意利用 | 中 | 低 | 限速 5 次/小时,首次绑定需 email 验证 |
| paperless 升级 API 不兼容 | 中 | 中 | PaperlessClient 加 `__version__` 探测 + 字段映射层 |
| 大文件上传超时 | 中 | 中 | Celery 上传分块(>= 50MB),multipart resumable |
| 同步冲突(OmniDesk 端编辑 + paperless 端编辑) | 低 | 低 | 单向策略:paperless 端编辑不同步回,UI 提示 |
| 离线部署首次启动 | 中 | 低 | paperless 首次启动 OCR 模型下载需在有网环境预热 |
| Windows 7 兼容 | 中 | 中 | 前端 paperless 高亮 HTML 用 `dangerouslySetInnerHTML` 需 XSS 转义 |

---

## 12. 实施步骤

### 阶段 1:基础脚手架(1 周)

- [ ] 1.1 在 `omni_desk_backend/` 下创建 `paperless_proxy` Django app,完成 models + 迁移
- [ ] 1.2 编写 `PaperlessClient`(基于 `requests`,带超时+重试+指数退避)
- [ ] 1.3 配置文件 / 环境变量 / docker-compose service
- [ ] 1.4 单元测试(模型 + Client)

### 阶段 2:Outbox 写降级(1.5 周)

- [ ] 2.1 `OutboxService`(入队/批量拉/重试退避/死信升级)
- [ ] 2.2 Celery 任务 `outbox_worker` + Celery beat 调度
- [ ] 2.3 视图:`/api/paperless/outbox/`(管理)+ 业务模块附件上传接入
- [ ] 2.4 健康检查 `health_check` + `PaperlessHealth` 模型 + 通知
- [ ] 2.5 集成测试 + E2E(正常上传 + paperless 宕机场景)

### 阶段 3:读穿透 + 联邦搜索(1.5 周)

- [ ] 3.1 下载/预览 API(降级时返缓存,`X-Degraded` 头)
- [ ] 3.2 本地缓存管理 + `cache_cleanup` 任务
- [ ] 3.3 `PaperlessSearchService`(带高亮)
- [ ] 3.4 `UnifiedSearchView`(`/api/search/unified/`)+ 前端联邦搜索栏
- [ ] 3.5 集成测试 + 性能压测(2 路并发 timeout)

### 阶段 4:账号绑定 + 文档库 UI(1 周)

- [ ] 4.1 `UserPaperlessBinding` + 绑定/解绑 API
- [ ] 4.2 前端「文档库」模块(我的/全部/上传/同步状态/账号绑定)
- [ ] 4.3 `SyncStatusBadge` + `PaperlessHealthBanner`
- [ ] 4.4 业务页(项目/合同/合规/人事)接入新上传按钮
- [ ] 4.5 E2E 完整流程跑通 + 部署文档 + 用户手册

### 依赖关系

```
1.x → 2.x → 3.x → 4.x
                ↑
              可与 2.x 部分并行
```

---

## 13. 文档输出

| 文档 | 位置 | 内容 |
|---|---|---|
| 设计文档(本文) | `docs/plans/2026-07-08_paperless-integration.md` | 设计方案 |
| 技术手册 | `docs/technical/21-paperless-integration.md` | 架构、API、模型、部署、配置 |
| 用户手册 | `docs/user-manual/09-document-library.md` | 文档库使用指南、绑定流程 |
| 部署脚本 | `deployment/docker/upgrade.sh` 增补 | paperless 升级/备份步骤 |
| README 增补 | `README.md` | 新增 "文档库 + paperless" 一节 |

---

## 14. 参考资料

- paperless-ngx API 文档:https://docs.paperless-ngx.com/api/
- OmniDesk 三层级外部集成:`docs/plans/2026-05-11_three-level-external-integration.md`
- OmniDesk RAGFlow 集成方案:`docs/plans/2026-07-06_ragflow-integration.md`(借鉴模型设计思路)
