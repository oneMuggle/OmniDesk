#!/bin/bash
# Docker镜像构建和导出脚本
# 使用方法: ./export_images.sh [版本号] [Docker Hub用户名] [导出目录(可选)]
# 如果不提供参数，将从.env文件读取默认配置

# 加载.env文件(如果存在)
if [ -f .env ]; then
  source .env
else
  echo "Warning: .env file not found, will require manual parameters"
fi

# 设置默认值
DEFAULT_VERSION=${FRONTEND_VERSION:-unset}
DEFAULT_USER=${DOCKER_USER:-unset}

# 参数处理
if [ $# -ge 2 ]; then
  # 使用命令行参数
  VERSION=$1
  DOCKER_USER=$2
elif [ "$DEFAULT_VERSION" != "unset" ] && [ "$DEFAULT_USER" != "unset" ]; then
  # 使用.env默认值
  VERSION=$DEFAULT_VERSION
  DOCKER_USER=$DEFAULT_USER
  echo "Using default values from .env:"
  echo "Version: $VERSION"
  echo "Docker User: $DOCKER_USER"
else
  echo "Error: Missing parameters and no valid defaults in .env"
  echo "Usage: $0 [version] [docker_username] [export_dir(optional)]"
  exit 1
fi

EXPORT_DIR=${3:-.}  # 默认导出目录为当前目录

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
