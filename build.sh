#!/bin/bash
# Docker镜像构建和推送脚本
# 使用方法: ./build.sh [版本号] [Docker Hub用户名]
# 优先从.env文件读取配置，命令行参数可覆盖

# 从.env文件读取默认值
if [ -f .env ]; then
  source .env
  DEFAULT_VERSION=$FRONTEND_VERSION
  DEFAULT_DOCKER_USER=$DOCKER_USER
fi

# 使用命令行参数或.env中的默认值
VERSION=${1:-$DEFAULT_VERSION}
DOCKER_USER=${2:-$DEFAULT_DOCKER_USER}

# 验证必要变量是否存在
if [ -z "$VERSION" ] || [ -z "$DOCKER_USER" ]; then
  echo "Error: Missing required parameters"
  echo "Either provide them in .env file or as command line arguments"
  echo "Usage: $0 [version] [docker_username]"
  exit 1
fi

# 构建并推送前端镜像
echo "Building frontend image..."
docker build -t $DOCKER_USER/calendar-frontend:$VERSION ./calendar_with_react
# docker push $DOCKER_USER/calendar-frontend:$VERSION

# 构建并推送后端镜像
echo "Building backend image..."
docker build -t $DOCKER_USER/calendar-backend:$VERSION ./DRFForVue
# docker push $DOCKER_USER/calendar-backend:$VERSION

echo "Build and push completed for version $VERSION"


