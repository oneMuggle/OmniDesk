# OmniDesk: 集成化业务管理平台

## 项目概述

OmniDesk 是一个全面的全栈业务管理平台，旨在简化各种组织运营。它采用基于 Django 的后端和基于 React 的前端，为管理文档、项目、传感器和用户提供了强大且可扩展的解决方案。

## 项目结构

该项目分为以下主要目录：

-   `omni_desk_backend/`: 包含 Django 后端应用程序，包括所有 API 端点、数据库模型和业务逻辑。
-   `omni_desk_frontend/`: 包含 React 前端应用程序，包括所有 UI 组件、页面和客户端逻辑。
-   `deployment/`: 包含用于部署应用程序的配置文件和脚本。它包括 Docker、Gunicorn 和 Nginx Unit 的选项。
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

该项目包括多种部署选项：

-   **Docker**: 部署应用程序最简单的方法是使用 `deployment/docker/` 目录中提供的 Docker Compose 配置。只需运行 `docker-compose up` 即可构建并启动容器。
-   **Gunicorn/Unit**: 对于更传统的部署，您可以使用 Gunicorn 来为 Django 应用程序提供服务，并使用像 Nginx 这样的 Web 服务器。`deployment/source/` 目录中提供了配置示例和脚本。