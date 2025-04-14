#!/bin/bash
# Docker镜像构建和导出脚本
# 使用方法: ./export_images.sh [版本号] [Docker Hub用户名] [导出目录(可选)]

if [ $# -lt 2 ]; then
  echo "Usage: $0 [version] [docker_username] [export_dir(optional)]"
  exit 1
fi

VERSION=$1
DOCKER_USER=$2
EXPORT_DIR=${3:-.}  # 默认当前目录

# 构建前端镜像
echo "Building frontend image..."
docker build -t $DOCKER_USER/calendar-frontend:$VERSION ./calendar_with_react

# 构建后端镜像
echo "Building backend image..."
docker build -t $DOCKER_USER/calendar-backend:$VERSION ./DRFForVue

# 创建导出目录(如果不存在)
mkdir -p $EXPORT_DIR

# 导出前端镜像
FRONTEND_EXPORT_FILE="$EXPORT_DIR/$DOCKER_USER-calendar-frontend-$VERSION.img"
echo "Exporting frontend image to $FRONTEND_EXPORT_FILE..."
docker save $DOCKER_USER/calendar-frontend:$VERSION -o $FRONTEND_EXPORT_FILE

# 导出后端镜像
BACKEND_EXPORT_FILE="$EXPORT_DIR/$DOCKER_USER-calendar-backend-$VERSION.img"
echo "Exporting backend image to $BACKEND_EXPORT_FILE..."
docker save $DOCKER_USER/calendar-backend:$VERSION -o $BACKEND_EXPORT_FILE

echo "Export completed:"
echo "Frontend: $FRONTEND_EXPORT_FILE"
echo "Backend: $BACKEND_EXPORT_FILE"
