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

COMPOSE_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$COMPOSE_DIR"

COMPOSE_FILE="-f docker-compose.offline.yml"
ENV_FILE="--env-file .env.production"

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

# Step 10: Record
echo "Step 10: Recording upgrade..."
echo "$(date '+%Y-%m-%d %H:%M:%S') Upgraded: $CURRENT_VERSION -> $TARGET_VERSION" >> upgrade.log
echo ""

echo "=========================================="
echo "  Upgrade complete: $CURRENT_VERSION -> $TARGET_VERSION"
echo "=========================================="
