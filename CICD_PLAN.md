# CI/CD 流水线设计方案

本文档旨在为 `omni-desk` 项目设计一个基于 GitHub Actions 的自动化持续集成与持续部署 (CI/CD) 流水线。

## 1. 整体工作流程

流水线将在代码推送到 `main` 分支时自动触发，并执行以下核心任务：

1.  **构建 Docker 镜像**: 并行构建后端和前端的生产环境 Docker 镜像。
2.  **推送镜像**: 将构建好的镜像分别标记版本并推送到容器镜像仓库 (例如 Docker Hub)。
3.  **部署到服务器**: 通过 SSH 安全连接到生产服务器，执行部署脚本，使用最新的镜像更新应用。

工作流程图如下所示：

```mermaid
graph TD
    A[Push to main] --> B{GitHub Actions CI/CD};
    B --> C[1. Checkout Code];
    C --> D{2. Build & Push Images};
    D --> E[Build & Push Backend];
    D --> F[Build & Push Frontend];
    E --> G{3. Deploy to Server};
    F --> G;
    G --> H[SSH to Server];
    H --> I[Pull Latest Images];
    I --> J[Run docker-compose up];
    J --> K[Cleanup Old Images];
    K --> L[✅ Deployment Complete];
```

## 2. GitHub Actions 工作流步骤 (`.github/workflows/cicd.yml`)

以下是推荐的 GitHub Actions 工作流文件中的关键步骤。

```yaml
name: CI/CD for Omni-Desk

on:
  push:
    branches:
      - main

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    steps:
      - name: 1. Checkout Code
        uses: actions/checkout@v4

      - name: 2. Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: 3. Login to Docker Hub
        uses: docker/login-action@v3
        with:
          username: ${{ secrets.DOCKER_USERNAME }}
          password: ${{ secrets.DOCKER_PASSWORD }}

      - name: 4. Generate Image Tags
        id: meta
        run: echo "tags=latest,${GITHUB_SHA::7}" >> $GITHUB_OUTPUT

      - name: 5. Build and Push Backend Image
        uses: docker/build-push-action@v5
        with:
          context: .
          file: ./deployment/docker/omni_desk_backend/Dockerfile
          push: true
          tags: ${{ secrets.DOCKER_USERNAME }}/omni-desk-backend:${{ steps.meta.outputs.tags }}

      - name: 6. Build and Push Frontend Image
        uses: docker/build-push-action@v5
        with:
          context: .
          file: ./omni_desk_frontend/Dockerfile
          push: true
          tags: ${{ secrets.DOCKER_USERNAME }}/omni-desk-frontend:${{ steps.meta.outputs.tags }}

      - name: 7. Deploy to Server via SSH
        uses: appleboy/ssh-action@v1.0.3
        with:
          host: ${{ secrets.SSH_HOST }}
          username: ${{ secrets.SSH_USER }}
          key: ${{ secrets.SSH_PRIVATE_KEY }}
          script: |
            # 将部署脚本内容放在这里或从仓库拉取
            # 为清晰起见，直接在此处定义
            set -e
            PROJECT_DIR="~/app/omni-desk"
            DOCKER_COMPOSE_FILE="deployment/docker/docker-compose.yml"
            ENV_FILE_PATH="deployment/docker/.env.production"

            cd $PROJECT_DIR || { echo "错误：项目目录 $PROJECT_DIR 不存在。"; exit 1; }
            
            echo "${{ secrets.SERVER_ENV_FILE }}" > $ENV_FILE_PATH
            
            docker-compose -f $DOCKER_COMPOSE_FILE pull
            docker-compose -f $DOCKER_COMPOSE_FILE up -d --remove-orphans --no-deps backend frontend worker
            docker image prune -f
            echo "✅ Deployment successful!"
```

## 3. 需要配置的 GitHub Secrets

为了确保流水线的正常运行，请在 GitHub 仓库的 `Settings > Secrets and variables > Actions` 中配置以下机密信息：

| Secret Name         | 描述                                                                                             | 示例值 (请替换为您的真实值)         |
| ------------------- | ------------------------------------------------------------------------------------------------ | ----------------------------------- |
| `DOCKER_USERNAME`   | 用于登录 Docker Hub 的用户名。                                                                   | `mydockeruser`                      |
| `DOCKER_PASSWORD`   | Docker Hub 的访问令牌 (Access Token)，**强烈建议使用令牌而非密码**。                              | `dckr_pat_...`                      |
| `SSH_HOST`          | 部署目标服务器的 IP 地址或域名。                                                                 | `123.45.67.89`                      |
| `SSH_USER`          | 用于 SSH 登录的用户名。                                                                          | `ubuntu`                            |
| `SSH_PRIVATE_KEY`   | 用于 SSH 免密登录的私钥。                                                                        | `-----BEGIN OPENSSH PRIVATE KEY...` |
| `SERVER_ENV_FILE`   | 服务器上 `deployment/docker/.env.production` 文件的完整内容，用于安全地传递环境变量。            | `POSTGRES_PASSWORD=secret...`       |

## 4. 服务器部署脚本 (`deploy.sh`)

以下脚本将在服务器上通过 SSH 执行，负责更新和重启服务。

```bash
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