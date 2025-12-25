#!/bin/bash
set -e # 如果任何命令失败，则立即退出

# 检查是否提供了镜像标签
if [ -z "$1" ]; then
  echo "错误：未提供镜像标签。"
  echo "用法: $0 <image-tag>"
  exit 1
fi

IMAGE_TAG=$1

echo "正在部署版本: $IMAGE_TAG"

# 设置环境变量，以便 docker-compose.prod.yml 可以使用它们
export BACKEND_IMAGE_TAG=${IMAGE_TAG}
export FRONTEND_IMAGE_TAG=${IMAGE_TAG}

# 拉取最新的镜像
docker-compose -f deployment/docker/docker-compose.prod.yml pull

# 以分离模式重新创建并启动服务
# --no-deps 防止重新创建依赖的服务（如数据库）
# --build 在此不需要，因为我们拉取预构建的镜像
docker-compose -f deployment/docker/docker-compose.prod.yml up -d --no-deps omni_desk_backend omni_desk_frontend

echo "部署完成。"