# OmniDesk API 接口分析

## API 架构概览

- **架构风格**: **RESTful**。API遵循REST的设计原则，使用HTTP方法（GET, POST, PUT, DELETE）对资源进行操作，并使用标准的HTTP状态码来表示操作结果。
- **统一前缀**: 所有API端点都以 `/api/` 为统一前缀，便于Nginx等反向代理进行路由转发。
- **框架**: 使用 **Django Rest Framework (DRF)** 构建。DRF提供了序列化、视图集、路由、认证、权限等一系列强大的工具，极大地规范和简化了API的开发。
- **认证机制**: 全局采用基于 **JWT (JSON Web Token)** 的无状态认证。通过`rest_framework_simplejwt`库实现，客户端在请求头中携带`Bearer <token>`进行身份验证。
- **数据格式**: API的主要数据交换格式为 **JSON** (`application/json`)。
- **分页**: DRF提供了全局的分页配置，多数列表接口（如获取项目列表）都支持分页，返回结果中包含`count`, `next`, `previous`, `results`等字段。

## API 接口分类

API可以根据其所属的业务模块（Django App）进行分类。

| 模块 (App) | API 前缀 | 主要功能 |
|---|---|---|
| `users` | `/api/auth/`, `/api/users/` | 用户注册、登录、个人资料管理、后台用户管理 |
| `projects` | `/api/projects/` | 项目的CRUD操作 |
| `documents` | `/api/documents/` | 文档、书籍、章节等的CRUD操作 |
| `personnel` | `/api/personnel/` | 员工档案、合同、教育背景等的管理 |
| `sensor_management` | `/api/sensor-management/` | 传感器及校准记录管理 |
| `compliance` | `/api/compliance/` | 合规性问题管理 |
| ... | ... | (其他业务模块) |

## 核心API接口详解

### 用户与认证 API (`users`模块)

#### `POST /api/auth/register/`
- **功能**: 创建一个新用户账户。
- **请求体**:
  ```json
  {
    "username": "newuser",
    "password": "some_password",
    "password_confirmation": "some_password",
    "email": "user@example.com"
  }
  ```
- **响应 (成功)**: `201 CREATED`，返回包含用户基本信息的JSON对象。
- **权限**: 允许任何人访问。

#### `POST /api/auth/login/`
- **功能**: 用户登录，验证凭据并获取访问令牌。
- **请求体**:
  ```json
  {
    "username": "testuser",
    "password": "password123"
  }
  ```
- **响应 (成功)**: `200 OK`，返回包含`access`和`refresh` JWT令牌，以及用户详细信息和权限列表。
  ```json
  {
    "success": true,
    "user": { ... },
    "access": "ey...",
    "refresh": "ey...",
    "permissions": ["admin", "documents.view_book", ...]
  }
  ```
- **权限**: 允许任何人访问。

#### `GET /api/users/me/`
- **功能**: 获取当前已登录用户的详细信息。
- **请求头**: `Authorization: Bearer <access_token>`
- **响应 (成功)**: `200 OK`，返回当前用户的序列化数据。
- **权限**: `IsAuthenticated` (仅限已登录用户)。

### 项目管理 API (`projects`模块)

#### `GET /api/projects/`
- **功能**: 获取项目列表。根据用户角色（管理员/经理）返回不同的结果。
- **请求头**: `Authorization: Bearer <access_token>`
- **响应 (成功)**: `200 OK`，返回一个包含项目列表的分页对象。
- **权限**: `IsAuthenticated`。

#### `POST /api/projects/`
- **功能**: 创建一个新项目。
- **请求头**: `Authorization: Bearer <access_token>`
- **请求体**:
  ```json
  {
    "name": "新项目 Alpha",
    "description": "这是一个测试项目。",
    "start_date": "2025-01-01",
    "manager": 2 
  }
  ```
- **响应 (成功)**: `201 CREATED`，返回新创建的项目对象。
- **权限**: `IsAuthenticated`, `IsProjectOwnerOrAdmin` (实际上由视图逻辑控制为仅限管理员和经理)。

## 数据模型与序列化
- **序列化器 (Serializers)**: 每个模块的`serializers.py`文件定义了API如何将复杂的Django模型实例转换为JSON，以及如何验证和解析传入的JSON数据。例如，`UserDetailSerializer`不仅序列化`CustomUser`模型，还通过`SerializerMethodField`动态地加入了用户的权限列表。
- **数据验证**: 验证逻辑主要在序列化器中实现。DRF的序列化器提供了强大的验证机制，包括字段类型、长度、格式（如`EmailField`）以及自定义的`validate()`方法（如检查两次输入的密码是否匹配）。

## 错误处理
- **标准HTTP状态码**: API严格使用HTTP状态码来表示请求结果。
  - `2xx`: 成功 (e.g., `200 OK`, `201 Created`, `204 No Content`)
  - `4xx`: 客户端错误 (e.g., `400 Bad Request`用于验证失败, `401 Unauthorized`用于认证失败, `403 Forbidden`用于权限不足, `404 Not Found`用于资源不存在)
  - `5xx`: 服务器内部错误。
- **统一的错误响应体**: 对于客户端错误（4xx），API通常会返回一个包含详细错误信息的JSON体，帮助前端开发者定位问题。
  ```json
  // 验证失败示例
  {
    "success": false,
    "error": "validation_error",
    "message": "注册验证失败",
    "validation_errors": {
      "username": ["用户名只能包含4-20位字母、数字和下划线"]
    }
  }
  ```

## API 安全性
- **认证**: 所有需要保护的端点都通过`permission_classes = [permissions.IsAuthenticated]`来确保只有携带有效JWT的请求才能访问。
- **授权**: 在认证的基础上，通过自定义权限类（如`IsAdmin`, `IsProjectOwnerOrAdmin`）或在视图中编写业务逻辑，实现更细粒度的访问控制。例如，`ProjectViewSet`会检查用户是否为项目负责人或管理员。
- **CORS**: 项目配置了`django-cors-headers`，以允许来自前端域（如`http://localhost:3000`）的跨域API请求。
