# Docker 部署指南

本文档提供了使用 Docker 和 Docker Compose 在不同环境中部署和运行此应用程序的说明。

## 先决条件

-   Docker
-   Docker Compose

## 核心概念

我们的 Docker 设置利用了 `docker-compose.yml` 作为基础配置文件，并结合环境特定的覆盖文件来实现灵活性和简洁性。

-   **`docker-compose.yml`**: 定义所有服务的核心结构和依赖关系。
-   **`docker-compose.override.yml`**: (默认加载) 包含所有本地开发的配置，如源码挂载、开发服务器端口和热重载。
-   **`docker-compose.prod.yml`**: 包含生产环境的特定配置，主要用于从容器镜像仓库拉取预构建的镜像。

## 本地开发

本地开发环境经过优化，可实现快速启动和热重载。

**启动开发环境:**

只需在 `deployment/docker` 目录下运行以下命令：

```bash
docker-compose up --build
```

-   `--build` 标志会强制重新构建镜像，以确保应用了最新的代码和依赖项更改。
-   Docker Compose 会自动加载 `docker-compose.yml` 和 `docker-compose.override.yml`。
-   服务将在后台启动。您可以通过以下地址访问它们：
    -   **前端**: http://localhost:3000
    -   **后端 API**: http://localhost:8000/api/

**停止开发环境:**

```bash
docker-compose down
```

## 生产部署

生产部署依赖于预先构建并推送到容器镜像仓库（如 GHCR）的镜像。

**部署步骤:**

1.  确保您的服务器上有所需的 `.env.production` 文件。
2.  从您的 CI/CD 流水线或手动将最新的镜像拉取到服务器上。
3.  在 `deployment/docker` 目录下运行以下命令启动服务：

```bash
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

-   `-f` 标志明确指定了要使用的配置文件。
-   `-d` 标志使服务在后台（分离模式）运行。

**停止生产服务:**

```bash
docker-compose -f docker-compose.yml -f docker-compose.prod.yml down
```

## CI/CD (持续集成/持续部署)

CI/CD 流水线负责自动化构建、测试和推送生产镜像。

1.  **构建和推送**: 流水线应使用 `docker build` 命令，并结合 `--target production` 标志来构建生产就绪的镜像。
2.  **镜像命名**: 在 CI 环境中，应设置 `REGISTRY` 和 `TAG` 环境变量，以正确标记要推送到生产镜像仓库的镜像。例如：
    ```bash
    export REGISTRY=ghcr.io/your-username
    export TAG=v1.2.3
    docker-compose build
    ```
3.  **推送**: 构建成功后，流水线将镜像推送到指定的 `REGISTRY`。