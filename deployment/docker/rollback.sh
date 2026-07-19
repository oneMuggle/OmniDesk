#!/bin/bash
set -e

# rollback.sh — Rollback to a previous version
# Usage: ./rollback.sh
#
# Workflow:
#   1. Show current version and available backups
#   2. Select target backup
#   3. Stop current services
#   4. Restore database (optional)
#   5. Restart services
#   6. Health check
#   7. Record rollback

COMPOSE_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$COMPOSE_DIR"

COMPOSE_FILE="-f docker-compose.offline.yml"
ENV_FILE="--env-file .env.production"

# Backup directory on the host (relative to script location)
BACKUP_DIR="${BACKUP_DIR:-./backups}"
# Path inside the container where the backup volume is mounted
CONTAINER_BACKUP_DIR="/usr/src/app/backups"

# 渠道参数(--channel,默认 stable)。hotfix 备份沿用 stable/ 目录。
ROLLBACK_CHANNEL="${ROLLBACK_CHANNEL:-stable}"
DRY_RUN=false
for arg in "$@"; do
    case "$arg" in
        --channel=*) ROLLBACK_CHANNEL="${arg#*=}" ;;
        --dry-run)    DRY_RUN=true ;;
        -h|--help)
            echo "Usage: $0 [--channel={alpha|beta|preview|stable|hotfix}] [--dry-run]"
            exit 0
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

echo "=========================================="
echo "  OmniDesk Version Rollback"
echo "=========================================="
echo ""

# Step 1: Show current version
CURRENT_VERSION=$(compose exec -T backend python manage.py shell -c "from django.conf import settings; print(settings.APP_VERSION)" 2>/dev/null || echo "unknown")
echo "Current version: $CURRENT_VERSION"
echo "Rollback channel: $ROLLBACK_CHANNEL"
echo ""

# Step 2: Show available backups
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

RESTORE_FILE=""
if [ -n "$backup_num" ] && [ "$backup_num" != "0" ]; then
    # Get the filename from the list
    RESTORE_FILE=$(ls -1t "$BACKUP_DIR"/backup_v*.sql.gz 2>/dev/null | sed -n "${backup_num}p")
    if [ -z "$RESTORE_FILE" ]; then
        echo "Invalid selection. Continuing without DB restore."
        RESTORE_FILE=""
    else
        # Convert host path to container path
        RESTORE_FILE_CONTAINER="$CONTAINER_BACKUP_DIR/$(basename "$RESTORE_FILE")"
    fi
fi
echo ""

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

# Step 7: Health check
echo "Step 7: Running health check..."
sleep 5
CONTAINER_ID=$(compose ps -q backend 2>/dev/null || true)
if [ -n "$CONTAINER_ID" ]; then
    HEALTH=$(docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}unknown{{end}}' "$CONTAINER_ID" 2>/dev/null || echo "unknown")
    if [ "$HEALTH" = "healthy" ]; then
        echo "Health check: PASSED"
    else
        echo "WARNING: Backend health status: $HEALTH"
        echo "Services may still be starting. Check manually."
    fi
else
    echo "WARNING: Backend container not running."
fi
echo ""

# Step 8: Record
NEW_VERSION=$(compose exec -T backend python manage.py shell -c "from django.conf import settings; print(settings.APP_VERSION)" 2>/dev/null || echo "unknown")
echo "$(date '+%Y-%m-%d %H:%M:%S') Rolled back: $CURRENT_VERSION -> $NEW_VERSION" >> upgrade.log
echo ""

echo "=========================================="
echo "  Rollback complete: $CURRENT_VERSION -> $NEW_VERSION"
echo "=========================================="
