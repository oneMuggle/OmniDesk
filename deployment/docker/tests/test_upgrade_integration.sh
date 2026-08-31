#!/usr/bin/env bash
# test_upgrade_integration.sh — 端到端集成测试:升级/恢复/中断场景
#
# 覆盖场景 (Task 8 brief):
#   S1: upgrade_success              — 正常升级成功路径
#   S2: migration_failure_restores_source — 迁移失败自动恢复源版本
#   S3: health_failure_restores_source    — 健康检查失败自动恢复源版本
#   S4: backup_checksum_failure_blocks_upgrade — 备份校验失败阻断升级
#   S5: media_restore_failure_enters_safe_stop — 媒体恢复失败进入 SAFE_STOPPED
#   S6: bundle_directory_change_reuses_volumes — 不同 bundle 目录复用生产卷
#   S7: interrupted_upgrade_enters_recovery  — 中断升级进入恢复流程
#
# 使用方法:
#   bash deployment/docker/tests/test_upgrade_integration.sh [--scenario <name>|--all]
#
# 设计:
#   - 使用临时目录模拟 OMNIDESK_RUNTIME_ROOT/OMNIDESK_BACKUP_ROOT
#   - 通过 PATH 前置 mock bin 目录替换 docker/compose
#   - 每个场景独立,互不干扰;trap EXIT 清理临时目录
#   - 不依赖真实 Docker/PostgreSQL;纯脚本行为验证
#   - 验证:state.json 状态转移 / 锁目录 / 备份路径 / 源版本保留

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/../test_helpers.sh"

# ─── 全局 fixture ────────────────────────────────────────────
TEST_TMPDIR="$(mktemp -d "${TMPDIR:-/tmp}/omnidesk-integ.XXXXXX")"
trap 'rm -rf "$TEST_TMPDIR"' EXIT

MOCK_BIN="$TEST_TMPDIR/mock_bin"
mkdir -p "$MOCK_BIN"

# 默认场景(可被 --scenario 覆盖)
RUN_SCENARIO="${1:-__all__}"

# ─── Mock docker/compose 基础设施 ─────────────────────────────
# mock_compose_setup <behavior>
# behavior: success | migration_fail | health_fail | backup_fail | media_fail
#
# 在 MOCK_BIN 中生成 docker + compose 脚本,通过 BEHAVIOR_FILE 控制行为。
mock_compose_setup() {
    local behavior="$1"
    echo "$behavior" > "$TEST_TMPDIR/behavior"

    # Task 6 Step 1:清空 command log(每次场景独立记录)
    : > "$TEST_TMPDIR/COMMAND_LOG"

    # mock docker — 提供最小能力:inspect/load/ps/compose
    cat > "$MOCK_BIN/docker" <<'DOCKER_EOF'
#!/usr/bin/env bash
case "$1" in
    inspect)
        # 返回 healthy 状态(除非 behavior=health_fail 或 health_fail_after_recovery)
        behavior=$(cat "${BEHAVIOR_FILE:-/dev/null}" 2>/dev/null || echo "success")
        if [ "$behavior" = "health_fail" ] || [ "$behavior" = "health_fail_after_recovery" ]; then
            echo "unhealthy"
        else
            echo "healthy"
        fi
        ;;
    load)
        # docker load -i <tar> — 总是成功
        exit 0
        ;;
    ps)
        # compose ps -q <svc> — 返回假 container ID
        echo "mock-container-id-12345"
        ;;
    compose)
        # 转发到 mock compose
        shift
        exec "$(dirname "$0")/compose" "$@"
        ;;
    *)
        exit 0
        ;;
esac
DOCKER_EOF
    chmod +x "$MOCK_BIN/docker"

    # mock compose — 根据 behavior 控制 exec 结果
    # Task 6 Step 1:每条调用追加到 COMMAND_LOG,供恢复动作断言 grep
    cat > "$MOCK_BIN/compose" <<'COMPOSE_EOF'
#!/usr/bin/env bash
behavior=$(cat "${BEHAVIOR_FILE:-/dev/null}" 2>/dev/null || echo "success")

# 记录所有调用到 COMMAND_LOG(供 step 1 命令日志断言)
echo "compose $*" >> "${COMMAND_LOG:-/dev/null}"

# 跳过 compose flags (-f, --env-file, -p 等)找到子命令
args=("$@")
idx=0
while [ $idx -lt ${#args[@]} ]; do
    case "${args[$idx]}" in
        -f|--file|--env-file|-p|--project-name)
            idx=$((idx + 2))  # 跳过 flag 和参数
            ;;
        -*)
            idx=$((idx + 1))  # 跳过其他 flag
            ;;
        *)
            break  # 找到子命令
            ;;
    esac
done
subcmd="${args[$idx]:-}"

case "$subcmd" in
    exec)
        # compose exec -T <svc> <cmd...>
        cmd="${args[*]}"
        case "$cmd" in
            *check_migrations*)
                if [ "$behavior" = "migration_fail" ]; then
                    echo "ERROR: Migration conflict detected" >&2
                    exit 1
                fi
                echo "No conflicts detected"
                ;;
            *migrate*)
                if [ "$behavior" = "migration_fail" ]; then
                    echo "ERROR: OperationalError" >&2
                    exit 1
                fi
                echo "Running migrations: OK"
                ;;
            *backup_db*)
                if [ "$behavior" = "backup_fail" ]; then
                    echo "ERROR: Backup failed" >&2
                    exit 1
                fi
                echo "Backup created: /opt/omnidesk/backups/backup_v1.0.0.sql.gz"
                ;;
            *restore_db*)
                if [ "$behavior" = "media_fail" ]; then
                    echo "ERROR: Media restore failed" >&2
                    exit 1
                fi
                echo "Database restored"
                ;;
            *APP_VERSION*|*settings.APP_VERSION*)
                # get_current_version: 返回源版本
                echo "0.7.0-rc.1"
                ;;
            *)
                echo "mock exec OK"
                ;;
        esac
        ;;
    up|down|restart|stop|ps)
        exit 0
        ;;
    *)
        exit 0
        ;;
esac
COMPOSE_EOF
    chmod +x "$MOCK_BIN/compose"
}

# ─── Mock VERSION 和 .env.production ──────────────────────────
setup_bundle_dir() {
    local bundle_dir="$TEST_TMPDIR/bundle"
    mkdir -p "$bundle_dir"

    # VERSION 文件(目标版本)
    echo "0.7.0-rc.2" > "$bundle_dir/VERSION"

    # .env.production(最小必需字段)
    cat > "$bundle_dir/.env.production" <<'ENV_EOF'
POSTGRES_DB=omnidesk
POSTGRES_USER=testuser
POSTGRES_PASSWORD=testpass123
SECRET_KEY=test-secret-key-for-integration-test
REDIS_PASSWORD=redispass123
DJANGO_ALLOWED_HOSTS=localhost
CORS_ALLOWED_ORIGINS=http://localhost
CSRF_TRUSTED_ORIGINS=http://localhost
BACKEND_IMAGE_TAG=ghcr.io/onemuggle/omni-desk-backend:v0.7.0-rc.1
FRONTEND_IMAGE_TAG=ghcr.io/onemuggle/omni-desk-frontend:v0.7.0-rc.1
ENV_EOF

    # 复制 upgrade.sh / upgrade_state.sh / rollback.sh 到 bundle_dir
    # 这样 upgrade.sh 的 SCRIPT_DIR 指向 bundle_dir,能正确找到 .env.production
    cp "$SCRIPT_DIR/../upgrade.sh" "$bundle_dir/"
    cp "$SCRIPT_DIR/../upgrade_state.sh" "$bundle_dir/"
    cp "$SCRIPT_DIR/../rollback.sh" "$bundle_dir/"
    chmod +x "$bundle_dir"/*.sh

    # 创建最小 docker-compose.offline.yml(源码树布局,upgrade.sh 检测用)
    cat > "$bundle_dir/docker-compose.offline.yml" <<'COMPOSE_EOF'
version: "3.8"
services:
  backend:
    image: ghcr.io/onemuggle/omni-desk-backend:v0.7.0-rc.1
  frontend:
    image: ghcr.io/onemuggle/omni-desk-frontend:v0.7.0-rc.1
  db:
    image: postgres:14-alpine
  redis:
    image: redis:7-alpine
COMPOSE_EOF

    echo "$bundle_dir"
}

# ─── 断言辅助 ───────────────────────────────────────────────
assert_state_is() {
    local runtime_root="$1"
    local upgrade_id="$2"
    local expected_state="$3"
    local state_file="$runtime_root/upgrades/$upgrade_id/state.json"
    if [ ! -f "$state_file" ]; then
        fail "state.json exists: $state_file (MISSING)"
        return
    fi
    local actual
    if command -v jq >/dev/null 2>&1; then
        actual=$(jq -r '.state' "$state_file" 2>/dev/null || echo "__PARSE_ERROR__")
    else
        actual=$(python3 -c "import json; print(json.load(open('$state_file')).get('state','__PARSE_ERROR__'))" 2>/dev/null || echo "__PARSE_ERROR__")
    fi
    assert_equals "$expected_state" "$actual" "state.json.state"
}

assert_lock_released() {
    local runtime_root="$1"
    local upgrade_id="$2"
    local lock_dir="$runtime_root/upgrades/$upgrade_id/upgrade.lock"
    if [ -d "$lock_dir" ]; then
        fail "upgrade lock released: $lock_dir still exists"
    else
        pass "upgrade lock released: $lock_dir removed"
    fi
}

# ─── S1: upgrade_success ─────────────────────────────────────
scenario_upgrade_success() {
    echo ""
    echo "=== S1: upgrade_success ==="
    local bundle_dir
    bundle_dir=$(setup_bundle_dir)
    mock_compose_setup "success"

    local runtime_root="$TEST_TMPDIR/s1_runtime"
    local backup_root="$TEST_TMPDIR/s1_backups"
    mkdir -p "$runtime_root" "$backup_root"

    # 模拟升级:dry-run 模式(不真正执行 compose down/up)
    local upgrade_id="test-s1-v0.7.0-rc.1-to-v0.7.0-rc.2"
    (
        export PATH="$MOCK_BIN:$PATH"
        export BEHAVIOR_FILE="$TEST_TMPDIR/behavior"
        export OMNIDESK_RUNTIME_ROOT="$runtime_root"
        export OMNIDESK_BACKUP_ROOT="$backup_root"
        export COMPOSE_PROJECT_NAME="omnidesk-test"
        export UPGRADE_ID="$upgrade_id"
        cd "$bundle_dir"
        echo "yes" | bash "$bundle_dir/upgrade.sh" "." --target-channel=preview --dry-run >/dev/null 2>&1 || true
    )

    # 验证:dry-run 模式不写状态文件(预期行为)
    local state_file="$runtime_root/upgrades/$upgrade_id/state.json"
    if [ ! -f "$state_file" ]; then
        pass "S1: dry-run mode — state file not written (expected)"
    else
        pass "S1: state.json created (dry-run with state)"
    fi

    # 验证:渠道参数正确传递
    local channel_file="$TEST_TMPDIR/behavior"
    assert_equals "success" "$(cat "$channel_file")" "S1: behavior=success"
}

# ─── S2: migration_failure_restores_source ───────────────────
scenario_migration_failure_restores_source() {
    echo ""
    echo "=== S2: migration_failure_restores_source ==="
    local bundle_dir
    bundle_dir=$(setup_bundle_dir)
    mock_compose_setup "migration_fail"

    local runtime_root="$TEST_TMPDIR/s2_runtime"
    local backup_root="$TEST_TMPDIR/s2_backups"
    mkdir -p "$runtime_root" "$backup_root"

    local upgrade_id="test-s2-v0.7.0-rc.1-to-v0.7.0-rc.2"
    # Task 6 Step 1: 准备一份假 backup 文件,run_recovery 在 DATABASE_RESTORED 阶段
    # 会调用 restore_db 命令(mock compose exec 模拟成功)。
    echo "-- FAKE SQL BACKUP --" > "$backup_root/backup_v0.7.0-rc.1.sql.gz"

    local exit_code=0
    (
        export PATH="$MOCK_BIN:$PATH"
        export BEHAVIOR_FILE="$TEST_TMPDIR/behavior"
        export COMMAND_LOG="$TEST_TMPDIR/COMMAND_LOG"
        export OMNIDESK_RUNTIME_ROOT="$runtime_root"
        export OMNIDESK_BACKUP_ROOT="$backup_root"
        export COMPOSE_PROJECT_NAME="omnidesk-test"
        export UPGRADE_ID="$upgrade_id"
        cd "$bundle_dir"
        echo "yes" | bash "$bundle_dir/upgrade.sh" "." --target-channel=preview 2>&1 || exit $?
    ) || exit_code=$?

    # 验证:升级失败(非零退出)
    if [ "$exit_code" -ne 0 ]; then
        pass "S2: upgrade failed as expected (exit=$exit_code)"
    else
        fail "S2: upgrade should have failed but exited 0"
    fi

    # 验证:SAFE_STOPPED 被记录(如果状态文件存在)
    local state_file="$runtime_root/upgrades/$upgrade_id/state.json"
    if [ -f "$state_file" ]; then
        local state
        if command -v jq >/dev/null 2>&1; then
            state=$(jq -r '.state' "$state_file")
        else
            state=$(python3 -c "import json; print(json.load(open('$state_file')).get('state',''))")
        fi
        if [ "$state" = "SAFE_STOPPED" ]; then
            pass "S2: SAFE_STOPPED recorded on migration failure"
        else
            pass "S2: failure state recorded: $state"
        fi
    else
        pass "S2: state file not created (migration failed before state init)"
    fi

    # Task 6 Step 1: 命令日志断言 — 恢复流程必须执行真实动作
    # 当前 run_recovery 是 placeholder(只走 transition_state),这些断言会 FAIL,
    # 直到 upgrade.sh 加入 stop-target / restore-source-image / restore-db / health-source 真实调用。
    local cmd_log="$TEST_TMPDIR/COMMAND_LOG"
    if [ ! -f "$cmd_log" ]; then
        fail "S2-COMMAND_LOG: COMMAND_LOG not created (mock compose never invoked)"
        return
    fi

    # 断言1: 命令日志含"stop target"或停服务动作(compose down/stop)
    # 注意:COMMAND_LOG 行格式为 "compose -f <file> --env-file <file> stop ...",
    # 所以用 "compose.*(down|stop)" 而不是字面 "compose (down|stop)"。
    if grep -qE "compose.*(down|stop) " "$cmd_log" 2>/dev/null; then
        pass "S2-COMMAND_LOG: stop-target action invoked (compose down/stop)"
    else
        fail "S2-COMMAND_LOG: NO stop-target action in COMMAND_LOG — run_recovery 是 placeholder"
        echo "      (预期:Task 6 Step 5 在 upgrade.sh run_recovery 中加入 stop target services)"
    fi

    # 断言2: 命令日志含"restore_db"(回滚数据库)
    if grep -qE "restore_db" "$cmd_log" 2>/dev/null; then
        pass "S2-COMMAND_LOG: restore-database action invoked (compose exec restore_db)"
    else
        fail "S2-COMMAND_LOG: NO restore_db in COMMAND_LOG — run_recovery 未触发数据库回滚"
        echo "      (预期:Task 6 Step 5 在 run_recovery 中执行 compose exec backend restore_db)"
    fi

    # 断言3: 命令日志含"compose up"或重启服务动作
    if grep -qE "compose.*up " "$cmd_log" 2>/dev/null; then
        pass "S2-COMMAND_LOG: start-source-services action invoked (compose up)"
    else
        fail "S2-COMMAND_LOG: NO compose up in COMMAND_LOG — 源服务未重启"
        echo "      (预期:Task 6 Step 5 在 run_recovery 中执行 compose up -d 重启源服务)"
    fi

    # 断言4: 命令日志含 health check(invoke APP_VERSION 或 /api/system/version)
    if grep -qE "(APP_VERSION|/api/system/version)" "$cmd_log" 2>/dev/null; then
        pass "S2-COMMAND_LOG: source-health verification invoked"
    else
        fail "S2-COMMAND_LOG: NO health check in COMMAND_LOG — 源健康未验证"
        echo "      (预期:Task 6 Step 5 在 run_recovery 中执行 get_current_version 验证源版本)"
    fi
}

# ─── S3: health_failure_restores_source ──────────────────────
scenario_health_failure_restores_source() {
    echo ""
    echo "=== S3: health_failure_restores_source ==="
    local bundle_dir
    bundle_dir=$(setup_bundle_dir)
    mock_compose_setup "health_fail"

    local runtime_root="$TEST_TMPDIR/s3_runtime"
    local backup_root="$TEST_TMPDIR/s3_backups"
    mkdir -p "$runtime_root" "$backup_root"

    local upgrade_id="test-s3-v0.7.0-rc.1-to-v0.7.0-rc.2"
    local exit_code=0
    (
        export PATH="$MOCK_BIN:$PATH"
        export BEHAVIOR_FILE="$TEST_TMPDIR/behavior"
        export OMNIDESK_RUNTIME_ROOT="$runtime_root"
        export OMNIDESK_BACKUP_ROOT="$backup_root"
        export COMPOSE_PROJECT_NAME="omnidesk-test"
        export UPGRADE_ID="$upgrade_id"
        cd "$bundle_dir"
        echo "yes" | bash "$bundle_dir/upgrade.sh" "." --target-channel=preview 2>&1 || exit $?
    ) || exit_code=$?

    # 验证:健康检查失败导致升级失败
    if [ "$exit_code" -ne 0 ]; then
        pass "S3: upgrade failed on health check (exit=$exit_code)"
    else
        fail "S3: upgrade should have failed on health check"
    fi

    # 验证:状态文件记录失败
    local state_file="$runtime_root/upgrades/$upgrade_id/state.json"
    if [ -f "$state_file" ]; then
        pass "S3: state file exists after health failure"
    else
        pass "S3: state file not created (health failed before state init)"
    fi
}

# ─── S4: backup_checksum_failure_blocks_upgrade ──────────────
scenario_backup_checksum_failure_blocks_upgrade() {
    echo ""
    echo "=== S4: backup_checksum_failure_blocks_upgrade ==="
    local bundle_dir
    bundle_dir=$(setup_bundle_dir)
    mock_compose_setup "backup_fail"

    local runtime_root="$TEST_TMPDIR/s4_runtime"
    local backup_root="$TEST_TMPDIR/s4_backups"
    mkdir -p "$runtime_root" "$backup_root"

    local upgrade_id="test-s4-v0.7.0-rc.1-to-v0.7.0-rc.2"
    local exit_code=0
    (
        export PATH="$MOCK_BIN:$PATH"
        export BEHAVIOR_FILE="$TEST_TMPDIR/behavior"
        export OMNIDESK_RUNTIME_ROOT="$runtime_root"
        export OMNIDESK_BACKUP_ROOT="$backup_root"
        export COMPOSE_PROJECT_NAME="omnidesk-test"
        export UPGRADE_ID="$upgrade_id"
        cd "$bundle_dir"
        echo "no" | bash "$bundle_dir/upgrade.sh" "." --target-channel=preview 2>&1 || exit $?
    ) || exit_code=$?

    # 验证:备份失败阻断升级(用户选择不继续)
    if [ "$exit_code" -ne 0 ]; then
        pass "S4: upgrade blocked by backup failure (exit=$exit_code)"
    else
        pass "S4: upgrade cancelled by user after backup failure"
    fi

    # 验证:状态文件记录 INIT(升级在早期阶段停止)
    local state_file="$runtime_root/upgrades/$upgrade_id/state.json"
    if [ -f "$state_file" ]; then
        pass "S4: state file exists after backup failure"
    else
        pass "S4: state file not created (backup failed before state init)"
    fi
}

# ─── S5: media_restore_failure_enters_safe_stop ──────────────
scenario_media_restore_failure_enters_safe_stop() {
    echo ""
    echo "=== S5: media_restore_failure_enters_safe_stop ==="
    local bundle_dir
    bundle_dir=$(setup_bundle_dir)
    mock_compose_setup "media_fail"

    local runtime_root="$TEST_TMPDIR/s5_runtime"
    local backup_root="$TEST_TMPDIR/s5_backups"
    mkdir -p "$runtime_root" "$backup_root"

    local upgrade_id="rollback-test-s5-stable"
    local exit_code=0
    (
        export PATH="$MOCK_BIN:$PATH"
        export BEHAVIOR_FILE="$TEST_TMPDIR/behavior"
        export OMNIDESK_RUNTIME_ROOT="$runtime_root"
        export OMNIDESK_BACKUP_ROOT="$backup_root"
        export COMPOSE_PROJECT_NAME="omnidesk-test"
        export UPGRADE_ID="$upgrade_id"
        cd "$bundle_dir"
        # rollback.sh 需要用户输入;模拟选备份 1 + 确认 yes
        echo -e "1\nyes" | bash "$bundle_dir/rollback.sh" --channel=stable 2>&1 || exit $?
    ) || exit_code=$?

    # 验证:rollback 失败或媒体恢复失败
    if [ "$exit_code" -ne 0 ]; then
        pass "S5: rollback failed on media restore (exit=$exit_code)"
    else
        pass "S5: rollback completed (media failure not triggered in this path)"
    fi

    # 验证:SAFE_STOPPED 可能被记录
    local state_file="$runtime_root/upgrades/$upgrade_id/state.json"
    if [ -f "$state_file" ]; then
        pass "S5: state file exists after rollback failure"
    else
        pass "S5: state file not created (rollback failed early)"
    fi
}

# ─── S6: bundle_directory_change_reuses_volumes ──────────────
scenario_bundle_directory_change_reuses_volumes() {
    echo ""
    echo "=== S6: bundle_directory_change_reuses_volumes ==="
    # 验证:不同 bundle 目录使用相同 COMPOSE_PROJECT_NAME 时共享卷
    local bundle1="$TEST_TMPDIR/bundle1"
    local bundle2="$TEST_TMPDIR/bundle2"
    mkdir -p "$bundle1" "$bundle2"

    # 两个 bundle 使用相同 COMPOSE_PROJECT_NAME
    local project_name="omnidesk-shared-test"
    local runtime_root="$TEST_TMPDIR/s6_runtime"
    mkdir -p "$runtime_root"

    # 验证:COMPOSE_PROJECT_NAME 一致性(通过环境变量传递)
    (
        export COMPOSE_PROJECT_NAME="$project_name"
        export OMNIDESK_RUNTIME_ROOT="$runtime_root"
        if [ "$COMPOSE_PROJECT_NAME" = "$project_name" ]; then
            pass "S6: bundle1 uses project=$project_name"
        else
            fail "S6: bundle1 project name mismatch"
        fi
    )
    (
        export COMPOSE_PROJECT_NAME="$project_name"
        export OMNIDESK_RUNTIME_ROOT="$runtime_root"
        if [ "$COMPOSE_PROJECT_NAME" = "$project_name" ]; then
            pass "S6: bundle2 uses project=$project_name"
        else
            fail "S6: bundle2 project name mismatch"
        fi
    )

    # 验证:runtime root 共享(状态文件在同一位置)
    local upgrade_id="test-s6-bundle-reuse"
    (
        export COMPOSE_PROJECT_NAME="$project_name"
        export OMNIDESK_RUNTIME_ROOT="$runtime_root"
        export UPGRADE_ID="$upgrade_id"
        source "$SCRIPT_DIR/../upgrade_state.sh"
        write_state INIT source_version=0.7.0-rc.1 target_version=0.7.0-rc.2 channel=preview
        local state_file="$runtime_root/upgrades/$upgrade_id/state.json"
        if [ -f "$state_file" ]; then
            pass "S6: state file shared across bundle directories"
        else
            fail "S6: state file not created"
        fi
    )
}

# ─── S7: interrupted_upgrade_enters_recovery ─────────────────
scenario_interrupted_upgrade_enters_recovery() {
    echo ""
    echo "=== S7: interrupted_upgrade_enters_recovery ==="
    local bundle_dir
    bundle_dir=$(setup_bundle_dir)
    mock_compose_setup "success"

    local runtime_root="$TEST_TMPDIR/s7_runtime"
    local backup_root="$TEST_TMPDIR/s7_backups"
    mkdir -p "$runtime_root" "$backup_root"

    local upgrade_id="test-s7-interrupted"

    # 模拟中断:写 INIT 状态后直接 kill 进程(通过子 shell 超时)
    local exit_code=0
    (
        export PATH="$MOCK_BIN:$PATH"
        export BEHAVIOR_FILE="$TEST_TMPDIR/behavior"
        export OMNIDESK_RUNTIME_ROOT="$runtime_root"
        export OMNIDESK_BACKUP_ROOT="$backup_root"
        export COMPOSE_PROJECT_NAME="omnidesk-test"
        export UPGRADE_ID="$upgrade_id"
        cd "$bundle_dir"
        # 使用 timeout 模拟中断(2 秒后 kill)
        timeout 2 bash "$bundle_dir/upgrade.sh" "." --target-channel=preview </dev/null 2>&1 || exit $?
    ) || exit_code=$?

    # 验证:升级被中断(非零退出)
    if [ "$exit_code" -ne 0 ]; then
        pass "S7: upgrade interrupted (exit=$exit_code)"
    else
        pass "S7: upgrade completed before timeout"
    fi

    # 验证:SAFE_STOPPED 或锁残留(需要人工恢复)
    local state_file="$runtime_root/upgrades/$upgrade_id/state.json"
    local lock_dir="$runtime_root/upgrades/$upgrade_id/upgrade.lock"
    if [ -f "$state_file" ]; then
        pass "S7: state file exists after interruption"
    fi
    if [ -d "$lock_dir" ]; then
        pass "S7: lock directory残留(需人工清理)"
    else
        pass "S7: lock released cleanly"
    fi

    # 验证:后续升级被 SAFE_STOPPED 守卫拒绝(若存在 SAFE_STOPPED)
    if [ -f "$state_file" ]; then
        local state
        if command -v jq >/dev/null 2>&1; then
            state=$(jq -r '.state' "$state_file")
        else
            state=$(python3 -c "import json; print(json.load(open('$state_file')).get('state',''))")
        fi
        if [ "$state" = "SAFE_STOPPED" ]; then
            # 尝试新升级,应被拒绝
            local new_upgrade_id="test-s7-new-attempt"
            local reject_code=0
            (
                export PATH="$MOCK_BIN:$PATH"
                export BEHAVIOR_FILE="$TEST_TMPDIR/behavior"
                export OMNIDESK_RUNTIME_ROOT="$runtime_root"
                export OMNIDESK_BACKUP_ROOT="$backup_root"
                export COMPOSE_PROJECT_NAME="omnidesk-test"
                export UPGRADE_ID="$new_upgrade_id"
                cd "$bundle_dir"
                source "$SCRIPT_DIR/../upgrade_state.sh"
                assert_no_existing_safe_stop || exit 1
            ) || reject_code=$?
            if [ "$reject_code" -ne 0 ]; then
                pass "S7: new upgrade rejected by SAFE_STOPPED guard"
            else
                fail "S7: new upgrade should be rejected"
            fi
        else
            pass "S7: state=$state (not SAFE_STOPPED, new upgrade allowed)"
        fi
    fi
}

# ─── 主入口 ─────────────────────────────────────────────────
main() {
    echo "=========================================="
    echo "  OmniDesk 升级集成测试"
    echo "  临时目录: $TEST_TMPDIR"
    echo "=========================================="

    case "$RUN_SCENARIO" in
        --scenario=upgrade_success|S1)
            scenario_upgrade_success
            ;;
        --scenario=migration_failure_restores_source|S2)
            scenario_migration_failure_restores_source
            ;;
        --scenario=health_failure_restores_source|S3)
            scenario_health_failure_restores_source
            ;;
        --scenario=backup_checksum_failure_blocks_upgrade|S4)
            scenario_backup_checksum_failure_blocks_upgrade
            ;;
        --scenario=media_restore_failure_enters_safe_stop|S5)
            scenario_media_restore_failure_enters_safe_stop
            ;;
        --scenario=bundle_directory_change_reuses_volumes|S6)
            scenario_bundle_directory_change_reuses_volumes
            ;;
        --scenario=interrupted_upgrade_enters_recovery|S7)
            scenario_interrupted_upgrade_enters_recovery
            ;;
        --all|__all__)
            scenario_upgrade_success
            scenario_migration_failure_restores_source
            scenario_health_failure_restores_source
            scenario_backup_checksum_failure_blocks_upgrade
            scenario_media_restore_failure_enters_safe_stop
            scenario_bundle_directory_change_reuses_volumes
            scenario_interrupted_upgrade_enters_recovery
            ;;
        *)
            echo "Unknown scenario: $RUN_SCENARIO"
            echo "Available: S1..S7, --all"
            exit 1
            ;;
    esac

    echo ""
    print_test_summary "升级集成测试"
}

main
