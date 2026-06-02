# 技术文档：排班与试验管理

## 1. 概述

本模块由后端的 `events` 应用统一提供支持，涵盖了日常排班管理和项目试验管理两大核心功能。系统不仅支持手动的排班调整，还实现了基于预设顺序的自动排班生成。同时，它也提供了对“试验”从创建到完成的全生命周期管理。

---

## 2. 后端实现 (`events` 应用)

### 2.1. 排班管理

排班管理的核心是围绕 `Schedule` 模型和相关的顺序定义模型展开的。

- **数据模型**:
  - **`Schedule`**: [`omni_desk_backend/events/models.py`](omni_desk_backend/events/models.py:182)
    - 记录每一天的排班信息，核心字段包括 `duty_date` (值班日期), `duty_person` (值班人员), 和 `duty_leader` (值班领导)。
  - **`PersonnelSequence`**: [`omni_desk_backend/events/models.py`](omni_desk_backend/events/models.py:247)
    - 用于定义自动排班时的工作日和节假日的值班人员顺序。`sequence` 和 `holiday_sequence` 字段以JSON格式存储人员ID列表。
  - **`LeaderSequence`**: [`omni_desk_backend/events/models.py`](omni_desk_backend/events/models.py:271)
    - 用于定义值班领导的顺序，同样以JSON格式存储人员ID列表。
  - **`Holiday`**: [`omni_desk_backend/events/models.py`](omni_desk_backend/events/models.py:303)
    - 用于定义节假日日期，以便在自动排班时应用不同的规则。

- **API 视图**:
  - **`ScheduleViewSet`**: [`omni_desk_backend/events/views.py`](omni_desk_backend/events/views.py:125)
    - 提供对 `Schedule` 模型的CRUD操作。
    - **`generate_schedules` (自定义 Action)**: 这是自动排班的核心API。
      - **端点**: `POST /api/events/schedules/generate-schedules/`
      - **功能**: 接收 `personnel_sequence_id`, `leader_sequence_id`, 起始日期/月份, 以及可选的起始人员/领导等参数，然后根据 `PersonnelSequence` 和 `LeaderSequence` 中定义的顺序，结合 `Holiday` 数据，自动生成指定时间范围内的排班记录。
    - **`swap_dates` / `swap_weekly_leaders` (自定义 Action)**: 提供交换排班的便捷操作。
  - **`PersonnelSequenceViewSet` / `LeaderSequenceViewSet`**: [`omni_desk_backend/events/views.py`](omni_desk_backend/events/views.py)
    - 提供对人员和领导顺序的CRUD管理功能。

### 2.2. 试验管理

试验管理功能允许用户跟踪和管理项目试验。

- **数据模型**:
  - **`Trial`**: [`omni_desk_backend/events/models.py`](omni_desk_backend/events/models.py:87)
    - 定义一个试验实体，包含标题、客户、描述、负责人、状态等。
    - 其 `start_date` 和 `end_date` 是根据关联的 `TimeSlot` 自动计算得出的。
  - **`TimeSlot`**: [`omni_desk_backend/events/models.py`](omni_desk_backend/events/models.py:51)
    - 定义试验中的一个具体时间段，包含起止时间和描述。`Trial` 的时间范围由其所有 `TimeSlot` 的最小开始时间和最大结束时间决定。
  - **`Equipment` / `Personnel`**: 定义试验可能涉及的设备和人员。

- **API 视图**:
  - **`TrialViewSet`**: [`omni_desk_backend/events/views.py`](omni_desk_backend/events/views.py:441)
    - 提供对 `Trial` 模型的完整CRUD操作。
  - **`TimeSlotViewSet`**: [`omni_desk_backend/events/views.py`](omni_desk_backend/events/views.py:39)
    - 提供对 `TimeSlot` 模型的CRUD操作。

---

## 3. 前端实现

前端为排班和试验管理提供了专门的管理页面。

- **排班管理页面**: [`omni_desk_frontend/src/pages/ScheduleManagementPage.jsx`](omni_desk_frontend/src/pages/ScheduleManagementPage.jsx)
  - 集成了日历组件，用于可视化展示排班信息。
  - 提供了一个界面来调用后端的 `generate_schedules` API，允许用户选择人员/领导顺序、起止日期等参数来自动生成排班。
  - 支持手动的排班增、删、改操作。

- **人员管理页面**: [`omni_desk_frontend/src/pages/PersonnelManagementPage.jsx`](omni_desk_frontend/src/pages/PersonnelManagementPage.jsx)
  - 提供对 `Personnel` 信息的管理，这是排班的基础数据。

- **试验日历页面**: (例如 `TrialCalendarPage.jsx`)
  - 以日历或列表形式展示所有 `Trial` 和 `TimeSlot`。
  - 提供创建和编辑试验的功能。