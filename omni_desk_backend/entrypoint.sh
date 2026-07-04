#!/bin/bash

# Ensure Django uses production settings in Docker
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-omni_desk_backend.settings.production}"
export DJANGO_ENV="${DJANGO_ENV:-production}"

# ─── Directory setup (runs as root for Docker named volumes) ───
for dir in /usr/src/app/backups /usr/src/app/media /usr/src/app/staticfiles; do
    mkdir -p "$dir"
    chown app:app "$dir" 2>/dev/null || true
done

set -e

# ─── Skip migration path for non-backend services (e.g. celery worker) ───
# v0.5.6 测试发现:worker 容器与 backend 容器共用同一镜像,都会跑 entrypoint.sh 的
# migrate/collectstatic 段。两者同时启动时 Postgres 报 UniqueViolation
# (django_migrations_id_seq 已存在),产生 race condition。
#
# 用法:在 docker-compose worker service 设 SKIP_MIGRATE=true
# 行为:跳过 wait_for_db / migrate / collectstatic,直接降权执行 "$@"
# 默认 false → backend 行为完全不变,向后兼容
if [ "${SKIP_MIGRATE:-false}" = "true" ]; then
    echo "SKIP_MIGRATE=true: 跳过 migrate / collectstatic(celery worker 等场景)"
    export HOME=/home/app
    exec setpriv --reuid=app --regid=app --init-groups "$@"
fi

echo "Waiting for database..."
# 环境变量名与 settings/production.py 和 .env.production 保持一致
# (DB_HOST/DB_PORT,而非 POSTGRES_HOST/POSTGRES_PORT)
until python -c "
import psycopg2
import os
try:
    conn = psycopg2.connect(
        host=os.environ.get('DB_HOST', 'db'),
        port=os.environ.get('DB_PORT', '5432'),
        dbname=os.environ.get('POSTGRES_DB', 'omnidesk'),
        user=os.environ.get('POSTGRES_USER', 'omnidesk'),
        password=os.environ.get('POSTGRES_PASSWORD', ''),
        connect_timeout=5
    )
    conn.close()
    print('Database is ready!')
except psycopg2.OperationalError:
    print('Database not ready yet, retrying...')
    exit(1)
"; do
    sleep 2
done

echo "Running database migrations..."
python manage.py migrate --noinput

if [ -n "${COLLECT_STATIC}" ] && [ "${COLLECT_STATIC}" = "true" ]; then
    echo "Collecting static files..."
    python manage.py collectstatic --noinput
fi

echo "Starting application as 'app' user..."
# Drop privileges to non-root user for the main process
# 关键:切换 HOME 到 app 用户的目录,避免 gunicorn 等工具回退到 /root 触发 Permission denied
export HOME=/home/app
exec setpriv --reuid=app --regid=app --init-groups "$@"
