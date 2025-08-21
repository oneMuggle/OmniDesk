# 排班生成功能增强计划

## 1. 目标

增强排班管理页面的排班生成功能，实现以下目标：

1.  **指定起始人员/领导**：在按顺序生成排班时，可以指定从哪位人员和领导开始。
2.  **按月份生成**：除了按指定天数生成外，增加按整个月份生成排班的选项。

## 2. 修订版开发计划

### 2.1. 后端修改 (Django)

**文件**: `omni_desk_backend/events/views.py`
**函数**: `ScheduleViewSet.generate_schedules`

*   **新增生成模式**: 函数将支持两种生成模式：按“持续天数”或按“指定月份”。
*   **参数调整**:
    *   接收 `target_month` (格式: "YYYY-MM") 或 `duration_days`。这两个参数是互斥的。
    *   接收可选参数 `start_personnel_id` 和 `start_leader_id`。
*   **逻辑调整**:
    *   如果提供了 `target_month`，后端计算该月总天数，并将该月的第一天作为 `start_date`。
    *   如果提供了 `start_personnel_id`，在 `personnel_order` 数组中找到该人员的索引，并从该索引开始循环。
    *   如果提供了 `start_leader_id`，在 `leader_order` 数组中找到该领导的索引，并从该索引开始循环。
    *   排班计算逻辑调整为 `(起始索引 + 当前循环次数) % 序列长度`。

### 2.2. 前端修改 (React)

**文件**: `omni_desk_frontend/src/pages/ScheduleManagementPage.jsx`
**组件**: `GenerateScheduleModal`

*   **增加生成方式选项**: 添加一个单选框，让用户选择“按天数生成”或“按月份生成”。
*   **动态表单项**:
    *   当选择“按天数生成”时，显示“起始日期”和“生成天数”的输入框。
    *   当选择“按月份生成”时，显示一个“选择月份”的组件 (`DatePicker.MonthPicker`)。
*   **新增下拉框**:
    *   增加“起始人员”下拉选择框。
    *   增加“起始领导”下拉选择框。
*   **动态加载选项**: 当用户选择了“人员顺序”或“领导顺序”后，动态地将对应顺序中的人员/领导填充到“起始人员”和“起始领导”的下拉框中。
*   **更新API调用**: 在 `handleGenerateModalOk` 函数中，将新选择的 `start_personnel_id` 和 `start_leader_id`，以及 `duration_days` 或 `target_month` 传递给后端。

### 2.3. API层修改

**文件**: `omni_desk_frontend/src/api/scheduleApi.js`
**函数**: `generateSchedules`

*   确保函数能将新的 `target_month`, `start_personnel_id`, 和 `start_leader_id` 参数包含在发送给后端的POST请求中。

## 3. 修订后计划图

```mermaid
graph TD
    subgraph 前端 (React)
        A["ScheduleManagementPage.jsx"] --> B{"GenerateScheduleModal"};
        B -- 新增 --> B1["选择生成方式 (天数/月份)"];
        B1 -- "按天数" --> B2["输入起始日期和天数"];
        B1 -- "按月份" --> B3["选择目标月份"];
        B -- 新增 --> C["选择起始人员"];
        B -- 新增 --> D["选择起始领导"];
        B -- 点击确认 --> G["handleGenerateModalOk"];
        G -- 调用 --> H["api.generateSchedules"];
    end

    subgraph API层
        H -- HTTP POST请求 --> I["/events/schedules/generate-schedules/"];
    end

    subgraph 后端 (Django)
        I --> J["events/views.py: ScheduleViewSet"];
        J -- 执行 --> K["generate_schedules"];
        K -- 接收参数 --> L["duration_days 或 target_month"];
        K -- 接收新参数 --> L2["start_personnel_id, start_leader_id"];
        K -- 判断逻辑 --> K1{"有 target_month 吗?"};
        K1 -- "是" --> K2["计算月份天数, 设置起始日期为月初"];
        K1 -- "否" --> K3["使用 duration_days 和 start_date"];
        K -- 查找起始位置 --> M["在序列中查找索引"];
        K -- 生成排班 --> N["创建排班记录"];
    end