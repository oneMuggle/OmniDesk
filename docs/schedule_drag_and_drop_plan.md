# 排班日历拖拽交换功能开发计划

## 1. 目标

在排班管理页面的日历视图中，实现通过拖拽来调整排班日期的功能。具体交互逻辑为：

- 当一个排班项被拖拽到**没有**排班的日期时，更新该排班项的日期。
- 当一个排班项被拖拽到**已有**排班的日期时，交换这两个排班项的日期。

## 2. 现状分析

目前，`ScheduleManagementPage.jsx` 页面使用的是 Ant Design 的 `Calendar` 组件。该组件功能相对基础，**不原生支持拖放（Drag and Drop）功能**，无法直接满足我们的需求。虽然项目中存在一个名为 `useScheduleEventDrop.js` 的 Hook，但它似乎是为 `FullCalendar` 这样的专业日历库设计的，与 Ant Design 的日历组件不兼容。

## 3. 技术选型

为了高效、稳定地实现拖拽功能，我建议**将 Ant Design 的 `Calendar` 替换为 `FullCalendar`**。

**理由如下：**

- **功能强大**: `FullCalendar` 是一个成熟的日历库，原生支持事件的拖放、缩放等高级交互。
- **兼容性好**: 现有的 `useScheduleEventDrop.js` Hook 的逻辑可以轻松适配或复用到 `FullCalendar` 的事件回调中。
- **社区活跃**: 拥有庞大的社区和丰富的文档，便于解决开发中遇到的问题。
- **API 支持**: 后端已经提供了 `swapScheduleDates` 接口，`FullCalendar` 的拖拽事件可以很好地与之结合。

## 4. 实施计划

核心逻辑的流程图如下所示：

```mermaid
graph TD
    A[用户在日历上开始拖拽一个排班项] --> B{获取拖拽的排班项A和目标日期};
    B --> C{检查目标日期上是否存在排班项B?};
    C -- 是 --> D[调用 swapScheduleDates(A.id, B.id) API];
    C -- 否 --> E[调用 updateSchedule(A.id, new_date) API];
    D --> F[API调用成功];
    E --> F;
    F --> G[重新获取并刷新日历数据];
    A -- 拖拽取消/失败 --> H[排班项回到原位];
```

具体的开发步骤分为以下几步：

1.  **环境准备**:
    -   在 `omni_desk_frontend` 目录下，安装 `FullCalendar` 相关的依赖包。
    ```bash
    npm install @fullcalendar/react @fullcalendar/daygrid @fullcalendar/interaction
    ```

2.  **前端组件改造 (`ScheduleManagementPage.jsx`)**:
    -   移除 Ant Design 的 `<AntdCalendar />` 组件及其 `cellRender` 逻辑。
    -   引入 `FullCalendar` 及其所需的插件 (`dayGridPlugin`, `interactionPlugin`)。
    -   将从 `getSchedules` API 获取的排班数据 `schedules` 格式化为 `FullCalendar` 需要的事件数组格式（例如：`{ id: '1', title: '张三 / 李四', start: '2024-08-21' }`）。
    -   在页面中渲染 `<FullCalendar />` 组件，并配置 `events`、`editable={true}` 和 `eventDrop` 等关键属性。

3.  **拖拽逻辑实现 (`eventDrop` 回调)**:
    -   在 `ScheduleManagementPage.jsx` 中定义 `handleEventDrop` 函数，并将其传递给 `FullCalendar` 的 `eventDrop` 属性。
    -   此函数将接收一个包含拖拽信息的对象（`eventDropInfo`）。
    -   **核心逻辑**:
        -   从 `eventDropInfo` 中获取被拖拽的事件 `draggedEvent` 和目标日期 `newDate`。
        -   在现有的 `schedules` 状态中，查找目标日期 `newDate` 是否存在其他事件 `targetEvent`。
        -   **如果 `targetEvent` 存在**: 调用 `scheduleApi.swapScheduleDates(draggedEvent.id, targetEvent.id)`。
        -   **如果 `targetEvent` 不存在**: 调用 `scheduleApi.updateSchedule(draggedEvent.id, { date: newDate, ... })` 来更新日期。

4.  **数据同步与反馈**:
    -   在 API 调用成功后，调用 `fetchData()` 函数重新从后端获取最新的排班数据，以确保日历显示正确。
    -   在 API 调用期间，显示加载提示；在调用失败时，`FullCalendar` 会自动将事件还原到原始位置，并给出错误提示。