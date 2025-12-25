# OmniDesk 开发与测试分析

## 开发环境分析

### 1.1 项目启动机制
项目采用基于Docker Compose的集成开发环境，可以一键启动整个应用所需的服务栈。

**启动命令清单**
| 服务 | 启动方式 | 配置文件 | 端口 (Host:Container) | 依赖关系 |
|---|---|---|---|---|
| **所有服务** | `docker-compose up` | `deployment/docker/docker-compose.yml` | - | - |
| Nginx | (由docker-compose启动) | `deployment/docker/nginx/nginx.conf` | `80:80` | `backend`, `frontend` |
| Backend | (由docker-compose启动) | `omni_desk_backend/` | `8000` (exposed) | `db`, `redis` |
| Database | (由docker-compose启动) | - | `5433:5432` | - |
| Redis | (由docker-compose启动) | - | `6379:6379` | - |
| Worker | (由docker-compose启动) | - | - | `db`, `redis` |

**本地开发启动流程 (不使用Docker)**
除了Docker，开发者也可以在本地分别启动前后端服务。

| 应用类型 | 启动命令 | 配置文件 | 端口 |
|---|---|---|---|
| Backend | `python manage.py runserver` | `omni_desk_backend/` | `8000` |
| Frontend | `npm start` | `omni_desk_frontend/` | `3000` |

**启动流程图 (Docker Compose)**
```mermaid
graph TD
    A[执行 `docker-compose up`] --> B{拉取/构建镜像};
    B --> C[启动 `db` (PostgreSQL) 容器];
    B --> D[启动 `redis` 容器];
    C -- 健康检查通过 --> E[启动 `backend` 容器];
    D -- 健康检查通过 --> E;
    D -- 健康检查通过 --> F[启动 `worker` 容器];
    C -- 健康检查通过 --> F;
    E --> G[启动 `nginx` 容器];
    G --> H[应用启动完成 @ http://localhost];
```

### 1.2 环境搭建
**环境依赖清单**
| 依赖类型 | 依赖名称 | 版本要求 | 安装方式 |
|---|---|---|---|
| 运行时 | Docker & Docker Compose | - | 官网下载安装 |
| 后端语言 | Python | 3.11 | `python:3.11-slim-bullseye` Docker镜像 |
| 前端语言 | Node.js | 18 | `node:18-alpine` Docker镜像 |
| 数据库 | PostgreSQL | 14 | `postgres:14-alpine` Docker镜像 |
| 缓存/消息队列 | Redis | 7 | `redis:7-alpine` Docker镜像 |

**环境变量配置**
项目的核心配置通过`deployment/docker/.env.production`文件注入到Docker容器中。关键变量包括：
- `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`: 数据库连接信息。
- `SECRET_KEY`: Django的安全密钥。
- `DJANGO_SETTINGS_MODULE`: 指定Django的设置文件。
- `DJANGO_ENV`: 区分生产和开发环境。

### 1.3 调试机制
- **后端 (Django)**: 在开发模式下（不使用Docker或使用`docker-compose.dev.yml`），Django会以Debug模式运行，提供详细的错误页面和堆栈跟踪。结合VSCode的Python插件，可以方便地进行断点调试。
- **前端 (React)**: `npm start`会启动一个带热重载的开发服务器。开发者可以使用浏览器的开发者工具（如Chrome DevTools）进行元素检查、网络分析和JavaScript断点调试。React DevTools浏览器扩展也为组件层级和状态检查提供了便利。

## 测试环境分析

### 2.1 测试框架
| 测试目标 | 框架 | 配置文件 | 测试文件命名 |
|---|---|---|---|
| **后端** | `pytest` | `omni_desk_backend/pytest.ini` | `tests.py`, `test_*.py`, `*_tests.py` |
| **前端** | `Jest` | `omni_desk_frontend/jest.config.js` | `*.test.js`, `*.spec.js` |

- **Pytest 配置**: `pytest.ini`文件指定了Django的设置模块 (`omni_desk_backend.settings.base`) 和测试文件的发现规则。
- **Jest 配置**: `jest.config.js`配置了测试环境为`jsdom`（模拟浏览器环境），并使用`babel-jest`来转换JS/JSX代码。`setupTests.js`文件提供了一些全局的mock（如`matchMedia`, `Notification`），以确保在Node.js测试环境中依赖浏览器API的组件能够正常渲染。

### 2.2 测试运行机制
**测试命令清单**
| 测试目标 | 执行命令 | 描述 |
|---|---|---|
| 后端 | `pytest` | 在`omni_desk_backend`目录下运行，执行所有符合命名规则的测试。 |
| 前端 | `npm test` | 在`omni_desk_frontend`目录下运行，启动Jest的交互式测试运行器。 |
| CI/CD | `npm test -- --watchAll=false` | 在CI环境中非交互式地运行所有前端测试。 |

**CI/CD中的测试流程 (`.github/workflows/build-and-push-images.yml`)**
1.  **触发**: 当代码推送到`main`分支时触发。
2.  **`test` Job**:
    - **启动服务**: 启动一个临时的PostgreSQL数据库容器，专供后端测试使用。
    - **前端测试**: 安装npm依赖并运行`npm test -- --watchAll=false`。
    - **后端测试**: 安装pip依赖并运行`pytest`。环境变量`DATABASE_URL`被设置为指向CI启动的测试数据库。
3.  **`build-and-push` Job**: 只有在`test` Job成功完成后，此Job才会执行，确保了代码质量。

### 2.3 测试组织结构
- **后端**: 测试文件通常与被测试的Django App放在同一个目录下，或在一个专门的`tests`子目录中。例如，`users`模块的测试可能在`users/tests.py`或`users/test_users.py`中。
- **前端**: 测试文件通常与被测试的组件或页面放在一起，并以`.test.js`为后缀。例如，`ProjectsPage.jsx`的测试文件是`ProjectsPage.test.js`。这种"co-location"的方式使得测试和组件代码的管理更加方便。
