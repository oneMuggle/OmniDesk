#!/bin/bash
# Docker镜像构建和导出脚本
# 使用方法: ./export_images.sh [版本号] [Docker Hub用户名] [导出目录(可选)]
# 如果不提供参数，将从 deployment/docker/.env.production 文件读取默认配置

# 加载 .env.production 文件
ENV_FILE="deployment/docker/.env.production"
if [ -f "$ENV_FILE" ]; then
  source "$ENV_FILE"
else
  echo "Warning: $ENV_FILE not found, will require manual parameters"
fi

# 设置默认值
DEFAULT_FRONTEND_VERSION=${FRONTEND_VERSION:-latest}
DEFAULT_BACKEND_VERSION=${BACKEND_VERSION:-latest}
DEFAULT_USER=${DOCKER_USER:-defaultuser}

# 参数处理
if [ $# -ge 2 ]; then
  # 使用命令行参数
  FRONTEND_VERSION=$1
  BACKEND_VERSION=$1
  DOCKER_USER=$2
else
  # 使用.env默认值
  FRONTEND_VERSION=$DEFAULT_FRONTEND_VERSION
  BACKEND_VERSION=$DEFAULT_BACKEND_VERSION
  DOCKER_USER=$DEFAULT_USER
  echo "Using default values from $ENV_FILE:"
  echo "Frontend Version: $FRONTEND_VERSION"
  echo "Backend Version: $BACKEND_VERSION"
  echo "Docker User: $DOCKER_USER"
fi

EXPORT_DIR=${3:-./exported_images}  # 默认导出目录

# 创建导出目录(如果不存在)
mkdir -p "$EXPORT_DIR"

# 定义镜像
FRONTEND_IMAGE="$DOCKER_USER/omni-desk-frontend:$FRONTEND_VERSION"
BACKEND_IMAGE="$DOCKER_USER/omni-desk-backend:$BACKEND_VERSION"
POSTGRES_IMAGE="postgres:14-alpine"
REDIS_IMAGE="redis:7-alpine"

# 导出文件路径
FRONTEND_EXPORT_FILE="$EXPORT_DIR/omni-desk-frontend-v$FRONTEND_VERSION.img"
BACKEND_EXPORT_FILE="$EXPORT_DIR/omni-desk-backend-v$BACKEND_VERSION.img"
POSTGRES_EXPORT_FILE="$EXPORT_DIR/postgres-14-alpine.img"
REDIS_EXPORT_FILE="$EXPORT_DIR/redis-7-alpine.img"

# 导出前端镜像
echo "Exporting frontend image: $FRONTEND_IMAGE..."
docker save "$FRONTEND_IMAGE" -o "$FRONTEND_EXPORT_FILE"

# 导出后端镜像
echo "Exporting backend image: $BACKEND_IMAGE..."
docker save "$BACKEND_IMAGE" -o "$BACKEND_EXPORT_FILE"

# 导出Postgres镜像
echo "Exporting postgres image: $POSTGRES_IMAGE..."
docker save "$POSTGRES_IMAGE" -o "$POSTGRES_EXPORT_FILE"

# 导出Redis镜像
echo "Exporting redis image: $REDIS_IMAGE..."
docker save "$REDIS_IMAGE" -o "$REDIS_EXPORT_FILE"

echo "----------------------------------------"
echo "Docker image export completed."
echo "Exported to directory: $EXPORT_DIR"
echo "----------------------------------------"
echo "Frontend: $FRONTEND_EXPORT_FILE"
echo "Backend:  $BACKEND_EXPORT_FILE"
echo "Postgres: $POSTGRES_EXPORT_FILE"
echo "Redis:    $REDIS_EXPORT_FILE"
echo "----------------------------------------"
