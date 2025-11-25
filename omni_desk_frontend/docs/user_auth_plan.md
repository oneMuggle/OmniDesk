# 用户系统与权限管理实施计划

这是一个分阶段的计划，旨在系统性地为您的项目构建强大的用户和权限管理功能。

## 总体架构

```mermaid
graph TD
    subgraph 后端 (Django Rest Framework)
        A[完善用户模型] --> B[统一认证与权限配置];
        B --> C[创建自定义权限类];
        C --> D[保护 API 端点];
    end

    subgraph 前端 (React)
        E[增强 AuthContext 获取角色] --> F[改造 ProtectedRoute];
        F --> G[更新路由配置];
        G --> H[实现动态 UI];
    end

    D --> E;
    H --> I[完成];

    style A fill:#f9f,stroke:#333,stroke-width:2px
    style B fill:#f9f,stroke:#333,stroke-width:2px
    style C fill:#f9f,stroke:#333,stroke-width:2px
    style D fill:#f9f,stroke:#333,stroke-width:2px
    style E fill:#ccf,stroke:#333,stroke-width:2px
    style F fill:#ccf,stroke:#333,stroke-width:2px
    style G fill:#ccf,stroke:#333,stroke-width:2px
    style H fill:#ccf,stroke:#333,stroke-width:2px
    style I fill:#cfc,stroke:#333,stroke-width:2px
```

---

## 阶段一：后端增强

1.  **完善用户模型 (`DRFForVue/users/models.py`)**
    *   重写 `has_perm` 和 `has_module_perms` 方法，使其根据 `self.role` 返回真实的权限结果。

2.  **统一认证与权限配置 (`DRFForVue/DRFForVue/settings.py`)**
    *   为 `REST_FRAMEWORK` 设置全局默认的认证和权限类，以确保所有 API 的安全性。
    *   **认证**: `DEFAULT_AUTHENTICATION_CLASSES`: `['rest_framework_simplejwt.authentication.JWTAuthentication']`
    *   **权限**: `DEFAULT_PERMISSION_CLASSES`: `['rest_framework.permissions.IsAuthenticated']`

3.  **创建自定义权限类 (`DRFForVue/users/permissions.py`)**
    *   创建一个新文件用于存放自定义权限。
    *   定义 `IsAdmin`、`IsManager` 等权限类，它们会检查 `request.user.role` 是否满足要求。

4.  **保护 API 端点 (各应用的 `views.py`)**
    *   在 `events`、`users` 等应用的视图中，为不同的 `action` (如 `create`, `update`, `destroy`) 分配不同的权限类。例如，只有 `IsAdmin` 或 `IsManager` 才能创建事件。

## 阶段二：前端集成

1.  **增强 `AuthContext` (`omni_desk_frontend/src/context/AuthContext.js`)**
    *   在用户登录成功后，除了保存 `token`，还要从后端 API 获取用户的 `role` 和其他基本信息，并存储在 Context 中。

2.  **改造 `ProtectedRoute` (`omni_desk_frontend/src/components/ProtectedRoute.js`)**
    *   修改此组件，使其可以接受一个 `roles` 数组作为 `prop`。
    *   在组件内部，从 `AuthContext` 获取当前用户的角色，并检查其是否在允许的 `roles` 数组中。如果不在，则重定向到 `/unauthorized` 页面。

3.  **更新路由配置 (`omni_desk_frontend/src/routes/index.js`)**
    *   为需要特定权限的路由添加 `roles` 属性。
    *   例如: `<ProtectedRoute roles={['admin', 'manager']}><EventsPage /></ProtectedRoute>`

4.  **实现动态 UI (各个页面组件)**
    *   在 `EventsPage`、`PersonnelManagementPage` 等组件中，从 `AuthContext` 获取用户角色。
    *   根据角色，使用条件渲染来决定是否显示“新增”、“编辑”、“删除”等操作按钮。