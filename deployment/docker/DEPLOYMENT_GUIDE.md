# Docker 部署指南

本文档提供了使用 Docker 和 Docker Compose 在本地开发和生产环境中部署 OmniDesk 应用程序的详细说明。

## 1. 架构概述

本部署方案采用多容器架构，通过 `docker-compose` 进行编排。主要服务包括：

*   **`db`**: PostgreSQL 数据库，用于持久化存储应用数据。
*   **`redis`**: Redis 服务，用作 Celery 的消息代理和结果后端。
*   **`backend`**: Django 后端应用程序。
*   **`frontend`**: React 前端应用程序。
*   **`worker`**: Celery 后台任务处理进程。
*   **`nginx`**: Nginx 反向代理，作为应用的统一入口，负责流量分发和静态文件服务。

## 2. 环境准备

在开始之前，请确保您的系统已安装以下软件：

*   [Docker](https://www.docker.com/get-started)
*   [Docker Compose](https://docs.docker.com/compose/install/)

## 3. 环境变量配置

项目通过 `.env` 文件管理环境变量。不同的环境使用不同的文件：

*   **开发环境**: 复制或重命名 `.env` 文件进行配置。此文件包含了本地开发所需的默认配置。
*   **生产环境**: 复制或重命名 `.env.production` 文件进行配置。此文件用于生产部署，请务必将数据库密码、`SECRET_KEY` 等敏感信息替换为安全的值。

**关键环境变量**:
*   `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`: 数据库连接信息。
*   `SECRET_KEY`: Django 的安全密钥。
*   `DEBUG`: `True` 用于开发，`False` 用于生产。
*   `ALLOWED_HOSTS`: 允许访问应用的主机列表。

## 4. 部署流程

项目提供了一个便捷的 `deploy_docker.sh` 脚本来简化开发环境的部署操作。

### 4.1. 开发环境部署

在开发环境中，代码会从本地文件系统挂载到容器中，实现热重载。

1.  **确保 `.env` 文件已配置。**
2.  **构建并启动服务**:
    ```bash
    ./deployment/docker/deploy_docker.sh up
    ```
    此命令会：
    *   使用 `docker-compose.yml` 和 `docker-compose.override.yml`。
    *   从本地源代码构建 `backend` 和 `frontend` 镜像。
    *   启动所有服务。

3.  **执行数据库迁移**:
    ```bash
    ./deployment/docker/deploy_docker.sh migrate
    ```

4.  **访问应用**:
    *   前端应用: `http://localhost`
    *   后端 API: `http://localhost/api/`

### 4.2. 生产环境部署

在生产环境中，应用会使用预构建的、经过优化的 Docker 镜像。

1.  **确保 `.env.production` 文件已配置。**
2.  **拉取或构建生产镜像**:
    *   **选项 A (推荐): 从镜像仓库拉取**
        ```bash
        docker-compose -f deployment/docker/docker-compose.yml -f deployment/docker/docker-compose.prod.yml pull
        ```
    *   **选项 B: 本地构建生产镜像**
        ```bash
        docker-compose -f deployment/docker/docker-compose.yml -f deployment/docker/docker-compose.prod.yml build
        ```

3.  **启动服务**:
    ```bash
    docker-compose -f deployment/docker/docker-compose.yml -f deployment/docker/docker-compose.prod.yml up -d
    ```

4.  **执行数据库迁移和静态文件收集**:
    ```bash
    # 数据库迁移
    docker-compose -f deployment/docker/docker-compose.yml -f deployment/docker/docker-compose.prod.yml exec backend python manage.py migrate

    # 收集静态文件
    docker-compose -f deployment/docker/docker-compose.yml -f deployment/docker/docker-compose.prod.yml exec backend python manage.py collectstatic --noinput
    ```

5.  **访问应用**:
    *   应用将通过 Nginx 监听在 `80` 端口。

## 5. 常用命令 (`deploy_docker.sh`)

*   **启动所有服务**:
    `./deployment/docker/deploy_docker.sh up`
*   **停止并移除所有服务**:
    `./deployment/docker/deploy_docker.sh down`
*   **查看服务日志**:
    `./deployment/docker/deploy_docker.sh logs`
    `./deployment/docker/deploy_docker.sh logs backend`
*   **强制重新构建镜像**:
    `./deployment/docker/deploy_docker.sh build`

## 6. 镜像构建详解

后端镜像 (`omni_desk_backend/Dockerfile`) 采用了多阶段构建，以优化镜像大小和构建速度：

*   **`builder` 阶段**: 将 Python 依赖预编译为 wheel 文件。
*   **`production` 阶段**: 从 `builder` 阶段复制预编译的依赖进行安装，避免了在生产镜像中保留编译工具，并加快了安装速度。
*   **`development` 阶段**: 用于开发，直接安装所有依赖并挂载源代码。

## 7. 内网（离线）部署流程

对于无法访问外部互联网的内网服务器，可以采用以下离线部署流程。

### 步骤 1：在有网环境打包镜像

首先，在一台可以访问互联网的机器上，构建并导出所有需要的 Docker 镜像。

1.  **确保 Docker 环境已就绪。**
2.  **进入 `deployment/docker` 目录。**
3.  **运行打包脚本**:
    ```bash
    ./build_and_export.sh
    ```
    该脚本会：
    *   使用 `docker-compose.build.yml` 构建生产版本的 `backend` 和 `frontend` 镜像。
    *   拉取 `postgres`, `redis`, `nginx` 的官方镜像。
    *   将所有五个镜像分别保存为 `.tar` 文件，并存放在 `exported_images` 目录下。

### 步骤 2：传输文件到内网服务器

将以下文件和目录从打包环境完整地传输到内网的 Ubuntu 服务器上：

*   `exported_images/` (整个目录)
*   `docker-compose.yml`
*   `docker-compose.prod.yml`
*   `.env.production` (请确保已根据内网环境修改配置)
*   `nginx/` (整个目录)
*   `deploy_offline.sh`

建议将这些文件统一放在服务器上的一个部署工作目录中，例如 `/opt/omni-desk-deployment`。

### 步骤 3：在内网服务器上部署

在内网服务器上，执行以下操作：

1.  **确保服务器已安装 Docker 和 Docker Compose。**
2.  **进入部署工作目录。**
3.  **为脚本添加执行权限**:
    ```bash
    chmod +x deploy_offline.sh
    ```
4.  **运行离线部署脚本**:
    ```bash
    ./deploy_offline.sh
    ```
    该脚本会：
    *   从 `exported_images` 目录下的 `.tar` 文件加载所有 Docker 镜像到本地。
    *   使用 `docker-compose.yml` 和 `docker-compose.prod.yml` 在后台启动所有服务。

5.  **首次部署的收尾工作**:
    如果这是第一次部署，您需要手动执行数据库迁移和静态文件收集。
    ```bash
    # 数据库迁移
    docker-compose -f docker-compose.yml -f docker-compose.prod.yml exec backend python manage.py migrate

    # 收集静态文件
    docker-compose -f docker-compose.yml -f docker-compose.prod.yml exec backend python manage.py collectstatic --noinput
    ```

部署完成后，应用程序即可在内网服务器上访问。