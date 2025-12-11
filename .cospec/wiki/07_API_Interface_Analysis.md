# OmniDesk API 接口分析

## 1. API 架构概览

- **架构风格**: **RESTful API**。项目遵循REST原则，使用标准的HTTP方法（GET, POST, PUT, DELETE）对资源进行操作。
- **技术实现**: 使用 **Django REST Framework (DRF)** 构建。DRF提供了序列化、视图、路由、认证和权限等一套完整的工具链，极大地简化了API的开发。
- **路由管理**:
    - 根 `urls.py` (`omni_desk_backend/omni_desk_backend/urls.py`) 将所有API请求路由到 `/api/` 前缀下。
    - 各个Django App（如 `users`, `events`, `personnel`）拥有自己的 `urls.py` 文件，负责定义该模块下的具体路由。
    - 大量使用DRF的 `DefaultRouter` 来自动为 `ViewSet` 生成标准的CRUD路由，简化了路由配置。
- **数据格式**: 所有API接口统一使用 **JSON** 作为数据交换格式。
- **认证与授权**:
    - **认证**: 采用基于 **JWT (JSON Web Token)** 的无状态认证机制，由 `djangorestframework-simplejwt` 库提供支持。
    - **授权**: 使用DRF的权限系统，结合自定义的权限类（如 `IsAdminOrManager`）对不同角色的用户进行访问控制。

## 2. API 接口分类与设计

### 按功能模块划分

| 模块 | URL前缀 | 主要功能 |
|---|---|---|
| **认证 (Authentication)** | `/api/auth/` | 用户注册、登录 (获取Token)、刷新Token。 |
| **用户 (Users)** | `/api/users/` | 管理用户账户，获取和更新个人资料。 |
| **人事 (Personnel)** | `/api/personnel/` | 管理核心人事档案、合同、教育背景等。 |
| **事件 (Events)** | `/api/events/` | 管理排班、试验、公告、节假日等时间相关活动。 |
| **项目 (Projects)** | `/api/projects/` | 管理项目信息。 |
| **文档 (Documents)** | `/api/documents/` | 文档管理。 |
| ... | ... | 其他业务模块，如配置、备忘录等。 |

### 设计模式
- **ViewSet 和 Router**: 项目广泛采用 `ModelViewSet` 结合 `DefaultRouter` 的模式。这为每个模型快速生成了一套完整的RESTful端点（list, create, retrieve, update, partial_update, destroy），是DRF推荐的最佳实践。
- **序列化 (Serialization)**: 每个模型都对应一个或多个 `Serializer`。序列化器负责将复杂的QuerySet或模型实例转换成JSON，以及对传入的JSON数据进行验证和反序列化为模型实例。
- **基于类的视图 (Class-Based Views)**: 对于非标准CRUD操作或需要更强自定义的逻辑，项目使用DRF的通用APIView或generics视图（如 `generics.CreateAPIView`）。

## 3. 核心API接口详解

### 用户与认证 API (`/api/auth/`, `/api/users/`)

| 接口路径 | 方法 | 功能描述 | 请求体 (示例) | 成功响应 (示例) |
|---|---|---|---|---|
| `/api/auth/register/` | `POST` | 注册新用户 | `{"username": "u", "password": "p", "password_confirmation": "p"}` | `201 CREATED` `{"success": true, "message": "注册成功..."}` |
| `/api/auth/token/` | `POST` | 用户登录 | `{"username": "u", "password": "p"}` | `200 OK` `{"access": "...", "refresh": "...", "user": {...}}` |
| `/api/users/me/` | `GET` | 获取当前登录用户信息 | (无) | `200 OK` `{"id": 1, "username": "u", ...}` |
| `/api/users/me/profile/` | `PUT` | 更新当前用户信息 | `{"real_name": "张三"}` | `200 OK` `{"id": 1, "real_name": "张三", ...}` |

### 人事 API (`/api/personnel/`)

| 接口路径 | 方法 | 功能描述 | 权限 |
|---|---|---|---|
| `/api/personnel/personnel/` | `GET` | 获取人事档案列表 (支持分页和搜索) | `IsAuthenticated` |
| `/api/personnel/personnel/` | `POST` | 创建新的人事档案 | `IsAdminOrManager` |
| `/api/personnel/personnel/<id>/` | `GET` | 获取单个人事档案详情 | `IsAuthenticated` |
| `/api/personnel/personnel/<id>/` | `PUT` | 更新人事档案 | `IsAdminOrManager` |
| `/api/personnel/personnel/<id>/` | `DELETE` | 删除人事档案 | `IsAdminOrManager` |

### 事件与排班 API (`/api/events/`)

| 接口路径 | 方法 | 功能描述 | 请求体 (示例) |
|---|---|---|---|
| `/api/events/schedules/` | `GET` | 获取排班列表 (支持按日期范围过滤) | (查询参数 `?start_date=...&end_date=...`) |
| `/api/events/schedules/` | `POST` | 创建单条排班记录 | `{"duty_date": "2025-12-25", "duty_person_id": 1, "duty_leader_id": 2}` |
| `/api/events/schedules/generate-schedules/` | `POST` | 自动生成排班 | `{"target_month": "2025-12", "personnel_sequence_id": 1, ...}` |

## 4. API 规范与错误处理

- **统一响应格式**:
    - **成功**: 响应体通常包含 `success: true` 和一个 `data` 字段，其中包含请求的资源。对于登录等操作，还会包含 `user`, `access`, `refresh` 等字段。
    - **失败**: 响应体包含 `success: false`，一个 `error` 键（表示错误类型，如 `invalid_credentials`），以及一个 `message` 或 `detail` 字段提供人类可读的错误信息。
- **HTTP状态码**:
    - `200 OK`: 请求成功（GET, PUT）。
    - `201 Created`: 资源创建成功（POST）。
    - `204 No Content`: 操作成功，但无内容返回（DELETE）。
    - `400 Bad Request`: 请求无效，通常是由于客户端发送的数据验证失败。响应体中会包含具体的字段错误。
    - `401 Unauthorized`: 用户未认证或认证失败。
    - `403 Forbidden`: 用户已认证，但无权访问该资源。
    - `404 Not Found`: 请求的资源不存在。
- **验证错误处理**: 当 `Serializer` 验证失败时，API会返回 `400 Bad Request`，并且响应体中会详细列出每个字段的错误信息，方便前端进行表单错误提示。例如：
  ```json
  {
      "success": false,
      "error": "validation_error",
      "message": "注册验证失败",
      "validation_errors": {
          "username": ["用户名至少需要4个字符"]
      }
  }
  ```

## 5. 性能与安全

- **性能**:
    - **分页**: 对于列表接口（如获取人员列表、排班列表），默认启用分页，避免一次性返回大量数据。
    - **数据库查询优化**: 在视图中通过 `select_related` 和 `prefetch_related` 减少数据库查询次数。
    - **缓存**: 虽然API层面没有显式的缓存逻辑，但系统设计上依赖Redis，可以方便地扩展缓存策略。
- **安全**:
    - **认证**: 所有需要保护的端点都强制要求提供有效的JWT。
    - **权限**: 严格的基于角色的访问控制，确保普通用户无法执行管理操作。
    - **输入验证**: 所有传入的数据都经过 `Serializer` 的严格验证，防止恶意输入。