# 2026-05-11_version-update-module.md

# 版本更新模块方案

## 背景与目标

OmniDesk 将在内网环境中长期运行，积累大量用户数据。当前的部署流程存在以下风险：

1. **没有版本标记** — 镜像使用 `:latest` 标签，无法追溯当前部署版本
2. **迁移无前置检查** — `manage.py migrate` 直接执行，一旦迁移脚本有 bug 可能破坏数据
3. **无回滚机制** — 更新失败后无法快速恢复到上一个稳定版本
4. **无数据备份** — 更新前没有自动备份数据库和媒体文件
5. **无兼容性检查** — 大版本跳跃时没有检查兼容性

**目标：** 实现一套安全、可追溯、可回滚的版本更新流程，确保更新不破坏已有数据。

---

## 涉及的文件与模块

| 文件/目录 | 变更类型 | 说明 |
|-----------|----------|------|
| `omni_desk_backend/core/version.py` | 新建 | 版本信息常量 |
| `omni_desk_backend/core/management/commands/check_migrations.py` | 新建 | 迁移兼容性检查命令 |
| `omni_desk_backend/core/management/commands/backup_db.py` | 新建 | 数据库备份命令 |
| `omni_desk_backend/core/management/commands/restore_db.py` | 新建 | 数据库恢复命令 |
| `omni_desk_backend/core/management/commands/list_versions.py` | 新建 | 版本历史查询命令 |
| `omni_desk_backend/omni_desk_backend/settings/base.py` | 修改 | 添加版本信息读取 |
| `deployment/docker/deploy_offline.sh` | 修改 | 整合更新流程 |
| `deployment/docker/upgrade.sh` | 新建 | 一键安全升级脚本 |
| `deployment/docker/rollback.sh` | 新建 | 一键回滚脚本 |
| `deployment/docker/backup.sh` | 新建 | 备份脚本 |
| `deployment/docker/VERSION` | 新建 | 版本标记文件 |
| `deployment/docker/CHANGELOG.md` | 新建 | 版本更新日志 |
| `omni_desk_backend/core/__init__.py` | 新建 | core 应用初始化 |
| `omni_desk_backend/core/apps.py` | 新建 | core 应用配置 |
| `omni_desk_frontend/src/features/system/VersionInfo.jsx` | 新建 | 前端版本信息展示 |
| `omni_desk_backend/core/api.py` | 新建 | 版本信息 API 端点 |

---

## 技术方案

### 整体架构

```
┌─────────────────────────────────────────────────────┐
│                   更新流程                           │
│                                                     │
│  1. 预检  → 版本兼容性 + 迁移兼容性检查              │
│  2. 备份  → 数据库 dump + 媒体文件 tar              │
│  3. 更新  → 新容器启动 + 迁移执行                    │
│  4. 验证  → 健康检查 + 核心 API 探测                 │
│  5. 回滚  → 失败时自动恢复备份                      │
└─────────────────────────────────────────────────────┘

版本标记策略：
  backend: omni-desk-backend:v1.2.3   (语义化版本)
  frontend: omni-desk-frontend:v1.2.3

数据保护策略：
  - 每次更新前自动备份到 /opt/omnidesk/backups/
  - 备份保留最近 10 个版本
  - 备份文件命名: backup_v1.2.3_20260511_143000.sql.gz
```

### 版本管理策略

采用**语义化版本**（SemVer）：`MAJOR.MINOR.PATCH`

| 版本号 | 说明 | 更新策略 |
|--------|------|----------|
| `1.0.0` | 首个稳定版 | 首次部署 |
| `1.0.1` | 修复 bug | 直接升级 |
| `1.1.0` | 新增功能，向后兼容 | 直接升级（需迁移） |
| `2.0.0` | 破坏性变更 | 需要数据迁移工具 + 手动确认 |

### 数据库迁移安全

Django 的迁移系统本身是安全的，但我们需要增加保护层：

1. **迁移预检**：在 `migrate` 之前运行 `showmigrations --plan`，输出即将执行的变更列表，要求操作者确认
2. **备份前置**：每次执行迁移前自动备份
3. **迁移锁**：防止并发迁移

### 镜像版本标记

放弃 `:latest` 标签，改用语义化版本 tag：

```
omni-desk-backend:v1.0.0
omni-desk-backend:v1.0.1
omni-desk-frontend:v1.0.0
omni-desk-frontend:v1.0.1
```

同时保留一个 `stable` 标签指向当前稳定版本。

---

## 实施步骤

### Phase 1: 核心基础设施（版本标记 + 信息查询）

- [x] 步骤 1：创建 `core` Django 应用
  - `core/apps.py` — 应用配置
  - `core/__init__.py` — 空文件
  - 注册到 `INSTALLED_APPS`

- [x] 步骤 2：创建版本信息模块
  - `core/version.py` — 定义 `VERSION = "1.0.0"` 常量
  - 在 `base.py` 中读取版本号暴露给 Django settings

- [x] 步骤 3：创建版本信息 API
  - `core/api.py` — 提供 `/api/system/version/` 端点
  - 返回：当前版本号、构建时间、Django 版本

- [x] 步骤 4：创建 `VERSION` 文件和 CI/CD 集成
  - `deployment/docker/VERSION` — 文本文件，写入版本号
  - 初始版本设为 `0.1.0`

**验收标准：** `curl /api/system/version/` 返回正确版本信息 ✅

### Phase 2: 数据库备份与恢复

- [x] 步骤 1：创建 `backup_db` 管理命令
  - 使用 `pg_dump` 导出数据库
  - 支持 gzip 压缩
  - 输出到指定备份目录

- [x] 步骤 2：创建 `restore_db` 管理命令
  - 从备份文件恢复数据库
  - 恢复前确认（防止误操作）
  - 验证恢复完整性

- [x] 步骤 3：创建 `backup.sh` 脚本
  - 调用 Django 命令备份数据库
  - 打包 media 文件
  - 自动清理过期备份（保留最近 10 个）

**验收标准：** 执行备份后能成功恢复到一个干净的数据库

### Phase 3: 迁移预检与安全检查

- [x] 步骤 1：创建 `check_migrations` 管理命令
  - 对比当前数据库迁移记录与代码中的迁移文件
  - 列出待执行的迁移
  - 检测破坏性变更（DROP TABLE、DROP COLUMN）
  - 输出预检报告

- [x] 步骤 2：创建 `list_versions` 管理命令
  - 列出所有已部署的版本记录
  - 显示当前版本和更新时间

- [x] 步骤 3：在 `production.py` settings 中添加迁移保护
  - 添加安全注释，明确迁移必须通过管理命令显式执行

**验收标准：** 运行预检命令能正确识别待执行迁移和潜在风险 ✅

### Phase 4: 安全升级脚本

- [x] 步骤 1：创建 `upgrade.sh` 脚本
  流程：
  ```
  1. 检查当前版本 → 读取 VERSION 文件确认目标版本
  2. 兼容性检查 → 不允许跨越 MAJOR 版本
  3. 加载新镜像 → docker load 新版本的 tar
  4. 预检迁移 → 运行 check_migrations
  5. 确认 → 显示变更列表，要求输入 yes 确认
  6. 备份 → 自动执行数据库 + media 备份
  7. 更新容器 → docker compose 切换镜像 tag
  8. 执行迁移 → python manage.py migrate
  9. 收集静态文件 → collectstatic
  10. 健康检查 → curl /api/health/ 确认服务正常
  11. 完成 → 记录更新日志
  ```

- [x] 步骤 2：创建 `rollback.sh` 脚本
  流程：
  ```
  1. 列出可回滚的版本
  2. 停止当前服务
  3. 切换回旧版本镜像
  4. 恢复数据库（可选，默认不恢复）
  5. 重启服务
  6. 健康检查
  7. 记录回滚日志
  ```

- [x] 步骤 3：改造 `deploy_offline.sh`
  - `start` 命令整合版本检测
  - 新增 `upgrade` 子命令
  - 新增 `rollback` 子命令
  - 新增 `version`、`backup`、`migrate` 子命令
  - 保留现有命令兼容性

**验收标准：** 从 v1.0.0 升级到 v1.1.0 后数据完整，回滚后数据恢复

### Phase 6: 系统更新管理页面（网页版）

- [x] 步骤 1：后端 — 新增 API 端点
  - `changelog()` — 读取 CHANGELOG.md 返回 Markdown 内容
  - `migration_list()` — 列出已应用和待执行的迁移
  - 路由：`GET /api/system/changelog/`、`GET /api/system/migrations/`

- [x] 步骤 2：前端 — 创建 SystemUpdatePage 页面
  - Tab 1: 版本信息（版本号、构建时间、Django 版本）
  - Tab 2: 更新日志（react-markdown 渲染）
  - Tab 3: 迁移状态（已应用 + 待执行 + 破坏性变更警告）

- [x] 步骤 3：路由注册
  - 添加 `/system-update` 路由，受 ProtectedRoute 保护

- [x] 步骤 4：依赖检查
  - 已安装 `react-markdown ^10.1.0`，无需额外安装

**验收标准：** 用户可通过浏览器访问 `/system-update` 查看版本、日志、迁移状态

---

## 风险评估与依赖

### 风险

| 风险 | 级别 | 应对措施 |
|------|------|----------|
| 数据库备份过大占用磁盘 | 中 | 使用 gzip 压缩 + 自动清理旧备份 |
| MAJOR 版本迁移复杂 | 高 | MAJOR 版本禁止自动升级，需手动迁移脚本 |
| 回滚时新迁移已执行 | 高 | Django 支持 `migrate app zero` 反向迁移 |
| 内网服务器磁盘不足 | 中 | 备份前检查磁盘空间，不足时告警 |
| 镜像导出/传输中断 | 低 | 使用 checksum 验证完整性 |

### 依赖

- PostgreSQL 的 `pg_dump` 和 `pg_restore` 工具
- Django 迁移系统的向后兼容性
- 内网服务器的 Docker 环境

### 磁盘空间估算

```
单次备份大小 ≈ 数据库大小 + media 文件大小
保留 10 个备份 ≈ 10 × (DB + media)

建议：备份目录所在磁盘预留至少 3 倍数据库大小的空间
```

---

## 目录结构（完成后）

```
omni_desk_backend/
├── core/                          # [新建] 核心应用
│   ├── __init__.py
│   ├── apps.py
│   ├── version.py                 # 版本常量
│   ├── api.py                     # 版本信息 API
│   └── management/commands/
│       ├── check_migrations.py    # 迁移预检
│       ├── backup_db.py           # 数据库备份
│       ├── restore_db.py          # 数据库恢复
│       └── list_versions.py       # 版本列表
│
deployment/docker/
├── VERSION                        # [新建] 当前版本号
├── CHANGELOG.md                   # [新建] 更新日志
├── upgrade.sh                     # [新建] 安全升级脚本
├── rollback.sh                    # [新建] 回滚脚本
├── backup.sh                      # [新建] 备份脚本
├── deploy_offline.sh              # [改造] 整合版本管理
└── backups/                       # [运行时] 备份目录
    ├── backup_v1.0.1_20260511.sql.gz
    └── media_v1.0.1_20260511.tar.gz
```

---

## 预计复杂度

- **Phase 1**: 低（2-3 小时）— 基础版本信息
- **Phase 2**: 中（3-4 小时）— 备份恢复逻辑
- **Phase 3**: 中（3-4 小时）— 迁移安全检查
- **Phase 4**: 高（5-6 小时）— 核心升级/回滚脚本
- **Phase 5**: 低（1-2 小时）— 前端展示

**总计：14-19 小时**
