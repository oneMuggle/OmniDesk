#!/bin/bash
# Docker镜像构建和推送脚本
# 使用方法: ./build.sh [版本号] [Docker Hub用户名]
# 如果不提供参数，将从 deployment/docker/VERSION 文件读取版本号

trap 'read -p "Press any key to exit..."' EXIT

# 从 VERSION 文件读取版本
VERSION_FILE="deployment/docker/VERSION"
if [ -f "$VERSION_FILE" ]; then
  FILE_VERSION=$(cat "$VERSION_FILE" | tr -d '[:space:]')
fi

# 加载 .env.production 文件
ENV_FILE="deployment/docker/.env.production"
if [ -f "$ENV_FILE" ]; then
  source "$ENV_FILE"
fi

# 设置默认值
DEFAULT_FRONTEND_VERSION=${FRONTEND_VERSION:-${FILE_VERSION:-latest}}
DEFAULT_BACKEND_VERSION=${BACKEND_VERSION:-${FILE_VERSION:-latest}}
DEFAULT_USER=${DOCKER_USER:-defaultuser}

# 参数处理
if [ $# -ge 1 ]; then
  VERSION=$1
  FRONTEND_VERSION=$VERSION
  BACKEND_VERSION=$VERSION
else
  FRONTEND_VERSION=$DEFAULT_FRONTEND_VERSION
  BACKEND_VERSION=$DEFAULT_BACKEND_VERSION
fi

# Docker 用户名处理
if [ $# -ge 2 ]; then
  DOCKER_USER=$2
else
  DOCKER_USER=$DEFAULT_USER
fi

# 验证版本格式（强制语义化版本）
for ver in "$FRONTEND_VERSION" "$BACKEND_VERSION"; do
  if [ "$ver" = "latest" ]; then
    echo "WARNING: Using :latest tag is discouraged. Set version in deployment/docker/VERSION"
  elif ! echo "$ver" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+$'; then
    echo "ERROR: Invalid version '$ver'. Use semantic versioning (MAJOR.MINOR.PATCH)."
    exit 1
  fi
done

# 验证必要变量是否存在
if [ -z "$FRONTEND_VERSION" ] || [ -z "$BACKEND_VERSION" ] || [ -z "$DOCKER_USER" ]; then
  echo "Error: Missing required variables."
  echo "Please define FRONTEND_VERSION, BACKEND_VERSION, and DOCKER_USER in $ENV_FILE or pass them as arguments."
  echo "Usage: $0 [version] [docker_username]"
  exit 1
fi

# 构建并推送前端镜像
echo "Building frontend image (omni-desk-frontend:$FRONTEND_VERSION)..."
docker build -t $DOCKER_USER/omni-desk-frontend:$FRONTEND_VERSION ./omni_desk_frontend
# docker push $DOCKER_USER/omni-desk-frontend:$FRONTEND_VERSION

# 构建并推送后端镜像
echo "Building backend image (omni-desk-backend:$BACKEND_VERSION)..."
docker build -t $DOCKER_USER/omni-desk-backend:$BACKEND_VERSION -f deployment/docker/omni_desk_backend/Dockerfile .
# docker push $DOCKER_USER/omni-desk-backend:$BACKEND_VERSION

echo "Build completed for:"
echo "  - Frontend: $DOCKER_USER/omni-desk-frontend:$FRONTEND_VERSION"
echo "  - Backend:  $DOCKER_USER/omni-desk-backend:$BACKEND_VERSION"
