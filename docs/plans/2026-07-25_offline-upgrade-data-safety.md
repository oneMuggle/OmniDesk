# OmniDesk 离线升级数据安全保护设计

## 背景与目标

当前离线包部署与升级流程已经具备部分版本校验、备份、健康检查和回滚能力，但标准离线包与源码树脚本存在分叉，备份路径、数据卷身份、迁移预检、真实镜像回滚和恢复错误处理尚未形成可靠闭环。生产部署后首先保证数据安全，因此升级必须遵循“先验证备份、再变更数据；失败自动恢复；恢复失败保守停机”的原则。

本设计目标：

- 升级前对数据库和媒体创建同一批次、可定位、可校验、可恢复的完整备份；
- 备份恢复到临时数据库验证成功后才允许升级；
- 升级期间停止业务写入，禁止容器入口自动迁移；
- 使用目标镜像进行迁移预检，并在验证通过后显式迁移；
- 升级失败时切回源镜像并恢复数据库与媒体；
- 任一恢复步骤失败时进入 `SAFE_STOPPED`，不在不一致状态下自动启动业务；
- 固定 Compose 项目名和数据卷身份，避免不同离线包目录使用空卷；
- 危险清理操作必须有备份门禁和明确确认；
- 通过 Shell、Django、Docker 集成和端到端测试验证完整闭环。

## 涉及的文件与模块

主要涉及：

- `deployment/docker/package_offline_bundle.sh`
- `deployment/docker/deploy_offline.sh`
- `deployment/docker/upgrade.sh`
- `deployment/docker/rollback.sh`
- `deployment/docker/backup.sh`
- `deployment/docker/verify.sh`
- `deployment/docker/docker-compose.offline.yml`
- `deployment/docker/.env.production.example`
- `deployment/docker/smoke_tests.sh`
- `omni_desk_backend/entrypoint.sh`
- `omni_desk_backend/core/management/commands/backup_db.py`
- `omni_desk_backend/core/management/commands/restore_db.py`
- `omni_desk_backend/core/management/commands/check_migrations.py`
- 对应 Shell、Python 与 Docker 集成测试。

文档更新范围：

- `docs/technical/02-deployment-guide.md`
- `docs/technical/23-offline-deployment.md`
- `docs/technical/30-release-channels.md`
- `docs/technical/40-smoke-test-coverage.md`
- `docs/user-manual/12-deployment-channels.md`
- 必要时更新技术手册和用户手册 README 章节目录。

## 技术方案

### 1. 升级事务与备份批次

每次升级生成唯一 `upgrade_id`，例如 `20260725T143000Z-v0.7.0-rc.1-to-v0.7.0-rc.2`。数据库备份、媒体备份、metadata、校验和、恢复验证结果和升级状态全部归属于该 ID：

```text
backups/<channel>/<upgrade_id>/
├── metadata.json
├── database.sql.gz
├── database.sql.gz.sha256
├── media.tar.gz
├── media.tar.gz.sha256
└── restore-verification.json
```

`metadata.json` 记录源/目标版本、渠道、镜像 tag、manifest 或 Git SHA、Compose 项目名、数据卷、数据库、文件大小、SHA-256、时间、当前阶段、失败原因与恢复结果。备份必须位于不会随 `docker compose down -v` 删除的外部持久路径。

### 2. 组件职责

- `upgrade.sh`：实现显式升级状态机、维护模式、备份验证、目标镜像加载、迁移预检、迁移、健康检查、冒烟测试、成功提交和失败恢复。
- `backup.sh`：创建升级批次，生成数据库与媒体备份，生成 checksum，写入 metadata，并将数据库恢复到临时库验证、将媒体包做结构与路径安全检查。
- `rollback.sh`：校验指定升级批次，停止业务容器，切换到 metadata 记录的源镜像，恢复数据库和媒体，验证后才启动源版本；任何失败进入安全停机。
- Compose：固定 `COMPOSE_PROJECT_NAME`、数据库/媒体/备份卷名和生产网络名，版本目录不能决定生产卷身份。
- Backend entrypoint：支持升级期间 `SKIP_MIGRATE=true`，迁移只由升级编排脚本在目标镜像中显式执行。

### 3. 升级状态机

正常状态：

```text
INIT → PREFLIGHT_PASSED → MAINTENANCE_ENABLED → BACKUP_CREATED
→ BACKUP_VERIFIED → RUNTIME_SNAPSHOT_RECORDED → WRITE_SERVICES_STOPPED
→ TARGET_IMAGE_READY → MIGRATION_PREFLIGHT_PASSED → MIGRATED
→ TARGET_HEALTHY → SMOKE_TEST_PASSED → COMMITTED → MAINTENANCE_DISABLED
```

状态文件使用临时文件写入后原子 `mv` 替换，记录升级批次、源/目标版本、镜像、卷、阶段、时间、命令结果和失败信息。动作成功后才允许写入下一状态，不允许跳过状态。

任何正常阶段失败都进入：

```text
RECOVERY_STARTED → TARGET_SERVICES_STOPPED → SOURCE_RUNTIME_RESTORED
→ DATABASE_RESTORED → MEDIA_RESTORED → RESTORED_STATE_VERIFIED
→ SOURCE_HEALTHY → RECOVERY_COMMITTED
```

恢复任一步失败进入 `SAFE_STOPPED`：业务容器保持停止，备份、卷、旧镜像和日志全部保留，不自动重试、不自动启动业务，退出码非零并输出人工恢复入口。

### 4. 维护与备份流程

第一阶段采用离线维护模式：创建维护标记，通过入口返回维护页面，停止 Backend、Worker、Beat 和前端业务容器，保留基础容器供备份、恢复和诊断。若无法可靠阻断业务写入，必须停止升级并恢复源版本。

备份顺序：

1. 获取升级锁并检查当前状态；
2. 创建维护标记；
3. 停止业务写入服务；
4. 等待数据库连接达到安全状态；
5. 导出数据库；
6. 打包媒体；
7. 生成和校验 checksum；
8. 恢复数据库到临时库验证；
9. 检查媒体包路径、结构和可读性；
10. 写入 `BACKUP_VERIFIED`。

备份失败时不开始升级：清理维护标记、恢复源服务、执行健康检查，同时保留失败目录用于诊断。

### 5. 迁移与目标版本切换

目标 Backend 使用 `SKIP_MIGRATE=true` 启动。迁移预检必须运行在目标镜像中，并使用 Django 真实 migration graph 枚举所有 app，识别 pending migration 和 destructive migration。破坏性迁移默认直接阻断并要求人工处理。预检通过后才执行显式 `migrate`，所有非零退出立即进入恢复流程。

升级成功必须同时满足：离线包校验、维护模式、数据库和媒体备份、临时库恢复验证、目标镜像加载、迁移预检、迁移、数据完整性检查、所有服务健康、关键冒烟测试和升级记录写入。

### 6. 恢复与安全停机

恢复顺序：

1. 停止目标 Backend、Worker、Beat 和前端；
2. 确认没有业务连接数据库；
3. 切回源镜像；
4. 重建或安全清理目标数据库后恢复 SQL；
5. 数据库成功后恢复媒体到临时目录并原子切换；
6. 校验迁移版本、关键表、媒体路径和关键文件；
7. 启动源版本并执行健康检查和关键冒烟测试。

数据库恢复必须使用 `ON_ERROR_STOP=1`、单事务或等效的失败即停机制，不能出现部分恢复仍报告成功。媒体恢复须检查 tar 路径遍历和权限。数据库恢复失败时不继续恢复媒体并不启动服务；媒体恢复失败时同样进入 `SAFE_STOPPED`。

`SAFE_STOPPED` 输出升级批次、源/目标版本、失败阶段、失败原因、备份目录、状态文件、镜像信息和人工恢复命令，并明确未自动启动服务、删除卷、删除备份或重试恢复。

### 7. 危险操作与数据卷

固定 Compose 项目名、数据库卷、媒体卷和备份卷。标准离线包可从任意目录执行但始终使用同一生产卷。`clean` 默认禁用或改为显式危险命令，要求已验证外部备份、明确确认短语和二次提示，不能删除与生产数据共存的备份。

## 实施步骤

- [ ] 梳理并统一标准离线包的脚本、Compose、环境文件和路径布局
- [ ] 固定 Compose 项目名、生产数据卷和外部备份目录
- [ ] 实现升级锁、维护标记和原子状态文件状态机
- [ ] 重构数据库与媒体成组备份、checksum、metadata 和临时恢复验证
- [ ] 修复 Django 迁移枚举、破坏性迁移检测和恢复命令失败处理
- [ ] 禁止 Backend entrypoint 在升级流程中自动迁移
- [ ] 实现目标镜像预检、显式迁移、健康检查和冒烟成功门禁
- [ ] 实现真实源镜像切换、数据库恢复、媒体恢复和 `SAFE_STOPPED`
- [ ] 修复离线包 `deploy.sh`、`upgrade.sh`、`rollback.sh` 入口一致性
- [ ] 编写 Shell、Python、Docker 集成和端到端升级恢复测试
- [ ] 按真实离线包流程完成正常升级和故障恢复验收
- [ ] 更新技术手册、用户手册和覆盖矩阵
- [ ] 运行代码审查、安全审查和完整验证

## 风险评估与依赖

### 风险

- 升级期间需要停机，备份和媒体复制时间会影响维护窗口；
- 原地数据库恢复需要可靠断开业务连接，否则可能发生并发写入；
- 大数据库备份若非真正流式可能造成 Backend OOM；
- PostgreSQL 版本、权限和扩展差异可能导致恢复失败；
- 媒体恢复与数据库恢复必须使用同一批次，否则附件记录和文件可能不一致；
- 旧版本镜像必须在本地保留，不能只保留目标离线包；
- 迁移预检和实际迁移必须使用同一目标镜像及同一配置；
- 断电或脚本中断后必须依据状态文件安全续接或进入人工恢复，而不能猜测当前状态。

### 依赖

- Docker Compose 支持固定项目名和显式卷名；
- PostgreSQL 客户端支持 `ON_ERROR_STOP` 和可靠事务恢复；
- 生产部署主机具有外部备份目录及足够磁盘空间；
- 目标离线包包含源镜像切换所需的镜像或源版本可在本地获取；
- 测试环境可以构建源版本和目标版本镜像，并运行临时 PostgreSQL 数据库；
- 维护入口能够可靠阻断所有业务请求和异步写入。

## 测试与验收标准

### 测试层级

- Shell 单元测试：状态转换、批次目录、校验、危险操作、数据卷和入口门禁；
- Django 单元/集成测试：备份、恢复、迁移枚举、破坏性迁移、失败即停、路径安全；
- Docker 集成测试：正常升级、迁移/健康/备份/校验失败、数据库与媒体恢复、真实镜像回切、目录变化复用卷、断电恢复和安全停机；
- 端到端测试：真实离线包部署、写入用户/权限/业务数据和媒体、升级成功核对、注入失败并验证原数据恢复。

### 验收门槛

- 数据库和媒体均属于同一 `upgrade_id`，并有可验证 checksum；
- 数据库备份已恢复到临时库；
- 新离线包目录不会创建空生产卷；
- 业务写入停止后才备份；
- 目标容器不会自动迁移；
- 迁移预检运行在目标镜像；
- 任一步失败都非零且不能误报升级成功；
- 能真实切回源镜像并恢复数据库和媒体；
- 恢复失败进入 `SAFE_STOPPED`，不自动启动业务；
- `clean` 无备份门禁和明确确认时不能删除卷；
- 代码审查、安全审查、测试和覆盖率门槛均通过。
