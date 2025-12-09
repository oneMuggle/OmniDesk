# 技术文档：用户交流模块

## 1. 概述

用户交流模块旨在提供一个内部的、类似论坛的功能，允许用户发布帖子并进行评论。该功能由后端的 `communication` 应用提供 API 支持。

**注意**: 截至目前，该模块仅实现了后端 API，尚未开发对应的前端用户界面。

---

## 2. 后端实现 (`communication` 应用)

### 2.1. 数据模型

- **`Post`**: [`omni_desk_backend/communication/models.py`](omni_desk_backend/communication/models.py:4)
  - 定义了一个帖子实体。
  - **核心字段**:
    - `title`: 帖子标题。
    - `content`: 帖子内容。
    - `author`: 外键，关联到 `CustomUser`，记录帖子作者。
    - `expires_at`: 可选字段，用于设置帖子的过期时间。
    - `is_archived`: 布尔字段，用于软删除或归档帖子。

- **`Comment`**: [`omni_desk_backend/communication/models.py`](omni_desk_backend/communication/models.py:16)
  - 定义了一条评论实体。
  - **核心字段**:
    - `post`: 外键，将评论关联到一个 `Post`。
    - `author`: 外键，关联到 `CustomUser`，记录评论作者。
    - `content`: 评论内容。

### 2.2. API 视图

- **`PostViewSet`**: [`omni_desk_backend/communication/views.py`](omni_desk_backend/communication/views.py:6)
  - 提供对 `Post` 模型的CRUD操作。
  - **端点**: `/api/communication/posts/`
  - **权限与数据隔离**:
    - `permission_classes = [IsAuthenticated]`: 确保只有登录用户才能访问。
    - `get_queryset()`: 此方法被重写，在 `list` action (列表视图) 下，只返回当前用户发布的帖子。在其他 action (如详情、更新、删除) 中，可以访问所有未归档的帖子。
    - `perform_create()`: 自动将新帖子的作者设置为当前登录用户。

- **`CommentViewSet`**: [`omni_desk_backend/communication/views.py`](omni_desk_backend/communication/views.py:21)
  - 提供对 `Comment` 模型的CRUD操作。
  - **端点**: `/api/communication/comments/`
  - **查询与筛选**: `get_queryset` 方法被重写，支持通过 `post_id` 查询参数来获取特定帖子下的所有评论。
  - `perform_create()`: 自动将新评论的作者设置为当前登录用户。

### 2.3. URL 路由

- [`omni_desk_backend/communication/urls.py`](omni_desk_backend/communication/urls.py) 文件为 `PostViewSet` 和 `CommentViewSet` 注册了相应的 API 端点。

---

## 3. 前端实现 (规划中)

根据 `user_system_master_plan.md` 中的设计，前端需要实现以下页面来完成此功能：

- **`PostListPage.jsx`**:
  - 用于展示帖子列表，应支持搜索和过滤。
  - 提供创建新帖子的入口。
- **`PostDetailPage.jsx`**:
  - 展示单个帖子的详细内容以及其下的所有评论。
  - 包含一个 `CommentList.jsx` 组件来展示评论，以及一个 `CommentForm.jsx` 组件来提交新评论。
- **`PostForm.jsx`**:
  - 一个包含富文本编辑器的表单，用于创建或编辑帖子。