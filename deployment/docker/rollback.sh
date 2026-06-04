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
echo ""

# Step 2: Show available backups
echo "Available database backups:"
if [ -d "$BACKUP_DIR" ]; then
    db_backups=$(ls -1t "$BACKUP_DIR"/backup_v*.sql.gz 2>/dev/null || true)
    if [ -z "$db_backups" ]; then
        echo "  No backups found in $BACKUP_DIR"
    else
        i=1
        echo "$db_backups" | while read -r f; do
            echo "  [$i] $(basename "$f")"
            i=$((i + 1))
        done
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
    compose exec -T backend python manage.py restore_db "$RESTORE_FILE_CONTAINER" --force
    echo ""
else
    echo "Step 5: Skipping database restore."
fi

# Step 6: Restart services
echo "Step 6: Restarting services..."
compose down
compose up -d
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
