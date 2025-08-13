# 项目部署计划 - 基于 Docker Compose

## 1. 概述

本项目是一个全栈应用，包含前端 React 应用（`calendar_with_react`）和后端 Django REST Framework 应用（`DRFForVue`）。部署将基于 Docker 容器化技术和 Docker Compose 进行服务编排，部署目标系统为 Ubuntu 22.04 LTS。

## 2. 部署架构

本项目将采用以下部署架构：

```mermaid
graph TD
    subgraph 用户端
        A[浏览器]
    end

    subgraph 部署服务器 (Ubuntu 22.04 LTS)
        direction LR
        B(Nginx Container) -- 反向代理 --> C(Backend Container)
        B -- 静态文件服务 --> D(Frontend Container)
        C -- DB 连接 --> E(PostgreSQL Container)
        F[Docker Daemon] -- 管理 --> B & C & D & E
        G[Docker Compose] -- 编排 --> B & C & D & E
    end

    A -- HTTP/HTTPS --> B
```

*   **前端 (Frontend):** React 应用，打包成静态文件，由 Nginx 提供服务。
*   **后端 (Backend):** Django REST Framework 应用，使用 Waitress 作为 WSGI 服务器，处理 API 请求。
*   **数据库 (Database):** PostgreSQL，用于存储应用数据。
*   **Nginx:** 作为反向代理服务器，将外部请求路由到前端静态文件或后端 API 服务，并处理静态文件服务。
*   **Docker & Docker Compose:** 提供容器化环境和服务编排。

## 3. 部署流程

部署流程将遵循以下步骤：

1.  **环境准备:**
    *   在 Ubuntu 22.04 服务器上安装 Docker 和 Docker Compose。
    *   进行必要的系统配置（如防火墙规则、用户组权限等）。
2.  **项目准备:**
    *   克隆项目代码到部署服务器。
    *   配置 `.env` 文件，包括 Docker Hub 用户名、镜像版本、数据库连接信息等敏感配置。
3.  **Docker 镜像管理:**
    *   **构建和推送镜像:** 在开发环境中，使用项目提供的 `build.sh` 脚本构建前端和后端应用的 Docker 镜像，并将其推送到 Docker Hub 或私有仓库。
    *   **拉取镜像:** 在部署服务器上，通过 `docker-compose pull` 命令从 Docker Hub 拉取最新版本的镜像。
4.  **服务部署与管理:**
    *   使用 `docker-compose up -d` 命令启动所有服务容器。
    *   执行数据库迁移 (`python manage.py migrate`) 和创建超级用户 (`python /app/init_superuser.py`)。
    *   验证服务是否正常运行，检查容器日志。
5.  **日常维护:**
    *   **版本更新:** 更新 `.env` 文件中的版本号，重新构建和推送镜像，然后重新部署。
    *   **回滚操作:** 修改 `.env` 文件中的版本号为旧版本，然后重新部署。
    *   **数据备份与恢复:** 详细说明如何备份 PostgreSQL 数据库数据卷 (`postgres_data`) 以及如何从备份中恢复数据。
6.  **故障排除:**
    *   列举常见问题及其解决方案。

## 4. 部署手册内容规划

部署手册将以 Markdown 格式编写，包含以下主要章节：

### 4.1. 部署环境准备
*   安装 Docker
*   安装 Docker Compose
*   系统防火墙配置
*   必要的系统依赖和工具

### 4.2. 项目代码准备与配置
*   克隆项目仓库
*   配置 `.env` 文件详解（包括 `DOCKER_USER`, `FRONTEND_VERSION`, `BACKEND_VERSION`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `SECRET_KEY` 等）

### 4.3. Docker 镜像管理
*   `build.sh` 脚本使用说明
*   手动构建和推送镜像（可选）
*   在部署服务器拉取镜像

### 4.4. 服务部署与管理
*   启动所有服务 (`docker-compose up -d`)
*   查看服务状态 (`docker-compose ps`)
*   查看服务日志 (`docker-compose logs`)
*   停止和重启服务 (`docker-compose stop`, `docker-compose restart`)
*   数据库初始化（迁移和超级用户创建）
*   Nginx 配置解析 (`docker/nginx.conf` 作用说明)

### 4.5. 日常维护
*   **版本升级流程:** 详细步骤
*   **回滚到旧版本:** 详细步骤
*   **数据库数据卷备份与恢复:**
    *   备份数据卷的方法（使用 `docker cp` 或 `docker run --rm -v ...`）
    *   从备份恢复数据的方法
    *   定期备份策略建议

### 4.6. 故障排除
*   端口冲突
*   容器启动失败
*   网络连接问题
*   数据库连接问题
*   日志分析
*   常见错误信息及解决方案

### 4.7. 其他部署方式简介 (作为参考)
*   传统部署 (Bare Metal / VM)
*   Kubernetes 部署
*   平台即服务 (PaaS)
*   无服务器 (Serverless)

## 5. 部署工具规划

除了现有的 `build.sh` 脚本，我们还将考虑编写一个名为 `deploy.sh` 的 Shell 脚本，以简化部署流程。

### 5.1. `build.sh` (现有)
*   功能：构建前端和后端 Docker 镜像，并推送到 Docker Hub。

### 5.2. `deploy.sh` (新增)
*   **功能目标：**
    *   检查 Docker 和 Docker Compose 是否安装。
    *   引导用户配置 `.env` 文件（或使用默认值）。
    *   执行 `docker-compose pull` 拉取最新镜像。
    *   执行 `docker-compose up -d` 启动服务。
    *   执行数据库迁移和超级用户创建。
    *   提供简单的健康检查，确认服务是否可访问。
*   **实现细节：**
    *   使用 Shell 脚本编写。
    *   包含错误处理和用户友好的提示信息。

## 6. 计划确认

在开始编写部署手册和工具之前，请您审阅此计划。如果您对计划满意，或者有任何修改意见，请告知我。一旦计划确认，我将开始编写工作。