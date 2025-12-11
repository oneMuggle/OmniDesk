# OmniDesk 服务模块分析

## 架构概览

OmniDesk 后端采用模块化单体架构。整个后端作为一个服务运行，但内部通过 Django Apps 实现了业务逻辑的划分。本篇文档将深入分析其中两个核心模块：`users` 和 `events`。

---

## 1. `users` 模块分析

### 服务概述
- **模块名称**: `users`
- **服务描述**: 负责用户账户管理、身份认证、权限控制和个人资料。是整个系统的基础模块。
- **技术栈**: Django, Django REST Framework, Simple JWT
- **部署方式**: 作为 `omni_desk_backend` 单体应用的一部分进行部署。

### 核心功能模块
- **用户模型 (`models.py`)**: 定义了 `CustomUser` 模型，继承自Django的 `AbstractUser`，并增加了 `role`, `real_name`, `avatar` 等自定义字段。同时定义了 `PhoneNumber` 模型。
- **认证逻辑 (`views.py`, `serializers.py`)**:
    - `UserRegistrationView`: 处理新用户注册。
    - `UserLoginView` / `CustomTokenObtainPairSerializer`: 处理用户登录，验证凭据并签发JWT。
- **API接口 (`urls.py`, `views.py`)**:
    - 提供用户个人资料的CRUD (`UserProfileUpdateView`, `CurrentUserView`)。
    - 提供管理员使用的用户管理接口 (`UserAdminListView`, `UserAdminDetailView`)。
    - 提供密码修改功能 (`ChangePasswordView`)。
- **权限控制 (`permissions.py`)**: 定义了 `IsAdminOrManager`, `IsAdmin` 等自定义权限类，用于API视图的访问控制。

### API 接口分析
| 接口路径 | HTTP 方法 | 功能描述 | 权限要求 |
|---|---|---|---|
| `/api/auth/register/` | POST | 用户注册 | `AllowAny` |
| `/api/auth/token/` | POST | 用户登录，获取JWT | `AllowAny` |
| `/api/auth/token/refresh/` | POST | 刷新JWT | `AllowAny` |
| `/api/users/me/` | GET | 获取当前用户信息 | `IsAuthenticated` |
| `/api/users/me/profile/` | PUT/PATCH | 更新当前用户个人资料 | `IsAuthenticated` |
| `/api/users/me/change-password/` | PUT | 修改当前用户密码 | `IsAuthenticated` |
| `/api/users/admin/` | GET | (管理员) 获取所有用户列表 | `IsAdmin` |
| `/api/users/admin/<id>/` | GET/PUT/PATCH | (管理员) 获取或更新指定用户信息 | `IsAdmin` |

### 数据模型与依赖
- **核心模型**: `CustomUser`
- **内部依赖**:
    - `personnel.Personnel`: 通过 `OneToOneField` 关联到 `CustomUser`，将用户账户与具体的人事信息绑定。
- **外部依赖**:
    - 强依赖 **PostgreSQL** 存储用户数据。
    - 强依赖 **Redis** 用于缓存权限和会话信息（如果使用）。

### 性能与安全
- **性能**: 用户认证是高频操作。通过JWT实现无状态认证，避免了每个请求都查询数据库session，提高了性能。
- **安全**:
    - 密码通过Django的哈希框架进行安全存储。
    - API端点受到严格的权限控制。
    - 使用Simple JWT进行安全的API认证。

---

## 2. `events` 模块分析

### 服务概述
- **模块名称**: `events`
- **服务描述**: 负责管理系统中的所有与时间相关的活动，包括试验、日程、排班、节假日和公告。
- **技术栈**: Django, Django REST Framework
- **部署方式**: 作为 `omni_desk_backend` 单体应用的一部分进行部署。

### 核心功能模块
- **数据模型 (`models.py`)**:
    - `Trial`: 试验，包含多个 `TimeSlot`。
    - `TimeSlot`: 具体的时间段。
    - `Schedule`: 每日排班记录。
    - `PersonnelSequence` & `LeaderSequence`: 用于自动生成排班的顺序。
    - `Holiday`: 节假日记录。
    - `Announcement`: 公告。
- **API接口 (`urls.py`, `views.py`)**:
    - 为每个核心模型（`Trial`, `Schedule`, `Announcement` 等）提供了完整的CRUD操作的 `ViewSet`。
    - `ScheduleViewSet` 提供了复杂的业务逻辑，如 `generate_schedules` (自动生成排班), `swap_dates` (交换排班), `bulk_update` (批量更新)。
- **业务逻辑 (`views.py`, `serializers.py`)**:
    - **排班生成**: `ScheduleViewSet.generate_schedules` 方法包含复杂的逻辑，它会根据人员顺序、节假日设置和指定的起止时间来自动创建排班表。
    - **事务管理**: 在多个数据库操作中（如批量创建/更新），广泛使用 `transaction.atomic()` 来保证数据一致性。
    - **时间范围更新**: `Trial` 模型的 `update_time_range` 方法会在其关联的 `TimeSlot` 发生变化时自动更新自身的起止时间，保证了数据的冗余一致性。

### API 接口分析
| 接口路径 | HTTP 方法 | 功能描述 | 权限要求 |
|---|---|---|---|
| `/api/events/schedules/` | GET, POST | 获取或创建排班 | `IsAdminOrManagerOrReadOnly` |
| `/api/events/schedules/<id>/` | GET, PUT, DELETE | 获取、更新或删除单个排班 | `IsAdminOrManagerOrReadOnly` |
| `/api/events/schedules/generate-schedules/` | POST | 自动生成排班表 | `IsAdminOrManager` |
| `/api/events/trials/` | GET, POST | 获取或创建试验 | `IsAdminOrManagerOrReadOnly` |
| `/api/events/announcements/` | GET, POST | 获取或创建公告 | `IsAdminOrManagerOrReadOnly` |
| `/api/events/personnel-sequences/` | GET, POST | 管理人员排班顺序 | `IsAdminOrManager` |
| `/api/events/holidays/` | GET, POST | 管理节假日 | `IsAdminOrManager` |

### 数据模型与依赖
- **核心模型**: `Schedule`, `Trial`, `TimeSlot`, `Announcement`, `Holiday`
- **内部依赖**:
    - `personnel.Personnel`: `Schedule`, `Trial`, `PersonnelSequence` 等模型都通过外键强依赖于 `personnel` 模块来关联具体的人员。
    - `users.CustomUser`: `Announcement` 和 `DocumentTemplate` 模型通过外键关联到 `CustomUser` 来记录作者或所有者。
- **外部依赖**:
    - 强依赖 **PostgreSQL** 存储所有事件相关数据。

### 性能与安全
- **性能**:
    - 对于排班、试验等可能返回大量数据的查询，使用了分页。
    - 在 `ScheduleViewSet` 的查询中，使用了 `select_related` 和 `prefetch_related` 来优化数据库查询，避免N+1问题。
- **安全**:
    - 所有API端点都配置了基于角色的权限控制 (`IsAdminOrManagerOrReadOnly`)，确保只有授权用户才能进行写操作。