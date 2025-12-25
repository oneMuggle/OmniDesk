# OmniDesk 整体架构分析

## 架构概览

### 系统定位
- **项目类型**: 全栈业务管理平台
- **业务领域**: 内部运营管理，包括人事、项目、文档、传感器数据、合规性等。
- **技术复杂度**: 中高。项目采用前后端分离架构，涉及多种技术栈（Python/Django, JS/React），并采用容器化部署和CI/CD流程。

### 架构目标
- **高性能**: 通过后端异步任务处理（Celery）和前端状态管理优化（React Query），确保关键操作的快速响应。
- **高可用**: 通过Gunicorn进行应用服务管理，并利用Docker容器化实现快速故障恢复和部署。
- **可扩展**: 后端采用模块化的Django App结构，前端采用功能切片的`features`目录结构，便于独立开发和扩展新功能。
- **易维护**: 清晰的代码分层，前后端分离的开发模式，以及通过`pip-tools`和`npm`进行的依赖管理，降低了维护成本。

## 系统架构设计

### 架构风格
#### 模块化单体架构 (Modular Monolith)
- **架构描述**: OmniDesk 采用的是一个模块化的单体架构。虽然前端和后端是分离的两个服务，但后端本身是一个单一的Django项目，内部通过多个独立的Django App（如 `personnel`, `projects`, `documents`）来划分业务模块。这种方式兼具了单体架构的部署简便性和微服务架构的模块化思想。
- **选择原因**: 
    - **开发效率**: 在项目初期和中小型团队中，单体架构可以更快地进行开发和迭代。
    - **部署简单**: 相对于复杂的微服务治理，单体应用的部署和运维更为直接。
    - **数据一致性**: 所有模块共享同一个数据库，易于保证数据的强一致性。
- **适用场景**: 适合业务逻辑紧密耦合、团队规模适中、需要快速迭代的企业级应用。
- **优缺点分析**: 
    - **优势**: 开发简单，部署方便，易于测试，数据一致性强。
    - **劣势**: 随着功能增加，代码库会变得庞大；技术栈单一，不利于引入新技术；单个模块的性能问题可能影响整个应用。

### 整体架构图
```mermaid
graph TB
    subgraph "用户/客户端"
        User[用户浏览器]
    end

    subgraph "接入与代理层"
        Nginx[Nginx]
    end

    subgraph "应用服务层"
        Frontend[React 前端服务 (Node.js)]
        Backend[Django 后端服务 (Gunicorn)]
        Worker[Celery 异步任务Worker]
    end
    
    subgraph "数据与中间件层"
        Postgres[(PostgreSQL 数据库)]
        Redis[(Redis 缓存/消息代理)]
    end

    User --> Nginx
    Nginx -- "/api" --> Backend
    Nginx -- "/" --> Frontend
    
    Frontend -- "API请求" --> Backend
    
    Backend -- "读写数据" --> Postgres
    Backend -- "读写缓存/发布任务" --> Redis
    
    Worker -- "获取任务" --> Redis
    Worker -- "读写数据" --> Postgres
```

### 架构分层说明
#### 接入层
- **Nginx**: 作为反向代理和负载均衡器。它将所有`/api`开头的请求转发到后端Django服务，其他请求则转发到前端React服务。同时，它也负责提供静态文件服务。

#### 应用服务层
- **前端服务 (omni_desk_frontend)**: 基于React构建的单页应用(SPA)，负责所有用户界面的渲染和交互。通过`features`目录按业务功能组织代码。
- **后端服务 (omni_desk_backend)**: 基于Django和Django Rest Framework构建的RESTful API服务。它包含了所有的核心业务逻辑，通过不同的Django App（如`users`, `projects`, `documents`等）实现模块化。
- **异步任务服务 (worker)**: 使用Celery实现的独立进程，通过Redis作为消息代理从后端服务接收任务，执行耗时的操作（如发送邮件、生成报告等），避免阻塞主应用。

#### 数据层
- **PostgreSQL**: 作为主关系型数据库，存储所有持久化的业务数据。
- **Redis**: 主要有两个作用：一是作为Celery的Broker，存储任务队列；二是作为应用缓存，存储热点数据以提高性能。

## 服务架构

### 模块设计 (Django Apps)
后端通过一系列Django App来组织业务逻辑，每个App对应一个核心业务域。
| 服务模块 (App) | 功能描述 |
|---|---|
| `users` | 用户管理、认证、权限控制 |
| `personnel` | 员工信息管理 |
| `projects` | 项目管理 |
| `documents` | 文档管理和处理 |
| `sensor_management` | 传感器数据管理 |
| `compliance` | 合规性管理 |
| `memos` | 备忘录功能 |
| `meeting_rooms` | 会议室预定 |
| ... | (其他业务模块) |

### 服务间通信
- **同步通信**: 前端和后端之间主要通过HTTP/RESTful API进行同步通信。
- **异步通信**: 后端服务通过向Redis任务队列中添加任务来与Celery Worker进行异步通信。

## 数据架构

### 数据存储架构
| 数据库类型 | 技术选型 | 用途 | 特点 |
|---|---|---|---|
| 关系数据库 | PostgreSQL | 存储核心业务数据，如用户信息、项目、文档等。 | 强一致性 (ACID), 支持复杂查询。 |
| 缓存/消息代理 | Redis | Celery任务队列，API响应缓存。 | 内存存储，高性能读写。 |

## 安全架构

### 认证授权架构
#### 身份认证
- **JWT认证**: 项目使用`djangorestframework-simplejwt`库实现基于JSON Web Token (JWT)的无状态认证。用户登录后，后端会签发一个access token和refresh token，前端在后续请求的HTTP Header中携带access token进行身份验证。

#### 权限控制
- **Django内置权限**: 利用Django的权限框架进行基本的模型级权限控制。
- **DRF权限类**: 可以在API视图中使用Django Rest Framework提供的权限类（如`IsAuthenticated`, `IsAdminUser`）或自定义权限类来控制API的访问。

## 部署架构

### 容器化架构
- **Docker**: 前后端应用以及数据库、缓存等依赖服务都通过Docker进行容器化。
- **Docker Compose**: 在`deployment/docker`目录中，使用`docker-compose.yml`文件来编排和管理开发及生产环境中的多个容器。

### 部署流水线 (CI/CD)
- **GitHub Actions**: 项目配置了`.github/workflows/ci-test.yml`，当代码推送到`test`分支时，会自动触发CI流程。
- **自动化测试**: CI流程会分别在Python和Node.js环境中安装依赖，并执行后端的`pytest`和前端的`npm test`，确保代码变更不会破坏现有功能。

## 总结

### 架构优势
- **职责清晰**: 前后端分离使得开发团队可以并行工作，技术栈选择更灵活。
- **模块化程度高**: 后端通过Django Apps，前端通过`features`目录，都实现了良好的业务模块划分，易于扩展和维护。
- **部署标准化**: 全面容器化的方案简化了环境配置和部署流程，保证了环境的一致性。

### 改进建议
- **服务拆分**: 对于未来可能变得特别复杂的模块（如`documents`或`sensor_management`），可以考虑将其从单体中拆分出来，演进为独立的微服务。
- **API网关**: 目前Nginx只做了简单的反向代理。未来可以引入功能更强大的API网关（如Kong, Traefik），来统一处理认证、限流、日志等横切关注点。
- **配置中心**: 敏感配置和应用配置目前通过环境变量和`.env`文件管理，未来可以引入专门的配置中心（如Consul, Apollo）进行集中管理。