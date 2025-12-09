# 技术文档：用户与权限管理

## 1. 概述

本系统采用一种混合权限模型，将后端API的访问控制与前端页面的可见性分离开来，以实现灵活而安全的用户权限管理。

- **后端API授权**: 基于在 `CustomUser` 模型中定义的静态角色（`role`），例如“管理员”、“经理”和“普通用户”。
- **前端页面可见性**: 一个完全动态的、由数据库驱动的系统，它允许管理员通过界面将特定的前端路由（页面）授权给不同的用户组。

---

## 2. 后端实现

### 2.1. API 访问控制 (基于角色)

API的访问权限主要由 `users` 应用负责。

- **核心模型**: [`omni_desk_backend/users/models.py`](omni_desk_backend/users/models.py:4)
  - `CustomUser` 模型包含一个 `role` 字段，用于定义用户的基本角色。

- **权限控制**: [`omni_desk_backend/users/permissions.py`](omni_desk_backend/users/permissions.py)
  - 定义了一系列权限类，如 `IsAdmin`、`IsManager` 和 `IsAdminOrManager`。
  - 这些类检查请求用户的 `role` 属性，以确定其是否有权访问特定的API端点。
  - 例如，一个视图如果设置了 `permission_classes = [IsAdmin]`，那么只有 `role` 为 `admin` 的用户才能访问。

### 2.2. 前端页面可见性 (基于用户组)

前端页面的可见性由一个独立的 `permissions` 应用管理。

- **核心模型**: [`omni_desk_backend/permissions/models.py`](omni_desk_backend/permissions/models.py)
  - `PageRoute`: 将每个前端路由（如 `/dashboard`, `/settings`）抽象为数据库中的一个条目。
  - `Group` (Django内置): 代表用户组（如“财务部”、“研发部”）。
  - `GroupPagePermission`: 一个中间表，用于建立 `Group` 和 `PageRoute` 之间的多对多关系，从而定义哪个用户组可以查看哪个页面。

- **核心API视图**: [`omni_desk_backend/permissions/views.py`](omni_desk_backend/permissions/views.py)
  - `GroupViewSet`: 提供对用户组的完整CRUD（创建、读取、更新、删除）操作。
  - `PageRouteViewSet`: 提供一个只读的API，用于获取所有已定义的页面路由，通常以树状结构返回。
  - `GroupPermissionView`: 核心视图，处理特定用户组的权限读取和更新。
    - `GET`: 获取一个用户组被授权的所有 `PageRoute` ID。
    - `PUT`: 批量更新一个用户组的页面权限。
  - `UserPermissionView`: 获取当前登录用户有权访问的所有页面路由。前端通常在登录后调用此接口来动态生成导航菜单。

---

## 3. 前端实现

前端的权限管理界面由 `GroupPermissionManager` 组件实现。

- **核心组件**: [`omni_desk_frontend/src/components/Admin/GroupPermissionManager.jsx`](omni_desk_frontend/src/components/Admin/GroupPermissionManager.jsx)
  - 该组件提供了一个完整的管理界面，允许管理员：
    1.  创建、编辑和删除用户组。
    2.  选择一个用户组。
    3.  在页面树中勾选该用户组可以访问的页面。
    4.  保存更改，通过调用后端的 `GroupPermissionView` 来更新权限。

- **API客户端**: [`omni_desk_frontend/src/api/permissionsApi.js`](omni_desk_frontend/src/api/permissionsApi.js)
  - 这是一个专门的API客户端，封装了所有与后端 `permissions` 应用交互的HTTP请求。

---

## 4. 用户-人员关联

系统还支持将一个用户账户（`CustomUser`）与一个“人员”实体（`events.Personnel`）进行一对一绑定。

- **后端**:
  - `CustomUser` 模型中有一个 `personnel` 字段，它是一个到 `events.Personnel` 的 `OneToOneField`。
  - [`omni_desk_backend/users/views.py`](omni_desk_backend/users/views.py) 中的 `UserPersonnelViewSet` 提供了API，允许管理员将用户账户指派给一个人员。
- **前端**:
  - 相关的管理界面允许管理员在用户列表中为每个用户选择并关联一个“人员”。