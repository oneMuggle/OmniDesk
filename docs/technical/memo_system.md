# 技术文档：备忘录系统

## 1. 概述

备忘录系统是一个为单个用户提供私人备忘录管理的功能模块。它允许用户创建、查看、编辑和删除自己的备忘录，并可以为备忘录设置提醒时间。该功能拥有独立的前端页面，数据与用户账户绑定，确保了隐私性。

---

## 2. 后端实现 (`memos` 应用)

该功能由一个全新的 `memos` Django 应用提供支持。

### 2.1. 数据模型

- **`Memo`**: [`omni_desk_backend/memos/models.py`](omni_desk_backend/memos/models.py:4)
  - 这是备忘录系统的核心模型，定义了一个备忘录实体。
  - **核心字段**:
    - `user`: 外键，强制将每条备忘录关联到一个 `CustomUser`，确保数据隔离。
    - `title`: 备忘录标题。
    - `content`: 备忘录的详细内容。
    - `reminder_time`: 一个可为空的 `DateTimeField`，用于设置提醒时间。
    - `is_completed`: 布尔字段，用于标记备忘录是否已完成。

### 2.2. API 视图

- **`MemoViewSet`**: [`omni_desk_backend/memos/views.py`](omni_desk_backend/memos/views.py:6)
  - 一个标准的 `ModelViewSet`，提供对 `Memo` 模型的完整CRUD操作。
  - **端点**: `/api/memos/`
  - **权限与数据隔离**:
    - `permission_classes = [IsAuthenticated]`: 确保只有登录用户才能访问此API。
    - `get_queryset()`: 此方法被重写，强制API只返回当前登录用户的备忘录数据 (`Memo.objects.filter(user=self.request.user)`)。
    - `perform_create()`: 此方法被重写，在创建新备忘录时，自动将 `user` 字段设置为当前登录用户。
    - 通过这些机制，后端在API层面保证了用户只能操作自己的备忘录数据。

### 2.3. URL 路由

- [`omni_desk_backend/memos/urls.py`](omni_desk_backend/memos/urls.py) 文件为 `MemoViewSet` 注册了API端点，并通过主 `urls.py` 文件暴露给前端。

---

## 3. 前端实现

前端实现了一个独立的、功能聚合的备忘录页面。

- **主页面**: [`omni_desk_frontend/src/pages/MemoPage.jsx`](omni_desk_frontend/src/pages/MemoPage.jsx)
  - 这是备忘录功能的入口和核心容器页面。
  - 它整合了以下所有子组件，并负责状态管理和数据流转。

- **核心组件**:
  - **`MiniCalendar`**: [`omni_desk_frontend/src/components/Memo/MiniCalendar.jsx`](omni_desk_frontend/src/components/Memo/MiniCalendar.jsx)
    - 一个紧凑的日历视图。
    - 它会高亮显示那些包含备忘录的日期。
    - 用户可以通过点击日期来筛选并显示该日期的备忘录列表。
  - **`MemoList`**: [`omni_desk_frontend/src/components/Memo/MemoList.jsx`](omni_desk_frontend/src/components/Memo/MemoList.jsx)
    - 负责展示备忘录列表。
    - 列表中的每一项都包含标题、内容、完成状态切换、编辑和删除按钮。
  - **`MemoModal`**: [`omni_desk_frontend/src/components/Memo/MemoModal.jsx`](omni_desk_frontend/src/components/Memo/MemoModal.jsx)
    - 一个弹窗组件，用于创建新的备忘录或编辑现有的备忘录。
    - 包含标题、内容和提醒时间等输入字段。

- **数据交互**:
  - 前端通过一个专门的API客户端（如 `memoApi.js`）与后端的 `/api/memos/` 端点进行通信。
  - 通常会使用自定义Hook（如 `useMemoData`）来封装数据获取、缓存和更新逻辑（例如，使用 `react-query`）。

- **定时提醒**:
  - 前端通过定时器（如 `setInterval`）定期检查所有备忘录的 `reminder_time`。
  - 当发现有备忘录的提醒时间到达时，会使用浏览器的 `Notification` API 来向用户发送桌面通知。此功能依赖于用户保持浏览器页面打开。