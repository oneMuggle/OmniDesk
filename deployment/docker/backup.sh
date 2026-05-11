#!/bin/bash
set -e

# backup.sh — Manual backup script for OmniDesk
# Usage: ./backup.sh [--media-only] [--db-only]

COMPOSE_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$COMPOSE_DIR"

COMPOSE_FILE="-f docker-compose.offline-standalone.yml"
ENV_FILE="--env-file .env.production"
BACKUP_DIR="${BACKUP_DIR:-/opt/omnidesk/backups}"

compose() {
    docker compose $COMPOSE_FILE $ENV_FILE "$@"
}

echo "=========================================="
echo "  OmniDesk Backup"
echo "=========================================="
echo ""

mkdir -p "$BACKUP_DIR"

ARGS="$*"
compose exec -T backend python manage.py backup_db --output-dir "$BACKUP_DIR" $ARGS

echo ""
echo "Backup contents:"
ls -lh "$BACKUP_DIR" | tail -n +2

echo ""
echo "Disk usage:"
du -sh "$BACKUP_DIR"

echo ""
echo "Backup complete."
