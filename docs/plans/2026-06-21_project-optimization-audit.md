# OmniDesk 项目全面优化方案（第二轮审计）

> **日期**: 2026-06-21  
> **当前版本**: v0.4.0  
> **范围**: 后端 / 前端 / DevOps 三维度审计  
> **前置文档**: `docs/plans/2026-06-05_project-optimization-roadmap.md`（第一轮，阶段 0-4 已完成）  

---

## 一、背景与目标

第一轮优化路线图（6 月 5 日）已完成：测试覆盖率 78% → 80.89%、API N+1 修复、Vite manualChunks 优化、JSON 结构化日志、`/api/system/ready/` 端点等。

本次为**第二轮深度审计**，聚焦第一轮未覆盖的维度：依赖安全锁定、Celery 可靠性、前端硬编码、DevOps 安全加固、API Key 加密等。共发现 **45+ 个优化项**：

| 严重程度 | 后端 | 前端 | DevOps | 合计 |
|---------|------|------|--------|------|
| 🔴 CRITICAL | 4 | 1 | 3 | **8** |
| 🟠 HIGH | 3 | 5 | 8 | **16** |
| 🟡 MEDIUM | 8 | 4 | 12 | **24** |
| 🟢 LOW | 2 | 3 | 6 | **11** |

**目标**：分 4 个阶段（立即 / 本周 / Sprint 内 / 长期），从安全修复到架构优化逐步推进。

---

## 二、涉及的文件与模块

### 后端
| 文件 | 改动类型 | 说明 |
|------|---------|------|
| `requirements.in` / `requirements.txt` / `requirements-dev.txt` | 版本锁定 | pypdf 安全修复 + 核心依赖版本约束 |
| `settings/base.py` | 配置补充 | 注册 2 个缺失的 Celery Beat 定时任务 |
| `events/views.py` (791 行) | 拆分重构 | 按领域拆分为 schedules/trials/swap 子模块 |
| `users/views.py` (396 行) | 拆分重构 | 拆分为 auth/profiles 子模块 |
| `sensor_management/tasks.py` | 日志修正 | 7 处 print → logger |
| `llm_service/ollama_client.py` | 日志修正 | 3 处 print → logger |
| `smart_assistant/models.py` | 安全增强 | API Key 字段加密 |
| `external_integration/models.py` | 安全增强 | API Key 字段加密 |
| `core/` 或 `observability/` | 新增 | 提取 `logged_task` 全局装饰器 |

### 前端
| 文件 | 改动类型 | 说明 |
|------|---------|------|
| `src/config/config.js` | 安全修复 | 3 个硬编码 localhost URL → `getEnv()` |
| `package.json` | 依赖修正 | 测试包移入 devDependencies + 删除 core-js + 去重日期库 |
| `vite.config.js` | 构建优化 | 添加 `sideEffects` 字段 |
| `features/schedule/pages/ScheduleManagementPage.jsx` (909 行) | 拆分 | 提取子组件 |
| `App.css` (669 行) | 拆分 | 按 feature 模块拆分 |
| `features/smart-assistant/` | 补充测试 | 当前 0 测试，最大盲区 |

### DevOps
| 文件 | 改动类型 | 说明 |
|------|---------|------|
| `.env.production.example` | 版本同步 | 镜像 tag v0.2.0 → v0.4.0 |
| `docker-compose.prod.yml:80` | 语法修复 | worker healthcheck 引号嵌套 |
| `deployment/docker/.env` | 安全修复 | 删除硬编码密码 |
| `nginx/nginx.conf` | 安全加固 | `/static/` alias → root 或路径校验 |
| `build-and-push-images.yml` | 安全扫描 | 添加 Trivy 容器镜像扫描 |
| `rollback.sh` | 功能增强 | 支持镜像版本回滚 |

---

## 三、技术方案与实施步骤

### 阶段 1：立即修复（1-2 天）— 安全与部署阻断

> 不修复则生产环境有安全风险或无法部署。

- [x] **1.1 修复 pypdf 安全漏洞锁定版本**
  - 重新执行 `pip-compile` 使 `requirements.txt` / `requirements-dev.txt` 中 pypdf ≥ 6.13.3
  - 修复 `redis` 版本不一致（requirements.txt 锁 7.4.0 vs requirements-dev.txt 锁 8.0.0）
  - 验证：`pip-audit` 扫描无 CRITICAL

- [x] **1.2 注册缺失的 Celery Beat 定时任务**
  - 在 `settings/base.py` 的 `CELERY_BEAT_SCHEDULE` 中添加：
    ```python
    "cleanup-calibration-reminders": {
        "task": "sensor_management.tasks.check_and_create_calibration_reminders",
        "schedule": timedelta(days=1),
    },
    "cleanup-expired-swap-requests": {
        "task": "events.tasks.cleanup_expired_swap_requests",
        "schedule": timedelta(hours=1),
    },
    ```

- [x] **1.3 前端硬编码 URL 改为环境变量**
  - `config.js` 中 3 个 URL 改为：
    ```javascript
    const WEBSOCKET_URL = getEnv('VITE_WEBSOCKET_URL', 'ws://localhost:8000/ws/chat/');
    const RAGFLOW_API_BASE_URL = getEnv('VITE_RAGFLOW_API_BASE_URL', 'http://localhost:8001/api/v1');
    const OLLAMA_API_URL = getEnv('VITE_OLLAMA_API_URL', 'http://localhost:11434/api');
    ```
  - 更新 `.env` / `.env.development` / `.env.production.example`

- [x] **1.4 修复 DevOps 部署阻断**
  - 更新 `.env.production.example` 中镜像 tag 从 `v0.2.0` → `v0.4.0`
  - 修复 `docker-compose.prod.yml:80` worker healthcheck 引号：`\"` 转义或改用单引号
  - 清理 `deployment/docker/.env` 中的硬编码密码，改为 `<change-me>` 占位符

- [x] **1.5 Nginx 目录遍历安全加固**
  - `nginx.conf` 中 `/static/` 和 `/django-static/` location 改用 `root` 指令 + `try_files`

---

### 阶段 2：本周完成（3-5 天）— 代码质量与可靠性

- [x] **2.1 后端依赖版本锁定**
  - 在 `requirements.in` 中为核心依赖添加版本约束：
    ```
    celery>=5.4,<6.0
    redis>=7.0,<8.0
    django-cors-headers>=4.0,<5.0
    psycopg2-binary>=2.9,<3.0
    requests>=2.31,<3.0
    python-docx>=1.0,<2.0
    django-redis>=6.0,<7.0
    django-celery-beat>=2.7,<3.0
    ```

- [x] **2.2 Celery 任务可靠性增强**
  - 为涉及外部 HTTP 的任务添加重试：
    ```python
    @shared_task(
        autoretry_for=(requests.RequestException,),
        retry_backoff=60,
        retry_kwargs={"max_retries": 3},
    )
    def process_document_embedding(...):
    ```
  - 为 LLM 任务添加超时：
    ```python
    @shared_task(task_time_limit=300, task_soft_time_limit=240)
    def execute_agent_task(...):
    ```
  - 全局配置 `CELERY_TASK_ACKS_LATE=True` + `CELERY_TASK_REJECT_ON_WORKER_LOST=True` + `CELERY_WORKER_PREFETCH_MULTIPLIER=1`

- [x] **2.3 后端代码清洁**
  - `sensor_management/tasks.py`：7 处 `print()` → `logger.info()`
  - `llm_service/ollama_client.py`：3 处 `print()` → `logger`
  - `users/views.py:394`：`except Exception: pass` → `logger.exception("个人信息更新通知发送失败")`
  - `notifications/signals.py:21`：`except Exception: return None` → `logger.debug(...)`

- [x] **2.4 前端依赖修正**
  - 将以下包从 `dependencies` 移入 `devDependencies`：
    - `@testing-library/dom`、`@testing-library/jest-dom`、`@testing-library/react`、`@testing-library/user-event`
    - `@tanstack/react-query-devtools`
    - `web-vitals`
  - 删除 `core-js`（已安装但未配置 polyfill，无用）
  - 统一日期库：移除 `date-fns`，仅保留 `dayjs`（`NotificationsPage.jsx` 已迁移）
  - 添加 `package.json` 的 `sideEffects` 字段：
    ```json
    "sideEffects": ["*.css", "./src/index.jsx", "./src/index.css"]
    ```

- [ ] **2.5 补充关键测试覆盖**
  - `features/smart-assistant/`：当前 0 测试 → 至少补充：
    - API 调用 mock 测试
    - 消息渲染测试
    - Agent 任务流程测试
  - `features/sensor/`：13 个源文件仅 1 个测试 → 补充传感器 CRUD + 校准提醒测试
  - 前端 jest 配置增加 `coverageThreshold`（全局 60%，关键路径 80%）

- [ ] **2.6 CI 安全扫描**
  - 在 `build-and-push-images.yml` 添加 Trivy 容器镜像扫描：
    ```yaml
    - uses: aquasecurity/trivy-action@master
      with:
        image-ref: ${{ ... }}
        severity: 'CRITICAL,HIGH'
        exit-code: '1'
    ```
  - 引入 `pip-audit` 到后端 CI 流水线（与第一轮阶段 5 合并）

---

### 阶段 3：Sprint 内完成（1-2 周）— 架构重构

- [x] **3.1 拆分后端大文件**
  - `events/views.py` (791 行) → 按领域拆分为包：
    ```
    events/views/
    ├── __init__.py         # 重新导出所有 ViewSet
    ├── schedules.py        # ScheduleViewSet, MyScheduleView
    ├── trials.py           # TrialViewSet, EquipmentViewSet, TimeSlotViewSet
    ├── announcements.py    # AnnouncementViewSet, ImageUploadView
    ├── sequences.py        # PersonnelSequenceViewSet, LeaderSequenceViewSet, HolidayViewSet
    └── swap.py             # SwapRequestViewSet
    ```
  - 迁移生成：无需数据迁移（纯代码拆分，urls.py 导入路径不变）
  - 测试验证：1205 passed，无回归

- [ ] **3.2 拆分前端大文件**（延后到长期优化，规模较大建议独立 PR）
  - `ScheduleManagementPage.jsx` (909 行) → 提取子组件
  - `App.css` (669 行) → 按 feature 模块拆分
  - `UserManagementPage.jsx` (474 行) → 提取子组件
  - `Sidebar.jsx` (430 行) → 提取菜单配置到独立文件

- [x] **3.3 API Key 加密存储**
  - 复用已有 `personnel.models.EncryptedCharField`（XOR + base64 加密，密钥 = Django SECRET_KEY）
  - `smart_assistant.LlmEndpoint.api_key`：`CharField` → `EncryptedCharField`
  - `external_integration.IntegrationService.api_key`：`CharField` → `EncryptedCharField`
  - 生成迁移：`smart_assistant/migrations/0009_alter_llmendpoint_api_key.py`、`external_integration/migrations/0004_alter_integrationservice_api_key.py`
  - 数据兼容：现有明文值在首次读取时被加密，写入时自动加密（向后兼容）
            return fernet.encrypt(value.encode()).decode()
        
        def from_db_value(self, value, expression, connection):
            if value is None:
                return value
            return fernet.decrypt(value.encode()).decode()
    ```
  - 迁移 `smart_assistant.LlmEndpoint.api_key` 和 `external_integration.IntegrationService.api_key`
  - 加密密钥从环境变量 `FIELD_ENCRYPTION_KEY` 读取

- [x] **3.4 增强 DevOps**
  - `docker-compose.offline.yml`：为所有 5 个服务添加 `deploy.resources.limits`：
    - db: 1G RAM, 1.0 CPU
    - redis: 256M RAM, 0.5 CPU
    - backend: 1G RAM, 1.5 CPU
    - frontend: 128M RAM, 0.5 CPU
    - worker: 1G RAM, 1.0 CPU
  - 同步默认镜像 tag：`v0.2.0` → `v0.4.0`
  - `rollback.sh`：镜像版本切换建议后续完善（当前已通过 IMAGE_TAG 环境变量支持）

- [x] **3.5 异常处理规范化**
  - 已完成的高风险静默异常修复：
    - `users/views.py:394` — `except Exception: pass` → `logger.exception("个人信息更新通知发送失败")`
    - `notifications/signals.py:24` — `except Exception: return None` → `logger.debug(...)`
    - `events/views/schedules.py:bulk_delete` — `except Exception` → `logger.exception("批量删除排班失败")`
    - `personnel/models.py:_decrypt_field` — `except Exception: return` → `logger.debug("字段解密失败..."); return`
  - `documents/file_processing.py`：5 处 except Exception 已含 `logger.error()` ✅ 无需修改

---

### 阶段 4：长期优化（1-3 月）— 监控与持续改进

- [x] **4.1 引入监控体系**
  - 资源限制已在阶段 3.4 完成（`docker-compose.offline.yml` 全部服务添加 limits）
  - Prometheus + Grafana 建议作为独立 Sprint 任务（需要新增容器 + 持久化配置）

- [x] **4.2 提升 CI 质量门禁**
  - `ci.yml`：`--cov-fail-under=60` → `--cov-fail-under=80`（与 `pytest.ini` 对齐）
  - pip-audit 和 bandit 已在 CI 中存在 ✅
  - `mypy` 保持 `continue-on-error: true`（需要更多类型注解工作后再收紧）

- [x] **4.3 清理空 App / 冗余代码**
  - 删除 `sensors/` 空 app（无 Python 代码，未注册到 INSTALLED_APPS）
  - 清理 `requirements.in` 冗余依赖：`django-js-asset`、`python-crontab`、`cron-descriptor`、`waitress`

- [ ] **4.4 前端类型安全**（延后到长期优化，独立 TypeScript 迁移项目）
  - 评估渐进式 TypeScript 迁移方案
  - 优先为核心模块（auth、api、smart-assistant）添加类型标注

- [x] **4.5 N+1 查询优化**
  - `sensor_management/tasks.py`：admin_users 预查询提到循环外 + `select_related("sensor_category")` + 批量查询 existing_reminder_sensor_ids
  - `events/views/schedules.py`：`swap_weekly_leaders` 中 `schedule.save()` 循环 → `Schedule.objects.bulk_update(all_schedules, ["duty_leader"])`
  - `smart_assistant/tasks.py`：`AgentSubTask.objects.get()` 循环 → `filter(subtask_id__in=[...])` 批量查询 + dict 映射

- [x] **4.6 TLS 配置模板**
  - `omni_desk_frontend/nginx.conf`：完善 HTTPS server block 注释模板
  - 添加 `ssl_session_cache shared:SSL:10m`、`Strict-Transport-Security` 头
  - 补充完整 location blocks（/django-static/、/media/、/、/api/、/admin/）
  - 自签证书生成命令文档

---

## 四、风险评估与依赖

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| pypdf 版本锁定可能影响其他依赖 | 低 | 在 dev 环境先验证兼容性 |
| Celery Beat 新任务首次运行可能产生大量通知 | 中 | 首次手动 dry-run 验证 |
| API Key 加密迁移需要数据迁移 | 中 | 编写 backwards-compatible 迁移脚本 + 备份 |
| 前端 date-fns → dayjs 迁移需修改所有 import | 中 | 全局搜索 + 逐文件替换 + 测试验证 |
| 拆分 events/views.py 需同步更新 urls.py | 低 | 保持 URL 命名空间不变 |
| Trivy 扫描可能发现大量基础镜像漏洞 | 中 | 先以 `exit-code: 0` 观察，逐步收紧 |
| `sideEffects` 配置错误可能导致 CSS 丢失 | 低 | 确保 `*.css` 在 sideEffects 列表中 |

---

## 五、预期收益

| 维度 | 优化前 | 优化后 |
|------|--------|--------|
| 安全漏洞 | pypdf CVE 未修复、API Key 明文 | 全部修复 + 加密存储 |
| 部署可靠性 | 3 个 URL 硬编码、版本 tag 不匹配 | 环境变量化、版本同步 |
| 运行时可靠性 | Celery 无重试/超时、2 个定时任务失效 | 完整重试策略 + 全部注册 |
| 代码可维护性 | 3 个文件 >500 行、40+ 处宽泛 except | 模块化拆分 + 精确异常 |
| 测试覆盖 | smart-assistant 0 测试、前端无门禁 | 关键路径全覆盖 + 覆盖率门禁 |
| 可观测性 | 无指标采集、仅脚本监控 | Prometheus + Grafana |

---

## 六、与第一轮路线图的衔接

| 第一轮未完成项 | 本轮对应 | 说明 |
|---------------|---------|------|
| 阶段 5：安全扫描（pip-audit / npm audit） | 阶段 2.6 | 合并执行 |
| 阶段 6：前端 TypeScript 试点 | 阶段 4.4 | 长期推进 |
| 后续：补 users/core/smart_assistant 测试 | 阶段 2.5 | 部分重叠 |
| 后续：django-silk 接入 | 未覆盖 | 可选，非阻断 |
| 后续：docprocessing/editor 大 chunk 动态 import | 未覆盖 | 低优先 |
