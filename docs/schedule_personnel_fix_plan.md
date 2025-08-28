# 排班日历人员显示问题修复计划

## 1. 问题诊断

排班日程页面在显示事件详情时，“值班人员”和“值班领导”字段显示为“未知人员”。

**根本原因**: 前端数据流在从数据源到展示组件的过程中出现断裂。

- **数据源**: 后端 API 返回的排班数据中，人员信息 (`responsible_persons`) 是一个包含用户对象的数组，每个用户对象都有一个 `role` 属性来标识其角色。
- **数据处理**: 前端在 `useTrialScheduleData.js` 中将此数组赋给了日历事件的 `extendedProps.personnel`。
- **数据断裂**: 当用户点击事件时，`TrialScheduleContainer.jsx` 组件未能处理 `extendedProps.personnel` 数组，没有根据 `role` 区分人员，也未创建 `EventModal.jsx` 所需的 `scheduleDetails` 对象。
- **最终表现**: `EventModal.jsx` 因为拿不到 `scheduleDetails` 数据，所以无法显示负责人和工作人员的姓名。

## 2. 修复计划

核心是在 `TrialScheduleContainer.jsx` 的 `onEventClick` 事件处理器中，将 `personnel` 数组转换成 `scheduleDetails` 对象。

### 2.1. 详细步骤

1.  **定位**: 找到 `omni_desk_frontend/src/components/TrialScheduleContainer.jsx` 文件中的 `onEventClick` 函数。
2.  **提取**: 从被点击事件的 `eventObj.extendedProps.personnel` 中提取出人员数组。如果 `personnel` 不存在或为空，则准备一个默认的空状态。
3.  **转换**:
    -   遍历 `personnel` 数组。
    -   根据每个成员的 `role` 属性来识别“领导” (leader) 和“工作人员” (staff)。假定 `role` 为 'manager' 或 'admin' 的是领导，其他为工作人员。
    -   为了程序的健壮性，如果找不到特定角色的成员，会设置一个默认值（例如，显示“未分配”）。
    -   创建一个新的 `scheduleDetails` 对象，其结构为：`{ leader: leaderObject, staff: staffObject, ... }`。
4.  **注入**: 将新创建的 `scheduleDetails` 对象添加到传递给 `setCurrentEvent` 的 `extendedProps` 中。

### 2.2. 数据流图

```mermaid
graph TD
    subgraph "后端"
        A[API 返回试验数据<br/>(包含 responsible_persons 数组<br/>每个 person 有 'role' 属性)]
    end

    subgraph "前端 Hooks"
        B[useTrialScheduleData.js<br/>将 responsible_persons 赋给<br/>event.extendedProps.personnel]
    end

    subgraph "前端组件"
        C[TrialScheduleContainer.jsx<br/>用户点击日历事件] --> D{onEventClick 处理器}
        
        subgraph "onEventClick 内部逻辑 (修改点)"
            D --> E[提取 event.extendedProps.personnel]
            E --> F{遍历 personnel 数组<br/>根据 'role' 查找 leader 和 staff}
            F --> G[创建 scheduleDetails 对象<br/>{ leader: {...}, staff: {...} }]
        end

        G --> H[setCurrentEvent<br/>将 scheduleDetails 注入 extendedProps]
        H --> I[EventModal.jsx<br/>接收 currentEvent]
        I --> J{读取 extendedProps.scheduleDetails}
        J --> K[成功渲染<br/>负责人和工作人员姓名]
    end

    A --> B --> C