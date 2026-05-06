# Docker 部署指南 (手动/遗留流程)

> ⚠️ **警告：这是一个遗留的部署指南**
>
> 本文档描述的流程是手动的，已被新的自动化 CI/CD 工作流取代。镜像构建和部署现在由 GitHub Actions 自动处理。
>
> - **自动化构建**: 镜像由 [`.github/workflows/build-and-push-images.yml`](../.github/workflows/build-and-push-images.yml) 自动构建并推送到 GitHub Container Registry (GHCR)。
> - **自动化部署**: 部署由 [`.github/workflows/deploy-ssh-windows.yml`](../.github/workflows/deploy-ssh-windows.yml) 自动执行。
>
> **建议您查阅最新的自动化部署文档：**
> - 了解完整的 CI/CD 流程，请参阅 [`docs/CICD_GUIDE.md`](./CICD_GUIDE.md)。
> - 了解详细的部署步骤，请参阅 [`docs/DEPLOYMENT_MANUAL.md`](./DEPLOYMENT_MANUAL.md)。

## 概述

本文档描述了如何手动使用 Docker Compose 在本地或服务器上部署 OmniDesk。这个流程在以下场景中可能仍然有用：
- 在没有 CI/CD 环境的情况下进行本地测试。
- 需要对特定版本进行调试。

## 手动部署流程

### 1. 拉取预构建的镜像

自动化 CI 流程会构建镜像并将其推送到 GHCR。您可以直接拉取这些镜像，而无需手动构建。

```bash
# 登录到 GitHub Container Registry
docker login ghcr.io -u YOUR_GITHUB_USERNAME -p YOUR_PERSONAL_ACCESS_TOKEN

# 从 docker-compose.prod.yml 拉取服务镜像
docker-compose -f deployment/docker/docker-compose.prod.yml pull
```

### 2. 启动服务

拉取镜像后，您可以使用 `docker-compose` 启动服务。

```bash
# 使用生产环境配置启动服务
docker-compose -f deployment/docker/docker-compose.prod.yml up -d
```

## (已归档) 手动构建镜像

以下是原始的手动构建流程，现已归档，不推荐使用。

### 1. 初始设置
```bash
# (已废弃) 添加执行权限
chmod +x build.sh

# (已废弃) 登录Docker Hub
docker login
```

### 2. 构建和推送镜像
```bash
# (已废弃) 构建并推送镜像到Docker Hub
./build.sh [版本号] [Docker Hub 用户名]
