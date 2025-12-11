# OmniDesk 开发与测试分析

## 1. 开发环境分析

### 1.1 项目启动机制

OmniDesk 是一个前后端分离的项目，需要分别启动后端和前端开发服务器。

#### 启动命令清单
| 应用类型 | 启动命令 | 配置文件 | 端口 | 依赖关系 |
|---|---|---|---|---|
| **后端 (Django)** | `python manage.py runserver` | `omni_desk_backend/settings/base.py` | 8000 | PostgreSQL, Redis |
| **前端 (React)** | `npm start` 或 `yarn start` | `omni_desk_frontend/package.json` | 3000 | 后端API |

#### 启动流程
```mermaid
graph TD
    subgraph "前提：基础服务"
        A[启动 PostgreSQL]
        B[启动 Redis]
    end

    subgraph "后端启动"
        C[cd omni_desk_backend] --> D[激活Python虚拟环境]
        D --> E[python manage.py migrate]
        E --> F[python manage.py runserver]
    end

    subgraph "前端启动"
        G[cd omni_desk_frontend] --> H[npm install]
        H --> I[npm start]
    end

    A --> F
    B --> F
    F --> I
```
**说明**:
1.  必须先确保 PostgreSQL 和 Redis 服务正在运行。
2.  启动后端 Django 服务器，它将监听 8000 端口。
3.  启动前端 React 开发服务器，它将监听 3000 端口，并通过 `proxy` 配置将 API 请求转发到后端的 8000 端口。

### 1.2 环境搭建

环境搭建流程在项目根目录的 `README.md` 文件中有详细说明。

#### 环境依赖清单
| 依赖类型 | 依赖名称 | 版本要求 | 安装方式 |
|---|---|---|---|
| 运行时 | Python | 3.8+ | 系统安装 |
| 运行时 | Node.js | 14+ | 系统安装 |
| 包管理 | pip | - | Python自带 |
| 包管理 | npm / yarn | - | Node.js自带 |
| 数据库 | PostgreSQL | - | Docker 或 系统安装 |
| 缓存/消息代理 | Redis | - | Docker 或 系统安装 |
| 容器化 | Docker & Docker Compose | - | 系统安装 |

#### 环境变量配置
后端应用通过 `.env` 文件加载环境变量。开发者需要在 `omni_desk_backend/` 目录下创建一个 `.env` 文件来配置关键信息，例如：
```bash
# .env file example
SECRET_KEY='your-django-secret-key'
DATABASE_URL='postgres://user:password@localhost:5432/omni_desk'
CELERY_BROKER_URL='redis://localhost:6379/0'
CELERY_RESULT_BACKEND='redis://localhost:6379/0'
OLLAMA_BASE_URL='http://localhost:11434'
```

### 1.3 调试机制
- **后端 (Django)**:
    - **标准调试**: 可以使用 `print()` 语句或 Python 的 `logging` 模块在开发服务器的控制台输出信息。
    - **VSCode 调试**: 可以在 `.vscode/launch.json` 中配置调试器，附加到 `manage.py runserver` 进程上，从而实现断点调试。
- **前端 (React)**:
    - **浏览器开发者工具**: 使用 Chrome 或 Firefox 的开发者工具进行元素检查、网络请求分析和 JavaScript 控制台调试。
    - **React DevTools**: 浏览器扩展，用于检查 React 组件的层次结构、Props 和 State。
    - **VSCode 调试**: 可以在 `.vscode/launch.json` 中配置 "Launch Chrome" 任务，以在 VSCode 中直接调试前端代码。

## 2. 测试环境分析

### 2.1 测试框架与配置

#### 后端测试
- **框架**: **Pytest** 与 **pytest-django**。
- **配置文件**: `omni_desk_backend/pytest.ini`。
    - `DJANGO_SETTINGS_MODULE`: 指定测试时使用的 Django 配置文件为 `omni_desk_backend.settings.base`。
    - `python_files`: 定义了测试文件的命名规则（`tests.py`, `test_*.py`, `*_tests.py`）。
- **依赖**: `requirements.txt` 中包含了 `pytest`, `pytest-django`, 和 `coverage`。

#### 前端测试
- **框架**: **Jest**。由 `react-scripts` 内置和配置。
- **配置文件**: `omni_desk_frontend/package.json` 中的 `jest` 字段。
    - `transformIgnorePatterns`: 配置了对 `node_modules` 中某些包（如 `axios`）进行Babel转译，以解决模块格式问题。
- **测试库**:
    - `@testing-library/react`: 用于组件的渲染和交互测试。
    - `@testing-library/jest-dom`: 提供自定义的DOM断言。

### 2.2 测试运行机制

#### 后端测试
- **命令**: 在 `omni_desk_backend` 目录下运行 `pytest`。
- **执行**: Pytest 会自动发现并执行所有符合 `pytest.ini` 中 `python_files` 规则的测试文件。
- **数据库**: `pytest-django` 会为测试创建一个独立的、临时的测试数据库，以确保测试与开发数据库隔离。测试结束后，该数据库会被销毁。
- **覆盖率**: 可以通过 `pytest --cov` 命令来生成代码覆盖率报告。

#### 前端测试
- **命令**: 在 `omni_desk_frontend` 目录下运行 `npm test` 或 `yarn test`。
- **执行**: 这会启动 Jest 的交互式观察模式（watch mode），它会自动运行自上次提交以来发生更改的文件的测试。
- **覆盖率**: 运行 `npm test -- --coverage` 来生成覆盖率报告。
- **超时设置**: `package.json` 中的 `test` 脚本设置了 `testTimeout=30000`，将测试的默认超时时间延长到30秒。

### 2.3 测试组织结构

- **后端**: 测试文件通常位于各个Django App的目录内，命名为 `tests.py` 或 `test_<feature>.py`。例如，`omni_desk_backend/users/test_users.py`。
- **前端**: 测试文件通常与被测试的组件文件放在一起，或者放在 `__tests__` 目录下，并以 `.test.js` 或 `.spec.js` 结尾。例如，一个 `MyComponent.jsx` 的测试文件可能是 `MyComponent.test.js`。