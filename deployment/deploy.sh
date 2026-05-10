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

COMPOSE_DIR="$(cd "$(dirname "$0")/docker" && pwd)"
cd "$COMPOSE_DIR"

# 设置环境变量，以便 docker-compose.prod.yml 可以使用它们
export REGISTRY=ghcr.io/onemuggle
export TAG=${IMAGE_TAG}

# 拉取最新的镜像
docker compose -f docker-compose.prod.yml --env-file .env.production pull

# 以分离模式重新创建并启动服务
# --no-deps 防止重新创建依赖的服务（如数据库）
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --no-deps backend frontend

echo "部署完成。"