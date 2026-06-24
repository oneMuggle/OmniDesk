# 更新日志

本项目的所有重要变更都将记录在此文件中。

格式遵循 [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)，
版本号遵循 [语义化版本](https://semver.org/spec/v2.0.0.html)。

### 如何发布新版本

运行 `python manage.py generate_release --preview` 预览变更，确认后去掉 `--preview` 执行。
系统会自动分析 git 提交、确定版本号并更新本文件。
详见 [CLAUDE.md](../../CLAUDE.md) 中的 Version Update System 章节。

## [未发布]

## [0.5.5] - 2026-06-24

### 修复
- **deploy.sh generate_env 自动同步 IMAGE_TAG 与 VERSION 一致**: 升级时 `config/.env.production` 是上次部署的 IMAGE_TAG(例如 v0.5.2),deploy.sh 直接 cp 不会更新,导致容器还在跑旧版本镜像(本次 v0.5.2 → v0.5.4 升级踩坑)。`generate_env` 末尾增加同步逻辑:读 `VERSION` 与 `compose/.env.production` 当前 IMAGE_TAG 对比,不匹配自动 sed 更新到 `v$VERSION`(`config/.env.production` 保留原样,只更新 `compose/.env.production`)。

### 验证
- bash 语法 OK(2 文件)
- 4 个场景逻辑测试通过(升级 v0.5.2→v0.5.4 / 首次部署 / 跨大版本 v0.3.0→v0.5.4 / IMAGE_TAG 缺失)
- 升级流程:从 v0.5.2 升级到 v0.5.4 不用再手动 sed 改 IMAGE_TAG

## [0.5.4] - 2026-06-24

### 修复

#### 人员管理
- **EncryptedCharField max_length=18 → 64 修复 18 字符身份证存储**: `_encrypt_field` 用 XOR+base64 编码,18 字符明文 → 24 字符密文超 `varchar(18)` 限制。`max_length` 改为 64(已有数据保留),并生成 migration 0006。Personnel 和 FamilyMember 同时修改(039f555)
- **Personnel seeder 用 18 字符真实身份证格式**: 配合 model 修复,seeder 恢复真实身份证格式(110101 + 8 位生日 + 4 位序号)而非短 fake 数据(c896d3e)

#### 路由权限
- **sync_routes 支持多路径**: backend 容器内找不到 routes.json,改为尝试多个路径(优先 `/usr/src/app/staticfiles/routes.json`,fallback 源码路径)。配合 Dockerfile 复制 routes.json,容器可同步 24 个前端路由(3ada87d + 4ff9460)

#### 后端
- **Llm Ollama 兜底 candidate 类型检查**: 直接调 `candidate.get("_is_ollama")` 在 candidate 不是 dict 时会抛 AttributeError,改为 `isinstance(candidate, dict) and ...`(e267baf)

#### 前端
- **登录请求不携带 Authorization 头**: 携带旧 token 可能导致后端用旧 token 验证而非 username/password。Login 检测到 `auth/login` 路径时跳过 Authorization 注入(878a226)

#### 部署配置
- **修正 postgres 镜像名 + 添加 VITE_API_PROXY_TARGET**: `postgres:14.2` → `postgres:14-alpine`(与 BUILD-MANIFEST.json 对齐);dev compose 添加 `VITE_API_PROXY_TARGET=http://backend:8000` 让 Vite dev server 代理 /api 请求到 backend(51411a1)
- **backend Dockerfile build 时复制 routes.json**: `COPY omni_desk_frontend/public/routes.json /usr/src/app/staticfiles/routes.json`,让 sync_routes 在生产 backend 镜像中能读到 frontend 路由(4ff9460)
- **.dockerignore 添加 routes.json negation**: `.dockerignore` 排除整个 `omni_desk_frontend/`,Dockerfile 复制 routes.json 失败。添加 `!omni_desk_frontend/public/routes.json` 让 build context 包含此文件(fc8f2f7)

#### CI
- **docker-integration job sed 分隔符 / 改 #**: `openssl rand -base64 32` 生成的字符串可能包含 `/` 字符,与 sed 表达式分隔符冲突,触发 `unknown option to 's'` 解析错误。改用 `#` 作为 sed 分隔符(base64 字符集不含 `#`)(e6688fc)
- **移除对未追踪本地脚本的依赖**: `scripts/validate-config.sh` 和 `scripts/check-container-logs.sh` 是本地未追踪文件,CI runner checkout 时不存在 → `No such file or directory`(91dec57)
- **所有 step 默认在 deployment/docker 工作目录**: 之前只有部分 step 有 `cd deployment/docker`,`Build Docker images` step 在 repo 根目录跑 `docker compose build` 找不到 compose 文件(c1ef5ff)
- **健康检查用公开端点 /api/health/ 代替 /api/system/version/**: `/api/system/version/` 需要认证返回 401,改用公开端点 `/api/health/`(c60cd1d)
- **测试登录 API 前先 migrate 数据库**: 直接 `python manage.py shell` 创建测试用户但数据库表没建 → `no such table: users_customuser`(6deb369)
- **Test frontend proxy 测试前端根路径 /**: `/api/system/version/` 在 dev compose(vite dev server)需要认证,改测前端根路径 /(98734e6)

### 验证
- 本地部署 5 个容器全部 healthy
- gunicorn Permission denied 错误 0,后端 500 错误 0
- 注册 API 全场景:正常 201、重复用户 400、用户名太短 400、密码不一致 400、空用户名 400、非法字符 400
- 登录 JWT 返回 access + refresh,refresh token 刷新正常
- 离线包 v0.5.2 重新打包,backend 镜像重建(包含 14 个 fix)
- 33+ 个表填充测试数据(15 personnel、89 子表、24 page routes)
- CI 全绿(8/8 jobs success)

## [0.5.2] - 2026-06-22

### 修复
- **deploy.sh generate_env 漏替换 `<CHANGE-TO-DB-USER>` 占位符**: `package_offline_bundle.sh` heredoc 内 `generate_env()` 补上 `re.sub(r'<CHANGE-TO-DB-USER>', 'omni_desk_user', content)`,避免离线部署首次启动时 `POSTGRES_USER` 保留为字面值 `<CHANGE-TO-DB-USER>` 导致 backend 连不上 DB(运行时 entrypoint.sh 死循环 "Database not ready yet, retrying...")
- 此问题由本次会话的离线包部署测试发现(在 `omnidesk-offline-v0.5.0` 复现)

## [0.5.1] - 2026-06-22

### 修复
- **离线部署包 .tar 镜像 RepoTags 缺 GHCR 全名**: `docker save` 改用 source + GHCR 双 tag,加载后无需额外 retag 即可被 compose 识别为 `ghcr.io/onemuggle/*` 镜像,避免部署兜底走 GHCR
- **离线包内 compose/env 的 IMAGE_TAG 默认值不同步**: `package_offline_bundle.sh` 在复制 compose/env 到 bundle 后,用 `sed` 把默认 tag 替换为 `${BUILD_VERSION}`,下次打 v0.5.1+ 自动正确
- **package_offline_bundle.sh heredoc 内 deploy.sh 缺 retag 逻辑**: 添加 11 行 retag,作为双保险(即便 tar 内 RepoTags 不全,部署时也能补)
- **POSTGRES_IMAGE 变量与 tar/compose 不一致**: `postgres:14.2` → `postgres:14-alpine`(与 BUILD-MANIFEST.json / compose / 实际 tar 对齐)

## [0.5.0] - 2026-06-22

### 新增
- **智能助手 — 多 Agent 协作(里程碑 1.1–1.4)**
  - 基础设施:`TaskPacket` 任务包、`SharedContext` 共享上下文、`MultiAgentExecutor` Pipeline 执行器
  - `Supervisor` 任务分解 + `IntentClassifier` 分流、REST API + SSE 推送
  - 工具未找到返回友好提示(rather than '无权限')
  - 显示体验优化:添加取消功能、改进 `<think>` 内容展示
- **前端 — 图片上传与表单校验**
  - `RichTextEditor` 恢复图片上传(`@tiptap/extension-image`)
  - `zod` 表单校验试点(登录页)+ 表单模式文档
- **可观测性** — 关键路径结构化日志(登录 / 权限 / Celery)
- **DevTools** — `django-silk` dev 模式接入(SQL profiling)

### 变更
- **前端构建** — `src/shared/api` 全部转 TypeScript(12 文件)
- **前端性能** — `React.lazy` 拆分 editor / docprocessing / markdown 页面
- **前端依赖** — `react-quill → tiptap` 迁移(修 quill XSS CVE);`npm audit` overrides 修 22→3 CVE
- **Vite target** — build target 提升至 `chrome109`(兼容 Win7 Chrome 109 / Edge 109)
- **后端重构** — 全面项目优化(四阶段)+ ruff format 规范化
- **视图集分页** — 恢复 3 处 ViewSet 分页 + 2 处封顶 1000

### 修复
- 登录表单空值验证消息
- 前端缺失的 `zod` 依赖
- 前端依赖与 CI 配置
- `events.trials.py` 未使用的 `status` import
- CI:`deploy-test.yml` 镜像 tag `v0.2.0 → v0.4.0`、lint-backend / security 失败、调低 lint-frontend 阻塞阈值
- ruff format 格式化新增和修改的文件

## [0.4.0] - 2026-06-05

### 新增
- **人员-用户关联方案** — `Personnel ↔ CustomUser` 1:1 可选关联,详见 `docs/technical/26-personnel-user-association.md`
  - 新端点 `GET/PATCH /api/users/me/personnel/`(用户自助维护白名单字段)
  - 新端点 `/api/notifications/{id}/mark_read/`、`mark_all_read/`、`unread_count/`(P1-3 增强)
  - 新管理命令 `python manage.py link_user_personnel`(支持 link/unlink/dry-run/rollback + 审计日志)
- **Notification 模型扩展** — 增字段 `priority`(LOW/NORMAL/HIGH/URGENT)、`dedupe_key`、`read_at`
- **NotificationPreference 模型** — 用户通知偏好(免打扰时段、渠道设置)
- **Personnel pre/post_save 信号** — 岗位/部门变更 → 通知本人(新增 `position_changed` 通知类型)
- **FamilyMember post_save 信号** — 紧急联系人增/改 → 通知本人确认(新增 `emergency_contact` 通知类型)
- **AuditLogEntry 模型** — 配套 link_user_personnel 命令的审计日志(可按 batch_id 回滚)
- **IsHR + IsAdminOrManagerOrReadOnly 权限类** — 区分 HR(Manager 组)与 Admin
- **前端组件** — `MyPersonnelInfo`、`NotificationBell`(5s 轮询)、`NotificationCenter`(分页 + 过滤)
- **前端路由** — `/me/personnel`、`/notifications`

### 变更
- **PersonnelViewSet 权限放宽** ⚠️ — `IsAdminOrReadOnly` → `IsAdminOrManagerOrReadOnly`(HR 现可写,需 Admin 注意)
- **NotificationService 增强** — `create()` 新增 `priority` + `dedupe_key` 参数(向后兼容,默认值不变)
- **测试覆盖率** — 80.57% (Phase 1-3 新增 64 个测试用例,648 passed)

### 修复
- `NotificationViewSet.mark_read` / `mark_all_read` 现同步设置 `read_at` 字段

### 数据库迁移
- `notifications/0003_notificationpreference_notification_dedupe_key_and_more.py`
- `users/0002_auditlogentry.py`

### 升级注意
- 升级前必跑 `python manage.py check_migrations` 确认无破坏性变更
- `PersonnelViewSet` 权限变更:HR 现可写,如有定制工作流需复核

## [0.3.0] - 2026-06-05

### 新增
- **后端 API 性能审计报告** — `docs/technical/25-api-performance-audit.md` 盘点 52 个 ViewSet
- **结构化 JSON 日志** — 生产环境输出 JSON,`python-json-logger==2.0.7` 接入
- **可观测性端点** — `/api/system/ready/`(GET, AllowAny),区分 liveness vs readiness,检查 DB / Redis / Celery
- **安全检查清单** — `docs/technical/24-security-checklist.md`,6 个 CVE 详细分析 + OWASP Top 10 对照
- **TypeScript 渐进支持** — `tsconfig.json` + `src/shared/types/api.d.ts`,不强制团队写 TS

### 变更
- **测试覆盖率 78% → 81%** — 新增 seeder 测试 21 个,CI 阈值 70% → 80%(`pytest.ini`)
- **前端 Vite manualChunks 从 3 项扩到 13 项** — `ScheduleManagementPage` 610kB → 22kB(-96%),`index main` 420kB → 262kB(-38%)
- **CI 安全门禁强化** — `safety` → `pip-audit --strict`,`npm audit --audit-level=high`,移除 `|| true`

### 修复
- **6 个依赖 CVE**:
  - djangorestframework 3.15.0 → 3.15.2(CVE-2024-21520)
  - djangorestframework-simplejwt 5.3.0 → 5.5.1(CVE-2024-22513)
  - pyjwt 2.12.1 → 2.13.0(PYSEC-2026-175/177/178/179)
- **3 个 N+1 查询** — `DocumentTemplateViewSet` / `BookViewSet` / `GeneratedDocumentViewSet`
- **CLAUDE.md/AGENTS.md 4 处过时描述** — 双 UI 库、根 package.json Vue 依赖、Django 3.2 → 4.2、React CRA → Vite 5.4

### 安全
- 删除含明文生产密钥的 `.env.production.bak.1780558283` 备份文件
- `bandit` 静态扫描已纳入 CI(原已存在)

## [0.2.0] - 2026-05-16

### 新增
- **内网离线部署打包** — `package_offline_bundle.sh` 将构建产物打包为标准离线介质（镜像 + 脚本 + 配置 + 校验）
- **离线包完整性校验** — `verify.sh` 支持 SHA256 checksum 校验、必需文件检查、镜像大小合理性验证
- **一键部署入口** — 离线包内含 `scripts/deploy.sh`，支持 start/stop/status/logs/exec/migrate/verify
- **环境变量模板** — `.env.production.template` 用于离线包中生成生产环境配置

### 变更
- 构建脚本 `build_and_export.sh` 增加 `--platform linux/amd64` 架构锁定
- 构建后验证增加 `pip check` 依赖完整性检查
- 前端 `nginx.conf` 添加 `X-UA-Compatible` 响应头

### 修复
- 前端 Win7 Chrome 109 兼容性：browserslist 锁定 `chrome >= 109`，Vite 构建目标设为 `chrome109`
- MathJax SRE 语音引擎 CDN 回退问题：内网中禁用 SRE 避免 `cdn.jsdelivr.net` 请求失败

### 兼容性说明
- Windows 7 客户端：支持 Chrome 109 / Edge 109
- **不支持 IE11**（React 18 已放弃支持）
- 内网 HTTPS 需 Win7 安装 KB3140245 补丁（启用 TLS 1.2）

## [0.1.0] - 2026-05-11

### 新增
- 版本管理模块（`core` Django 应用）
- `/api/system/version/` 版本信息 API 端点
- 数据库备份命令 `backup_db`（gzip 压缩，自动清理超过 10 个的旧备份）
- 数据库恢复命令 `restore_db`
- 迁移预检命令 `check_migrations`（检测 DROP TABLE / DROP COLUMN 等破坏性变更）
- 版本历史查询命令 `list_versions`
- 安全升级脚本 `upgrade.sh`（预检 → 备份 → 确认 → 更新 → 健康检查）
- 回滚脚本 `rollback.sh`（可选数据库恢复）
- 手动备份脚本 `backup.sh`
- `deploy_offline.sh` 新增 `version`、`backup`、`upgrade`、`rollback`、`migrate` 子命令
- 前端版本信息展示组件 `VersionInfo.jsx`
- 语义化版本文件 `VERSION`（初始版本 `0.1.0`）
