#!/bin/bash

# 部署脚本 - 基于 Docker Compose

# --------------------------------------------------------------------------------------------------
# 功能：
#   1. 检查 Docker 和 Docker Compose 是否安装。
#   2. 引导用户配置 .env 文件（如果不存在或需要更新）。
#   3. 拉取最新 Docker 镜像。
#   4. 启动所有服务容器。
#   5. 执行数据库迁移。
#   6. 创建 Django 超级用户。
# --------------------------------------------------------------------------------------------------

# 定义颜色
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 脚本开始
echo -e "${GREEN}### 开始部署项目 ###${NC}"

# 1. 检查 Docker 和 Docker Compose 是否安装
echo -e "${YELLOW}1. 检查 Docker 和 Docker Compose 安装...${NC}"

# 检查 Docker
if ! command -v docker &> /dev/null
then
    echo -e "${RED}Docker 未安装。请按照手册第 3.2 节安装 Docker。${NC}"
    exit 1
fi
echo -e "${GREEN}Docker 已安装。${NC}"

# 检查 Docker Compose
if ! command -v docker compose &> /dev/null
then
    echo -e "${RED}Docker Compose 未安装。请按照手册第 3.2 节安装 Docker Compose。${NC}"
    exit 1
fi
echo -e "${GREEN}Docker Compose 已安装。${NC}"

# 2. 引导用户配置 .env 文件
echo -e "${YELLOW}2. 检查并配置 .env 文件...${NC}"
ENV_FILE=".env"

if [ ! -f "$ENV_FILE" ]; then
    echo -e "${YELLOW}.env 文件不存在，将为您创建。${NC}"
    cp .env.example "$ENV_FILE" # 假设存在一个 .env.example 文件
    if [ $? -ne 0 ]; then
        echo -e "${RED}错误：无法创建 .env 文件。请手动创建或检查 .env.example 是否存在。${NC}"
        exit 1
    fi
fi

# 提示用户检查并编辑 .env
echo -e "${YELLOW}请检查并编辑 ${ENV_FILE} 文件，确保 DOCKER_USER, FRONTEND_VERSION, BACKEND_VERSION, SECRET_KEY 和数据库配置正确无误。${NC}"
echo -e "${YELLOW}编辑完成后，请按任意键继续...${NC}"
read -n 1 -s

# 3. 拉取最新 Docker 镜像
echo -e "${YELLOW}3. 拉取最新 Docker 镜像...${NC}"
docker compose pull
if [ $? -ne 0 ]; then
    echo -e "${RED}错误：拉取 Docker 镜像失败。请检查网络连接或 .env 中的镜像版本和 Docker Hub 用户名。${NC}"
    exit 1
fi
echo -e "${GREEN}Docker 镜像拉取成功。${NC}"

# 4. 启动所有服务容器
echo -e "${YELLOW}4. 启动所有服务容器...${NC}"
docker compose up -d
if [ $? -ne 0 ]; then
    echo -e "${RED}错误：启动服务失败。请检查 docker compose 日志。${NC}"
    exit 1
fi
echo -e "${GREEN}所有服务已成功启动。${NC}"

# 5. 执行数据库迁移
echo -e "${YELLOW}5. 执行数据库迁移...${NC}"
docker compose exec backend python manage.py migrate
if [ $? -ne 0 ]; then
    echo -e "${RED}错误：数据库迁移失败。请检查后端服务日志。${NC}"
    # 尽管失败，不立即退出，尝试继续创建超级用户
fi
echo -e "${GREEN}数据库迁移完成。${NC}"

# 6. 创建 Django 超级用户
echo -e "${YELLOW}6. 创建 Django 超级用户...${NC}"
docker compose exec backend python /app/init_superuser.py
if [ $? -ne 0 ]; then
    echo -e "${RED}警告：创建超级用户失败。可能超级用户已存在，或后端服务存在问题。${NC}"
fi
echo -e "${GREEN}创建超级用户操作完成。${NC}"

echo -e "${GREEN}### 项目部署完成！ ###${NC}"
echo -e "${GREEN}您可以使用 'docker compose ps' 查看服务状态。${NC}"
echo -e "${GREEN}如果遇到问题，请参考 DEPLOYMENT_MANUAL.md 进行故障排除。${NC}"