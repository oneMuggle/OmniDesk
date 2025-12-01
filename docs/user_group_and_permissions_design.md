# 用户组管理与页面可见性后端架构设计

本文档详细描述了用于用户组管理和前端页面可见性控制的后端架构设计。该设计旨在提供一个灵活、可扩展且安全的权限管理系统。

## 1. 数据库模型设计

为了实现功能需求，我们将在现有 `users` 应用中进行扩展，并创建一个新的 `permissions` 应用。

### 1.1. 数据库关系图 (ERD)

```mermaid
erDiagram
    CustomUser {
        int id
        string username
        string email
        string real_name
        string role
        # ... 其他字段
    }

    UserGroup {
        int id
        string name
        string description
    }

    FrontendPage {
        int id
        string name
        string route
        string description
    }

    CustomUser ||--o{ UserGroup : "user_groups (m-n)"
    UserGroup ||--o{ FrontendPage : "visible_to_groups (m-n)"
```

### 1.2. 模型定义

#### a. `UserGroup` 模型

**应用**: `users`
**文件**: `omni_desk_backend/users/models.py`

此模型用于定义用户组。

```python
class UserGroup(models.Model):
    name = models.CharField(max_length=150, unique=True, verbose_name='组名')
    description = models.TextField(blank=True, verbose_name='描述')

    class Meta:
        verbose_name = '用户组'
        verbose_name_plural = '用户组'

    def __str__(self):
        return self.name
```

#### b. `CustomUser` 模型更新

**应用**: `users`
**文件**: `omni_desk_backend/users/models.py`

向 `CustomUser` 模型添加与 `UserGroup` 的多对多关系。

```python
class CustomUser(AbstractUser):
    # ... (现有字段) ...

    user_groups = models.ManyToManyField(
        UserGroup,
        blank=True,
        related_name="users",
        verbose_name='所属用户组'
    )
    
    # ... (现有其他代码) ...
```

#### c. `FrontendPage` 模型

**应用**: `permissions` (新应用)
**文件**: `omni_desk_backend/permissions/models.py`

此模型用于将前端页面（路由）实体化，并管理其与用户组的可见性关系。

```python
from django.db import models
from users.models import UserGroup

class FrontendPage(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name='页面名称')
    route = models.CharField(max_length=255, unique=True, help_text="前端路由路径，例如 '/admin/dashboard'", verbose_name='路由路径')
    description = models.TextField(blank=True, verbose_name='页面描述')

    visible_to_groups = models.ManyToManyField(
        UserGroup,
        blank=True,
        related_name="visible_pages",
        verbose_name='对哪些用户组可见'
    )

    class Meta:
        verbose_name = '前端页面权限'
        verbose_name_plural = '前端页面权限'

    def __str__(self):
        return self.name
```

## 2. API 端点设计

所有 API 端点都将受到管理员权限（`IsAdminUser`）或用户认证（`IsAuthenticated`）的保护。

### 2.1. 用户组管理 API (CRUD)

-   **URL**: `/api/user-groups/` 和 `/api/user-groups/<id>/`
-   **应用**: `users`
-   **权限**: 仅限管理员

| 方法   | URL                     | 描述                                   |
| :----- | :---------------------- | :------------------------------------- |
| `GET`  | `/api/user-groups/`     | 获取所有用户组的列表。                 |
| `POST` | `/api/user-groups/`     | 创建一个新的用户组。                   |
| `GET`  | `/api/user-groups/<id>/` | 获取单个用户组的详细信息，包括用户列表。 |
| `PUT`  | `/api/user-groups/<id>/` | 完整更新一个用户组的信息及其用户。     |
| `PATCH`| `/api/user-groups/<id>/` | 部分更新一个用户组的信息及其用户。     |
| `DELETE`| `/api/user-groups/<id>/` | 删除一个用户组。                       |

### 2.2. 页面权限管理 API

-   **URL**: `/api/page-permissions/`
-   **应用**: `permissions`
-   **权限**: 仅限管理员

| 方法  | URL                     | 描述                                                         |
| :---- | :---------------------- | :----------------------------------------------------------- |
| `GET` | `/api/page-permissions/` | 获取所有前端页面及其对各用户组的可见性状态。                 |
| `PUT` | `/api/page-permissions/` | 批量更新页面的可见性设置。请求体为一个包含 `page_id` 和 `group_ids` 的对象列表。 |

**`PUT` 请求体示例**:
```json
[
    { "page_id": 1, "group_ids": [1, 3] },
    { "page_id": 2, "group_ids": [2] },
    { "page_id": 3, "group_ids": [] }
]
```

### 2.3. 获取当前用户可访问页面的 API

-   **URL**: `/api/my-accessible-pages/`
-   **应用**: `permissions`
-   **权限**: 已登录用户

| 方法  | URL                        | 描述                                                         |
| :---- | :------------------------- | :----------------------------------------------------------- |
| `GET` | `/api/my-accessible-pages/` | 返回一个包含当前登录用户有权访问的所有前端页面路由的字符串列表。 |

**`GET` 响应示例**:
```json
[
    "/dashboard",
    "/profile",
    "/settings/billing"
]
```

---
该设计文档为后续的开发工作提供了清晰的蓝图。