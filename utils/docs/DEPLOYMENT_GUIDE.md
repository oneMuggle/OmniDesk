# 部署指南：omni_desk、Dify 和 Ragflow 与 Nginx 反向代理

## 概述

本指南旨在提供在服务器上使用 Docker 和 Docker Compose 部署 `omni_desk`、`Dify` 和 `Ragflow` 项目的详细步骤。通过 Nginx 反向代理，所有服务将通过统一的 80 端口进行访问，避免端口冲突。

## 前置条件

在开始部署之前，请确保您的服务器已安装以下软件：

*   **Docker**: Docker 引擎，用于容器化应用程序。
    *   安装指南：[https://docs.docker.com/engine/install/](https://docs.docker.com/engine/install/)
*   **Docker Compose**: 用于定义和运行多容器 Docker 应用程序。
    *   安装指南：[https://docs.docker.com/compose/install/](https://docs.docker.com/compose/install/)

## 文件结构

所有部署相关的文件都将位于项目根目录下的 `utils` 目录中。

```
.
├── utils/
│   ├── docker/
│   │   ├── docker-compose.yml  # 包含 omni_desk, Dify, Ragflow 服务定义
│   │   ├── dify/               # Dify 相关的 Dockerfile 或配置 (可选，如果需要自定义构建)
│   │   └── ragflow/            # Ragflow 相关的 Dockerfile 或配置 (可选，如果需要自定义构建)
│   ├── nginx/
│   │   └── nginx.conf          # Nginx 反向代理配置文件
│   └── docs/
│       └── DEPLOYMENT_GUIDE.md # 本部署指南
├── omni_desk_backend/          # omni_desk 后端项目目录
├── omni_desk_frontend/         # omni_desk 前端项目目录
└── deployment/                 # 现有部署相关文件 (部分配置已迁移到 utils)
```

## 配置说明

### `utils/docker/docker-compose.yml`

该文件定义了所有服务的容器化配置，包括数据库 (PostgreSQL)、缓存 (Redis)、`omni_desk` 的后端、前端、Celery Worker，以及 `Dify` 和 `Ragflow` 服务。

*   **`omni_desk_db` (PostgreSQL)**: 数据库服务。
    *   通过 `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` 环境变量配置数据库凭据。
    *   数据将持久化到 `postgres_data` 卷。
*   **`omni_desk_redis` (Redis)**: 缓存服务。
*   **`omni_desk_backend`**: `omni_desk` 后端服务。
    *   使用 `deployment/docker/omni_desk_backend/Dockerfile` 构建镜像。
    *   通过 `env_file` 加载 `./deployment/docker/.env` 中的环境变量。
    *   内部暴露 8000 端口，供 Nginx 反向代理。
*   **`omni_desk_frontend`**: `omni_desk` 前端服务。
    *   使用 `omni_desk_frontend/Dockerfile` 构建镜像。
    *   内部暴露 80 端口，供 Nginx 反向代理。
    *   **注意**: 前端静态文件将直接由 Nginx 容器提供，而不是通过代理到此容器。此容器主要用于构建前端应用。
*   **`omni_desk_worker`**: `omni_desk` 的 Celery Worker 服务，用于处理异步任务。
*   **`dify`**: Dify 服务。
    *   `image`: 请替换为 Dify 的官方 Docker 镜像名称（例如 `langchain/dify:latest` 或特定版本）。
    *   `environment`: 根据 Dify 的官方文档配置必要的环境变量，特别是数据库连接信息。
    *   `volumes`: `dify_data` 卷用于数据持久化。
    *   内部暴露 80 端口（假设 Dify 默认监听 80 端口）。
*   **`ragflow`**: Ragflow 服务。
    *   `image`: 请替换为 Ragflow 的官方 Docker 镜像名称。
    *   `environment`: 根据 Ragflow 的官方文档配置必要的环境变量。
    *   `volumes`: `ragflow_data` 卷用于数据持久化。
    *   内部暴露 80 端口（假设 Ragflow 默认监听 80 端口）。
*   **`combined_nginx`**: Nginx 反向代理服务。
    *   将 `utils/nginx/nginx.conf` 挂载到容器的 `/etc/nginx/nginx.conf`。
    *   将 `omni_desk_frontend/build` 目录挂载到容器的 `/usr/share/nginx/html`，以便 Nginx 直接提供前端静态文件。
    *   将容器的 80 和 443 端口映射到主机的 80 和 443 端口。

### `utils/nginx/nginx.conf`

该文件配置 Nginx 作为所有服务的统一入口。

*   **`listen 80`**: Nginx 监听 80 端口。
*   **`server_name localhost`**: 请将其替换为您的实际域名（例如 `yourdomain.com`）。
*   **`location /`**: 处理 `omni_desk` 前端页面的请求，直接从 `/usr/share/nginx/html` 提供静态文件。
*   **`location /api/`**: 将 `omni_desk` 后端 API 请求反向代理到 `backend` 容器的 8000 端口。
*   **`location /static/`**: 将 `omni_desk` 后端静态文件请求反向代理到 `backend` 容器的 8000 端口。
*   **`location /admin/`**: 将 `omni_desk` 后端管理界面请求反向代理到 `backend` 容器的 8000 端口。
*   **`location /dify/`**: 将所有以 `/dify/` 开头的请求反向代理到 `dify_app` 容器的 80 端口。`rewrite` 规则用于移除 `/dify` 前缀。
*   **`location /ragflow/`**: 将所有以 `/ragflow/` 开头的请求反向代理到 `ragflow_app` 容器的 80 端口。`rewrite` 规则用于移除 `/ragflow` 前缀。

## 部署步骤

1.  **准备项目文件**:
    *   确保您的 `omni_desk_backend` 和 `omni_desk_frontend` 项目目录完整且包含所有必要的源代码和配置文件。
    *   将本指南中提到的 `utils` 目录及其内容（`docker/docker-compose.yml`, `nginx/nginx.conf`, `docs/DEPLOYMENT_GUIDE.md`）放置在您项目的根目录下。
    *   确保 `omni_desk_backend/requirements.txt` 和 `omni_desk_frontend/package.json` 存在且完整。

2.  **构建前端应用**:
    *   进入 `omni_desk_frontend` 目录，并执行以下命令构建前端静态文件：
        ```bash
        cd omni_desk_frontend
        npm install
        npm run build
        cd ..
        ```
    *   这将会在 `omni_desk_frontend` 目录下生成一个 `build` 文件夹，其中包含前端的静态资源。Nginx 将直接从这个 `build` 文件夹提供服务。

3.  **配置环境变量**:
    *   在项目根目录下的 `deployment/docker/.env` 文件中，根据您的实际情况配置数据库、Redis 和其他服务的环境变量。
    *   例如：
        ```ini
        POSTGRES_DB=omni_desk
        POSTGRES_USER=user
        POSTGRES_PASSWORD=password

        # Dify 数据库配置 (如果 Dify 使用自己的数据库，请相应配置)
        # DIFY_DB_URL=postgresql://difyuser:difypassword@db:5432/difydb

        # Dify 和 Ragflow 的 Docker 镜像用户（如果需要）
        # DOCKER_USER=your_docker_hub_username
        # BACKEND_VERSION=1.0.0
        # FRONTEND_VERSION=1.0.0
        ```
    *   **重要**: 对于 `Dify` 和 `Ragflow`，请查阅其官方文档以获取完整的环境变量列表和配置指南。

4.  **构建 Docker 镜像并启动服务**:
    *   打开终端，导航到项目根目录（包含 `utils` 目录的目录）。
    *   执行以下命令构建并启动所有服务：
        ```bash
        docker compose -f utils/docker/docker-compose.yml build
        docker compose -f utils/docker/docker-compose.yml up -d
        ```
    *   `build` 命令会根据 Dockerfile 构建 `omni_desk` 的后端和前端镜像。
    *   `up -d` 命令会在后台启动所有服务。

5.  **验证部署**:
    *   等待所有容器启动并运行。您可以使用 `docker ps` 命令查看容器状态。
    *   **访问 `omni_desk`**: 在浏览器中访问 `http://localhost` 或您的域名。您应该能看到 `omni_desk` 的前端页面。
    *   **访问 `omni_desk` API**: 尝试访问 `http://localhost/api/` 或您的域名下的 API 路径，验证后端是否正常工作。
    *   **访问 `Dify`**: 在浏览器中访问 `http://localhost/dify/` 或您的域名下的 `/dify/` 路径。您应该能看到 Dify 的界面。
    *   **访问 `Ragflow`**: 在浏览器中访问 `http://localhost/ragflow/` 或您的域名下的 `/ragflow/` 路径。您应该能看到 Ragflow 的界面。

## 常见问题与故障排除

*   **端口冲突**: 如果您在启动容器时遇到端口冲突，请检查 `docker-compose.yml` 中 `ports` 部分的映射，确保没有其他应用程序正在使用相同的端口。
*   **容器无法启动**:
    *   查看 `docker logs <container_name>` 命令的输出，了解具体的错误信息。
    *   检查 `.env` 文件中的环境变量是否正确配置。
    *   检查 Dockerfile 或 `docker-compose.yml` 中的路径是否正确。
*   **Nginx 反向代理问题**:
    *   检查 `utils/nginx/nginx.conf` 文件中的 `proxy_pass` 地址是否正确指向了 `docker-compose.yml` 中定义的服务名称和内部端口（例如 `http://backend:8000`）。
    *   确保 `location` 块的 `rewrite` 规则正确。
    *   查看 Nginx 容器的日志 `docker logs combined_nginx`。
*   **Dify/Ragflow 无法访问**:
    *   检查 `docker-compose.yml` 中 Dify/Ragflow 服务的 `image` 名称是否正确。
    *   检查 Dify/Ragflow 服务的环境变量是否根据其官方文档正确配置。
    *   查看 Dify/Ragflow 容器的日志。
*   **前端静态文件未找到**:
    *   确保您已执行 `npm run build` 并在 `omni_desk_frontend` 目录下生成了 `build` 文件夹。
    *   检查 `utils/docker/docker-compose.yml` 中 Nginx 服务的 `volumes` 部分，确保 `omni_desk_frontend/build` 正确挂载到 `/usr/share/nginx/html`。

如果您遇到任何其他问题，请参考 Docker、Docker Compose、Nginx 以及 Dify/Ragflow 的官方文档。