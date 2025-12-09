# 技术文档：会议室预约系统

## 1. 概述

会议室预约系统是一个独立的、功能完善的模块，旨在提供全面的会议室预定和管理服务。它允许普通用户浏览和预约会议室，同时为管理员和经理提供了管理会议室、维护计划和查看使用统计的后台功能。

---

## 2. 后端实现 (`meeting_rooms` 应用)

该功能由一个全新的 `meeting_rooms` Django 应用提供支持。

### 2.1. 数据模型

- **`MeetingRoom`**: [`omni_desk_backend/meeting_rooms/models.py`](omni_desk_backend/meeting_rooms/models.py:6)
  - 定义了一个会议室实体，包含名称、描述、容量和位置等基本信息。

- **`MeetingRoomBooking`**: [`omni_desk_backend/meeting_rooms/models.py`](omni_desk_backend/meeting_rooms/models.py:19)
  - 记录了每一条预约信息，关联到特定的 `MeetingRoom` 和 `CustomUser`。
  - 包含预约主题、参与人员、开始/结束时间等字段。
  - **核心验证逻辑**: 模型中的 `clean()` 方法实现了强大的业务逻辑验证，在数据保存到数据库之前，会自动检查：
    1.  结束时间是否晚于开始时间。
    2.  预约时间是否在当前时间之后。
    3.  与同一会议室的其他 `MeetingRoomBooking` 是否存在时间冲突。
    4.  与该会议室的 `MeetingRoomMaintenance` 记录是否存在时间冲突。

- **`MeetingRoomMaintenance`**: [`omni_desk_backend/meeting_rooms/models.py`](omni_desk_backend/meeting_rooms/models.py:72)
  - 允许管理员为会议室设置维护时段，包含起止时间和维护原因。
  - 同样具有 `clean()` 方法，以防止维护计划与现有预约或其他维护计划发生冲突。

### 2.2. API 视图

- **`MeetingRoomViewSet`**: [`omni_desk_backend/meeting_rooms/views.py`](omni_desk_backend/meeting_rooms/views.py:15)
  - 提供对 `MeetingRoom` 模型的CRUD操作，所有认证用户均可访问。

- **`MeetingRoomBookingViewSet`**: [`omni_desk_backend/meeting_rooms/views.py`](omni_desk_backend/meeting_rooms/views.py:20)
  - 提供对 `MeetingRoomBooking` 模型的CRUD操作。
  - **权限控制**:
    - 所有认证用户都可以查看所有预约并创建自己的预约。
    - 只有预约的创建者、管理员或经理才能修改或删除预约。
  - **自定义API**: 包含一个 `this-week` 的自定义 action，用于快速获取本周的预约数据。

- **`MeetingRoomMaintenanceViewSet`**: [`omni_desk_backend/meeting_rooms/views.py`](omni_desk_backend/meeting_rooms/views.py:66)
  - 提供对 `MeetingRoomMaintenance` 模型的CRUD操作。
  - **权限控制**: 仅限管理员和经理访问。

- **`MeetingRoomStatsAPIView`**: [`omni_desk_backend/meeting_rooms/views.py`](omni_desk_backend/meeting_rooms/views.py:71)
  - 一个只读的API视图，用于提供会议室使用情况的统计报告。
  - **端点**: `/api/meeting-rooms/meeting-room-stats/`
  - **功能**: 可根据时间范围和会议室ID进行筛选，返回总预约次数、总预约时长以及每个会议室的详细统计数据。
  - **权限控制**: 仅限管理员和经理访问。

### 2.3. URL 路由

- [`omni_desk_backend/meeting_rooms/urls.py`](omni_desk_backend/meeting_rooms/urls.py) 文件为上述所有 `ViewSet` 和 `APIView` 注册了相应的API端点，并通过主 `urls.py` 文件以 `/api/meeting-rooms/` 为前缀暴露给前端。

---

## 3. 前端实现

- **会议室预约页面**: [`omni_desk_frontend/src/pages/MeetingRoomBookingPage.jsx`](omni_desk_frontend/src/pages/MeetingRoomBookingPage.jsx)
  - 作为用户预约会议室的主要界面。
  - 通常会集成一个日历组件（如 `react-big-calendar`）来可视化地展示已有预约。
  - 用户可以通过点击日历或表单来创建新的预约。
  - 页面会根据当前用户的角色，决定是否显示编辑和删除他人预约的权限。

- **会议室管理页面**: [`omni_desk_frontend/src/pages/MeetingRoomManagementPage.jsx`](omni_desk_frontend/src/pages/MeetingRoomManagementPage.jsx)
  - 这是一个仅对管理员和经理可见的管理后台页面。
  - 提供对 `MeetingRoom` 实体本身的增删改查功能。
  - 提供界面来管理会议室的 `MeetingRoomMaintenance` 记录。
  - 展示由 `MeetingRoomStatsAPIView` 提供的统计数据，可能以图表或表格形式呈现。