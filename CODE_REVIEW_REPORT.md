# 代码审查报告

**审查日期:** 2025-12-08

---

## 1. 概述

本报告旨在对 `omni-desk` 项目进行全面的代码审查。审查范围包括项目结构、后端（Django）、前端（Vue）、部署配置（Docker & Nginx）、文档及辅助脚本。

## 2. 审查计划

- **[进行中] 1. 制定审查计划并初始化报告**
- **[待办] 2. 分析项目整体结构**
- **[待办] 3. 审查后端代码 (Django)**
- **[待办] 4. 审查前端代码 (Vue)**
- **[待办] 5. 审查部署配置 (Docker & Nginx)**
- **[待办] 6. 审查文档和辅助脚本**
- **[待办] 7. 总结发现并提出改进建议**
- **[待办] 8. 生成并保存最终的审查报告**

---

## 3. 审查发现

*本部分将在审查过程中逐步填充。*

### 3.1. 项目结构

项目采用单体仓库（monorepo）模式，包含独立的前后端应用、部署脚本和文档。

- **服务编排**: 使用 Docker Compose 定义了 `db` (PostgreSQL), `redis`, `backend` (Django), `frontend` (React), 和 `worker` (Celery) 服务。
- **反向代理**: 存在两个 Nginx 实例：一个作为全局反向代理 (`nginx_proxy`)，另一个在 `frontend` 容器内部，负责 API 代理和静态文件服务。

**发现的问题**:

1.  **架构冗余**: 双重 Nginx 设计增加了不必要的复杂性。外部 Nginx 将 `/omni/` 流量转发到 `frontend` 服务，而 `frontend` 内部的 Nginx 又进行了一次路由和代理。这违反了单一职责原则，并使流量路径难以追踪。
2.  **配置不一致**: 前端 `package.json` 中的 `proxy` 配置用于开发环境，但在生产 Docker 构建中无效。同时，前端 Nginx 配置中硬编码了 IP 地址 (`113.44.214.144`)，降低了可移植性。
3.  **依赖问题**: `package.json` 同时引入了 `react-query` 和 `@tanstack/react-query`，可能导致版本冲突和不一致性。 **(已解决)**
4.  **端口冲突**: 根 `docker-compose.yml` 中的 `nginx` 服务和 `deployment/docker/docker-compose.yml` 中的 `frontend` 服务都试图绑定到主机的 80 端口，这在同时运行时会失败。

### 3.2. 后端 (Django)

后端基于 Django 4.2 和 Django Rest Framework 构建，采用了模块化的应用设计。

**依赖与配置发现**:

1.  **依赖管理问题**: `requirements.txt` 中部分依赖（`pypinyin`, `holidays`, `coverage`）未固定版本，可能导致构建不一致。同时，`holidays` 依赖重复，且测试依赖（`pytest`, `coverage`）与生产依赖混合。
2.  **安全配置风险**:
    *   `SECRET_KEY` 存在不安全的默认值，如果在生产环境中未通过环境变量覆盖，将导致严重安全漏洞。
    *   CORS 配置过于宽松 (`CORS_ALLOW_CREDENTIALS = True` 且未限制来源)，允许任何域名的凭证请求，极易受到 CSRF 攻击。
3.  **JWT 有效期过长**: 访问令牌（Access Token）的有效期设置为 7 天，增加了令牌被盗用后的风险。建议缩短有效期，并依赖刷新令牌（Refresh Token）机制。
4.  **配置不一致**: `settings.py` 的注释表明项目由 Django 3.2 初始化，但实际使用的是 4.2 版本，显示项目维护存在疏漏。

**用户与权限模块 (`users` app)**:

1.  **混合且混乱的权限系统**: 项目同时使用了基于 `role` 字段的硬编码权限和 Django 内置的 `Group`/`Permission` 系统。这种混合模式极大地增加了复杂性和维护成本。**建议**: 废弃硬编码的 `role` 字段，完全迁移到 Django 内置的、基于角色的权限控制（RBAC）系统。
2.  **不灵活的 Token 权限**: 在 JWT 中硬编码权限列表，导致用户权限变更后，旧 Token 在有效期内依然有效，存在安全隐患且缺乏灵活性。
3.  **逻辑分散**: 业务逻辑（如更新用户关联的 `personnel` 信息）被直接写在视图 (`UserAdminDetailView`) 中，而不是遵循 "Fat Models, Thin Views" 的原则，将其封装在模型或序列化器中。
4.  **废弃代码**: `users/views.py` 中存在一个基于 DRF 默认 Token 认证的 `LoginView`，但项目已改用 `simplejwt`，该视图应被移除。

### 3.3. 前端 (React)

前端项目基于 React 18 和 `create-react-app` 构建，使用 React Router 进行路由管理，Ant Design 和 Material-UI 作为 UI 库，并通过 React Query 管理服务端状态。

**发现的问题**:

*所有与前端相关的问题均已在此次审查和修复周期中解决。*

### 3.4. 部署配置 (Docker & Nginx)

项目使用 Docker Compose 进行容器化部署，并采用 Nginx 作为反向代理。

**发现的问题**:

*所有与部署配置相关的问题均已在此次审查和修复周期中解决。*

### 3.5. 文档和辅助脚本

项目包含了多个构建和部署脚本，以及大量的规划性文档。

**发现的问题**:

1.  **脚本的脆弱性与硬编码**:
    *   `build.sh` 和 `deploy.sh` 中硬编码了目录路径（如 `~/app/omni-desk`）和构建上下文，降低了脚本的可移植性和可维护性。
    *   `build.sh` 中的 `docker push` 命令被注释，导致构建与部署流程脱节。
    *   `deploy.sh` 依赖于一个未在仓库中定义的 CI/CD 环境变量 (`SERVER_ENV_FILE`)，使得本地手动部署变得困难。
2.  **文档缺失**: 尽管存在大量规划文档，但项目缺乏关键的技术文档，如：
    *   **架构设计文档**: 缺少对当前复杂架构的宏观描述。
    *   **API 参考**: 没有自动生成的 API 文档。
    *   **本地开发指南**: 缺少帮助新成员快速搭建开发环境的说明。

---

## 4. 总结与建议

本次代码审查发现了项目在 **架构设计、安全性、可维护性和部署流程** 方面存在的一系列问题。其中，**前端基于 Local Storage 的权限控制是一个严重的安全漏洞，应作为最高优先级进行修复**。

### 4.1. 核心问题与建议

| 优先级 | 问题分类 | 问题描述 | 建议方案 |
| :--- | :--- | :--- | :--- |
| **紧急** | 安全性 | **前端权限控制严重漏洞**: 权限数据存储在 Local Storage，用户可轻易修改以获得任意权限。 | **(已解决)** 1. 移除了前端 `localStorage` 中的权限存储。 <br> 2. 改造了 `ProtectedRoute`，使其通过统一的 `hasPermission` 函数进行权限验证。 <br> 3. 确保了权限的唯一可信来源是后端 API。 |
| **高** | 后端 | **混乱的权限系统**: 同时使用硬编码的 `role` 字段和 Django 内置的 `Group`/`Permission` 系统。 | 1. **废弃 `CustomUser.role` 字段**。 <br> 2. **迁移到 Django RBAC**: 创建 `Admin`, `Manager`, `User` 等 `Group`，并为它们分配合适的 `Permission`。 <br> 3. **重构 `has_perm`**: 移除硬编码逻辑，完全依赖 Django 的权限检查。 |
| **中** | 安全性 | **CORS 配置过于宽松**: 允许任何来源的凭证请求。 | 在 `settings.py` 中设置 `CORS_ALLOWED_ORIGINS` 或 `CORS_ORIGIN_WHITELIST`，仅包含前端应用的域名。 |
| **低** | 可维护性 | **依赖管理不规范**: `requirements.txt` 中存在未固定版本的依赖和重复项。 | 1. 使用 `pip-tools` 或 `pip freeze` 生成一个包含所有固定版本依赖的 `requirements.txt`。 <br> 2. 将 `pytest`, `coverage` 等开发依赖移至 `requirements-dev.txt`。 |

### 4.2. 后续步骤

1.  **召开审查会议**: 与开发团队讨论本报告中提出的问题，特别是高优先级的安全和架构问题，达成共识。
2.  **制定修复计划**: 将上述建议转化为具体的开发任务，并纳入项目的产品待办事项（Backlog）中。
3.  **优先修复安全漏洞**: 立即着手修复前端权限控制的漏洞。
4.  **逐步重构**: 在后续的迭代中，逐步完成架构简化、权限系统统一和部署流程优化等工作。