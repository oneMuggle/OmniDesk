#!/bin/bash
set -e

# upgrade.sh — Safe version upgrade script for OmniDesk
# Usage: ./upgrade.sh [path-to-new-images-dir] [--target-channel {alpha|beta|preview|stable|hotfix}]
#
# Workflow:
#   1. Check current version
#   2. Version compatibility check (no major version skip)
#   3. Load new images
#   4. Pre-check migrations
#   5. Confirm with user
#   6. Backup database + media
#   7. Update containers
#   8. Run migrations
#   9. Health check
#  10. Record changelog

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# 自动检测布局:源码树(扁平,文件直接在 deployment/docker/)vs 离线包(分层,compose/ 子目录)
# brief 要求 bundle 内脚本通过 SCRIPT_DIR/../compose 定位 compose/env 文件
if [ -f "$SCRIPT_DIR/../compose/docker-compose.offline.yml" ]; then
    # 离线包布局:compose 在 SCRIPT_DIR/../compose/
    cd "$SCRIPT_DIR/.."
    COMPOSE_FILE="-f compose/docker-compose.offline.yml"
    ENV_FILE_PATH="compose/.env.production"
else
    # 源码树布局:compose 文件与脚本同目录
    cd "$SCRIPT_DIR"
    COMPOSE_FILE="-f docker-compose.offline.yml"
    ENV_FILE_PATH=".env.production"
fi
ENV_FILE="--env-file $ENV_FILE_PATH"

# 硬门禁:启动/升级前必须存在真实 .env.production(本脚本只对"已部署"包有意义)。
# 协调员 follow-up:verify.sh 容忍缺失(example fallback),但 upgrade 必须实际 .env.production。
if [ ! -f "$ENV_FILE_PATH" ]; then
    echo "ERROR: $ENV_FILE_PATH 不存在 — upgrade 必须在已部署的实例上运行。" >&2
    echo "  首次部署请先: cd <bundle> && ./scripts/deploy.sh start(生成 .env.production)" >&2
    exit 1
fi

# Backup directory on the host (relative to script location)
BACKUP_DIR="${BACKUP_DIR:-./backups}"
# Path inside the container where the backup volume is mounted
CONTAINER_BACKUP_DIR="/usr/src/app/backups"

# Phase 11 DS-4: Structured log function with timestamp + log file
LOG_FILE="${LOG_FILE:-./logs/upgrade-$(date +%Y%m%d-%H%M%S).log}"
mkdir -p "$(dirname "$LOG_FILE")"
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

compose() {
    docker compose $COMPOSE_FILE $ENV_FILE "$@"
}

# ─── 升级状态机(Task 2 brief) ──────────────────────────────
# 加载 upgrade_state.sh,提供 write_state / transition_state / enter_safe_stop。
# OMNIDESK_RUNTIME_ROOT 默认 /opt/omnidesk/runtime,源码树测试时可通过
# 环境变量覆盖。UPGRADE_ID 是本次升级的唯一标识(时间戳 + 版本对)。
SCRIPT_DIR_ENV="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=./upgrade_state.sh
source "$SCRIPT_DIR_ENV/upgrade_state.sh"
export OMNIDESK_RUNTIME_ROOT="${OMNIDESK_RUNTIME_ROOT:-/opt/omnidesk/runtime}"

# trap:任何失败 → SAFE_STOPPED(保留现场供回滚/排查);升级完成 → 释放锁
# 注意:仅当本脚本确实持有锁时才记录 SAFE_STOPPED — 若我们因 assert_no_existing_safe_stop
# 失败而退出,那不应该再为"被拒绝的新升级"写一个新 SAFE_STOPPED(避免覆盖原状态)。
on_upgrade_failure() {
    local rc=$?
    local lock_path="$OMNIDESK_RUNTIME_ROOT/upgrades/$UPGRADE_ID/upgrade.lock"
    if [ "$rc" -ne 0 ] && [ -d "$lock_path" ]; then
        enter_safe_stop "upgrade.sh 失败 (exit=$rc)" >/dev/null 2>&1 || true
    fi
    release_upgrade_lock >/dev/null 2>&1 || true
}
trap on_upgrade_failure EXIT

# ─── Helper Functions ──────────────────────────────────────────

compare_major() {
    local old=$1 new=$2
    local old_major=$(echo "$old" | cut -d. -f1)
    local new_major=$(echo "$new" | cut -d. -f1)
    if [ "$old_major" != "$new_major" ]; then
        echo "DIFFERENT"
    else
        echo "SAME"
    fi
}

wait_for_backend() {
    echo "Waiting for backend to be ready..."
    local max_retries=30
    local retry=0
    while [ $retry -lt $max_retries ]; do
        local container_id
        container_id=$(compose ps -q backend 2>/dev/null || true)
        if [ -n "$container_id" ]; then
            local health
            health=$(docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}starting{{end}}' "$container_id" 2>/dev/null || echo "unknown")
            if [ "$health" = "healthy" ]; then
                echo "Backend is ready."
                return 0
            fi
        fi
        retry=$((retry + 1))
        echo "  Waiting... ($retry/$max_retries)"
        sleep 2
    done
    echo "WARNING: Backend did not become ready after $((max_retries * 2)) seconds"
    return 1
}

get_current_version() {
    compose exec -T backend python manage.py shell -c "from django.conf import settings; print(settings.APP_VERSION)" 2>/dev/null || echo "unknown"
}

get_target_version() {
    if [ -f "VERSION" ]; then
        cat VERSION | tr -d '[:space:]'
    else
        echo "unknown"
    fi
}

# ─── Main Script ───────────────────────────────────────────────

IMAGE_DIR="${1:-.}"

# 渠道参数(--target-channel,默认从 VERSION 后缀推导)
TARGET_CHANNEL="${TARGET_CHANNEL:-}"
DRY_RUN=false
for arg in "$@"; do
    case "$arg" in
        --target-channel=*) TARGET_CHANNEL="${arg#*=}" ;;
        --dry-run)           DRY_RUN=true ;;
        -h|--help)
            echo "Usage: $0 [IMAGE_DIR] [--target-channel={alpha|beta|preview|stable|hotfix}] [--dry-run]"
            exit 0
            ;;
    esac
done

if $DRY_RUN; then
    echo "=========================================="
    echo "  DRY-RUN MODE — no destructive ops"
    echo "=========================================="
fi

echo "=========================================="
echo "  OmniDesk Version Upgrade"
echo "=========================================="
echo ""

# Step 1: Check current version
CURRENT_VERSION=$(get_current_version)
TARGET_VERSION=$(get_target_version)

if [ -z "$TARGET_CHANNEL" ]; then
    case "$TARGET_VERSION" in
        *-alpha.*) TARGET_CHANNEL="alpha" ;;
        *-beta.*)  TARGET_CHANNEL="beta" ;;
        *-rc.*)    TARGET_CHANNEL="preview" ;;
        *)         TARGET_CHANNEL="stable" ;;
    esac
fi

echo "Current version: $CURRENT_VERSION"
echo "Target version:  $TARGET_VERSION"
echo "Target channel:  $TARGET_CHANNEL"
echo ""

if [ "$CURRENT_VERSION" = "$TARGET_VERSION" ]; then
    echo "Already at target version. Nothing to do."
    exit 0
fi

# ─── Step 1.5: 初始化升级状态文件(Task 2 brief) ──────────
# UPGRADE_ID = UTC 时间戳 + 版本对;写入 INIT 状态。
# 关键守卫(任一失败必须 HARD-FAIL,不吞错):
#   1) assert_no_existing_safe_stop — 已有 SAFE_STOPPED 拒绝新升级
#   2) acquire_upgrade_lock — 并发升级互斥
#   3) write_state INIT — 状态文件写入;失败时 trap 会触发 SAFE_STOPPED 记录现场
TS_UTC=$(date -u +'%Y%m%dT%H%M%SZ')
export UPGRADE_ID="${TS_UTC}-${CURRENT_VERSION}-to-${TARGET_VERSION}"
# (1) SAFE_STOPPED 守卫:已有升级卡在 SAFE_STOPPED 时硬拒绝
if ! assert_no_existing_safe_stop; then
    echo "ERROR: 拒绝升级 — 已有 SAFE_STOPPED 标记。请先人工排查并清理旧 state.json。" >&2
    exit 1
fi
# (2) 升级锁:并发升级互斥
LOCK_PATH="$OMNIDESK_RUNTIME_ROOT/upgrades/$UPGRADE_ID/upgrade.lock"
if ! acquire_upgrade_lock; then
    echo "ERROR: 已有升级在运行(lock dir: $LOCK_PATH)。" >&2
    echo "  若确认是遗留,可手动 rm -rf $LOCK_PATH 后重试。" >&2
    exit 1
fi
# (3) IMAGE_TAG 从 .env.production 读;缺省用 VERSION 派生
SRC_IMG_TAG="$(grep -E '^BACKEND_IMAGE_TAG=' "$ENV_FILE_PATH" 2>/dev/null | cut -d= -f2- || true)"
TGT_IMG_TAG="$(grep -E '^BACKEND_IMAGE_TAG=' "$ENV_FILE_PATH" 2>/dev/null | cut -d= -f2- || true)"
[ -z "$TGT_IMG_TAG" ] && TGT_IMG_TAG="v${TARGET_VERSION}"
# (4) 写 INIT — 必须成功;set -e 让 write_state 失败自动非零退出
write_state INIT \
    source_version="$CURRENT_VERSION" target_version="$TARGET_VERSION" \
    channel="$TARGET_CHANNEL" backup_dir="${OMNIDESK_BACKUP_ROOT:-/opt/omnidesk/backups}/${ROLLBACK_CHANNEL:-${TARGET_CHANNEL}}/${UPGRADE_ID}" \
    source_image_tag="$SRC_IMG_TAG" target_image_tag="$TGT_IMG_TAG"

# Step 2: Compatibility check
MAJOR_CHECK=$(compare_major "$CURRENT_VERSION" "$TARGET_VERSION")
if [ "$MAJOR_CHECK" = "DIFFERENT" ]; then
    echo "ERROR: Major version change detected ($CURRENT_VERSION -> $TARGET_VERSION)"
    echo "Major version upgrades require a manual migration plan."
    echo "Do NOT use this script for major version upgrades."
    exit 1
fi

echo "Compatibility check: PASSED"
echo ""

# ─── Step 2.5: 渠道校验(禁止跳级) ─────────────────────
CURRENT_CHANNEL=""
if [ "$CURRENT_VERSION" != "unknown" ]; then
    case "$CURRENT_VERSION" in
        *-alpha.*) CURRENT_CHANNEL="alpha" ;;
        *-beta.*)  CURRENT_CHANNEL="beta" ;;
        *-rc.*)    CURRENT_CHANNEL="preview" ;;
        *)         CURRENT_CHANNEL="stable" ;;
    esac
fi
if [ -n "$CURRENT_CHANNEL" ] && [ "$CURRENT_CHANNEL" != "$TARGET_CHANNEL" ]; then
    case "$CURRENT_CHANNEL:$TARGET_CHANNEL" in
        alpha:beta|beta:preview|preview:stable|alpha:preview|alpha:stable|beta:stable)
            echo "Channel upgrade: $CURRENT_CHANNEL -> $TARGET_CHANNEL (allowed)" ;;
        *)
            echo "ERROR: Channel downgrade or invalid jump detected ($CURRENT_CHANNEL -> $TARGET_CHANNEL)."
            echo "Allowed forward jumps: alpha->beta, beta->preview, preview->stable (or skip forward)."
            echo "Downgrades (stable->anything, beta->alpha, etc.) are FORBIDDEN."
            exit 1
            ;;
    esac
fi
echo ""

# Step 3: Load new images
echo "Step 3: Loading new Docker images..."
for tar_file in "$IMAGE_DIR"/*.tar; do
    if [ -f "$tar_file" ]; then
        echo "  Loading: $(basename "$tar_file")"
        if $DRY_RUN; then
            echo "    [DRY-RUN] would run: docker load -i $tar_file"
        else
            docker load -i "$tar_file"
        fi
    fi
done
echo "Images loaded."
echo ""

# Step 4: Pre-check migrations
echo "Step 4: Checking pending migrations..."
compose up -d backend --no-recreate 2>/dev/null || true
wait_for_backend

MIGRATION_OUTPUT=$(compose exec -T backend python manage.py check_migrations 2>/dev/null || true)
echo "$MIGRATION_OUTPUT"
echo ""

# Step 5: Confirm
echo "Step 5: Ready to upgrade from $CURRENT_VERSION to $TARGET_VERSION"
read -p "Type 'yes' to proceed with upgrade: " confirm
if [ "$confirm" != "yes" ]; then
    echo "Upgrade cancelled."
    exit 0
fi
echo ""

# Step 6: Backup
echo "Step 6: Creating backup..."
if $DRY_RUN; then
    echo "  [DRY-RUN] would run: compose exec -T backend python manage.py backup_db --output-dir $CONTAINER_BACKUP_DIR"
else
    mkdir -p "$BACKUP_DIR"
    compose exec -T backend python manage.py backup_db --output-dir "$CONTAINER_BACKUP_DIR" || {
        echo "WARNING: Backup failed. Proceed with caution."
        read -p "Type 'yes' to continue without backup: " confirm2
        if [ "$confirm2" != "yes" ]; then
            echo "Upgrade cancelled."
            exit 1
        fi
    }
fi
echo ""

# Step 7: Update containers
echo "Step 7: Updating containers..."
if $DRY_RUN; then
    echo "  [DRY-RUN] would run: compose down && compose up -d"
else
    compose down
    compose up -d
fi
echo "Containers updated."
echo ""

# Step 8: Run migrations
echo "Step 8: Running database migrations..."
if $DRY_RUN; then
    echo "  [DRY-RUN] would run: compose exec -T backend python manage.py migrate"
else
    compose exec -T backend python manage.py migrate
fi
echo ""

# Step 9: Health check
echo "Step 9: Running health check..."
wait_for_backend

# Step 9.5: Smoke gate (P0)
# set -e (脚本顶部) 让 smoke 失败自动终止;插在 Step 10 记录前 → 失败不会
# 留下"已升级"伪记录,且在成功 banner 前 → 输出语义一致。
# ${BASE_URL:-http://localhost} 让 smoke 透传环境变量(若未设则与原默认一致)。
echo ""
echo "Step 9.5: Running smoke tests (gate before recording)..."
./smoke_tests.sh "${BASE_URL:-http://localhost}"
echo ""

# Step 10: Record
echo "Step 10: Recording upgrade..."
echo "$(date '+%Y-%m-%d %H:%M:%S') Upgraded: $CURRENT_VERSION -> $TARGET_VERSION" >> upgrade.log
echo ""

echo "=========================================="
echo "  Upgrade complete: $CURRENT_VERSION -> $TARGET_VERSION"
echo "=========================================="
