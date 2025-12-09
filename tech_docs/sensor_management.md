# 技术文档：传感器全生命周期管理

## 1. 概述

传感器管理是一个功能强大且复杂的模块，旨在提供对传感器从入库、使用、校准到报废的全生命周期跟踪和管理。该模块由后端的 `sensor_management` 应用提供核心支持，并包含一个用于定时任务的 `tasks` 模块。

**注意**: 当前后端路由配置不完整，部分已在视图中定义的功能（如类别管理、出入库管理等）尚未通过URL暴露给前端。

---

## 2. 后端实现 (`sensor_management` 应用)

### 2.1. 数据模型

该应用包含了一套完整的、相互关联的模型来描述传感器的各个方面。

- **`Sensor`**: [`omni_desk_backend/sensor_management/models.py`](omni_desk_backend/sensor_management/models.py:6)
  - 核心模型，记录了传感器的唯一标识（`sensor_number`, `serial_number`）、静态属性（`manufacturer`, `calibration_interval_days`）、动态状态（`status`, `current_quantity`）以及关联信息（`sensor_category`, `location`）。
  - 通过 `@property` 动态计算下一次校准日期 `next_calibration_date`。

- **`SensorCategory` & `StorageLocation`**: [`omni_desk_backend/sensor_management/models.py`](omni_desk_backend/sensor_management/models.py)
  - 分别用于定义传感器的类别和物理存放位置，实现了数据的规范化管理。

- **`SensorMovement`**: [`omni_desk_backend/sensor_management/models.py`](omni_desk_backend/sensor_management/models.py:66)
  - 记录传感器的每一次库存变动（入库/出库），包括操作人员、数量、日期和原因。这是实现库存跟踪的关键。

- **`SensorCalibration` & `CalibrationDataPoint`**: [`omni_desk_backend/sensor_management/models.py`](omni_desk_backend/sensor_management/models.py)
  - `SensorCalibration` 详细记录了一次校准操作的所有信息，如校准仪器、环境参数、校准人、审核人等。
  - `CalibrationDataPoint` 记录了该次校准中具体的压力和电压数据点，为生成校准报告提供了原始数据。

- **`CalibrationReminder`**: [`omni_desk_backend/sensor_management/models.py`](omni_desk_backend/sensor_management/models.py:88)
  - 用于存储由定时任务生成的校准提醒记录，包含提醒日期、是否已发送等状态。

### 2.2. 核心业务逻辑与API

- **`SensorViewSet`**: [`omni_desk_backend/sensor_management/views.py`](omni_desk_backend/sensor_management/views.py:13)
  - 提供了对 `Sensor` 模型的CRUD操作。

- **`SensorMovementViewSet`**: [`omni_desk_backend/sensor_management/views.py`](omni_desk_backend/sensor_management/views.py:20)
  - **关键业务逻辑**: 在 `perform_create` 和 `perform_update` 方法中，实现了在创建或修改出入库记录时，自动更新关联 `Sensor` 的 `current_quantity` (当前数量) 和 `status` (状态) 的功能。这确保了传感器库存数据的实时准确性。

- **其他 `ViewSet`**:
  - 应用内还为 `SensorCategory`, `StorageLocation`, `SensorCalibration`, `CalibrationReminder` 等模型提供了相应的 `ViewSet`，用于管理这些辅助数据。

### 2.3. 定时任务 (`tasks.py`)

- **`check_and_create_calibration_reminders`**: [`omni_desk_backend/sensor_management/tasks.py`](omni_desk_backend/sensor_management/tasks.py:25)
  - 这是一个通过 Celery 调度的后台定时任务。
  - **功能**: 定期扫描所有 `Sensor`，根据其 `last_calibration_date` 和 `calibration_interval_days` 判断是否即将或已经到期。
  - 如果传感器需要校准，并且当天尚未生成提醒，任务会自动创建一个 `CalibrationReminder` 记录，并模拟向管理员/经理发送通知。

---

## 3. 前端实现

前端实现了一系列页面来与 `sensor_management` 后端进行交互。

- **`SensorManagementPage.jsx`**: 传感器列表和基本管理的主入口。
- **`SensorCategoryManagementPage.jsx`**: 管理传感器类别。
- **`StorageLocationManagementPage.jsx`**: 管理存放位置。
- **`SensorMovementHistoryPage.jsx`**: 查看传感器出入库历史。
- **`SensorCalibrationHistoryPage.jsx`**: 查看特定传感器的校准历史记录。
- **`AddCalibrationRecordPage.jsx`**: 添加新的校准记录。

---

## 4. 已知问题

- **路由配置不完整**: 后端应用 `sensor_management` 的 `urls.py` 文件目前只注册了 `/api/sensor-management/sensors/` 这一个端点。其他如 `SensorCategoryViewSet`, `SensorMovementViewSet` 等虽然已在 `views.py` 中定义，但并未注册路由，导致前端无法访问 `/api/sensor-management/sensor-categories/` 等API，功能无法正常使用。