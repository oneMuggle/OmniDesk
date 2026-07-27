# Task 9 Report: 更新部署文档和用户操作手册

## 修改文件清单

| 文件 | 修改内容 |
|------|----------|
| `docs/technical/02-deployment-guide.md` | Phase 7 升级/回滚流程重写(状态机保护 + 实际 bundle 命令路径);文件位置参考新增 bundle 布局图 |
| `docs/technical/23-offline-deployment.md` | 新增 §4.1-§4.12 完整数据安全保护章节(状态机、upgrade_id、固定卷名、shadow DB 验证、迁移预检、SAFE_STOPPED、恢复流程、clean、日志);§5 环境变量表补充 identity 字段 |
| `docs/technical/30-release-channels.md` | 新增"渠道升级数据安全"章节(固定身份字段、状态机、渠道校验);链接到 23 详细操作 |
| `docs/user-manual/12-deployment-channels.md` | 完整重写:升级前置条件(磁盘空间/停机窗口/完整性校验/SAFE_STOPPED 检查);首次部署/升级/回滚操作;SAFE_STOPPED 处理流程;禁止操作清单;clean 危险警告;FAQ 扩展 |
| `docs/technical/README.md` | 02/23/30 章节简介更新,反映数据安全保护 |
| `docs/user-manual/README.md` | 12 章节简介更新,反映 SAFE_STOPPED 处理和失败恢复 |

## 文档一致性检查结果

### 1. 禁止引用检查(通过)

```bash
$ grep -RIn 'deploy\.sh rollback' docs/technical docs/user-manual
PASS: 无 deploy.sh rollback 引用

$ grep -RIn 'deploy\.sh' docs/technical docs/user-manual | grep -iE "rollback|clean"
PASS: deploy.sh 不涉及 rollback/clean
```

### 2. `scripts/upgrade.sh` 引用(合法)

`scripts/upgrade.sh` 在 bundle 中**确实存在**(`package_offline_bundle.sh:476` 将其复制到 `scripts/`)。所有引用均指向 bundle 内路径,正确。

### 3. Bundle 命令路径与实际一致

| 文档命令 | 实际脚本 | 状态 |
|----------|----------|------|
| `./scripts/verify.sh` | `package_offline_bundle.sh:470` 复制 | ✅ |
| `./scripts/deploy.sh start` | `package_offline_bundle.sh:194` 内联生成 | ✅ |
| `./scripts/deploy_offline.sh upgrade` | `package_offline_bundle.sh:476` 复制 | ✅ |
| `./scripts/deploy_offline.sh rollback` | 同上 | ✅ |
| `./scripts/deploy_offline.sh clean` | 同上 | ✅ |
| `./scripts/upgrade.sh` | 同上 | ✅ |
| `./scripts/rollback.sh` | 同上 | ✅ |
| `./scripts/upgrade_state.sh` | 同上 | ✅ |
| `./scripts/smoke_tests.sh` | `package_offline_bundle.sh:502` 复制 | ✅ |

### 4. 固定身份字段(与代码一致)

| 字段 | 文档默认值 | `.env.production.example` 实际值 | 一致? |
|------|-----------|----------------------------------|------|
| `COMPOSE_PROJECT_NAME` | `omnidesk-${CHANNEL:-rc}` | `omnidesk-${CHANNEL:-rc}` | ✅ |
| `OMNIDESK_POSTGRES_VOLUME` | `omnidesk-${CHANNEL:-rc}-postgres-data` | `omnidesk-${CHANNEL:-rc}-postgres-data` | ✅ |
| `OMNIDESK_MEDIA_VOLUME` | `omnidesk-${CHANNEL:-rc}-media-data` | `omnidesk-${CHANNEL:-rc}-media-data` | ✅ |
| `OMNIDESK_BACKUP_ROOT` | `/opt/omnidesk/backups` | `/opt/omnidesk/backups` | ✅ |
| `OMNIDESK_RUNTIME_ROOT` | `/opt/omnidesk/runtime` | `/opt/omnidesk/runtime` | ✅ |

### 5. 状态机转移表(与 `upgrade_state.sh:44` 一致)

```
INIT → PREFLIGHT_PASSED → MAINTENANCE_ENABLED → BACKUP_CREATED → BACKUP_VERIFIED
→ RUNTIME_SNAPSHOT_RECORDED → WRITE_SERVICES_STOPPED → TARGET_IMAGE_READY
→ MIGRATION_PREFLIGHT_PASSED → MIGRATED → TARGET_HEALTHY → SMOKE_TEST_PASSED
→ COMMITTED → MAINTENANCE_DISABLED
```

SAFE_STOPPED 可由任何状态转入(`upgrade_state.sh:116-118`)。

### 6. state.json 字段(与 `upgrade_state.sh:48-108` 一致)

`upgrade_id`, `source_version`, `target_version`, `channel`, `state`, `backup_dir`, `source_image_tag`, `target_image_tag`, `compose_project_name`, `updated_at`(强制字段)。SAFE_STOPPED 追加 `reason`, `stop_failures`。

## Concerns

### Concern 1: `deploy_offline.sh clean` 6 门禁未实现(文档准确反映现状)

Brief 要求文档说明 `deploy_offline.sh clean` 6 门禁(无 active upgrade、batch 存在、metadata restore_verified=true、checksum 校验通过、备份位于外部 root、确认参数等于 "DELETE OMNIDESK DATA <channel>")。

**实际代码**:`deploy_offline.sh` 第 290-295 行 `clean)` 仅执行 `compose down -v`,无 6 门禁。

**文档处理**:§4.11 / 用户手册"clean 命令(危险)"章节准确描述当前实现(`compose down -v`),**未虚假声称** 6 门禁已实现。这是 brief 中描述但尚未落地的功能。

### Concern 2: 恢复顺序文档化为"trap + SAFE_STOPPED + 人工 rollback"

Brief 要求文档说明"恢复顺序(停止服务 → 切回源镜像 → 恢复 DB → 恢复 media → 校验 → 启动源版本)"。

**实际代码**:`upgrade.sh` 的 `on_upgrade_failure` trap 仅做 `enter_safe_stop` + 释放锁,没有自动切回源镜像/恢复 DB/media/校验/启动源版本的完整序列。集成测试 `test_upgrade_integration.sh` 也仅验证 SAFE_STOPPED 状态记录,不验证完整恢复顺序。

**文档处理**:§4.10 / 用户手册"人工恢复步骤"描述为"排查 → rollback(手动) → 清理 SAFE_STOPPED → 重试"。未虚假声称自动恢复。

### Concern 3: 备份验证(shadow DB)是冒烟阶段而非升级路径

Brief 要求文档说明"备份验证(临时库恢复)"。

**实际代码**:shadow DB 验证在 `smoke_tests.sh` 阶段 11,升级脚本本身不主动触发 shadow DB 验证。`BACKUP_VERIFIED` 状态转移在 `upgrade.sh` 中也未显式写入。

**文档处理**:§4.5 准确描述为"`smoke_tests.sh` 阶段 11 端到端验证备份可恢复性"。未虚假声称升级脚本主动调用。

## Commit

- **SHA**: `e0bb29b9`
- **Branch**: `worktree-agent-adcfa5575459e2677`
- **Stats**: 7 files changed, 460 insertions(+), 38 deletions(-)
