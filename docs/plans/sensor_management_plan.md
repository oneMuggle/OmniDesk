# 传感器管理页面实施计划

本文档概述了传感器管理页面的实施计划，旨在增强其功能以显示、创建、编辑和删除传感器。

## 1. UI 设计

传感器管理页面将使用 Ant Design 的 `Table` 组件来显示传感器列表。

- **页面布局**:
    - 页面顶部将包含一个标题“传感器管理”。
    - 标题下方将有一个“新增传感器”按钮，点击后会弹出一个用于创建新传感器的模态框。
    - 页面主体将是一个表格，用于显示所有传感器。

## 2. 传感器列表

表格将显示以下列：

- **名称**: 传感器的名称。
- **类别**: 传感器的类别 (例如, "温度", "湿度")。
- **存放地点**: 传感器的物理存放位置。
- **状态**: 传感器的当前状态 (例如, "正常", "需校准", "维修中")。
- **操作**: 针对每个传感器的可用操作。

## 3. 可用操作

对于列表中的每个传感器，将提供以下操作按钮：

- **查看详情**: 导航到传感器的详细信息页面 (`/sensors/:id`)。
- **编辑**: 打开一个模态框，其中包含一个表单，用于修改传感器的详细信息。
- **删除**: 显示一个确认对话框，在确认后从系统中删除传感器。

## 4. API 端点

将使用以下 API 端点来管理传感器数据：

- `GET /api/sensor-management/sensors/`: 获取所有传感器的列表。
- `POST /api/sensor-management/sensors/`: 创建一个新传感器。
- `PUT /api/sensor-management/sensors/:id/`: 更新现有传感器的信息。
- `DELETE /api/sensor-management/sensors/:id/`: 删除一个传感器。

## 5. 组件变更

### 5.1. 需要修改的文件

- **`omni_desk_frontend/src/features/sensor/pages/SensorManagementPage.jsx`**:
    - 将完全重构此页面。
    - 它将使用 `useQuery` (或类似的 hook) 从 `getSensors` API 获取数据。
    - 它将渲染一个 `Table` 组件来显示数据。
    - 它将包含处理“新增”、“编辑”和“删除”操作的逻辑。

- **`omni_desk_frontend/src/features/sensor/api/sensorApi.js`**:
    - 将添加 `updateSensor(id, data)` 函数来处理 `PUT` 请求。
    - 将添加 `deleteSensor(id)` 函数来处理 `DELETE` 请求。

### 5.2. 需要创建的新组件

- **`omni_desk_frontend/src/features/sensor/components/SensorForm.jsx`**:
    - 这是一个新的可重用表单组件，用于创建和编辑传感器。
    - 它将包含名称、类别、存放地点和状态的输入字段。
    - 类别和存放地点将是下拉选择框，数据分别从 `getSensorCategories` 和 `getStorageLocations` API 获取。
    - 此表单将在一个模态框中显示。