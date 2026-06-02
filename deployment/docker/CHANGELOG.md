# 更新日志

本项目的所有重要变更都将记录在此文件中。

格式遵循 [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)，
版本号遵循 [语义化版本](https://semver.org/spec/v2.0.0.html)。

### 如何发布新版本

运行 `python manage.py generate_release --preview` 预览变更，确认后去掉 `--preview` 执行。
系统会自动分析 git 提交、确定版本号并更新本文件。
详见 [CLAUDE.md](../../CLAUDE.md) 中的 Version Update System 章节。

## [未发布]

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
