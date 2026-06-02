# 技术文档：公告系统

## 1. 概述

公告系统允许授权用户（管理员和经理）发布、编辑和删除包含富文本内容的公告。所有登录用户均可查看公告。该系统支持图片上传和展示，并提供了一个用户友好的前端界面进行管理和浏览。

---

## 2. 后端实现 (`events` 应用)

### 2.1. 数据模型

- **`Announcement`**: [`omni_desk_backend/events/models.py`](omni_desk_backend/events/models.py:217)
  - `title`: 公告标题。
  - `content`: 公告内容，存储由前端富文本编辑器生成的HTML字符串。
  - `author`: 外键，关联到 `CustomUser` 模型，记录发布者。
  - `created_at`, `updated_at`: 自动记录创建和更新时间。

- **`UploadedImage`**: [`omni_desk_backend/events/models.py`](omni_desk_backend/events/models.py:240)
  - `image`: `ImageField`，用于存储上传的图片文件。
  - `uploaded_at`: 自动记录上传时间。
  - 此模型专门用于处理富文本编辑器中的图片上传。

### 2.2. API 视图

- **`AnnouncementViewSet`**: [`omni_desk_backend/events/views.py`](omni_desk_backend/events/views.py:557)
  - 一个标准的 `ModelViewSet`，提供对 `Announcement` 模型的完整CRUD操作。
  - **端点**: `/api/events/announcements/`
  - **权限**: `IsAdminOrManagerOrReadOnly`。这意味着：
    - `GET` (读取): 任何已认证的用户都可以访问。
    - `POST`, `PUT`, `PATCH`, `DELETE` (写入/修改/删除): 仅限于角色为“管理员”或“经理”的用户。
  - `perform_create` 方法会自动将当前登录用户设置为公告的 `author`。

- **`ImageUploadView`**: [`omni_desk_backend/events/views.py`](omni_desk_backend/events/views.py:565)
  - 一个独立的 `APIView`，专门用于处理图片上传。
  - **端点**: `/api/events/upload-image/`
  - **权限**: `IsAuthenticated`。任何登录用户都可以上传图片，但该端点主要由公告表单内部调用。
  - 接收 `multipart/form-data` 格式的请求，保存图片并返回图片的URL。

---

## 3. 前端实现

### 3.1. 公告管理

- **管理页面**: [`omni_desk_frontend/src/pages/ManageAnnouncementsPage.jsx`](omni_desk_frontend/src/pages/ManageAnnouncementsPage.jsx)
  - 此页面以表格形式列出所有公告，并提供“编辑”和“删除”按钮。
  - 包含一个“发布新公告”的链接，指向公告表单。

- **公告表单**: [`omni_desk_frontend/src/components/AnnouncementForm.jsx`](omni_desk_frontend/src/components/AnnouncementForm.jsx)
  - 这是一个核心组件，用于创建和编辑公告。
  - 使用 `react-quill` 库作为富文本编辑器。
  - **图片上传**: 实现了一个自定义的 `imageHandler`，当用户点击编辑器中的图片按钮时：
    1.  创建一个文件输入框。
    2.  用户选择图片后，将图片文件POST到后端的 `ImageUploadView`。
    3.  获取返回的图片URL，并将其插入到编辑器内容中。
  - 表单提交时，将标题和包含HTML内容的 `content` 发送到后端的 `AnnouncementViewSet`。

### 3.2. 公告展示

- **展示页面**: [`omni_desk_frontend/src/pages/AnnouncementsPage.jsx`](omni_desk_frontend/src/pages/AnnouncementsPage.jsx)
  - 从 `/api/events/announcements/` 获取公告列表。
  - 使用 `react-slick` 库将公告以轮播（Slider）的形式展示。
  - **内容渲染**: 使用 `dangerouslySetInnerHTML` 属性来渲染从后端获取的HTML内容，从而正确显示富文本格式。
  - 为了避免过长的公告撑破布局，对超过一定长度的内容进行了截断，并提供“查看更多”/“收起”的切换按钮。

---

## 4. 安全说明

- **XSS风险**: 由于系统直接渲染由管理员输入的HTML (`dangerouslySetInnerHTML`)，存在潜在的跨站脚本（XSS）风险。
- **当前策略**: 基于对内容发布者（管理员/经理）的信任，目前未在后端或前端实施HTML清理。在对安全性要求更高的场景下，应考虑引入如 `DOMPurify` 之类的库来过滤恶意脚本。