#!/bin/bash
set -e

# backup.sh — Manual backup script for OmniDesk
# Usage: ./backup.sh [--media-only] [--db-only]

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BUNDLE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# 自动检测布局:源码树(扁平,文件直接在 deployment/docker/)vs 离线包(分层,compose/ 子目录)
if [ -f "$BUNDLE_DIR/compose/docker-compose.offline.yml" ]; then
    # 离线包布局:compose 在 BUNDLE_DIR/compose/
    cd "$BUNDLE_DIR"
    COMPOSE_FILE="-f compose/docker-compose.offline.yml"
    ENV_FILE="--env-file compose/.env.production"
else
    # 源码树布局:compose 文件在 SCRIPT_DIR/ 同级
    cd "$SCRIPT_DIR"
    COMPOSE_FILE="-f docker-compose.offline.yml"
    ENV_FILE="--env-file .env.production"
fi

# Use a relative backup directory on the host
BACKUP_DIR="${BACKUP_DIR:-$SCRIPT_DIR/backups}"

# Path inside the container where the backup volume is mounted
CONTAINER_BACKUP_DIR="/usr/src/app/backups"

compose() {
    docker compose $COMPOSE_FILE $ENV_FILE "$@"
}

echo "=========================================="
echo "  OmniDesk Backup"
echo "=========================================="
echo ""

mkdir -p "$BACKUP_DIR"

# 默认带 --verify 触发 shadow DB 端到端验证,使 metadata.restore_verified=true。
# BACKUP_NO_VERIFY=1 是紧急旁路(已知 shadow 步骤会超时的运维情况)。
BACKUP_ARGS="--verify --verify-timeout ${BACKUP_VERIFY_TIMEOUT:-600}"
if [ "${BACKUP_NO_VERIFY:-0}" = "1" ]; then
    echo "WARN: BACKUP_NO_VERIFY=1 set, skipping shadow verification"
    BACKUP_ARGS="--no-verify"
fi

# 去掉原始 $* 中的 --verify / --no-verify / --verify-timeout,避免与上面默认冲突;
# 用户其它参数(legacy --db-only / --media-only / --skip-media 等)原样透传。
ARGS_FILTERED=$(echo "$*" | sed -E 's/--(no-)?verify(=[^ ]+)?//g; s/--verify-timeout(=[^ ]+)?//g; s/  +/ /g; s/^ //; s/ $//')

compose exec -T backend python manage.py backup_db --output-dir "$CONTAINER_BACKUP_DIR" $BACKUP_ARGS $ARGS_FILTERED

echo ""
echo "Backup contents:"
ls -lh "$BACKUP_DIR" | tail -n +2

echo ""
echo "Disk usage:"
du -sh "$BACKUP_DIR"

echo ""
echo "Backup complete."
