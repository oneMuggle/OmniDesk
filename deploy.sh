#!/bin/bash
set -e # 如果任何命令失败，立即退出脚本

# --- 配置 ---
# 假设您的项目部署在服务器的 '~/app/omni-desk' 目录下
PROJECT_DIR="~/app/omni-desk" 
DOCKER_COMPOSE_FILE="deployment/docker/docker-compose.yml"
ENV_FILE_PATH="deployment/docker/.env.production"

# --- 部署步骤 ---
echo ">>> 正在开始部署..."

# 1. 导航到项目目录
cd $PROJECT_DIR || { echo "错误：项目目录 $PROJECT_DIR 不存在。"; exit 1; }
echo "当前工作目录: $(pwd)"

# 2. 更新 .env.production 文件
# 注意：SERVER_ENV_FILE 将由 GitHub Actions 通过环境变量注入
if [ -n "$SERVER_ENV_FILE" ]; then
    echo ">>> 正在更新 .env.production 文件..."
    echo "$SERVER_ENV_FILE" > $ENV_FILE_PATH
    echo ".env.production 文件已更新。"
else
    echo "警告：未提供 SERVER_ENV_FILE 环境变量，跳过 .env.production 文件更新。"
fi

# 3. 拉取最新的 Docker 镜像
echo ">>> 正在拉取最新的 Docker 镜像..."
docker-compose -f $DOCKER_COMPOSE_FILE pull

# 4. 使用 docker-compose 重新部署服务
echo ">>> 正在使用 docker-compose 重新部署服务..."
# --remove-orphans 会移除在 docker-compose.yml 中已不存在的服务的容器
# --no-deps 防止重新创建依赖的服务（如数据库）
docker-compose -f $DOCKER_COMPOSE_FILE up -d --remove-orphans --no-deps backend frontend worker

# 5. 清理悬空的 Docker 镜像
echo ">>> 正在清理旧的 Docker 镜像..."
docker image prune -f

echo ">>> ✅ 部署成功完成！"