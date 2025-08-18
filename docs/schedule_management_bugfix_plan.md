# 排班管理页面 `personnelSequences.map is not a function` 错误修复计划

## 问题识别

`personnelSequences.map is not a function` 错误发生在 `GenerateScheduleModal` 组件中，原因是 `personnelSequences` 或 `leaderSequences` 在调用 `map` 方法时不是数组类型。尽管在 `ScheduleManagementPage` 中它们被初始化为空数组，但在异步数据加载过程中，如果 API 返回的数据类型不正确，或者在数据加载完成之前组件尝试渲染，就会出现此问题。

## 解决方案

在 `GenerateScheduleModal` 组件内部添加防御性编程，确保在调用 `map` 方法之前，`personnelSequences` 和 `leaderSequences` 确实是数组。

## 具体修改

*   在 `omni_desk_frontend/src/pages/ScheduleManagementPage.jsx` 的第137行，将 `{personnelSequences.map(...)` 修改为 `{Array.isArray(personnelSequences) && personnelSequences.map(...)`。
*   在 `omni_desk_frontend/src/pages/ScheduleManagementPage.jsx` 的第150行，将 `{leaderSequences.map(...)` 修改为 `{Array.isArray(leaderSequences) && leaderSequences.map(...)`。

## 流程图

```mermaid
graph TD
    A[用户点击排班管理] --> B{GenerateScheduleModal组件渲染};
    B --> C{personnelSequences和leaderSequences作为props传入};
    C --> D{组件内部尝试调用personnelSequences.map()};
    D -- personnelSequences不是数组 --> E[TypeError: personnelSequences.map is not a function];
    D -- personnelSequences是数组 --> F[正常渲染];

    subgraph 修复方案
        G[修改GenerateScheduleModal组件] --> H{在map调用前添加Array.isArray()检查};
        H -- 检查通过 --> F;
        H -- 检查不通过 --> I[跳过map调用，避免错误];
    end

    E --> G;