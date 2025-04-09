#!/bin/bash
# Docker镜像构建和推送脚本
# 使用方法: ./build.sh [版本号] [Docker Hub用户名]

if [ $# -ne 2 ]; then
  echo "Usage: $0 [version] [docker_username]"
  exit 1
fi

VERSION=$1
DOCKER_USER=$2

# 构建并推送前端镜像
echo "Building frontend image..."
docker build -t $DOCKER_USER/calendar-frontend:$VERSION ./calendar_with_react
# docker push $DOCKER_USER/calendar-frontend:$VERSION

# 构建并推送后端镜像
echo "Building backend image..."
docker build -t $DOCKER_USER/calendar-backend:$VERSION ./DRFForVue
# docker push $DOCKER_USER/calendar-backend:$VERSION

echo "Build and push completed for version $VERSION"

sleep 10000

echo 按任意键继续
read -n 1
echo 继续运行