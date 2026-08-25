#!/bin/bash
set -e

# rollback.sh — Rollback to a previous version
# Usage: ./rollback.sh [--batch-dir <path>] [--channel={alpha|beta|preview|stable|hotfix}]
#                     [--skip-metadata-verify] [--dry-run]
#
# Workflow:
#   1. Show current version and available backups
#   2. Select target backup (interactive or via --batch-dir)
#   3. Stop current services
#   4. Restore database + media (from paired batch, verified)
#   5. Restart services
#   6. Health check
#   7. Record rollback
#
# 关键安全增强(Task 4 brief):
#   - --batch-dir:指定成组备份目录(取代旧的孤立 sql.gz)
#   - verify_backup_batch.sh:验证 metadata + sha256 + size + tar 成员路径
#   - --skip-metadata-verify:紧急旁路(默认不开)
#   - 状态文件原子写(mktemp + mv -f,继承自 upgrade_state.sh 自身)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# 自动检测布局:源码树(扁平)vs 离线包(compose/ 子目录)
# brief 要求 bundle 内脚本通过 SCRIPT_DIR/../compose 定位 compose/env 文件
if [ -f "$SCRIPT_DIR/../compose/docker-compose.offline.yml" ]; then
    # 离线包布局
    cd "$SCRIPT_DIR/.."
    COMPOSE_FILE="-f compose/docker-compose.offline.yml"
    ENV_FILE_PATH="compose/.env.production"
else
    # 源码树布局
    cd "$SCRIPT_DIR"
    COMPOSE_FILE="-f docker-compose.offline.yml"
    ENV_FILE_PATH=".env.production"
fi
ENV_FILE="--env-file $ENV_FILE_PATH"

# 硬门禁:rollback 只对"已部署"实例有意义,缺 .env.production 时立即拒绝
if [ ! -f "$ENV_FILE_PATH" ]; then
    echo "ERROR: $ENV_FILE_PATH 不存在 — rollback 必须在已部署的实例上运行。" >&2
    exit 1
fi

# Backup directory on the host (relative to script location)
BACKUP_DIR="${BACKUP_DIR:-./backups}"
# Path inside the container where the backup volume is mounted
CONTAINER_BACKUP_DIR="/usr/src/app/backups"

# 渠道参数(--channel,默认 stable)。hotfix 备份沿用 stable/ 目录。
ROLLBACK_CHANNEL="${ROLLBACK_CHANNEL:-stable}"
DRY_RUN=false
SKIP_METADATA_VERIFY=0
BATCH_DIR=""
prev_arg=""
for arg in "$@"; do
    case "$arg" in
        --channel=*)            ROLLBACK_CHANNEL="${arg#*=}" ;;
        --dry-run)              DRY_RUN=true ;;
        --skip-metadata-verify) SKIP_METADATA_VERIFY=1 ;;
        --batch-dir=*)          BATCH_DIR="${arg#*=}" ;;
        --batch-dir)            prev_arg="--batch-dir" ;;
        -h|--help)
            echo "Usage: $0 [--batch-dir <path>] [--channel={alpha|beta|preview|stable|hotfix}] [--skip-metadata-verify] [--dry-run]"
            exit 0
            ;;
        *)
            # 处理 --batch-dir <path>(两 token 形式:prev_arg == --batch-dir)
            if [ "$prev_arg" = "--batch-dir" ] && [ -z "$BATCH_DIR" ]; then
                BATCH_DIR="$arg"
                prev_arg=""
            else
                prev_arg=""
            fi
            ;;
    esac
done
if [ "$ROLLBACK_CHANNEL" = "hotfix" ]; then
    ROLLBACK_CHANNEL="stable"
fi
BACKUP_DIR="${BACKUP_DIR:-./backups}/${ROLLBACK_CHANNEL}"

# Phase 11 DS-4: Structured log function with timestamp + log file
LOG_FILE="${LOG_FILE:-./logs/rollback-$(date +%Y%m%d-%H%M%S).log}"
mkdir -p "$(dirname "$LOG_FILE")"
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

if $DRY_RUN; then
    log "DRY-RUN MODE — no destructive ops"
fi

compose() {
    docker compose $COMPOSE_FILE $ENV_FILE "$@"
}

# ─── 升级状态机(Task 2 brief) ──────────────────────────────
# 加载 upgrade_state.sh:rollback 失败时触发 SAFE_STOPPED,记录现场供升级脚本排查。
SCRIPT_DIR_ENV="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=./upgrade_state.sh
source "$SCRIPT_DIR_ENV/upgrade_state.sh"
export OMNIDESK_RUNTIME_ROOT="${OMNIDESK_RUNTIME_ROOT:-/opt/omnidesk/runtime}"

# ─── Step 0.5: 生成 rollback 专属 UPGRADE_ID(必须 unique 且非 unknown) ──
# rollback 标识 = rollback-<UTC时间戳>-<channel>;通过前缀区分 upgrade / rollback
# 这样:
#   1) 永远不会落到默认 sentinel "unknown" 上
#   2) trap 触发 enter_safe_stop 时,状态文件路径唯一,不会污染其他升级记录
#   3) 调用方可以用 grep 区分 rollback vs upgrade 的状态目录
TS_UTC_ROLLBACK=$(date -u +'%Y%m%dT%H%M%SZ')
export UPGRADE_ID="rollback-${TS_UTC_ROLLBACK}-${ROLLBACK_CHANNEL}"

# 持有 rollback 专属升级锁(并发回滚互斥;若与当前 upgrade 抢锁,upgrade 锁优先,
# 这里 acquire 失败意味着另有 rollback 在跑,直接拒绝)。
LOCK_PATH_ROLLBACK="$OMNIDESK_RUNTIME_ROOT/upgrades/$UPGRADE_ID/upgrade.lock"
if ! acquire_upgrade_lock; then
    echo "ERROR: 已有 rollback 在运行(lock dir: $LOCK_PATH_ROLLBACK)。" >&2
    echo "  若确认是遗留,可手动 rm -rf $LOCK_PATH_ROLLBACK 后重试。" >&2
    exit 1
fi

# trap:rollback 失败 → SAFE_STOPPED(保留现场);成功 → 释放锁
# 注意:仅当本脚本确实持有锁时才记录 SAFE_STOPPED — 避免给"被守卫拒绝"的新回滚
# 写新 SAFE_STOPPED 标记。
on_rollback_failure() {
    local rc=$?
    local lock_path="$OMNIDESK_RUNTIME_ROOT/upgrades/$UPGRADE_ID/upgrade.lock"
    if [ "$rc" -ne 0 ] && [ -d "$lock_path" ]; then
        enter_safe_stop "rollback.sh 失败 (exit=$rc)" >/dev/null 2>&1 || true
    fi
    release_upgrade_lock >/dev/null 2>&1 || true
}
trap on_rollback_failure EXIT

echo "=========================================="
echo "  OmniDesk Version Rollback"
echo "=========================================="
echo ""

# Step 1: Show current version
CURRENT_VERSION=$(compose exec -T backend python manage.py shell -c "from django.conf import settings; print(settings.APP_VERSION)" 2>/dev/null || echo "unknown")
echo "Current version: $CURRENT_VERSION"
echo "Rollback channel: $ROLLBACK_CHANNEL"
echo ""

# ─── Step 2: 解析 batch_dir(若指定) ──────────────────────
# --batch-dir 形式:直接使用成组批次
# 若未指定:走旧的"列表 + 编号"交互路径
RESTORE_FILE=""
RESTORE_FILE_CONTAINER=""
MEDIA_RESTORE_FILE=""
MEDIA_RESTORE_CONTAINER=""

if [ -n "$BATCH_DIR" ]; then
    echo "Using batch dir: $BATCH_DIR"

    # ─── 关键安全闸:调用 verify_backup_batch.sh 校验批次 ──
    # 即使 --skip-metadata-verify 给了旁路,基础目录存在性 + metadata.json
    # 必填字段仍由 verify_backup_batch.sh 强制(verify 内部的 --skip-verify
    # 跳过的是 sha256/size + tar 成员路径,基础 schema 仍查)。
    if [ ! -f "$SCRIPT_DIR_ENV/verify_backup_batch.sh" ]; then
        echo "ERROR: $SCRIPT_DIR_ENV/verify_backup_batch.sh 缺失 — bundle 不完整。" >&2
        exit 1
    fi
    VERIFY_ARGS=("$BATCH_DIR")
    if [ "$SKIP_METADATA_VERIFY" -eq 1 ]; then
        VERIFY_ARGS=("--skip-verify" "$BATCH_DIR")
        echo "WARN: --skip-metadata-verify active; sha256/size NOT checked" >&2
    fi
    if ! bash "$SCRIPT_DIR_ENV/verify_backup_batch.sh" "${VERIFY_ARGS[@]}"; then
        echo "ERROR: 批次 $BATCH_DIR 校验失败,拒绝回滚(保护数据不被破坏批次污染)" >&2
        exit 1
    fi

    # 从 metadata.json 解析 database_file / media_file
    DB_FILE_REL=$(jq -r '.database_file' "$BATCH_DIR/metadata.json")
    MEDIA_FILE_REL=$(jq -r '.media_file' "$BATCH_DIR/metadata.json")

    # host 路径(直接是 BATCH_DIR/<file>)
    RESTORE_FILE="$BATCH_DIR/$DB_FILE_REL"
    MEDIA_RESTORE_FILE="$BATCH_DIR/$MEDIA_FILE_REL"

    if [ ! -f "$RESTORE_FILE" ]; then
        echo "ERROR: database file not found: $RESTORE_FILE" >&2
        exit 1
    fi
    # 容器内路径:把 BATCH_DIR 映射到 CONTAINER_BACKUP_DIR
    RESTORE_FILE_CONTAINER="$CONTAINER_BACKUP_DIR/$(basename "$DB_FILE_REL")"
    MEDIA_RESTORE_CONTAINER="$CONTAINER_BACKUP_DIR/$(basename "$MEDIA_FILE_REL")"
    echo ""
else
    # Step 2 (旧路径):列出孤立 sql.gz 备份
    echo "Available database backups:"
    if [ -d "$BACKUP_DIR" ]; then
        db_backups=$(ls -1t "$BACKUP_DIR"/backup_v*.sql.gz 2>/dev/null || true)
        if [ -z "$db_backups" ]; then
            echo "  No backups found in $BACKUP_DIR"
        else
            # Phase 11 DS-2: Use nl for numbering (pipe-to-while was a subshell that reset i)
            echo "$db_backups" | nl -ba -w1 -s'] [' | sed "s/^/  [/"
        fi
    else
        echo "  Backup directory $BACKUP_DIR does not exist."
    fi
    echo ""

    # Step 3: Select backup
    read -p "Enter backup number to restore (or 0 to skip DB restore): " backup_num

    if [ -n "$backup_num" ] && [ "$backup_num" != "0" ]; then
        RESTORE_FILE=$(ls -1t "$BACKUP_DIR"/backup_v*.sql.gz 2>/dev/null | sed -n "${backup_num}p")
        if [ -z "$RESTORE_FILE" ]; then
            echo "Invalid selection. Continuing without DB restore."
            RESTORE_FILE=""
        else
            RESTORE_FILE_CONTAINER="$CONTAINER_BACKUP_DIR/$(basename "$RESTORE_FILE")"
        fi
    fi
    echo ""
fi

# Step 4: Confirm
read -p "Type 'yes' to proceed with rollback: " confirm
if [ "$confirm" != "yes" ]; then
    echo "Rollback cancelled."
    exit 0
fi
echo ""

# Step 5: Restore database
if [ -n "$RESTORE_FILE_CONTAINER" ]; then
    echo "Step 5: Restoring database from $(basename "$RESTORE_FILE")..."
    if $DRY_RUN; then
        echo "  [DRY-RUN] would run: compose exec -T backend python manage.py restore_db $RESTORE_FILE_CONTAINER --force"
    else
        compose exec -T backend python manage.py restore_db "$RESTORE_FILE_CONTAINER" --force
    fi
    echo ""
else
    echo "Step 5: Skipping database restore."
fi

# Step 5b: Restore media (仅在成组批次模式下)
if [ -n "$MEDIA_RESTORE_CONTAINER" ] && [ -f "$MEDIA_RESTORE_FILE" ]; then
    echo "Step 5b: Restoring media from $(basename "$MEDIA_RESTORE_FILE")..."
    if $DRY_RUN; then
        echo "  [DRY-RUN] would run: docker cp media → backend /usr/src/app/media"
    else
        # 把 media tar 解到 backend 容器内 media 目录
        # 用 docker cp 传送,容器内 tar 解压(verify 已经校验过 tar 成员路径)
        BACKEND_CID=$(compose ps -q backend 2>/dev/null || true)
        if [ -n "$BACKEND_CID" ]; then
            docker cp "$MEDIA_RESTORE_FILE" "$BACKEND_CID:/tmp/media_restore.tar.gz"
            compose exec -T backend bash -c "cd /usr/src/app/media && tar -xzf /tmp/media_restore.tar.gz && rm /tmp/media_restore.tar.gz"
        else
            echo "WARN: backend 容器不在,跳过 media 恢复" >&2
        fi
    fi
    echo ""
fi

# Step 6: Restart services
echo "Step 6: Restarting services..."
if $DRY_RUN; then
    echo "  [DRY-RUN] would run: compose down && compose up -d"
else
    compose down
    compose up -d
fi
echo "Services restarted."
echo ""

# Step 7: Health check (Task 6 Step 6:硬门禁)
# 之前 Step 7 只 WARN 不 return 非零;现在若 backend 健康检查非 healthy,
# 直接返回 1 → 触发 on_rollback_failure trap → enter_safe_stop。
echo "Step 7: Running health check..."
sleep 5
HEALTH_GATE_RC=0
CONTAINER_ID=$(compose ps -q backend 2>/dev/null || true)
if [ -n "$CONTAINER_ID" ]; then
    HEALTH=$(docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}unknown{{end}}' "$CONTAINER_ID" 2>/dev/null || echo "unknown")
    if [ "$HEALTH" = "healthy" ]; then
        echo "Health check: PASSED"
    else
        echo "ERROR: Backend health status: $HEALTH (期望 healthy)" >&2
        echo "       进入 SAFE_STOPPED 兜底(由 on_rollback_failure trap 处理)" >&2
        HEALTH_GATE_RC=1
    fi
else
    echo "ERROR: Backend container not running." >&2
    HEALTH_GATE_RC=1
fi
if [ "$HEALTH_GATE_RC" -ne 0 ]; then
    return $HEALTH_GATE_RC 2>/dev/null || exit $HEALTH_GATE_RC
fi
echo ""

# Step 7.5: Smoke gate (P0)
# 注:rollback.sh 的 Step 7 health 当前不 return 非零(只 WARN),smoke 是唯一硬 gate。
# set -e (脚本顶部) 让 smoke 失败自动终止;插在 Step 8 记录前 → 失败不会
# 留下"已回滚"伪记录,且在成功 banner 前 → 输出语义一致。
echo "Step 7.5: Running smoke tests (gate before recording)..."
./smoke_tests.sh "${BASE_URL:-http://localhost}"
echo ""

# Step 8: Record
NEW_VERSION=$(compose exec -T backend python manage.py shell -c "from django.conf import settings; print(settings.APP_VERSION)" 2>/dev/null || echo "unknown")
echo "$(date '+%Y-%m-%d %H:%M:%S') Rolled back: $CURRENT_VERSION -> $NEW_VERSION" >> upgrade.log
echo ""

echo "=========================================="
echo "  Rollback complete: $CURRENT_VERSION -> $NEW_VERSION"
echo "=========================================="