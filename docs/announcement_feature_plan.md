# 公告功能开发计划

## 概述

为了优化公告栏的显示样式，并为管理员提供发布和修改公告的功能，特制定本计划。

## 核心需求

1.  **样式优化**: 优化公告栏的视觉效果。
2.  **内容截断**: 对于较长的公告文本，默认简略显示，并提供“查看更多”选项以展示全文。
3.  **后台管理**: 新增一个管理页面，用于发布和修改公告。
4.  **发布者信息**: 在公告中显示发布者的姓名。

## 技术方案

### 后端 (Django)

1.  **数据模型**: 在 `events` 应用的 `models.py` 文件中，创建一个新的 `Announcement` 模型。
    *   `title`: 公告标题 (CharField)
    *   `content`: 公告内容 (TextField)
    *   `author`: 发布者 (ForeignKey, 关联到 `users.CustomUser`)
    *   `created_at`: 创建时间 (DateTimeField, auto_now_add=True)
    *   `updated_at`: 更新时间 (DateTimeField, auto_now=True)
2.  **序列化器**: 创建 `AnnouncementSerializer` 用于将 `Announcement` 模型实例序列化为 JSON 格式。
3.  **视图集**: 创建 `AnnouncementViewSet`，提供标准的 CRUD 操作，并使用 `manage_announcements` 权限进行访问控制。
4.  **路由**: 在 `events` 应用的 `urls.py` 中为 `AnnouncementViewSet` 注册路由，使其可以通过 `/api/announcements/` 访问。

### 前端 (React)

1.  **公告展示页面 (`AnnouncementsPage.jsx`)**:
    *   修改 `useEffect` hook，从 `/api/announcements/` API 端点获取公告数据。
    *   实现一个可展开/折叠的组件，用于处理长篇公告的“查看更多”功能。
    *   更新组件的 CSS (`AnnouncementsPage.css`) 以优化样式，并确保发布者信息正确显示。
2.  **公告管理页面 (`ManageAnnouncementsPage.jsx`)**:
    *   创建一个新页面，用于展示所有公告的列表。
    *   提供“新建公告”和“编辑”按钮。
3.  **公告表单 (`AnnouncementForm.jsx`)**:
    *   创建一个新组件，包含用于输入公告标题和内容的表单。
    *   处理表单提交逻辑，分别对应创建（POST）和更新（PUT/PATCH）公告的 API 请求。
4.  **路由与导航 (`Sidebar.jsx`, `routes/index.js`)**:
    *   在侧边栏中添加一个指向“公告管理”页面的链接。
    *   使用 `manage_announcements` 权限来控制该链接的可见性。
    *   在路由配置中添加新页面的路由。

### 数据库

1.  **数据库迁移**:
    *   运行 `python manage.py makemigrations events` 来创建新的数据库迁移文件。
    *   运行 `python manage.py migrate` 来将模型变更应用到数据库。

## 实施计划图

```mermaid
graph TD
    subgraph 后端 (Django)
        A[在 models.py 中创建包含 author 的 Announcement 模型] --> B[创建 AnnouncementSerializer];
        B --> C[创建 AnnouncementViewSet];
        C --> D[在 urls.py 中注册路由];
    end

    subgraph 前端 (React)
        E[修改 AnnouncementsPage.jsx 获取真实数据并显示发布者] --> F[实现“查看更多”功能];
        F --> G[优化公告样式];
        G --> H[创建 AnnouncementForm.jsx];
        H --> I[创建 ManageAnnouncementsPage.jsx];
        I --> J[在侧边栏和路由中添加链接和权限];
    end

    subgraph 数据库
        K[创建数据库迁移] --> L[应用数据库迁移];
    end

    A --> K;
    D --> E;