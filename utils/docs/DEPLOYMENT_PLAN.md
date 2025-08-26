# Docker化部署与Nginx反向代理计划

## 概述
本计划旨在指导如何在服务器上使用 Docker 部署多个项目，包括 `omni_desk`、`dify` 和 `ragflow`，并利用 Nginx 进行反向代理以避免端口冲突。所有生成的相关文件和说明文档将统一存放在 `utils` 目录下。

## 详细计划

### 阶段 1: 准备工作和文件结构

*   **目标**: 创建 `utils` 目录及其子目录，用于存放所有生成的文件。
*   **步骤**:
    *   在项目根目录创建 `utils` 目录。
    *   在 `utils` 目录下创建 `docker` 和 `nginx` 子目录。
    *   在 `utils/docker` 目录下创建 `dify` 和 `ragflow` 子目录。
    *   在 `utils` 目录下创建 `docs` 子目录。

### 阶段 2: `dify` 和 `ragflow` 的 Docker 集成

*   **目标**: 获取 `dify` 和 `ragflow` 的 Docker 部署信息，并将其整合到新的 `docker-compose.yml` 文件中。
*   **步骤**:
    *   **了解 `dify` 和 `ragflow` 的 Docker 部署方式**: 假设它们有标准的 `docker-compose.yml` 或 Dockerfile。
    *   **创建 `dify` 和 `ragflow` 的 `docker-compose.yml` 片段**: 创建示例的 `docker-compose.yml` 片段，其中包含它们的服务定义、端口映射和卷挂载。这些片段将考虑到端口冲突问题，并预留 Nginx 反向代理所需的内部端口。
    *   **创建新的主 `docker-compose.yml`**: 将 `omni_desk`、`dify` 和 `ragflow` 的服务整合到一个新的 `utils/docker/docker-compose.yml` 文件中。确保 `omni_desk` 的服务定义（db, redis, backend, frontend, worker）与您现有的一致，并调整端口映射以避免与 `dify` 和 `ragflow` 冲突。对于 `omni_desk_frontend`，将移除外部端口映射，因为 Nginx 将作为统一入口。

### 阶段 3: Nginx 反向代理配置

*   **目标**: 编写一个通用的 Nginx 配置文件，用于反向代理 `omni_desk`、`dify` 和 `ragflow`。
*   **步骤**:
    *   **创建 `utils/nginx/nginx.conf`**: 基于现有的 `omni_desk_frontend/nginx.conf`，扩展它以包含 `dify` 和 `ragflow` 的反向代理配置。
    *   **定义 Nginx Location**: 为每个服务（`omni_desk` 的 API、静态文件，以及 `dify` 和 `ragflow`）定义独立的 `location` 块，并将其代理到相应的 Docker 容器内部端口。
    *   **端口映射**: Nginx 将监听 80 端口，并通过不同的路径（例如 `/dify/`, `/ragflow/`, `/api/` 等）将请求转发到后端服务。

### 阶段 4: 编写说明文档

*   **目标**: 提供清晰的部署说明，指导用户如何使用这些文件进行部署。
*   **步骤**:
    *   **创建 `utils/docs/DEPLOYMENT_GUIDE.md`**: 包含以下内容：
        *   前置条件（Docker, Docker Compose 安装）。
        *   文件结构说明。
        *   `docker-compose.yml` 配置说明（包括环境变量）。
        *   Nginx 配置说明。
        *   部署步骤（构建镜像、启动容器、访问方式）。
        *   常见问题和故障排除。

### 阶段 5: 实施和验证（由用户执行）

*   **目标**: 用户根据提供的文档部署和验证。
*   **步骤**:
    *   用户将根据 `DEPLOYMENT_GUIDE.md` 进行操作。
    *   用户将检查所有服务是否正常运行，并通过 Nginx 访问。

## 关键考虑点和假设

*   **Dify 和 Ragflow 的内部端口**: 假设 Dify 和 Ragflow 在其 Docker 容器内部默认监听 80 端口。如果实际不是，用户可能需要根据它们的官方文档进行调整。
*   **Dify 和 Ragflow 的 Docker Image**: 将使用占位符来表示 Dify 和 Ragflow 的 Docker 镜像名称，用户需要根据实际情况替换。
*   **环境变量**: 考虑到 `.env` 文件，将在 `docker-compose.yml` 中使用环境变量，并说明用户需要创建或修改 `.env` 文件。
*   **数据持久化**: `dify` 和 `ragflow` 可能需要数据持久化，将在 `docker-compose.yml` 中为它们添加卷。

## Mermaid 图示

```mermaid
graph TD
    A[用户任务] --> B{分析现有配置};
    B --> C[读取 omni_desk 配置];
    C --> D[制定详细部署计划];
    D --> E[创建 utils 目录结构];
    E --> F[生成 utils/docker/docker-compose.yml];
    F --> G[生成 utils/nginx/nginx.conf];
    G --> H[生成 utils/docs/DEPLOYMENT_GUIDE.md];
    H --> I[提交计划给用户确认];
    I -- 用户确认 --> J[开始实施];
    I -- 用户修改 --> D;
    J --> K[切换到 Code 模式进行实现];