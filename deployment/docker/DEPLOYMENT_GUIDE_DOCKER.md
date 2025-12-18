# Omni Desk Docker 部署指南

本文档将指导您如何使用 Docker 和 Docker Compose 在开发和生产环境中部署 Omni Desk 应用。

## 1. 开发环境

开发环境旨在提供一个快速、高效的开发体验，支持代码热重载。

### 1.1 启动开发环境

我们使用 `docker-compose.dev.yml` 文件来管理开发环境的服务。要启动所有服务，请在 `deployment/docker` 目录下运行以下命令：

```bash
docker-compose -f docker-compose.dev.yml up --build
```

这个命令会执行以下操作：
-   `--build`: 在启动容器前，会根据 `Dockerfile.dev` 构建 `backend` 和 `frontend` 服务的镜像。
-   `up`: 创建并启动 `db`, `redis`, `backend`, 和 `frontend` 四个服务。

### 1.2 代码热重载

为了实现热重载，我们在 `docker-compose.dev.yml` 文件中为 `backend` 和 `frontend` 服务配置了卷挂载（volumes）：

**后端 (backend):**
```yaml
services:
  backend:
    # ...
    volumes:
      - ../../omni_desk_backend:/app
```
这将您本地的 `omni_desk_backend` 目录挂载到容器内的 `/app` 目录。当您在本地修改后端代码时，更改会立即同步到容器中，Django 开发服务器会自动重新加载，使您的更改生效。

**前端 (frontend):**
```yaml
services:
  frontend:
    # ...
    volumes:
      - ../../omni_desk_frontend:/app
```
同样，`omni_desk_frontend` 目录被挂载到容器的 `/app` 目录。当您修改 React 代码时，Create React App 的开发服务器会检测到文件变化，并自动在浏览器中刷新页面。

## 2. 生产环境

生产环境的部署侧重于性能、安全和稳定性。代码会被打包到最终的 Docker 镜像中，而不是通过卷挂载。

### 2.1 构建和部署生产镜像

我们使用 `docker-compose.prod.yml` 和 `Dockerfile.prod` 文件来构建和部署生产环境。

在 `deployment/docker` 目录下，运行以下命令来构建和启动生产服务：

```bash
docker-compose -f docker-compose.prod.yml up --build -d
```

-   `--build`: 会根据 `Dockerfile.prod` 为 `backend` 和 `frontend` 构建生产镜像。
-   `-d`: (detached mode) 会在后台运行容器。

### 2.2 代码打包机制

与开发环境不同，生产镜像直接将应用程序代码和依赖项打包进去，以创建独立的、可移植的镜像。

**后端 (backend):**

在 `deployment/docker/omni_desk_backend/Dockerfile.prod` 中：
1.  `COPY ./omni_desk_backend/requirements-prod.txt .`: 复制生产环境所需的依赖文件。
2.  `RUN pip install ...`: 安装这些依赖。
3.  `COPY ./omni_desk_backend/ /app/`: 将整个 `omni_desk_backend` 项目目录复制到镜像的 `/app/` 目录中。
4.  `CMD ["gunicorn", ...]`: 使用 Gunicorn 作为 WSGI 服务器来运行 Django 应用。

**前端 (frontend):**

在 `omni_desk_frontend/Dockerfile.prod` 中，我们使用多阶段构建（multi-stage build）来优化镜像大小：

1.  **Build Stage**:
    *   `FROM node:18-alpine AS build`: 使用 Node.js 镜像作为构建环境。
    *   `COPY package.json ./` 和 `npm install`: 安装所有依赖。
    *   `COPY . .`: 复制所有前端源代码。
    *   `RUN npm run build`: 执行构建命令，生成优化的静态文件（HTML, CSS, JS）到 `/app/build` 目录。

2.  **Production Stage**:
    *   `FROM nginx:stable-alpine`: 使用一个轻量级的 Nginx 镜像作为最终的生产镜像。
    *   `COPY --from=build /app/build /usr/share/nginx/html`: **关键步骤** - 仅将上一个阶段生成的静态文件复制到 Nginx 的静态文件服务目录。源代码和 `node_modules` 都不会被包含在最终镜像中。
    *   `COPY nginx.conf ...`: 复制 Nginx 配置文件。
    *   `CMD ["nginx", ...]`: 启动 Nginx 服务器来提供前端静态文件。

通过这种方式，我们创建了两个优化的生产镜像：一个包含运行 Django 应用所需的一切，另一个则是一个非常小的、只包含静态文件和 Nginx 的前端镜像。

---
部署完成！