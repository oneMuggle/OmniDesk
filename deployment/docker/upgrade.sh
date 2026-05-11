#!/bin/bash
set -e

# upgrade.sh — Safe version upgrade script for OmniDesk
# Usage: ./upgrade.sh [path-to-new-images-dir]
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

COMPOSE_FILE="-f docker-compose.offline-standalone.yml"
ENV_FILE="--env-file .env.production"
BACKUP_DIR="/opt/omnidesk/backups"

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

echo "=========================================="
echo "  OmniDesk Version Upgrade"
echo "=========================================="
echo ""

# Step 1: Check current version
CURRENT_VERSION=$(get_current_version)
TARGET_VERSION=$(get_target_version)

echo "Current version: $CURRENT_VERSION"
echo "Target version:  $TARGET_VERSION"
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

# Step 3: Load new images
echo "Step 3: Loading new Docker images..."
for tar_file in "$IMAGE_DIR"/*.tar; do
    if [ -f "$tar_file" ]; then
        echo "  Loading: $(basename "$tar_file")"
        docker load -i "$tar_file"
    fi
done
echo "Images loaded."
echo ""

# Step 4: Pre-check migrations
echo "Step 4: Checking pending migrations..."
compose up -d backend --no-recreate 2>/dev/null || true
sleep 3

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
mkdir -p "$BACKUP_DIR"
compose exec -T backend python manage.py backup_db --output-dir "$BACKUP_DIR" || {
    echo "WARNING: Backup failed. Proceed with caution."
    read -p "Type 'yes' to continue without backup: " confirm2
    if [ "$confirm2" != "yes" ]; then
        echo "Upgrade cancelled."
        exit 1
    fi
}
echo ""

# Step 7: Update containers
echo "Step 7: Updating containers..."
compose down
compose up -d
echo "Containers updated."
echo ""

# Step 8: Run migrations
echo "Step 8: Running database migrations..."
compose exec -T backend python manage.py migrate
echo ""

# Step 9: Health check
echo "Step 9: Running health check..."
sleep 5
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/health/ 2>/dev/null || echo "000")
VERSION_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/system/version/ 2>/dev/null || echo "000")

if [ "$HTTP_CODE" = "200" ] && [ "$VERSION_CODE" = "200" ]; then
    echo "Health check: PASSED"
else
    echo "WARNING: Health check returned HTTP $HTTP_CODE / $VERSION_CODE"
    echo "Services may still be starting. Check manually."
fi
echo ""

# Step 10: Record
echo "Step 10: Recording upgrade..."
echo "$(date '+%Y-%m-%d %H:%M:%S') Upgraded: $CURRENT_VERSION -> $TARGET_VERSION" >> upgrade.log
echo ""

echo "=========================================="
echo "  Upgrade complete: $CURRENT_VERSION -> $TARGET_VERSION"
echo "=========================================="
