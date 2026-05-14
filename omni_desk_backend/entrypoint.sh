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

echo "Waiting for database..."
until python -c "
import psycopg2
import os
try:
    conn = psycopg2.connect(
        host=os.environ.get('POSTGRES_HOST', 'db'),
        port=os.environ.get('POSTGRES_PORT', '5432'),
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
exec setpriv --reuid=app --regid=app --init-groups "$@"
