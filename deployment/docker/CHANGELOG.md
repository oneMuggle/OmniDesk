# 更新日志

本项目的所有重要变更都将记录在此文件中。

格式遵循 [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)，
版本号遵循 [语义化版本](https://semver.org/spec/v2.0.0.html)。

### 如何发布新版本

运行 `python manage.py generate_release --preview` 预览变更，确认后去掉 `--preview` 执行。
系统会自动分析 git 提交、确定版本号并更新本文件。
详见 [CLAUDE.md](../../CLAUDE.md) 中的 Version Update System 章节。

## [未发布]

### 新增
- **智能助手 3 个新工具(阶段 3)** — `AnnouncementTool` / `ComplianceTool` / `ExternalLinkTool`
  - `announcement_query`:查询 `communication.Post`(未过期+未归档),关键词匹配 title/content,上限 10 条
  - `compliance_query`:查询 `compliance.ComplianceIssue`(待处理+处理中),按业务优先级排序(紧急>高>中>低)
  - `external_link_query`:查询 `external_integration.ExternalLink`(active),支持 SSO 链接
  - 详情见 `docs/plans/2026-06-07_smart-assistant-stage3-new-tools.md` 与 `docs/technical/16-smart-assistant.md §2.2.1`
- **`ToolContext` 类型化抽象** — 替代裸 dict,`frozen=True` dataclass 含 `user` / `request_id` / `history` 字段,`from_request()` 工厂方法
- **`BaseTool.required_auth: bool = True` 字段** — fail-closed 默认值;`ToolRegistry.get_tool_for_user(intent_type, user)` 分发时校验,未授权返回 `None`
- **前端 `ToolResult.jsx` 3 个新卡片** — AnnouncementCard(geekblue)/ComplianceCard(red 含严重程度 + 状态 tag)/LinkCard(cyan 含 SSO 标签)

### 变更
- **`BaseTool.execute` 签名升级**:`context: "ToolContext"` 替代 `context: dict = None`,10 个旧工具兼容(子类 override 允许签名偏离基类)
- **覆盖率门槛 85% 维持**:模块总覆盖率 96%(1430 statements),`smart_assistant/tools/registry.py` 62%(Task 0.3 `get_tool_for_user` 部分未 E2E 覆盖,后续 Task 4.1 E2E 4 场景已部分覆盖)
- **测试基线 392 passed + 11 xpassed**(smart_assistant 后端);371 passed(前端)

### 修复
- **ComplianceTool severity 排序** — 替换 `order_by("-severity")` 字典序错误(高>紧>低>中)为 `Case/When` 业务优先级(紧急=0/高=1/中=2/低=3)
- **ComplianceTool `description[:200]` 加 `...` 后缀** — 与 `AnnouncementTool` 一致,LLM 可识别截断

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
