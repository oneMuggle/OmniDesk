# paperless-ngx 集成

## 1. 概述

OmniDesk 通过新增 `paperless_proxy` Django app 和 `search_federation` Django app，将 [paperless-ngx](https://docs.paperless-ngx.com/) 作为**真实文档存储后端**。业务模块（项目、合同、合规、人事）的附件统一落 paperless，顶部搜索栏支持联邦查询（OmniDesk 内部表 + paperless），paperless 故障时通过 Outbox 写降级 + 读穿透缓存保证业务不中断。

### 1.1 核心能力

| 能力 | 说明 |
|------|------|
| Outbox 写降级 | 附件上传先写本地 Outbox，Celery Worker 异步推送到 paperless，失败指数退避重试 |
| 读穿透缓存 | 下载文档时本地缓存一份，paperless 宕机时返回缓存（`X-Degraded: true`） |
| 联邦搜索 | 顶部搜索栏并发查询 OmniDesk 业务表 + paperless Tantivy 全文检索，结果合并 + 高亮 |
| 账号绑定 | OmniDesk 用户绑定 paperless 用户，上传时以绑定用户作为 paperless owner |
| 健康检查 | Celery beat 30 秒探测 paperless，连续 3 次失败标记不健康，前端展示降级横幅 |
| 同步状态 | 前端 `SyncStatusBadge` 实时显示 Outbox 项状态（待同步/同步中/已同步/失败/死信） |

### 1.2 非目标

- 不替代 paperless 原生 UI（用户仍可直接登录 paperless 操作）
- 不实现双向元数据同步（仅 OmniDesk → paperless 单向）
- 不迁移现有 `documents` app 的"模板/生成文档"功能

---

## 2. 架构

```
┌─────────────────────────────────────────────────────────────────┐
│                   OmniDesk 前端 (React 18 + Ant Design 5)        │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  UnifiedSearchBar (联邦搜索)                              │    │
│  │  POST /api/search/unified/ → 并发查内部 + paperless      │    │
│  └─────────────────────────────────────────────────────────┘    │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────┐  │
│  │ 文档库 /documents │  │ 业务页(项目/合同) │  │  集成中心     │  │
│  │ - 我的文档        │  │ - 上传/预览按钮   │  │  (已有)      │  │
│  │ - 上传/同步状态   │  │ - SyncStatusBadge │  │              │  │
│  │ - 账号绑定        │  │                  │  │              │  │
│  └──────────────────┘  └──────────────────┘  └──────────────┘  │
└────────────────────────────┬────────────────────────────────────┘
                             │ JWT (axios)
┌────────────────────────────▼────────────────────────────────────┐
│                   OmniDesk 后端 (Django 4.2 + DRF)               │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  paperless_proxy app                                      │   │
│  │  模型: DocumentBinding / OutboxItem / UserPaperlessBinding │   │
│  │       / PaperlessHealth                                   │   │
│  │  服务: PaperlessClient / OutboxService / SearchService     │   │
│  │       / PaperlessUploadService                             │   │
│  │  任务: process_outbox / check_health / cleanup_cache       │   │
│  │  API:  /api/paperless/outbox/  /api/paperless/bind/       │   │
│  │        /api/paperless/health/  /api/paperless/documents/  │   │
│  └──────────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  search_federation app                                    │   │
│  │  API: POST /api/search/unified/                           │   │
│  └──────────────────────────────────────────────────────────┘   │
└────────────────────────────┬────────────────────────────────────┘
                             │ Token + HTTP
┌────────────────────────────▼────────────────────────────────────┐
│               paperless-ngx (Docker: paperless:8000)             │
│  /api/documents/post_document/  (multipart 上传)                 │
│  /api/documents/?query=...       (Tantivy 全文检索 + 高亮)       │
│  /api/tags/  /api/correspondents/  /api/document_types/          │
│  /api/users/  (账号绑定查询)                                      │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. 数据模型

### 3.1 DocumentBinding

OmniDesk 业务对象 ↔ paperless 文档的绑定表。

| 字段 | 类型 | 说明 |
|------|------|------|
| `source_type` | CharField(32) | 业务源类型：`project_document` / `contract` / `policy` / `compliance_report` / `personnel_file` |
| `source_id` | PositiveIntegerField | 业务表主键 |
| `paperless_id` | PositiveIntegerField(unique) | paperless Document.id |
| `paperless_checksum` | CharField(64) | paperless 校验和，用于变更检测 |
| `owner` | ForeignKey(CustomUser) | 文档所有者 |
| `title` | CharField(255) | 文档标题（冗余便于展示） |
| `correspondent_id` | PositiveIntegerField(null) | paperless correspondent |
| `extra_metadata` | JSONField | 扩展元数据 |

- `unique_together = [('source_type', 'source_id')]`：一一对应
- 索引：`(source_type, source_id)` + `(owner, source_type)`

### 3.2 OutboxItem

Outbox 写降级核心，记录待同步到 paperless 的操作。

| 字段 | 类型 | 说明 |
|------|------|------|
| `operation` | CharField(32) | `upload` / `update_metadata` / `delete` |
| `status` | CharField(16) | `pending` → `syncing` → `synced` / `failed` → `dead` |
| `payload` | JSONField | 操作载荷（file_path / title / correspondent / tags 等） |
| `binding` | ForeignKey(DocumentBinding) | 关联的绑定 |
| `retry_count` | PositiveIntegerField | 已重试次数 |
| `max_retries` | PositiveIntegerField | 最大重试次数（默认 10） |
| `next_retry_at` | DateTimeField | 下次重试时间（指数退避） |
| `last_error` | TextField | 最后错误信息 |

- 索引：`(status, next_retry_at)` — Worker 拉取优化
- 退避策略：`30s × 2^retry_count`，上限 1 小时

### 3.3 UserPaperlessBinding

OmniDesk 用户 ↔ paperless 用户账号绑定（一对一）。

| 字段 | 类型 | 说明 |
|------|------|------|
| `user` | OneToOneField(CustomUser) | OmniDesk 用户 |
| `paperless_user_id` | PositiveIntegerField(unique) | paperless 用户 ID |
| `paperless_username` | CharField(150) | paperless 用户名 |
| `is_active` | BooleanField | 是否激活 |

### 3.4 PaperlessHealth

健康检查状态（逻辑单例，通过 `get_singleton()` 访问）。

| 字段 | 类型 | 说明 |
|------|------|------|
| `is_healthy` | BooleanField | 是否健康 |
| `consecutive_failures` | PositiveIntegerField | 连续失败次数 |
| `last_error` | TextField | 最后错误 |

---

## 4. API 端点

### 4.1 paperless_proxy API（`/api/paperless/`）

| 端点 | 方法 | 权限 | 说明 |
|------|------|------|------|
| `/api/paperless/outbox/` | GET | admin | 列出 Outbox 项（支持 `?status=` / `?operation=` 过滤） |
| `/api/paperless/outbox/{id}/retry/` | POST | admin | 手动重试死信（仅 `status=dead` 可重试） |
| `/api/paperless/health/` | GET | 登录 | 查询 paperless 健康状态 |
| `/api/paperless/bind/` | POST | 登录 | 绑定 paperless 账号（body: `{username, password}`） |
| `/api/paperless/bind/` | GET | 登录 | 查询绑定状态（`{bound: true/false, ...}`） |
| `/api/paperless/bind/` | DELETE | 登录 | 解绑 paperless 账号 |
| `/api/paperless/bind/status/` | GET | 登录 | 查询绑定状态（同 GET /bind/） |
| `/api/paperless/documents/{binding_id}/download/` | GET | owner/admin | 下载文档（降级时返回缓存 + `X-Degraded: true`） |
| `/api/paperless/documents/{binding_id}/preview/` | GET | owner/admin | 获取文档预览图（PNG） |
| `/api/paperless/bindings/{binding_id}/sync-status/` | GET | owner/admin | 查询绑定对应的 Outbox 同步状态 |

### 4.2 联邦搜索 API（`/api/search/`）

| 端点 | 方法 | 权限 | 说明 |
|------|------|------|------|
| `/api/search/unified/` | POST | 登录 | 联邦搜索（body: `{query: "..."}`)，返回 `{results: [...], degraded: bool}`） |

联邦搜索结果按来源分组，paperless 来源带 `source: "paperless"` + `highlight`（HTML 高亮）。paperless 不健康时跳过 paperless 源，`degraded: true`。

### 4.3 业务模块上传

业务模块（项目等）通过 `PaperlessUploadService.queue_upload()` 统一入口上传附件，自动创建 `DocumentBinding` + `OutboxItem`，异步推送到 paperless。

---

## 5. 服务层

### 5.1 PaperlessClient

`paperless_proxy/services/client.py` — 基于 `requests` 的 HTTP 客户端。

| 方法 | 说明 |
|------|------|
| `post_token(username, password)` | 账号密码换取 paperless token |
| `get_user_by_username(username)` | 根据用户名查 paperless 用户 |
| `upload(file_obj, filename, title, owner, ...)` | multipart 上传文档 |
| `get_document(paperless_id)` | 获取文档元数据 |
| `download(paperless_id)` | 下载文档原始内容 |
| `preview(paperless_id)` | 获取预览图 |
| `search(query, page, page_size)` | Tantivy 全文搜索 |
| `health_check()` | 健康检查（GET /api/） |

- 超时：`PAPERLESS_TIMEOUT_SECONDS`（默认 10s）
- 异常：`PaperlessUnavailableError`(5xx/网络) / `PaperlessAuthError`(401/403) / `PaperlessNotFoundError`(404)

### 5.2 OutboxService

`paperless_proxy/services/outbox.py` — Outbox 写降级核心。

| 方法 | 说明 |
|------|------|
| `enqueue(operation, payload, binding, created_by)` | 创建 pending 状态 Outbox 项 |
| `fetch_pending(batch_size)` | 拉取到期 pending 项，标记为 syncing |
| `mark_synced(outbox)` | 标记同步成功，重置重试计数 |
| `mark_failed(outbox, error_msg)` | 失败处理：重试计数++，指数退避；达上限则升级为 dead |
| `retry_dead(outbox)` | 管理员手动重试死信 |

### 5.3 PaperlessSearchService

`paperless_proxy/services/search.py` — 搜索结果标准化，返回统一格式（`source` / `id` / `title` / `highlight` / `score` / `url`）。

### 5.4 PaperlessUploadService

`paperless_proxy/services/upload.py` — 业务模块统一上传入口。

1. 保存文件到 `MEDIA_ROOT/paperless_pending/<uuid>_<filename>`
2. 创建 `DocumentBinding`（`paperless_id=0` 占位）
3. 创建 `OutboxItem`（`operation=upload`，`status=pending`）
4. 返回 `{binding_id, outbox_id, status}`

---

## 6. Celery 任务

| 任务 | 调度 | 说明 |
|------|------|------|
| `paperless_proxy.process_outbox` | 每 1 分钟 | 拉取 pending Outbox 项，调用 PaperlessClient 推送到 paperless |
| `paperless_proxy.check_health` | 每 30 秒 | 探测 paperless 健康状态，连续 3 次失败标记不健康 |
| `paperless_proxy.cleanup_cache` | 每 6 小时 | 清理超过 `PAPERLESS_CACHE_MAX_AGE_DAYS`（默认 30 天）的本地缓存 |

---

## 7. 配置项

在 `omni_desk_backend/settings/base.py` 中定义，均支持环境变量覆盖：

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `PAPERLESS_URL` | `http://paperless:8000` | paperless 服务地址 |
| `PAPERLESS_API_TOKEN` | `''` | paperless 服务账号 Token |
| `PAPERLESS_TIMEOUT_SECONDS` | `10` | HTTP 请求超时（秒） |
| `PAPERLESS_HEALTH_CHECK_INTERVAL` | `30` | 健康检查间隔（秒） |
| `PAPERLESS_HEALTH_FAILURE_THRESHOLD` | `3` | 连续失败几次标记不健康 |
| `PAPERLESS_OUTBOX_BATCH_SIZE` | `50` | Worker 每次拉取批次大小 |
| `PAPERLESS_OUTBOX_MAX_RETRIES` | `10` | Outbox 最大重试次数 |
| `PAPERLESS_OUTBOX_BASE_BACKOFF_SECONDS` | `30` | 退避基数（秒） |
| `PAPERLESS_CACHE_DIR` | `paperless_cache/` | 缓存目录（相对 MEDIA_ROOT） |
| `PAPERLESS_PENDING_DIR` | `paperless_pending/` | 待同步目录（相对 MEDIA_ROOT） |
| `PAPERLESS_CACHE_MAX_AGE_DAYS` | `30` | 缓存最大保留天数 |
| `PAPERLESS_CLEANUP_INTERVAL_HOURS` | `6` | 缓存清理间隔（小时） |

Token 通过环境变量注入，不进代码。示例 env 文件：`omni_desk_backend/omni_desk_backend/settings/paperless.example.env`。

---

## 8. 部署

### 8.1 docker-compose 新增服务

paperless-ngx 需要 3 个容器：paperless 本体、独立 PostgreSQL、独立 Redis。详见 `deployment/docker/docker-compose.yml` 中 `paperless` / `paperless-db` / `paperless-redis` 服务定义。

关键环境变量：

| 变量 | 说明 |
|------|------|
| `PAPERLESS_SECRET_KEY` | paperless Django SECRET_KEY |
| `PAPERLESS_DB_PASSWORD` | paperless 数据库密码 |
| `PAPERLESS_API_TOKEN` | OmniDesk 调用 paperless 的服务账号 Token |

### 8.2 首次部署

1. 在 `.env` 中配置 `PAPERLESS_SECRET_KEY`、`PAPERLESS_DB_PASSWORD`、`PAPERLESS_API_TOKEN`
2. `docker compose up -d` — 会自动拉起 paperless + paperless-db + paperless-redis
3. 访问 `http://<host>:8001` 完成 paperless 初始化（创建 admin 用户）
4. 在 paperless 中创建 API Token（Settings → Account → API Token）
5. 将 Token 填入 `.env` 的 `PAPERLESS_API_TOKEN`
6. 重启 OmniDesk 后端：`docker compose restart backend worker`

### 8.3 离线部署

paperless 首次启动需要下载 OCR 语言模型（`chi_sim` + `eng`）。在有网环境先：

```bash
docker pull ghcr.io/paperless-ngx/paperless-ngx:latest
docker pull postgres:15
docker save -o paperless-images.tar ghcr.io/paperless-ngx/paperless-ngx:latest postgres:15 redis:7
```

传输到内网后 `docker load -i paperless-images.tar`。

---

## 9. 备份与恢复

### 9.1 备份

paperless 数据包括两部分：

1. **paperless PostgreSQL 数据库** — `docker exec paperless-db pg_dump -U paperless paperless | gzip > paperless-db-$(date +%Y%m%d).sql.gz`
2. **paperless media 卷** — `docker run --rm -v paperless_media:/data -v $(pwd):/backup alpine tar czf /backup/paperless-media-$(date +%Y%m%d).tar.gz /data`

OmniDesk 自身的 `backup_db` 命令同时会备份 `DocumentBinding` / `OutboxItem` 等表。

### 9.2 恢复

1. 恢复 paperless 数据库：`gunzip -c paperless-db-*.sql.gz | docker exec -i paperless-db psql -U paperless paperless`
2. 恢复 media 卷：`docker run --rm -v paperless_media:/data -v $(pwd):/backup alpine tar xzf /backup/paperless-media-*.tar.gz -C /`
3. 重启 paperless：`docker compose restart paperless`

---

## 10. 故障排查

### 10.1 paperless 不可用

| 现象 | 排查 |
|------|------|
| 前端显示"paperless 文档服务暂不可用"横幅 | 检查 `docker compose ps paperless`，查看日志 `docker compose logs paperless` |
| Outbox 堆积 `pending` | 检查 Worker 日志：`docker compose logs worker \| grep paperless` |
| 健康 API 返回 `is_healthy: false` | 查 `PaperlessHealth` 表 `last_error` 字段 |

### 10.2 Outbox 死信

| 现象 | 排查 |
|------|------|
| Outbox 项 `status=dead` | 管理页面 `/api/paperless/outbox/?status=dead` 查看 `last_error` |
| 手动重试 | `POST /api/paperless/outbox/{id}/retry/` |

### 10.3 文档下载失败

| 现象 | 排查 |
|------|------|
| 下载返回 503 | paperless 不可用且无本地缓存。检查 `PAPERLESS_URL` 配置 |
| 下载返回 `X-Degraded: true` | 正常降级行为，返回的是本地缓存副本 |
| 下载返回 404 | paperless 中文档已被删除（单向同步，OmniDesk 侧未感知） |

### 10.4 联邦搜索无 paperless 结果

| 现象 | 排查 |
|------|------|
| 搜索只有内部结果 | 检查 paperless 健康状态；确认 `PAPERLESS_URL` 和 `PAPERLESS_API_TOKEN` 正确 |
| 搜索返回 `degraded: true` | paperless 不健康，已自动降级 |

---

## 11. 前端模块

### 11.1 文档库（`/documents-library`）

| 页面 | 路径 | 说明 |
|------|------|------|
| DocumentLibraryPage | `/documents-library` | 我的文档列表（分页 + 过滤） |
| DocumentUploadPage | `/documents-library/upload` | 上传文档 |
| SyncStatusPage | `/documents-library/sync` | 同步状态（Outbox 列表） |
| AccountBindingPage | `/documents-library/account` | 绑定/解绑 paperless 账号 |

### 11.2 组件

| 组件 | 说明 |
|------|------|
| `DocumentCard` | 文档卡片（标题 + 来源 + 同步状态 + 预览/下载/在 paperless 打开） |
| `SyncStatusBadge` | 同步状态徽标（pending/syncing/synced/failed/dead 五种状态） |
| `PaperlessHealthBanner` | 全局降级横幅（paperless 不健康时显示） |

### 11.3 联邦搜索

`UnifiedSearchBar` 组件嵌入顶部 Header，输入关键词后并发查询 OmniDesk 内部表 + paperless，结果合并展示，paperless 来源带 `📄 paperless 文档` 标签和高亮摘要。

---

## 12. 测试覆盖

| 测试文件 | 覆盖范围 |
|----------|----------|
| `test_models.py` | 4 个模型的创建、唯一约束、单例逻辑 |
| `test_client.py` | PaperlessClient 所有方法 + 异常处理（mock HTTP） |
| `test_outbox.py` | OutboxService 入队/拉取/标记成功/失败退避/死信升级 |
| `test_tasks.py` | 3 个 Celery 任务（outbox worker / health check / cache cleanup） |
| `test_views.py` | Outbox API / Health API / Bind API / Download/Preview API 权限与逻辑 |
| `test_search_federation.py` | PaperlessSearchService + UnifiedSearchView 合并/降级 |
| `test_business_integration.py` | PaperlessUploadService 业务入口 |
| `test_app_config.py` | App 注册验证 |
