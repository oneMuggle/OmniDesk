# 书籍管理功能拆分计划

## 任务目标
在管理中心中，将书籍管理中的内容分为两个页面：
1. 书籍导入相关功能
2. 管理书籍和导出书籍相关功能

并将这两个页面都放在书籍管理链接下。

## 详细计划

### 步骤 1：创建新的组件文件

*   **创建 `calendar_with_react/src/components/BookImportPage.jsx`**：
    将 `BookManagementPage.jsx` 中处理书籍导入逻辑（`handleSubmit` 函数及相关状态和表单 UI）的代码迁移到这个新文件。

*   **创建 `calendar_with_react/src/components/BookManageExportPage.jsx`**：
    将 `BookManagementPage.jsx` 中处理书籍管理（`fetchBooks`, `handleDeleteBook`）和导出（`handleExportMarkdown`）逻辑及相关列表 UI 的代码迁移到这个新文件。

### 步骤 2：删除 `BookManagementPage.jsx`

*   `BookManagementPage.jsx` 将不再需要，它将被拆分为两个独立的页面。

### 步骤 3：修改前端路由配置 (`calendar_with_react/src/routes/index.js`)

*   删除原有的 `/admin/book-management` 路由及其对应的 `BookManagementPage` 组件引用。
*   在 `/admin` 路径下，直接添加 `/admin/book-import` 路由，将元素指向 `BookImportPage` 组件。
*   添加 `/admin/book-manage-export` 路由，将元素指向 `BookManageExportPage` 组件。

### 步骤 4：更新 `AdminLayout.jsx` 侧边栏菜单

*   在 `AdminLayout.jsx` 中，在“书籍管理”菜单项下，添加两个子菜单项：
    *   “书籍导入”，指向 `/admin/book-import`。
    *   “书籍管理与导出”，指向 `/admin/book-manage-export`。

### 步骤 5：后端 API 确认

*   现有的后端 API (`/api/documents/import_book/` 和 `/api/documents/books/`) 能够支持前端的拆分，因此无需修改后端代码。

### 步骤 6：测试

*   确保新的路由和组件能够正常工作。
*   验证书籍导入、书籍管理和导出功能在新的页面结构下依然可用。

```mermaid
graph TD
    A[用户任务: 拆分书籍管理功能] --> B(创建 BookImportPage.jsx);
    A --> C(创建 BookManageExportPage.jsx);
    B --> D(删除 BookManagementPage.jsx);
    C --> D;
    D --> E(修改 routes/index.js 路由);
    E --> F(更新 AdminLayout.jsx 侧边栏);
    F --> G(功能测试);