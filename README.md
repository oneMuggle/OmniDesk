# OmniDesk: 集成化业务管理平台

## 项目概述

OmniDesk 是一个全面的全栈业务管理平台，旨在简化各种组织运营。它采用基于 Django 的后端和基于 React 的前端，为管理文档、项目、传感器和用户提供了强大且可扩展的解决方案。

## 项目结构

该项目分为以下主要目录：

-   `omni_desk_backend/`: 包含 Django 后端应用程序，包括所有 API 端点、数据库模型和业务逻辑。
-   `omni_desk_frontend/`: 包含 React 前端应用程序，包括所有 UI 组件、页面和客户端逻辑。
-   `deployment/`: 包含用于部署应用程序的 Docker 配置文件。
-   `docs/`: 包含项目文档。
-   `utils/`: 包含项目的实用程序脚本。

## 先决条件

在开始之前，请确保您的系统上安装了以下软件：

-   **Python** (版本 3.8 或更高)
-   **Node.js** (版本 14 或更高)
-   **npm** 或 **yarn**
-   **Docker** 和 **Docker Compose** (用于容器化部署)
-   **PostgreSQL**
-   **Redis**

## 安装与设置

请按照以下步骤为后端和前端设置开发环境。

### 后端设置 (`omni_desk_backend`)

1.  **导航到后端目录：**
    ```bash
    cd omni_desk_backend
    ```

2.  **创建并激活虚拟环境：**
    ```bash
    python -m venv venv
    source venv/bin/activate  # 在 Windows 上，使用 `venv\Scripts\activate`
    ```

3.  **安装所需的 Python 包：**
    ```bash
    pip install -r requirements.txt
    ```

4.  **配置您的环境变量：**
    在 `omni_desk_backend` 目录中创建一个 `.env` 文件，并添加数据库、密钥等必要的配置。

5.  **应用数据库迁移：**
    ```bash
    python manage.py migrate
    ```

### 依赖管理 (`pip-tools`)

本项目的 Python 依赖项通过 `pip-tools` 进行管理，以确保在所有环境中保持一致性。

- **核心依赖项** 在 `omni_desk_backend/requirements.in` 中定义。
- **开发和测试依赖项** 在 `omni_desk_backend/requirements-dev.in` 中定义。

要更新依赖项，请执行以下步骤：

1.  **修改 `.in` 文件**: 在 `requirements.in` 或 `requirements-dev.in` 中添加或删除包。

2.  **重新生成 `requirements.txt` 和 `requirements-prod.txt`**:
    ```bash
    # 确保你已经安装了 pip-tools
    pip install pip-tools

    # 进入后端目录
    cd omni_desk_backend

    # 生成生产环境的依赖
    pip-compile -o requirements-prod.txt requirements.in

    # 生成开发环境的依赖
    pip-compile -o requirements.txt requirements-dev.in
    ```

**重要提示**: 请勿手动编辑 `requirements.txt` 或 `requirements-prod.txt` 文件。始终使用 `pip-compile` 来更新它们。
### 前端设置 (`omni_desk_frontend`)

1.  **导航到前端目录：**
    ```bash
    cd omni_desk_frontend
    ```

2.  **安装所需的 Node.js 包：**
    ```bash
    npm install
    # 或
    yarn install
    ```

## 运行项目

### 后端

要启动 Django 开发服务器，请从 `omni_desk_backend` 目录运行以下命令：

```bash
python manage.py runserver
```

后端 API 将在 `http://127.0.0.1:8000` 上可用。

### 前端

要启动 React 开发服务器，请从 `omni_desk_frontend` 目录运行以下命令：

```bash
npm start
# 或
yarn start
```

前端应用程序将在 `http://localhost:3000` 上可用。

## 部署

### 自动化部署 (CI/CD) - 推荐

本项目采用 GitHub Actions 进行持续集成与持续部署 (CI/CD)。

**推送流程 (推送到 `main` 分支):**

```
Push → 构建镜像 → 运行测试 → 推送至 GHCR → SSH 部署到服务器
```

**详细步骤:**
1. **自动构建**: [`.github/workflows/build-and-push-images.yml`](.github/workflows/build-and-push-images.yml) 自动构建 Docker 镜像并推送到 GitHub Container Registry (GHCR)
2. **自动部署**: [`.github/workflows/deploy-ssh-windows.yml`](.github/workflows/deploy-ssh-windows.yml) 通过 SSH 部署到 Windows 服务器

### Docker 部署

项目提供完整的 Docker 部署方案，详见 [部署指南](deployment/docker/DEPLOYMENT_GUIDE.md)。

**快速启动:**
```bash
cd deployment/docker
./deploy_docker.sh up          # 开发环境
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d  # 生产环境
```

**部署脚本功能:**
| 命令 | 说明 |
|------|------|
| `./deploy_docker.sh up` | 构建并启动所有服务 |
| `./deploy_docker.sh down` | 停止所有服务 |
| `./deploy_docker.sh logs [service]` | 查看日志 |
| `./deploy_docker.sh migrate` | 执行数据库迁移 |
| `./deploy_docker.sh collectstatic` | 收集静态文件 |

### 离线/内网部署

对于无法访问互联网的内网服务器:

```bash
# 1. 在有网环境打包镜像
cd deployment/docker
./build_and_export.sh

# 2. 传输 exported_images/ 目录到内网服务器

# 3. 在内网服务器部署
./deploy_offline.sh
```

详细说明请参考 [完整部署指南](deployment/docker/DEPLOYMENT_GUIDE.md)。

## 测试

### 单元测试

**后端测试:**
```bash
cd omni_desk_backend
pytest --cov=. --cov-fail-under=80
```

**前端测试:**
```bash
cd omni_desk_frontend
npm test
```

### Docker 集成测试

在提交代码前，建议运行 Docker 集成测试以确保所有服务正常工作：

```bash
# 运行完整的 Docker 集成测试
./scripts/test-docker-integration.sh
```

该脚本会自动执行以下测试：
1. ✅ 验证环境配置
2. ✅ 构建 Docker 镜像
3. ✅ 启动所有服务
4. ✅ 健康检查（后端、前端、数据库、Redis）
5. ✅ 测试登录 API
6. ✅ 测试受保护的 API 端点
7. ✅ 测试前端代理
8. ✅ 检查容器日志

### 辅助测试脚本

**配置验证:**
```bash
# 验证环境变量配置是否完整
./scripts/validate-config.sh
```

**日志检查:**
```bash
# 检查所有容器的日志
./scripts/check-container-logs.sh

# 检查特定服务的日志
./scripts/check-container-logs.sh backend
```

### CI/CD 测试

所有测试已集成到 GitHub Actions CI 流程中：

- **代码质量检查**: ruff (Python), ESLint (JavaScript)
- **单元测试**: pytest (后端), Jest (前端)
- **安全扫描**: bandit, pip-audit, npm audit
- **类型检查**: mypy
- **Docker 集成测试**: 完整的端到端测试

CI 会在每次推送和 PR 时自动运行，确保代码质量。

## 开发工作流

### 提交前检查清单

在提交代码前，请确保：

- [ ] 运行单元测试并通过
- [ ] 运行 Docker 集成测试并通过
- [ ] 检查代码风格（ruff/ESLint）
- [ ] 更新相关文档
- [ ] 无硬编码的配置（使用环境变量）

### 常见问题排查

**前端无法连接到后端 API:**
- 检查 `vite.config.js` 中的代理配置
- 确保 `VITE_API_PROXY_TARGET` 环境变量正确设置
- Docker 环境中应设置为 `http://backend:8000`

**数据库连接失败:**
- 检查 `.env` 文件中的数据库配置
- 确保数据库服务已启动：`docker compose ps`
- 查看数据库日志：`docker compose logs db`

**登录失败 (500 错误):**
- 检查前端代理配置
- 查看后端日志：`docker compose logs backend`
- 验证数据库迁移是否完整：`docker compose exec backend python manage.py migrate`

## 贡献指南

1. Fork 项目
2. 创建特性分支 (`git checkout -b feature/amazing-feature`)
3. 运行测试并确保通过
4. 提交更改 (`git commit -m 'Add amazing feature'`)
5. 推送到分支 (`git push origin feature/amazing-feature`)
6. 创建 Pull Request

## 许可证

本项目采用 MIT 许可证。详见 [LICENSE](LICENSE) 文件。

## 联系方式

项目维护者：[您的联系方式]

---

**提示**: 遇到问题请先查看 [常见问题排查](#常见问题排查) 部分，或提交 Issue。