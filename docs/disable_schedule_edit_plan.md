# 主页面禁用人员排班编辑功能计划

**目标：** 由于管理中心已支持人员排班编辑，主页面将不再提供此功能。

**计划详情：**

1.  **分析并修改 `ScheduleModal.jsx`：**
    *   **目标：** 将 [`calendar_with_react/src/components/Calendar/ScheduleModal.jsx`](calendar_with_react/src/components/Calendar/ScheduleModal.jsx) 中的编辑和新建排班功能禁用，使其仅用于展示排班详情。
    *   **步骤：**
        1.  读取 `calendar_with_react/src/components/Calendar/ScheduleModal.jsx` 的内容。
        2.  识别并修改与表单编辑相关的 UI 元素（如输入框、选择器等），将其设置为只读或禁用状态。
        3.  识别并移除或禁用“编辑”和“新建”按钮及其对应的提交逻辑（例如 `onSave` 函数中处理编辑和新建的部分）。
        4.  确认此修改不会影响管理中心对该组件的调用（如果管理中心也使用了此组件进行编辑，则需要考虑如何进行区分，例如通过 `props` 传递一个 `isManagementMode` 标志，或者考虑将编辑逻辑拆分到管理中心专属的组件中）。

2.  **分析并修改 `ScheduleCalendar.jsx`：**
    *   **目标：** 确保主页面日历上的排班事件始终不可编辑和拖放。
    *   **步骤：**
        1.  读取 [`calendar_with_react/src/components/Calendar/ScheduleCalendar.jsx`](calendar_with_react/src/components/Calendar/ScheduleCalendar.jsx) 的内容。
        2.  找到设置日历事件 `editable` 属性的地方（如搜索 `editable: !isGuest`），将其逻辑修改为始终为 `false`，或者确保在主页面上下文中，此属性最终解析为 `false`。

3.  **验证：**
    *   **目标：** 确认修改已成功生效，主页面无法编辑或新建排班。
    *   **步骤：**
        1.  建议用户运行应用程序。
        2.  验证主页面日历中点击人员排班事件时，模态框是否仅显示详情，且无法进行编辑操作。
        3.  验证日历上的人员排班事件是否无法拖动或直接修改。

**流程图：**

```mermaid
graph TD
    A[用户任务: 主页面禁用人员排班编辑] --> B{计划制定};

    B --> C[步骤 1: 修改 ScheduleModal.jsx];
    C --> C1[读取文件内容];
    C1 --> C2[禁用编辑UI和逻辑];
    C2 --> C3[移除或禁用编辑/新建按钮];
    C3 --> C4[处理管理中心复用情况];

    B --> D[步骤 2: 修改 ScheduleCalendar.jsx];
    D --> D1[读取文件内容];
    D1 --> D2[设置排班事件editable为false];

    C & D --> E[步骤 3: 验证修改];
    E --> E1[用户运行应用];
    E1 --> E2[验证ScheduleModal仅展示];
    E2 --> E3[验证日历事件不可编辑/拖放];

    E --> F[任务完成];