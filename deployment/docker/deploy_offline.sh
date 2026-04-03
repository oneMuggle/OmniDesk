#!/bin/bash
set -e

# 定义镜像和导入目录
IMPORT_DIR="exported_images"

echo "Loading images from .tar files..."
docker load -i "$IMPORT_DIR/omni_desk_backend.tar"
docker load -i "$IMPORT_DIR/omni_desk_frontend.tar"
docker load -i "$IMPORT_DIR/postgres.tar"
docker load -i "$IMPORT_DIR/redis.tar"
docker load -i "$IMPORT_DIR/nginx.tar"

echo "Images loaded successfully."

echo "Starting production services..."
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

echo "Deployment complete."
echo "You may need to run database migrations and collect static files if this is the first deployment."
echo "Example:"
echo "docker-compose -f docker-compose.yml -f docker-compose.prod.yml exec backend python manage.py migrate"
echo "docker-compose -f docker-compose.yml -f docker-compose.prod.yml exec backend python manage.py collectstatic --noinput"