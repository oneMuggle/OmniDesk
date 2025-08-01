# 侧边栏权限控制实施计划

**目标：** 修改侧边栏，使其根据用户的权限动态显示或隐藏链接。

**核心思路：**

1.  **后端**：用户的权限信息已经在登录时被打包进了 JWT (JSON Web Token) 中。
2.  **前端**：我们需要修改前端的认证逻辑 (`AuthContext`) 来解析这个 JWT，提取出权限信息，并提供一个方便的权限检查函数。然后，我们将更新侧边栏组件 (`Sidebar`) 来使用这个函数，动态地过滤导航链接。

---

### **详细实施计划**

#### **第一部分：增强 `AuthContext` 以处理权限**

我将修改 `calendar_with_react/src/context/AuthContext.js` 文件：

1.  **解析 JWT**：在用户登录和应用初始化时，解析从服务器获取的 JWT，并从中提取出 `permissions` 列表。
2.  **存储权限**：将这个 `permissions` 列表与用户信息一起存储在 `AuthContext` 的 `user` 状态中。
3.  **提供 `hasPermission` 函数**：在 `AuthContext` 中新增一个名为 `hasPermission` 的辅助函数。这个函数将用于检查当前用户是否拥有特定的权限。

#### **第二部分：更新 `Sidebar` 组件以使用新的权限逻辑**

我将修改 `calendar_with_react/src/components/Sidebar.jsx` 文件：

1.  **获取 `hasPermission` 函数**：从 `AuthContext` 中获取新创建的 `hasPermission` 函数。
2.  **更新过滤逻辑**：修改侧边栏导航链接的过滤逻辑。对于每个需要权限的链接，调用 `hasPermission` 函数进行检查。只有当用户拥有相应权限时，链接才会被渲染出来。

---

### **流程图**

```mermaid
graph TD
    subgraph Frontend (React)
        A[Sidebar Component] -- "需要知道用户权限" --> B{AuthContext};
        B -- "用户登录时" --> C[login() function];
        C -- "调用 /auth/login/ API" --> D[Backend API];
        D -- "返回 JWT (包含 permissions)" --> C;
        C -- "解码 JWT, 提取 permissions" --> E[user state with permissions];
        B -- "提供 hasPermission() 函数" --> A;
        A -- "使用 hasPermission() 过滤链接" --> F[渲染侧边栏];
    end

    subgraph Backend (Django)
        G[CustomTokenObtainPairSerializer] -- "在生成 token 时" --> H{user.get_all_permissions()};
        H -- "获取用户所有权限" --> G;
        G -- "将 permissions 添加到 JWT payload" --> D;
    end