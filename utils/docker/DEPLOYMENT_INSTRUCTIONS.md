# Docker 应用独立部署与 Nginx 反向代理说明

本文档旨在说明如何独立启动各个 Docker 应用，并通过 Nginx 实现反向代理。

## 已完成的更改：

1.  **原始 Docker Compose 文件重命名**：
    `utils/docker/docker-compose.yml` 已重命名为 `utils/docker/old-docker-compose.yml`。
2.  **创建新的独立 Docker Compose 文件**：
    *   [`utils/docker/nginx-compose.yml`](utils/docker/nginx-compose.yml)
    *   [`utils/docker/backend-compose.yml`](utils/docker/backend-compose.yml)
    *   [`utils/docker/frontend-compose.yml`](utils/docker/frontend-compose.yml)
    *   [`utils/docker/dify-compose.yml`](utils/docker/dify-compose.yml)
    *   [`utils/docker/ragflow-compose.yml`](utils/docker/ragflow-compose.yml)
    这些文件现在包含了各自服务的定义，并配置为使用一个名为 `omni_desk_network` 的共享 Docker 网络。

## 新的启动流程：

为了独立启动各个应用并实现反向代理，请按照以下步骤操作：

1.  **创建共享网络**：
    在任何一个 Docker Compose 文件启动之前，您需要先手动创建共享网络。只需执行一次即可：
    ```bash
    docker network create omni_desk_network
    ```

2.  **独立启动各个服务**：
    在 `e:/ProgrammingData/vue/calendar/utils/docker/` 目录下，按以下顺序或您需要的顺序独立启动各个服务。每个命令都会在后台启动相应的服务：

    *   **启动后端服务 (数据库, Redis, Backend, Worker)**:
        ```bash
        docker compose -f backend-compose.yml up -d
        ```

    *   **启动前端服务**:
        ```bash
        docker compose -f frontend-compose.yml up -d
        ```

    *   **启动 Dify 服务**:
        ```bash
        docker compose -f dify-compose.yml up -d
        ```

    *   **启动 Ragflow 服务**:
        ```bash
        docker compose -f ragflow-compose.yml up -d
        ```

3.  **启动 Nginx 反向代理服务**：
    在所有您希望代理的服务都启动并运行后，启动 Nginx：
    ```bash
    docker compose -f nginx-compose.yml up -d
    ```

## 停止服务：

要停止某个服务，您可以使用相应的 `docker compose down` 命令。例如，要停止后端服务：
```bash
docker compose -f backend-compose.yml down
```

要停止所有服务和清理网络：
```bash
docker compose -f backend-compose.yml down
docker compose -f frontend-compose.yml down
docker compose -f dify-compose.yml down
docker compose -f ragflow-compose.yml down
docker compose -f nginx-compose.yml down
docker network rm omni_desk_network
```

这个新的设置允许您根据需要独立管理和部署每个应用，同时通过共享网络和 Nginx 实现统一的反向代理。