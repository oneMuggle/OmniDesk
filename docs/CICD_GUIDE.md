# CI/CD 与自动化部署指南

本文档旨在指导开发人员理解并使用基于 GitHub Actions 的持续集成 (CI) 与持续部署 (CD) 流程，实现从代码推送到自动化部署的端到端工作流。

## 1. 概述

本 CI/CD 流程的核心目标是实现完全自动化的软件交付生命周期：

- **阶段 1: 持续集成 (CI)**
  - **自动化构建**: 当代码推送到 `main` 分支时，由 [`.github/workflows/build-and-push-images.yml`](../.github/workflows/build-and-push-images.yml) 工作流自动构建生产环境的 Docker 镜像。
  - **集中存储**: 将构建好的镜像推送到 GitHub Container Registry (GHCR) 进行统一管理。

- **阶段 2: 持续部署 (CD)**
  - **自动化部署**: CI 成功后，由 [`.github/workflows/deploy-ssh-windows.yml`](../.github/workflows/deploy-ssh-windows.yml) 工作流自动接管，通过 SSH 连接到目标服务器并部署更新。

    > [!NOTE]
    > 请注意，此部署工作流并非由代码推送直接触发。它采用`workflow_run`事件，**仅在`build-and-push-images.yml`工作流成功完成之后**才会被自动触发。这种链式反应确保了只有在构建和推送镜像成功后，部署才会进行。

这个端到端的流程确保了代码的快速、可靠交付，并将开发人员从繁琐的手动部署任务中解放出来。

## 2. 完整自动化流程 (生产/预发环境)

### 步骤 1: 推送代码
当您完成一项功能开发或错误修复后，将您的代码提交并推送到 `main` 分支。
```bash
git add .
git commit -m "你的提交信息"
git push origin main
```

### 步骤 2: 监控自动化流程
代码推送后，GitHub Actions 将自动触发 CI/CD 流程。您可以访问您 GitHub 仓库的 `Actions` 标签页来实时查看进度：
1.  **"Build and Push Docker Images"** 工作流将首先运行，负责构建和推送镜像。
2.  该工作流成功后，**"Deploy to Windows Server via SSH"** 工作流将自动开始，负责部署。

等待两个工作流都成功执行完毕，您的最新代码就已经成功部署到服务器上。

## 3. 本地开发与测试流程

尽管生产环境的部署是全自动的，但在本地开发和测试时，您仍然可以利用 CI 构建的镜像来搭建一个与生产环境一致的测试环境。

### 步骤 1: 准备工作
在开始之前，请确保您的 `deployment/docker/docker-compose.yml` 文件已配置为使用 GHCR 的镜像，而不是本地构建。**请务必将 `YOUR_GITHUB_USERNAME` 替换为您的 GitHub 用户名或组织名。**

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

### 步骤 2: 拉取最新镜像
在您的代码被合并到 `main` 分支并且 CI 构建成功后，您可以在本地项目的 `deployment/docker/` 目录下，执行以下命令拉取最新的镜像：

```bash
docker-compose pull
```
此命令会从 GHCR 下载 `backend` 和 `frontend` 的最新镜像。

### 步骤 3: 启动服务进行测试
镜像拉取成功后，执行以下命令启动所有服务：

```bash
docker-compose up
```
现在，您可以在本地浏览器中访问应用，进行与生产环境一致的完整测试。

## 4. 总结

通过分离自动化部署流程和本地测试流程，我们既保证了生产环境部署的自动化和可靠性，又为开发人员提供了利用 CI 产物进行高效本地测试的灵活性。