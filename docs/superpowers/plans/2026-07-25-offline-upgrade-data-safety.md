# OmniDesk 离线升级数据安全保护实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 OmniDesk 离线包建立“升级前可验证成组备份、失败自动恢复、恢复失败保守停机”的数据安全闭环。

**Architecture:** 以 `upgrade_id` 为边界组织数据库、媒体、metadata、checksum 和状态文件；由 `upgrade.sh` 驱动显式状态机，`backup.sh` 负责成组备份与临时恢复验证，`rollback.sh` 负责源镜像切换和数据恢复。Compose 固定项目名与生产卷，Backend entrypoint 在升级流程中禁止自动迁移；所有失败进入恢复流程，恢复任一步失败进入 `SAFE_STOPPED`。

**Tech Stack:** Bash（Docker Compose 编排与离线包脚本）、Docker Compose、PostgreSQL `pg_dump`/`psql`、Django 4.2 management commands、pytest、Shell 测试、Docker 集成测试。

## Global Constraints

- 所有功能与文档使用中文；代码标识符和命令保留技术惯例。
- 升级必须停机并停止所有业务写入后才允许备份和迁移。
- 数据库和媒体必须归属于同一 `upgrade_id`，并位于不会被 `docker compose down -v` 删除的外部持久目录。
- 数据库恢复必须失败即停，启用 `ON_ERROR_STOP=1`、单事务或等效机制，禁止部分恢复后报告成功。
- 目标 Backend 使用 `SKIP_MIGRATE=true`，迁移只能由升级脚本在目标镜像中显式执行。
- 恢复任一步失败必须进入 `SAFE_STOPPED`，不自动启动业务、不删除卷、不删除备份、不自动重试。
- 生产卷、Compose 项目名、旧镜像和备份目录必须记录并可重复定位。
- Python 测试只能使用项目专用 `omni_desk` conda 环境；不得污染 base 或系统 Python。
- 每个任务先写失败测试（RED），再实现最小改动（GREEN），再运行相关测试并提交独立 commit。
- 测试截图统一放在 `test-artifacts/screenshots/`，验证完成后删除临时截图。
- 完成代码后必须运行 code-reviewer 与 security-reviewer；覆盖率目标至少 80%。

---

## 文件与模块地图

| 文件 | 职责 | 本计划中的边界 |
|---|---|---|
| `deployment/docker/package_offline_bundle.sh` | 生成标准离线包和包内 `deploy.sh` | 补齐升级/回滚/备份/验证脚本，统一 bundle 路径 |
| `deployment/docker/deploy_offline.sh` | 源码树部署入口 | 复用统一环境、卷和危险操作门禁 |
| `deployment/docker/upgrade.sh` | 升级状态机和成功/失败编排 | 成为唯一升级事务入口 |
| `deployment/docker/rollback.sh` | 批次恢复和源镜像切换 | 只能恢复已验证批次，失败进入安全停机 |
| `deployment/docker/backup.sh` | 宿主侧备份入口 | 统一外部备份目录和批次元数据 |
| `deployment/docker/verify.sh` | 离线包完整性检查 | 检查升级/回滚脚本、manifest、checksum |
| `deployment/docker/docker-compose.offline.yml` | 离线服务、卷、健康检查 | 固定项目/卷名，支持 `SKIP_MIGRATE` |
| `deployment/docker/.env.production.example` | 生产环境模板 | 增加项目名、卷名、外部备份和运行时目录 |
| `omni_desk_backend/entrypoint.sh` | 后端容器启动 | `SKIP_MIGRATE=true` 时禁止自动迁移 |
| `.../backup_db.py` | DB/媒体备份命令 | 流式导出、批次 metadata、checksum、配对保留 |
| `.../restore_db.py` | 数据库恢复命令 | 失败即停、目标库安全重建/覆盖、恢复校验 |
| `.../check_migrations.py` | 迁移风险检查 | 使用 Django migration graph，检测 destructive 变更 |
| `deployment/docker/tests/` | Shell 门禁测试 | 状态、路径、卷、危险操作和脚本入口 |
| `omni_desk_backend/**/tests/` | Python 测试 | 备份、恢复和迁移检查单元/集成测试 |
| `docs/technical/*`、`docs/user-manual/*` | 部署与用户文档 | 同步真实入口、恢复流程和限制 |

---

### Task 1: 固定离线部署身份与包内脚本布局

**Files:**
- Modify: `deployment/docker/docker-compose.offline.yml`
- Modify: `deployment/docker/.env.production.example`
- Modify: `deployment/docker/package_offline_bundle.sh`
- Modify: `deployment/docker/verify.sh`
- Modify: `deployment/docker/deploy_offline.sh`
- Create: `deployment/docker/tests/test_offline_bundle_layout.sh`

**Interfaces:**
- Produces environment variables `COMPOSE_PROJECT_NAME`, `OMNIDESK_POSTGRES_VOLUME`, `OMNIDESK_MEDIA_VOLUME`, `OMNIDESK_BACKUP_ROOT`, `OMNIDESK_RUNTIME_ROOT`。
- Produces bundle layout `scripts/{deploy.sh,upgrade.sh,rollback.sh,backup.sh,verify.sh}`, `compose/docker-compose.offline.yml`, `compose/.env.production`。
- `verify.sh` receives bundle root and exits non-zero when any required script, manifest, checksum or compose file is missing。

- [ ] **Step 1: 写失败测试，锁定跨目录复用卷和脚本完整性**

```bash
#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT/test_helpers.sh"

bundle="$TEST_TMPDIR/bundle"
mkdir -p "$bundle/scripts" "$bundle/compose"
cp "$ROOT/../upgrade.sh" "$bundle/scripts/upgrade.sh"
cp "$ROOT/../rollback.sh" "$bundle/scripts/rollback.sh"
cp "$ROOT/../backup.sh" "$bundle/scripts/backup.sh"
cp "$ROOT/../verify.sh" "$bundle/scripts/verify.sh"
cp "$ROOT/../docker-compose.offline.yml" "$bundle/compose/docker-compose.offline.yml"

assert_file_exists "$bundle/scripts/upgrade.sh"
assert_file_exists "$bundle/scripts/rollback.sh"
assert_contains "$bundle/compose/docker-compose.offline.yml" 'COMPOSE_PROJECT_NAME'
assert_contains "$bundle/compose/docker-compose.offline.yml" 'OMNIDESK_POSTGRES_VOLUME'
assert_contains "$bundle/compose/docker-compose.offline.yml" 'OMNIDESK_MEDIA_VOLUME'
```

- [ ] **Step 2: 运行测试确认当前实现失败**

运行：`bash deployment/docker/tests/test_offline_bundle_layout.sh`

预期：FAIL，当前标准包生成器没有同时复制 `upgrade.sh`，Compose 也没有固定生产项目/卷身份。

- [ ] **Step 3: 实现统一 bundle 布局和固定卷名**

在环境模板中加入：

```dotenv
COMPOSE_PROJECT_NAME=omnidesk-${CHANNEL:-rc}
OMNIDESK_POSTGRES_VOLUME=omnidesk-${CHANNEL:-rc}-postgres-data
OMNIDESK_MEDIA_VOLUME=omnidesk-${CHANNEL:-rc}-media-data
OMNIDESK_BACKUP_ROOT=/opt/omnidesk/backups
OMNIDESK_RUNTIME_ROOT=/opt/omnidesk/runtime
```

Compose 使用显式 external/固定 name：

```yaml
name: ${COMPOSE_PROJECT_NAME}
volumes:
  postgres_data:
    name: ${OMNIDESK_POSTGRES_VOLUME}
  media_volume:
    name: ${OMNIDESK_MEDIA_VOLUME}
```

修改 `package_offline_bundle.sh`，将 `upgrade.sh`、`rollback.sh`、`backup.sh`、`verify.sh`、`deploy_offline.sh` 和所需 smoke 测试复制到 bundle 的 `scripts/`，并让脚本通过 `SCRIPT_DIR/../compose` 定位 Compose 文件和环境文件。修改 `verify.sh` 检查这些文件及固定身份字段。

- [ ] **Step 4: 运行测试确认通过**

运行：`bash deployment/docker/tests/test_offline_bundle_layout.sh`

预期：PASS；在两个不同临时目录以同一 `.env.production` 解析 Compose 配置时，项目名和卷名一致。

- [ ] **Step 5: 提交**

```bash
git add deployment/docker/docker-compose.offline.yml deployment/docker/.env.production.example deployment/docker/package_offline_bundle.sh deployment/docker/verify.sh deployment/docker/deploy_offline.sh deployment/docker/tests/test_offline_bundle_layout.sh
git commit -m "fix: 固定离线部署项目与数据卷身份"
```

---

### Task 2: 实现升级锁、维护标记和原子状态文件

**Files:**
- Modify: `deployment/docker/upgrade.sh`
- Modify: `deployment/docker/rollback.sh`
- Modify: `deployment/docker/deploy_offline.sh`
- Create: `deployment/docker/tests/test_upgrade_state.sh`

**Interfaces:**
- `write_state <state> [key=value...]`：在 `$OMNIDESK_RUNTIME_ROOT/upgrades/<upgrade_id>/state.json.tmp` 写入后原子替换 `state.json`。
- `transition_state <expected> <next>`：只允许定义的状态边迁移，否则返回非零。
- `enter_safe_stop <reason>`：写入 `SAFE_STOPPED`，停止业务服务并输出恢复信息。
- 状态 JSON 必须至少包含 `upgrade_id`、`source_version`、`target_version`、`channel`、`state`、`backup_dir`、`source_image_tag`、`target_image_tag`、`compose_project_name`、`updated_at`。

- [ ] **Step 1: 写失败测试**

```bash
#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/../test_helpers.sh"

export OMNIDESK_RUNTIME_ROOT="$TEST_TMPDIR/runtime"
export UPGRADE_ID='20260725T143000Z-v0.7.0-rc.1-to-v0.7.0-rc.2'
source "$(dirname "$0")/../upgrade_state.sh"

write_state INIT source_version=0.7.0-rc.1 target_version=0.7.0-rc.2
assert_json_field "$OMNIDESK_RUNTIME_ROOT/upgrades/$UPGRADE_ID/state.json" state INIT
transition_state INIT PREFLIGHT_PASSED
assert_json_field "$OMNIDESK_RUNTIME_ROOT/upgrades/$UPGRADE_ID/state.json" state PREFLIGHT_PASSED
! transition_state INIT BACKUP_CREATED
assert_file_not_contains "$OMNIDESK_RUNTIME_ROOT/upgrades/$UPGRADE_ID/state.json" 'BACKUP_CREATED'
```

- [ ] **Step 2: 运行测试确认失败**

运行：`bash deployment/docker/tests/test_upgrade_state.sh`

预期：FAIL，当前没有可复用的严格状态转换和原子状态文件模块。

- [ ] **Step 3: 实现状态模块**

创建 `deployment/docker/upgrade_state.sh`，使用 `jq`（无 jq 时调用 Python 标准库 fallback）生成 JSON；通过 `mktemp` 写入同目录临时文件并 `mv -f`。状态转换表固定为：

```bash
STATE_EDGES='INIT:PREFLIGHT_PASSED PREFLIGHT_PASSED:MAINTENANCE_ENABLED MAINTENANCE_ENABLED:BACKUP_CREATED BACKUP_CREATED:BACKUP_VERIFIED BACKUP_VERIFIED:RUNTIME_SNAPSHOT_RECORDED RUNTIME_SNAPSHOT_RECORDED:WRITE_SERVICES_STOPPED WRITE_SERVICES_STOPPED:TARGET_IMAGE_READY TARGET_IMAGE_READY:MIGRATION_PREFLIGHT_PASSED MIGRATION_PREFLIGHT_PASSED:MIGRATED MIGRATED:TARGET_HEALTHY TARGET_HEALTHY:SMOKE_TEST_PASSED SMOKE_TEST_PASSED:COMMITTED COMMITTED:MAINTENANCE_DISABLED'
```

同时实现升级锁 `flock` 或 `mkdir` 原子锁；检测已有 `SAFE_STOPPED` 或运行中升级时拒绝新升级。`enter_safe_stop` 必须先尝试停止 Backend、Worker、Beat、frontend，再写入状态，失败时仍保留状态和非零退出。

- [ ] **Step 4: 运行测试确认通过**

运行：`bash deployment/docker/tests/test_upgrade_state.sh`

预期：PASS；检查 `state.json` 不出现半写入文件，非法状态边迁移被拒绝。

- [ ] **Step 5: 提交**

```bash
git add deployment/docker/upgrade_state.sh deployment/docker/upgrade.sh deployment/docker/rollback.sh deployment/docker/deploy_offline.sh deployment/docker/tests/test_upgrade_state.sh
git commit -m "feat: 增加离线升级状态与安全停机机制"
```

---

### Task 3: 重构数据库与媒体成组备份

**Files:**
- Modify: `omni_desk_backend/core/management/commands/backup_db.py`
- Modify: `deployment/docker/backup.sh`
- Create: `omni_desk_backend/core/tests/test_backup_db.py`
- Create: `deployment/docker/tests/test_backup_batch.sh`

**Interfaces:**
- `backup_db --batch-id <upgrade_id> --output-dir <dir> --verify`：创建 `metadata.json`、`database.sql.gz`、`media.tar.gz` 和对应 `.sha256`，成功时返回 0。
- `backup_db` 使用 `subprocess.Popen` 流式读取 `pg_dump` stdout，不允许 `capture_output=True` 保存全库。
- metadata 字段：`upgrade_id`、`channel`、`source_version`、`database_file`、`media_file`、`database_sha256`、`media_sha256`、`database_size`、`media_size`、`restore_verified`、`created_at`。
- 失败时不写 `restore_verified=true`，并返回非零。

- [ ] **Step 1: 写失败 Python 测试**

```python
from pathlib import Path
from unittest.mock import patch

from django.core.management import call_command


def test_backup_streams_pg_dump_and_writes_paired_metadata(tmp_path):
    output_dir = tmp_path / "backups" / "rc" / "20260725T143000Z-test"
    output_dir.mkdir(parents=True)
    dump_bytes = b"CREATE TABLE sample(id integer);\n"

    class FakeProcess:
        returncode = 0
        stdout = iter([dump_bytes])
        stderr = iter([])

        def wait(self):
            return self.returncode

    with patch("subprocess.Popen", return_value=FakeProcess()) as popen:
        call_command(
            "backup_db",
            batch_id="20260725T143000Z-test",
            output_dir=str(output_dir),
            skip_media=True,
        )

    popen.assert_called_once()
    assert "capture_output" not in popen.call_args.kwargs
    assert (output_dir / "database.sql.gz").exists()
    assert (output_dir / "database.sql.gz.sha256").exists()
    assert (output_dir / "metadata.json").exists()
```

- [ ] **Step 2: 运行测试确认失败**

运行：`conda run -n omni_desk pytest --ds=omni_desk_backend.settings.test omni_desk_backend/core/tests/test_backup_db.py::test_backup_streams_pg_dump_and_writes_paired_metadata -v`

预期：FAIL，现有命令没有批次参数、metadata 和流式 Popen 接口。

- [ ] **Step 3: 实现最小备份批次**

修改 management command 参数和输出流程：数据库通过 `Popen([...], stdout=PIPE, stderr=PIPE)` 接入 `gzip.open(..., 'wb')`；检测进程返回码，stderr 写日志；媒体使用确定的 `tarfile` 或容器侧 tar 输出到临时文件后原子命名。所有文件完成后计算 SHA-256 和大小，metadata 使用 UTC ISO-8601 `YYYY-MM-DDTHH:MM:SSZ`。数据库和媒体必须同时成功才允许写 `restore_verified`。

修改 `backup.sh`：解析 `.env.production`，将 output dir 设置为 `${OMNIDESK_BACKUP_ROOT}/${CHANNEL}/${UPGRADE_ID}`，不再创建或读取与容器 named volume 同名的宿主临时目录；执行完成后验证 metadata、两个 checksum 和文件大小。

- [ ] **Step 4: 增加媒体包结构与备份配对测试并运行**

运行：`bash deployment/docker/tests/test_backup_batch.sh && conda run -n omni_desk pytest --ds=omni_desk_backend.settings.test omni_desk_backend/core/tests/test_backup_db.py -v`

预期：PASS；缺失任一 DB/media 文件、checksum 不匹配或 metadata 不完整时返回非零。

- [ ] **Step 5: 提交**

```bash
git add omni_desk_backend/core/management/commands/backup_db.py deployment/docker/backup.sh omni_desk_backend/core/tests/test_backup_db.py deployment/docker/tests/test_backup_batch.sh
git commit -m "feat: 建立离线升级成组备份与校验"
```

---

### Task 4: 增加备份恢复验证与安全恢复命令

**Files:**
- Modify: `omni_desk_backend/core/management/commands/restore_db.py`
- Modify: `deployment/docker/backup.sh`
- Modify: `deployment/docker/rollback.sh`
- Create: `omni_desk_backend/core/tests/test_restore_db.py`
- Create: `deployment/docker/tests/test_restore_safety.sh`

**Interfaces:**
- `restore_db --backup-file <path> --database <name> --recreate --verify`：停止前置业务后，在指定数据库上以失败即停方式恢复；失败返回非零且不输出成功消息。
- `verify_backup_batch <batch_dir>`：检查 DB/media 文件、SHA-256、metadata 的 `upgrade_id` 和 `restore_verified`。
- `restore_media_batch <batch_dir> <media_root>`：恢复至临时目录，检查 tar 成员不得绝对路径或包含 `..`，成功后原子切换。

- [ ] **Step 1: 写失败测试**

```python
from pathlib import Path
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError


def test_restore_stops_on_psql_error(tmp_path):
    dump = tmp_path / "database.sql.gz"
    dump.write_bytes(b"not-a-valid-gzip")
    with patch("subprocess.run", side_effect=RuntimeError("psql failed")) as run:
        with pytest.raises(CommandError):
            call_command("restore_db", backup_file=str(dump), database="testdb")
    run.assert_not_called() or True
```

```bash
#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/../test_helpers.sh"

batch="$TEST_TMPDIR/batch"
mkdir -p "$batch"
printf 'x' > "$batch/media.tar.gz"
printf 'x  media.tar.gz\n' > "$batch/media.tar.gz.sha256"
! verify_backup_batch "$batch"
```

- [ ] **Step 2: 运行测试确认失败**

运行：`conda run -n omni_desk pytest --ds=omni_desk_backend.settings.test omni_desk_backend/core/tests/test_restore_db.py -v` 和 `bash deployment/docker/tests/test_restore_safety.sh`

预期：FAIL，现有恢复命令没有可靠失败即停、批次验证和媒体路径安全检查。

- [ ] **Step 3: 实现安全恢复**

`restore_db.py` 使用 `subprocess.Popen` 或 `subprocess.run(check=True)`，通过 `gunzip -c ... | psql -v ON_ERROR_STOP=1 --single-transaction`，任何解压、psql 或事务错误都抛出 `CommandError`。生产恢复前由 shell 确认所有业务容器已停止；数据库重建逻辑必须显式指定目标库，断开连接后删除/创建，禁止拼接未经验证的数据库名。

`rollback.sh` 实现批次验证、停止业务服务、读取 metadata 中的源镜像、恢复 DB，再恢复媒体临时目录；媒体 tar 成员使用 `tar --extract --directory` 前检查每个路径，拒绝绝对路径和 `..`。恢复成功后再切换媒体目录并启动源版本；任一步失败调用 `enter_safe_stop`。

- [ ] **Step 4: 运行测试确认通过**

运行：`conda run -n omni_desk pytest --ds=omni_desk_backend.settings.test omni_desk_backend/core/tests/test_restore_db.py -v` 和 `bash deployment/docker/tests/test_restore_safety.sh`

预期：PASS；恢复失败不报告成功，非法 checksum、metadata 或 tar 路径均被拒绝。

- [ ] **Step 5: 提交**

```bash
git add omni_desk_backend/core/management/commands/restore_db.py deployment/docker/backup.sh deployment/docker/rollback.sh omni_desk_backend/core/tests/test_restore_db.py deployment/docker/tests/test_restore_safety.sh
git commit -m "fix: 让离线恢复失败即停并校验媒体安全"
```

---

### Task 5: 修复迁移检查并禁止入口自动迁移

**Files:**
- Modify: `omni_desk_backend/core/management/commands/check_migrations.py`
- Modify: `omni_desk_backend/core/api.py`
- Modify: `omni_desk_backend/entrypoint.sh`
- Modify: `deployment/docker/docker-compose.offline.yml`
- Create: `omni_desk_backend/core/tests/test_check_migrations.py`

**Interfaces:**
- `check_migrations --plan-json --fail-on-destructive`：使用 `MigrationLoader(connection).graph` 和 `MigrationExecutor`，输出所有 app 的 pending migration，发现 destructive migration 时返回非零。
- `entrypoint.sh`：环境变量 `SKIP_MIGRATE=true` 时完全跳过 `python manage.py migrate`，仍执行必要的服务启动前检查。
- `get_migration_status()`：复用真实 migration graph，不访问不存在的 `app_config.migrations` 属性。

- [ ] **Step 1: 写失败测试**

```python
from unittest.mock import patch

from django.core.management import call_command


def test_check_migrations_loads_real_migration_graph(capsys):
    call_command("check_migrations", "--plan-json")
    output = capsys.readouterr().out
    assert '"apps"' in output
    assert "app_config.migrations" not in output


def test_entrypoint_skip_migrate_does_not_call_manage_migrate():
    with patch.dict("os.environ", {"SKIP_MIGRATE": "true"}):
        # 将入口脚本中的可执行迁移调用抽取为可测试函数后断言不执行。
        assert should_run_migrations() is False
```

- [ ] **Step 2: 运行测试确认失败**

运行：`conda run -n omni_desk pytest --ds=omni_desk_backend.settings.test omni_desk_backend/core/tests/test_check_migrations.py -v`

预期：FAIL，当前检查命令使用非标准属性，入口脚本默认自动迁移。

- [ ] **Step 3: 实现真实迁移图和显式跳过**

使用：

```python
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

executor = MigrationExecutor(connection)
plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
```

从 migration operation 类型识别 `DeleteModel`、`RemoveField`、`RemoveConstraint`、可能的数据丢失操作；`--fail-on-destructive` 返回 2。API 使用同一 helper 生成 applied/pending/destructive。entrypoint 将 migrate 包在 `if [ "${SKIP_MIGRATE:-false}" != "true" ]; then ... fi` 中；Compose backend/worker 升级路径传入 `SKIP_MIGRATE=true`。

- [ ] **Step 4: 运行测试确认通过**

运行：`conda run -n omni_desk pytest --ds=omni_desk_backend.settings.test omni_desk_backend/core/tests/test_check_migrations.py -v`

预期：PASS；目标镜像可输出完整 migration plan，`SKIP_MIGRATE=true` 时不会执行迁移。

- [ ] **Step 5: 提交**

```bash
git add omni_desk_backend/core/management/commands/check_migrations.py omni_desk_backend/core/api.py omni_desk_backend/entrypoint.sh deployment/docker/docker-compose.offline.yml omni_desk_backend/core/tests/test_check_migrations.py
git commit -m "fix: 使用真实迁移图并关闭升级时自动迁移"
```

---

### Task 6: 完成升级状态机、目标镜像切换和失败自动恢复

**Files:**
- Modify: `deployment/docker/upgrade.sh`
- Modify: `deployment/docker/rollback.sh`
- Modify: `deployment/docker/deploy_offline.sh`
- Modify: `deployment/docker/package_offline_bundle.sh`
- Create: `deployment/docker/tests/test_upgrade_failure_recovery.sh`

**Interfaces:**
- `upgrade.sh --bundle-dir <dir> --channel <channel> --yes`：执行完整升级，成功返回 0；任一步失败自动调用恢复。
- `rollback.sh --upgrade-id <id> [--yes]`：只恢复 `BACKUP_VERIFIED` 批次。
- `capture_runtime_snapshot()`：记录 source image、target image、Compose 项目名、卷名、当前版本和镜像加载结果。
- `run_upgrade()`：严格按 `PREFLIGHT_PASSED → MAINTENANCE_ENABLED → BACKUP_VERIFIED → ...` 状态推进。

- [ ] **Step 1: 写失败测试**

```bash
#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/../test_helpers.sh"

stub_compose_failure_on_health_check
stub_backup_verified_batch
run_script upgrade.sh --bundle-dir "$TEST_TMPDIR/bundle" --channel rc --yes && exit 1 || status=$?
[ "$status" -ne 0 ]
assert_json_field "$TEST_TMPDIR/runtime/upgrades/"*/state.json state RECOVERY_COMMITTED
assert_not_contains_stub_calls 'up -d' 'after_restore_failure'
```

- [ ] **Step 2: 运行测试确认失败**

运行：`bash deployment/docker/tests/test_upgrade_failure_recovery.sh`

预期：FAIL，当前升级脚本预检使用旧容器、入口会自动迁移，且没有完整恢复状态机。

- [ ] **Step 3: 实现正常与失败路径**

`upgrade.sh` 依次：

1. preflight 校验 bundle、版本、渠道、固定卷和磁盘空间；
2. 获取锁并写 `PREFLIGHT_PASSED`；
3. 创建维护标记，停止业务服务；
4. 调用 `backup.sh` 并验证批次；
5. 记录运行时快照和源镜像；
6. 加载目标镜像并以 `SKIP_MIGRATE=true` 启动基础服务；
7. 在目标 Backend 容器运行 `check_migrations --plan-json --fail-on-destructive`；
8. 预检成功后执行目标镜像中的 `migrate`；
9. 启动目标服务并执行健康、数据完整性和 smoke gate；
10. 原子写成功记录，解除维护模式。

所有命令使用 `set -Eeuo pipefail`、显式日志和返回码。错误 trap 只进入一次恢复流程：停止目标业务服务，调用 `rollback.sh --upgrade-id`；恢复成功才启动源版本并解除维护，恢复失败调用 `enter_safe_stop`。不得在失败时执行 `down -v`，不得删除备份或旧镜像。

- [ ] **Step 4: 运行测试确认通过**

运行：`bash deployment/docker/tests/test_upgrade_failure_recovery.sh`，再使用测试 Compose 执行正常升级和注入迁移失败两条路径。

预期：正常路径返回 0 且状态为 `COMMITTED`；注入失败路径返回非零并完成源镜像、DB、media 恢复；恢复失败状态为 `SAFE_STOPPED` 且业务服务保持停止。

- [ ] **Step 5: 提交**

```bash
git add deployment/docker/upgrade.sh deployment/docker/rollback.sh deployment/docker/deploy_offline.sh deployment/docker/package_offline_bundle.sh deployment/docker/tests/test_upgrade_failure_recovery.sh
git commit -m "feat: 完成离线升级失败自动恢复闭环"
```

---

### Task 7: 加固危险清理和验证门禁

**Files:**
- Modify: `deployment/docker/deploy_offline.sh`
- Modify: `deployment/docker/verify.sh`
- Modify: `deployment/docker/tests/test_offline_bundle_layout.sh`
- Create: `deployment/docker/tests/test_destructive_commands.sh`

**Interfaces:**
- `deploy_offline.sh clean --confirm-delete-data --backup-id <id>`：只有备份已通过验证、确认短语完全匹配且状态无运行中升级时才允许删除卷。
- `verify.sh`：必须验证 bundle manifest、全文件 checksum、脚本完整性、Compose 固定项目/卷字段和 metadata schema。

- [ ] **Step 1: 写失败测试**

```bash
#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/../test_helpers.sh"

! bash deployment/docker/deploy_offline.sh clean
! bash deployment/docker/deploy_offline.sh clean --confirm-delete-data WRONG --backup-id missing
assert_no_stub_call 'down -v'
```

- [ ] **Step 2: 运行测试确认失败**

运行：`bash deployment/docker/tests/test_destructive_commands.sh`

预期：FAIL，当前 `clean` 可直接执行 `docker compose down -v`。

- [ ] **Step 3: 实现删除门禁**

删除前按顺序检查：无 active upgrade、指定 batch 存在、metadata `restore_verified=true`、DB/media checksum 通过、备份目录位于外部 root、确认参数等于 `DELETE OMNIDESK DATA <channel>`。任一失败返回非零且不调用 `down -v`。删除成功后只删除生产数据卷，不删除外部备份 root，并写入审计日志。

- [ ] **Step 4: 运行测试确认通过**

运行：`bash deployment/docker/tests/test_destructive_commands.sh` 和 `bash deployment/docker/tests/test_offline_bundle_layout.sh`

预期：PASS；所有未满足门禁的危险命令都不执行。

- [ ] **Step 5: 提交**

```bash
git add deployment/docker/deploy_offline.sh deployment/docker/verify.sh deployment/docker/tests/test_offline_bundle_layout.sh deployment/docker/tests/test_destructive_commands.sh
git commit -m "fix: 为离线数据清理增加备份与确认门禁"
```

---

### Task 8: 补齐 Docker 升级/恢复集成与端到端验收

**Files:**
- Create: `deployment/docker/tests/test_upgrade_integration.sh`
- Modify: `deployment/docker/smoke_tests.sh`
- Modify: `.github/workflows/deploy-test.yml`
- Modify: `docs/technical/40-smoke-test-coverage.md`

**Interfaces:**
- Integration fixture builds/loads source and target test images, creates test data and media, invokes actual bundle scripts, and emits non-zero on any mismatch。
- `smoke_tests.sh` 接受显式 `COMPOSE_PROJECT_NAME`，不引用未定义变量，使用同一 batch backup path。

- [ ] **Step 1: 写集成场景矩阵**

```bash
SCENARIOS=(
  upgrade_success
  migration_failure_restores_source
  health_failure_restores_source
  backup_checksum_failure_blocks_upgrade
  media_restore_failure_enters_safe_stop
  bundle_directory_change_reuses_volumes
  interrupted_upgrade_enters_recovery
)
```

- [ ] **Step 2: 运行当前集成脚本确认缺口**

运行：`bash deployment/docker/tests/test_upgrade_integration.sh --scenario upgrade_success`

预期：当前环境因缺少真实升级闭环而 FAIL；记录 Docker、磁盘、版本和耗时，不吞掉失败。

- [ ] **Step 3: 实现可重复测试夹具**

脚本使用临时 Compose 项目名、显式临时卷、测试数据库和合成数据（用户、权限、核心业务记录、关联记录、媒体文件）。每个场景执行前后清理测试卷但不得清理生产卷；在正常场景验证记录、附件和 migration 状态；在失败场景验证源镜像、原始记录、原始媒体、状态文件和业务容器状态。

- [ ] **Step 4: 修复 smoke 测试环境变量和 CI 入口**

为 `smoke_tests.sh` 在启动时设置并校验 `COMPOSE_PROJECT_NAME`、`OMNIDESK_BACKUP_ROOT`；去除 `|| true` 对健康检查、镜像加载和冒烟失败的吞错。CI 在专用测试 job 中运行 Shell 单元、Django 测试和集成场景；生产凭证不得进入 fixture 或日志。

- [ ] **Step 5: 运行集成矩阵**

运行：`bash deployment/docker/tests/test_upgrade_integration.sh --all`

预期：所有场景 PASS；失败恢复场景只允许两种终态：完整恢复到源版本，或 `SAFE_STOPPED` 且业务容器停止。

- [ ] **Step 6: 提交**

```bash
git add deployment/docker/tests/test_upgrade_integration.sh deployment/docker/smoke_tests.sh .github/workflows/deploy-test.yml docs/technical/40-smoke-test-coverage.md
git commit -m "test: 覆盖离线升级与恢复集成场景"
```

---

### Task 9: 更新部署文档和用户操作手册

**Files:**
- Modify: `docs/technical/02-deployment-guide.md`
- Modify: `docs/technical/23-offline-deployment.md`
- Modify: `docs/technical/30-release-channels.md`
- Modify: `docs/user-manual/12-deployment-channels.md`
- Modify: `docs/technical/README.md`
- Modify: `docs/user-manual/README.md`

**Interfaces:**
- 文档必须只描述已实现入口；禁止继续描述不存在的 `deploy.sh rollback` 或未打包的 `upgrade.sh`。
- 用户手册必须明确停机窗口、升级前置条件、备份目录、失败状态、人工恢复入口和禁止操作。

- [ ] **Step 1: 写文档一致性检查**

```bash
! grep -RIn 'deploy\.sh rollback\|scripts/upgrade\.sh' docs/technical docs/user-manual
bash deployment/docker/verify.sh <synthetic-bundle>
```

预期：在脚本入口尚未统一前检查失败或发现旧文档引用。

- [ ] **Step 2: 更新技术文档**

加入：升级状态机、`upgrade_id` 目录结构、固定 Compose 项目/卷、备份验证、迁移预检、恢复顺序、`SAFE_STOPPED`、日志位置、数据卷保护和 `clean` 门禁。所有命令使用实际 bundle 路径，例如：

```bash
./scripts/verify.sh
./scripts/upgrade.sh --bundle-dir . --channel rc
./scripts/rollback.sh --upgrade-id 20260725T143000Z-v0.7.0-rc.1-to-v0.7.0-rc.2
```

- [ ] **Step 3: 更新用户手册**

用中文说明：升级前确认备份磁盘空间和停机窗口；升级期间不得手动启动业务容器；失败时不要删除卷或备份；看到 `SAFE_STOPPED` 时保存状态文件、批次目录和日志并联系管理员。

- [ ] **Step 4: 更新 README 章节表**

确保技术/用户手册 README 的章节编号、链接和一句话简介与实际文件一致，不新建重复章节。

- [ ] **Step 5: 运行一致性检查并提交**

运行：`grep -RIn 'deploy\\.sh rollback\\|scripts/upgrade\\.sh' docs/technical docs/user-manual || true`，并执行 Markdown 链接检查。

预期：所有命令和路径与 bundle 实现一致。

```bash
git add docs/technical docs/user-manual
git commit -m "docs: 更新离线升级数据安全操作说明"
```

---

### Task 10: 完成验证、代码审查和计划归档

**Files:**
- Modify: `docs/plans/2026-07-25_offline-upgrade-data-safety.md`
- Modify: `deployment/docker/CHANGELOG.md`
- Modify: `deployment/docker/VERSION`（仅按项目发布流程需要时）

- [ ] **Step 1: 在专用环境运行后端检查和测试**

```bash
conda run -n omni_desk python manage.py check --deploy
conda run -n omni_desk pytest --ds=omni_desk_backend.settings.test --cov=omni_desk_backend --cov-report=term-missing
```

预期：测试通过，覆盖率达到项目最低 80% 目标；失败时停止并交给 build-error-resolver 或 tdd-guide，不修改测试绕过失败。

- [ ] **Step 2: 运行前端和 Shell/集成验证**

```bash
cd omni_desk_frontend && npm test -- --runInBand
cd ..
bash deployment/docker/tests/test_offline_bundle_layout.sh
bash deployment/docker/tests/test_upgrade_state.sh
bash deployment/docker/tests/test_backup_batch.sh
bash deployment/docker/tests/test_restore_safety.sh
bash deployment/docker/tests/test_destructive_commands.sh
bash deployment/docker/tests/test_upgrade_integration.sh --all
```

预期：所有命令成功；测试临时文件和截图位于规定目录并在完成后清理。

- [ ] **Step 3: 委托代码质量和安全审查**

调用 `everything-claude-code:code-reviewer` 审查所有脚本、Compose、Django 命令和测试；调用 `everything-claude-code:security-reviewer` 专门检查数据库恢复、tar 路径、shell 注入、卷删除、日志敏感信息、权限和错误处理。任何 CRITICAL/HIGH 必须修复后重新测试。

- [ ] **Step 4: 更新计划进度**

将设计文档 `## 实施步骤` 和本计划中已完成任务全部标为 `[x]`，记录实际测试命令和结果；若仍有未完成项，不得声称功能已完成。

- [ ] **Step 5: 更新 CHANGELOG 并完成文档归档**

按项目已有 `deployment/docker/CHANGELOG.md` 格式记录数据安全保护。将已完成设计内容并入技术/用户手册后，删除进行中的 `docs/plans/2026-07-25_offline-upgrade-data-safety.md`，或者按项目当前“计划完成后保留完整记录”的约定保留并全部勾选；不得同时产生重复计划文档。

- [ ] **Step 6: 最终验证与提交**

```bash
git diff --check
git status --short
git log --oneline --decorate -12
git diff origin/main...HEAD --stat
```

预期：无空白错误、无未说明的调试文件、工作区状态清晰，所有功能性 commit 遵循 Conventional Commits；在共享分支前完成 code review、安全审查和测试报告。

---

## 计划自检结果

- **规格覆盖：** 已覆盖成组备份、临时库恢复验证、维护模式、固定卷、真实源镜像回切、迁移预检、失败即停、`SAFE_STOPPED`、危险清理门禁、Shell/Python/Docker/E2E 测试、文档和审查。
- **占位符检查：** 未使用 `TBD` 或“稍后补充”等计划占位语句；测试场景和接口均已给出具体名称、命令或结构。
- **接口一致性：** `upgrade_id`、`state.json`、`verify_backup_batch`、`restore_media_batch`、`SKIP_MIGRATE`、固定 Compose 变量在相关任务间保持一致。
- **环境约束：** 后端命令均使用 `conda run -n omni_desk`，未安排 base 或系统 Python 安装操作。
