# 管理面板新页面开发计划

**任务目标**: 在管理面板中添加一个新的页面，提供给管理员管理人员角色、权限以及页面隐藏与显示等更细颗粒度的管理操作。

**核心需求**:
1.  **用户管理**: 列出所有用户，并允许管理员修改用户的角色。
2.  **权限管理**: 通过修改人员角色来管理权限。
3.  **页面可见性管理**: 实现页面在前端的隐藏与显示控制，并允许管理员进行配置。

**系统现状分析**:
*   **后端**: `CustomUser` 模型通过 `role` 字段（`admin`, `manager`, `user`）定义用户角色，并通过 `has_perm` 方法实现权限判断。权限是基于角色预定义的。
*   **前端**:
    *   `AuthContext` 管理用户的认证状态和用户信息，包括用户的 `role`。
    *   登录成功后，用户数据（包括 `role`）会被存储在 `AuthContext` 的 `user` 对象中。
    *   `ProtectedRoute` 组件根据 `user?.role` 和路由配置的 `roles` 属性来控制页面访问权限。

**详细计划**:

## 1. 后端开发 (Django REST Framework)

### API 接口设计
*   **获取用户列表**: `GET /api/users/`
    *   **描述**: 允许管理员获取所有用户信息，包括角色。
    *   **权限**: 仅限 `admin` 角色访问。
*   **更新用户角色**: `PATCH /api/users/<id>/set_role/` 或 `PUT /api/users/<id>/`
    *   **描述**: 允许管理员修改指定用户的角色。
    *   **请求体**: `{"role": "new_role"}`
    *   **权限**: 仅限 `admin` 角色访问。
*   **获取可管理页面列表**: `GET /api/pages/`
    *   **描述**: 获取前端所有可配置可见性的页面列表。
    *   **权限**: 仅限 `admin` 角色访问。
*   **更新页面可见性**: `PATCH /api/pages/<id>/set_visibility/` 或 `PUT /api/pages/<id>/`
    *   **描述**: 允许管理员修改指定页面的可见性。
    *   **请求体**: `{"is_hidden_for_non_admin": true/false}`
    *   **权限**: 仅限 `admin` 角色访问。

### 模型 (`omni_desk_backend/users/models.py` 等)
*   `CustomUser` 模型已包含 `role` 字段，无需修改。
*   **新增模型 `PageConfig`**:
    *   **文件路径**: 考虑在 `omni_desk_backend/config/models.py` 或新建 `omni_desk_backend/pages/models.py`。
    *   **字段**:
        *   `page_name`: `CharField` (例如: "Meeting Room Booking Page")
        *   `page_path`: `CharField` (例如: "/meeting-rooms"，用于前端匹配)
        *   `is_hidden_for_non_admin`: `BooleanField`, default `False` (表示除管理员外是否隐藏)
    *   **用途**: 存储前端页面名称、路径和可见性配置。

### 序列化器 (`omni_desk_backend/users/serializers.py` 等)
*   **`UserAdminSerializer`**:
    *   为 `CustomUser` 创建一个适用于管理员的序列化器。
    *   **字段**: `id`, `username`, `email`, `role`。
    *   允许更新 `role` 字段。
*   **`PageConfigSerializer`**:
    *   为 `PageConfig` 模型创建序列化器。
    *   **字段**: `id`, `page_name`, `page_path`, `is_hidden_for_non_admin`。
    *   允许更新 `is_hidden_for_non_admin` 字段。

### 视图 (`omni_desk_backend/users/views.py` 等)
*   **`UserAdminListView`**:
    *   继承 `generics.ListAPIView`。
    *   **权限**: `IsAdmin`。
*   **`UserAdminDetailView`**:
    *   继承 `generics.RetrieveUpdateAPIView`。
    *   **权限**: `IsAdmin`。
    *   用于获取单个用户详情和更新用户角色。
*   **`PageConfigListView`**:
    *   继承 `generics.ListCreateAPIView`。
    *   **权限**: `IsAdmin`。
*   **`PageConfigDetailView`**:
    *   继承 `generics.RetrieveUpdateAPIView`。
    *   **权限**: `IsAdmin`。
    *   用于获取单个页面配置和更新页面可见性。

### URL 配置 (`omni_desk_backend/omni_desk_backend/urls.py` 或 `omni_desk_backend/<app>/urls.py` 等)
*   配置上述 API 接口的 URL 路由。

## 2. 前端开发 (React)

### 新建管理页面 (`omni_desk_frontend/src/pages/AdminUserManagementPage.jsx`)
*   在 `omni_desk_frontend/src/pages/` 目录下创建。
*   **页面内容**:
    *   **用户管理区**:
        *   显示用户列表，包括 `username`, `email`, `role`。
        *   每个用户行提供一个下拉选择器或按钮，用于修改 `role`。
        *   调用后端 `PATCH /api/users/<id>/` 接口更新用户角色。
    *   **页面可见性管理区**:
        *   显示可配置页面列表，包括 `page_name`, `page_path`。
        *   每个页面行提供一个开关 (`Switch`)，用于切换 `is_hidden_for_non_admin` 状态。
        *   调用后端 `PATCH /api/pages/<id>/` 接口更新页面可见性。

### 路由配置 (`omni_desk_frontend/src/routes/index.js`)
*   在 `/admin` 路径下添加新的路由：
    ```javascript
    {
      path: "user-management",
      element: <ProtectedRoute roles={['admin']}><AdminUserManagementPage /></ProtectedRoute>
    },
    ```
    确保只有 `admin` 角色可以访问。

### API 集成 (`omni_desk_frontend/src/api/` 目录下)
*   **`userManagementApi.js`**:
    *   封装 `GET /api/users/` 和 `PATCH /api/users/<id>/` 的请求。
*   **`pageConfigApi.js`**:
    *   封装 `GET /api/pages/` 和 `PATCH /api/pages/<id>/` 的请求。

### 状态管理
*   在 `AdminUserManagementPage.jsx` 中使用 `useState` 和 `useEffect` 来管理用户列表和页面配置数据，并在数据更新时重新渲染。

### UI 组件
*   使用 Ant Design 的 `Table`, `Select`, `Switch`, `Button`, `message` 等组件。

### 侧边栏导航 (`omni_desk_frontend/src/components/Sidebar.jsx`)
*   在侧边栏的“管理”部分添加一个新的导航项，指向 `/admin/user-management`。
*   使用 `ProtectedRoute` 或其他逻辑确保只有 `admin` 角色可见此导航项。

### 页面可见性逻辑调整
*   **`AuthContext` 增强**: `AuthContext` 需要新增一个 `pageConfig` 状态，用于存储从后端获取的页面配置列表。在应用初始化时（`useEffect` 钩子中）或登录成功后，从后端获取页面配置数据并存储。
*   **通用页面可见性判断函数**: 在 `AuthContext` 中提供一个 `isPageVisible(pagePath)` 方法，该方法会：
    1.  检查用户角色（如果是 `admin`，则始终可见）。
    2.  查询 `pageConfig` 状态，根据 `pagePath` 找到对应的配置项。
    3.  根据 `is_hidden_for_non_admin` 字段和当前用户角色判断页面是否可见。
*   **`ProtectedRoute` 增强**: 在 `ProtectedRoute` 中，除了 `roles` 检查外，增加对 `isPageVisible` 的调用，例如：
    ```javascript
    const ProtectedRoute = ({ children, roles, pagePath }) => {
      const { user, isAuthenticated, isInitializing, isPageVisible } = useAuth();
      // ... (现有逻辑)
      if (pagePath && !isPageVisible(pagePath)) {
        return <Navigate to="/unauthorized" replace />;
      }
      return children;
    };
    ```
    需要更新所有路由定义，为需要控制可见性的路由添加 `pagePath` 属性。
*   **动态侧边栏**: 根据 `pageConfig` 和用户角色，动态渲染侧边栏的导航项。

## 3. 权限细化 (可选，当前任务不涉及)
*   如果未来需要实现更细粒度的权限管理，则需要扩展后端 `CustomUser` 模型中的权限逻辑，并更新前端 `AuthContext` 中的 `hasPermission` 方法。

## Mermaid 图示

```mermaid
graph TD
    subgraph Backend
        B1[CustomUser Model] --> B2(User API: GET /api/users/, PATCH /api/users/<id>/set_role/);
        B3[New PageConfig Model] --> B4(PageConfig API: GET /api/pages/, PATCH /api/pages/<id>/set_visibility/);
        B2 -- Authenticated --> FE1;
        B4 -- Authenticated --> FE1;
    end

    subgraph Frontend
        FE1[AdminUserManagementPage.jsx] --> FE2(用户列表 & 角色编辑器);
        FE1 --> FE3(页面列表 & 可见性开关);
        FE4[omni_desk_frontend/src/routes/index.js] --> FE1;
        FE5[omni_desk_frontend/src/components/Sidebar.jsx] --> FE1;
        FE6[AuthContext] -- 用户角色 --> FE4;
        FE6 -- 用户角色 & 页面配置 --> FE3;
        FE7[ProtectedRoute] --> FE4;
    end

    FE1 -- 调用 API --> B2;
    FE1 -- 调用 API --> B4;
    FE7 -- 使用 --> FE6;
    FE6 -- 获取用户数据 --> B2;