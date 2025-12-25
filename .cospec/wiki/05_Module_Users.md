# 服务模块分析: users

## 模块概述
- **模块名称**: `users`
- **模块描述**: 负责OmniDesk平台所有与用户、认证和授权相关的功能。它是整个系统的安全基石。
- **技术栈**: Django, Django Rest Framework, DRF Simple JWT
- **部署方式**: 作为 `omni_desk_backend` 单体服务的一部分进行部署。

## 核心功能
| 功能 | 描述 | 业务价值 |
|---|---|---|
| **用户注册** | 提供API接口允许新用户创建账户。 | 平台增长的基础。 |
| **用户登录/认证** | 通过用户名和密码进行身份验证，并签发JWT令牌。 | 保护系统资源，识别用户身份。 |
| **用户详情** | 提供接口获取当前登录用户或指定用户的详细信息。 | 支持前端展示用户信息和个性化功能。 |
| **密码修改** | 允许已登录用户修改自己的密码。 | 基础的用户安全功能。 |
| **权限管理** | 通过Django的组和权限，以及自定义的逻辑，在JWT中附加用户权限。 | 实现基于角色的访问控制 (RBAC)。 |
| **管理员操作** | 提供专供管理员使用的接口，用于管理所有用户账户。 | 方便系统管理员维护用户体系。 |

## 接口分析 (REST API)
`users` 模块提供了一系列API端点来暴露其功能。

| 接口路径 | HTTP方法 | 功能描述 | 权限要求 |
|---|---|---|---|
| `/api/auth/register/` | `POST` | 用户注册 | `AllowAny` (允许任何人) |
| `/api/auth/login/` | `POST` | 用户登录，获取JWT | `AllowAny` |
| `/api/users/me/` | `GET` | 获取当前用户信息 | `IsAuthenticated` |
| `/api/users/me/profile/` | `PUT`, `PATCH` | 更新当前用户个人资料 | `IsAuthenticated` |
| `/api/users/me/change-password/` | `PUT` | 修改当前用户密码 | `IsAuthenticated` |
| `/api/users/control-panel/` | `GET` | (管理员) 获取所有用户列表 | `IsAdmin` |
| `/api/users/control-panel/<id>/` | `GET`, `PUT`, `PATCH` | (管理员) 获取/更新指定用户信息 | `IsAdmin` |
| `/api/users/<id>/` | `GET`, `PATCH` | (管理员/经理) 获取/更新用户与人员的关联 | `IsAdminOrManager` |

## 数据模型分析

### `CustomUser` 模型
- **描述**: 继承自Django的`AbstractUser`，是系统的核心用户模型。
- **关键字段**:
    - `username`: (主键) 用户名，唯一标识。
    - `password`: 哈希后的密码。
    - `email`, `real_name`, `avatar`: 用户的基本信息。
    - `personnel`: `OneToOneField` 关联到 `personnel.Personnel` 模型，将用户账户与具体的员工信息绑定。
    - `groups`: `ManyToManyField` 关联到Django的`Group`模型，用于实现基于角色的权限控制。
- **关系**: 与`personnel.Personnel`是一对一关系，与`auth.Group`是多对多关系。

### `PhoneNumber` 模型
- **描述**: 用于存储用户的多个电话号码。
- **关键字段**:
    - `user`: `ForeignKey` 关联到`CustomUser`。
    - `number`: 电话号码字符串。

## 模块依赖分析

### 内部依赖
- **`personnel` 模块**: `CustomUser`模型与`Personnel`模型直接关联。`users`模块的视图和序列化器中也导入并使用了`personnel`的模型和序列化器，以实现用户和员工信息的联动。
- **`permissions` 模块**: `UserDetailSerializer`中调用了`get_user_permissions`函数，该函数依赖`permissions.models.GroupPagePermission`来获取用户的页面级权限。
- **`events` 模块**: `views.py`中导入了`events.models.Position`，但似乎是一个残留的导入，实际使用的是`personnel.models.Position`。

### 外部库依赖
- **`djangorestframework`**: 构建RESTful API的基础。
- **`djangorestframework-simplejwt`**: 用于实现JWT认证。

### 基础设施依赖
- **PostgreSQL**: `CustomUser`等模型的数据都存储在PostgreSQL中。
- **Redis**: 不直接依赖，但整个认证流程（JWT）是无状态的，不依赖会话存储。

## 安全分析
- **认证**: 采用基于JWT的无状态认证。登录成功后，用户的权限信息会被编码到JWT的payload中，服务端通过验证JWT来确认用户身份和权限，无需每次请求都查询数据库。
- **授权**: 
    - **API层**: 使用DRF的权限类（如`IsAuthenticated`, `IsAdmin`）在视图级别进行访问控制。
    - **数据层**: `get_user_permissions`函数实现了复杂的权限逻辑，它会聚合Django的标准权限、用户的组权限以及自定义的页面权限，为前端提供统一的权限列表，以便在UI上控制元素的显示和隐藏。
- **密码安全**: 用户密码通过Django内置机制进行哈希处理，保证了存储安全。
