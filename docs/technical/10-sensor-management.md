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

---

## 5. 校准提醒通知（接 NotificationService,P0-L,2026-07 批次）

> 完整审计轨迹见 [41-p0-security-data-safety-batch-2026-07.md §1.6](41-p0-security-data-safety-batch-2026-07.md)。本节聚焦修复前"模拟通知"的假闭环。

### 背景

[`sensor_management/tasks.py`](omni_desk_backend/sensor_management/tasks.py) 历史实现 `send_notification(sensor, today)` 仅 `logger.info("calibration reminder ...")` —— **真正的 NotificationService 调用从未发生**,管理员无法在通知中心看到校准提醒。**2026-07 P0 批次**接 `NotificationService` + `dedupe_key`。

### 修复实现

```python
# omni_desk_backend/sensor_management/tasks.py
def send_notification(sensor, today):
    from notifications.services import NotificationService

    target_user = getattr(sensor, 'responsible_user', None) or _first_admin()
    NotificationService.create(
        user=target_user,
        type='calibration_reminder',
        dedupe_key=f'calibration:{sensor.id}:{today.isoformat()}',
        priority='normal',
        payload={
            'sensor_id': sensor.id,
            'sensor_number': sensor.sensor_number,
            'last_calibrated_at': sensor.last_calibrated_at.isoformat() if sensor.last_calibrated_at else None,
        },
    )
```

**注:** 旧 Sensor 模型无 `responsible_user` 字段,实际接收人回退到"第一个 admin"。如未来增加负责人字段,改用 `sensor.responsible_user`。

### 测试覆盖

`omni_desk_backend/sensor_management/tests/test_calibration_notification.py`:

- ✅ `test_calibration_reminder_creates_notification`:mock `timezone.now()` 到到期日,跑命令,断言 `Notification` 表有 `type='calibration_reminder'` + `dedupe_key` 一致。
- ✅ `test_deduped_reminder_not_resent_same_day`:同一日重复跑命令,断言只产生一条通知。
- ✅ `test_calibration_overdue_severity_escalates`:超期传感器 urgent 优先级。

### 用户侧效果

- 管理员打开 `/notifications` 能看到 "🔧 传感器 S-2024-001 已到期校准" 类型提醒
- 通知详情包含 sensor number、上次校准日期、过期天数