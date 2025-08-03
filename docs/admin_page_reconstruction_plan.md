# 管理页面重构计划

## 目标
将“试验管理”、“人员管理”、“书籍管理”和“设置”等页面重构到一套独立的管理页面中，该页面包含独立的导航栏，并且只允许 `admin` 和 `manager` 角色的用户访问。

## 详细计划

### 1. 创建新的管理布局组件 `AdminLayout.jsx`

*   **路径**: `calendar_with_react/src/components/Admin/AdminLayout.jsx`
*   **内容**:
    *   该组件将作为管理页面的顶级布局。
    *   它将包含一个全新的、完全独立的侧边栏导航，专门用于管理功能。
    *   侧边栏将只包含指向“试验管理”、“人员管理”、“书籍管理”和“设置”等页面的链接。
    *   `AdminLayout` 本身将使用 `ProtectedRoute` 进行包裹，确保只有 `admin` 和 `manager` 角色可以访问此布局及其所有子页面。
    *   内部导航项的显示也将根据用户权限进行控制。

### 2. 定义新的权限路由 `index.js`

*   **路径**: `calendar_with_react/src/routes/index.js`
*   **修改内容**:
    *   添加一个新的顶级路由 `/admin`。
    *   此路由的 `element` 将是受 `ProtectedRoute` 保护的 `AdminLayout` 组件，权限要求为 `['admin', 'manager']`。
    *   将以下页面的路由定义从现有的 `App` 路由下移除，并作为 `/admin` 路由的子路由嵌套定义：
        *   `TrialsPage` (试验管理)
        *   `PersonnelPage` (人员管理)
        *   `BookManagementPage` (书籍管理)
        *   `SettingsPage` (设置)
    *   这些子路由将继续使用 `ProtectedRoute` 进行权限控制，如果需要更细粒度的权限（例如，`SettingsPage` 可能只允许 `admin` 访问）。

### 3. 迁移相关页面组件

*   将 `TrialsPage`, `PersonnelPage`, `BookManagementPage`, `SettingsPage` 等组件的路由定义从 `App` 路由的 `children` 数组中移除。
*   将这些组件的导入和路由定义移动到 `/admin` 路由的 `children` 数组中。

### 4. 更新现有侧边栏 `Sidebar.jsx`

*   **路径**: `calendar_with_react/src/components/Sidebar.jsx`
*   **修改内容**:
    *   从侧边栏的导航项列表中移除指向“试验管理”、“人员管理”、“书籍管理”和“设置”页面的链接。
    *   在 `Sidebar.jsx` 中添加一个新的导航项，例如“管理中心”或“高级管理”，指向新的 `/admin` 路径。
    *   这个新的导航项将使用 `ProtectedRoute` 或 `hasPermission` 检查，确保只有 `admin` 和 `manager` 角色可见。

### 5. 权限细化与验证

*   确保 `ProtectedRoute` 在 `AdminLayout` 及其子路由中正确应用，以强制执行 `admin` 和 `manager` 角色的访问限制。
*   考虑在用户没有权限访问时，如何优雅地处理重定向到 `UnauthorizedPage` 或显示友好的提示信息。

### 6. 文件结构调整

*   **创建新目录**: `calendar_with_react/src/components/Admin/`
*   将 `AdminLayout.jsx` 和任何与管理侧边栏或导航相关的组件放置在此目录下，以保持项目结构的清晰和模块化。

## Mermaid 图表

```mermaid
graph TD
    A[用户] --> B(访问应用)
    B --> C{是否已认证?}
    C -- 是 --> D[App Layout (ProtectedRoute)]
    C -- 否 --> E[登录/注册]

    D --> F[日历页面]
    D --> G[文档管理页面]
    D --> H[书库页面]
    D --> I[其他普通页面]
    D --> J(管理中心入口) -- 权限检查(`admin`, `manager`) --> K[Admin Layout (ProtectedRoute)]

    K --> M[试验管理页面]
    K --> N[人员管理页面]
    K --> O[书籍管理页面]
    K --> P[设置页面]
    K --> Q[新的管理导航]

    J -- 无权限 --> L[未经授权页面]
    K -- 无权限 --> L