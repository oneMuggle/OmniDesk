# CI/CD 自动化构建与本地测试操作手册

本文档旨在指导开发人员如何使用基于 GitHub Actions 的持续集成（CI）流程，以实现自动化构建 Docker 镜像，并在本地环境中快速拉取和测试。

## 1. 概述

本 CI/CD 流程的核心目标是：
- **自动化构建**: 当代码推送到 `main` 分支时，自动构建前端和后端的生产环境 Docker 镜像。
- **集中存储**: 将构建好的镜像推送到 GitHub Container Registry (GHCR) 进行统一管理。
- **提升效率**: 开发者无需在本地执行耗时的 `docker build` 命令，只需拉取（`pull`）最新镜像即可进行测试，从而实现开发与构建的并行。

## 2. 准备工作

在开始之前，请确保您已完成以下准备工作：

1.  **修改 `docker-compose.yml`**:
    打开 `deployment/docker/docker-compose.yml` 文件，将 `backend` 和 `frontend` 服务的 `build` 配置替换为 `image` 配置。**请务必将 `YOUR_GITHUB_USERNAME` 替换为您的 GitHub 用户名或组织名。**

    ```yaml
    # deployment/docker/docker-compose.yml

    services:
      backend:
        # build: ... (确保这部分已被删除或注释)
        image: ghcr.io/YOUR_GITHUB_USERNAME/omni-desk-backend:latest
        # ...

      frontend:
        # build: ... (确保这部分已被删除或注释)
        image: ghcr.io/YOUR_GITHUB_USERNAME/omni-desk-frontend:latest
        # ...
    ```

2.  **Docker 环境**: 确保您的本地开发环境已正确安装并运行 Docker 和 Docker Compose。

## 3. 开发与测试流程

### 步骤 1: 推送代码

当您完成一项功能开发或错误修复后，将您的代码提交并推送到 `main` 分支。

```bash
git add .
git commit -m "你的提交信息"
git push origin main
```

### 步骤 2: 监控 CI/CD 流程

代码推送后，GitHub Actions 将自动触发名为 "Build and Push Docker Images" 的工作流。您可以访问您 GitHub 仓库的 `Actions` 标签页来实时查看构建进度。

等待该工作流执行成功。

### 步骤 3: 拉取最新镜像

当工作流成功完成后，回到您本地项目的 `deployment/docker/` 目录下，在终端中执行以下命令，拉取刚刚由 CI/CD 构建的最新镜像：

```bash
docker-compose pull
```

此命令会从 GHCR 下载 `backend` 和 `frontend` 的最新镜像。

### 步骤 4: 启动服务进行测试

镜像拉取成功后，执行以下命令启动所有服务：

```bash
docker-compose up
```

现在，您可以在本地浏览器中访问应用，进行与生产环境一致的完整测试。

## 4. 总结

通过遵循此流程，您可以将耗时的构建任务外包给 GitHub Actions，从而显著缩短本地测试的准备时间，提高整体开发效率。