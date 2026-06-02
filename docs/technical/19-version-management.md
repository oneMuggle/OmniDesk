# 版本管理系统

## 1. 概述

使用语义化版本号（SemVer）管理应用版本，配合自动化备份、迁移检查和升级/回滚机制。

## 2. 版本文件

`deployment/docker/VERSION` — 格式 `v{MAJOR}.{MINOR}.{PATCH}`，由 `core/version.py` 读取。

## 3. Django 管理命令

| 命令 | 说明 |
|------|------|
| `check_migrations` | 预检查待执行迁移，警告破坏性变更 |
| `backup_db` | 备份数据库+media，自动清理旧备份（保留10个） |
| `restore_db <file>` | 从 `.sql.gz` 恢复数据库 |
| `generate_release` | 根据 git 提交自动生成版本号和 CHANGELOG |
| `list_versions` | 显示当前版本和迁移历史 |

## 4. API 端点

| 端点 | 返回 |
|------|------|
| `GET /api/system/version/` | `{version, build_time, django_version}` |
| `GET /api/system/changelog/` | CHANGELOG markdown 内容 |
| `GET /api/system/migrations/` | `{applied, pending, has_destructive}` |

## 5. 部署脚本

| 脚本 | 说明 |
|------|------|
| `upgrade.sh` | 10步安全升级 |
| `rollback.sh` | 回滚到上一版本 |
| `backup.sh` | 手动备份 |
| `deploy_offline.sh` | 离线部署（version/backup/upgrade/rollback/migrate 子命令） |

## 6. 升级规则

1. 每次更新前备份
2. 预检查迁移，破坏性变更需人工审核
3. 大版本升级禁止使用 `upgrade.sh`
4. Django 迁移不会自动执行，必须显式 `migrate`

## 7. 前端

`/control-panel/system-update` — 管理员页面，显示版本/CHANGELOG/迁移状态。
