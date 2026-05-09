#!/bin/bash
set -e

# 定义镜像和导出目录
EXPORT_DIR="exported_images"
BACKEND_IMAGE="omni-desk-backend-prod:latest"
FRONTEND_IMAGE="omni-desk-frontend-prod:latest"
POSTGRES_IMAGE="postgres:14.2"
REDIS_IMAGE="redis:7-alpine"
NGINX_IMAGE="nginx:latest"

# 创建导出目录
mkdir -p $EXPORT_DIR

echo "Building production images locally..."
docker compose -f docker-compose.build.yml build

echo "Pulling required service images..."
docker pull $POSTGRES_IMAGE
docker pull $REDIS_IMAGE
docker pull $NGINX_IMAGE

echo "Saving images to .tar files..."
docker save -o "$EXPORT_DIR/omni_desk_backend.tar" $BACKEND_IMAGE
docker save -o "$EXPORT_DIR/omni_desk_frontend.tar" $FRONTEND_IMAGE
docker save -o "$EXPORT_DIR/postgres.tar" $POSTGRES_IMAGE
docker save -o "$EXPORT_DIR/redis.tar" $REDIS_IMAGE
docker save -o "$EXPORT_DIR/nginx.tar" $NGINX_IMAGE

echo "Image export complete. Files are in the '$EXPORT_DIR' directory."

# Generate .env.production from defaults with auto-filled secrets
if [ -f ".env.production.defaults" ]; then
    echo "Generating .env.production with secure defaults..."
    cp .env.production.defaults .env.production

    python3 -c "
import secrets
with open('.env.production', 'r') as f:
    content = f.read()
content = content.replace('<GENERATE-NEW-SECRET-KEY>', secrets.token_urlsafe(50))
content = content.replace('<CHANGE-TO-STRONG-PASSWORD>', secrets.token_urlsafe(20))
with open('.env.production', 'w') as f:
    f.write(content)
"

    echo ".env.production generated successfully."
    echo "IMPORTANT: Review and change secrets before deploying to production."
fi

echo "Next steps:"
echo "1. Copy the '$EXPORT_DIR' directory to your offline server."
echo "2. Copy 'docker-compose.yml', 'docker-compose.offline.yml', '.env.production', and 'nginx' directory to your offline server."
echo "3. On the offline server, run the deployment script."
