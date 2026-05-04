# “按功能组织”重构计划：排期功能

本文档概述了将排期（Schedule）相关的前端代码按功能模块进行重构的计划。

## 1. 背景

当前，与排期功能相关的文件分散在项目的不同目录中，例如：

-   API 调用: `omni_desk_frontend/src/api/scheduleApi.js`
-   页面组件: `omni_desk_frontend/src/pages/ScheduleManagementPage.jsx`
-   通用组件: `omni_desk_frontend/src/components/TrialScheduleContainer.jsx`
-   测试文件: `omni_desk_frontend/src/api/scheduleApi.test.js`

这种结构使得功能维护和扩展变得困难，因为开发者需要跨多个目录去查找和修改相关代码。

## 2. 重构目标

将所有与排期功能相关的文件（包括 API、组件、页面、Hooks、样式和测试）集中到一个统一的功能目录 `src/features/schedule` 下，以提高代码的内聚性和可维护性。

## 3. 建议的新目录结构

```
omni_desk_frontend/src/
└── features/
    └── schedule/
        ├── api/
        │   ├── scheduleApi.js
        │   └── scheduleApi.test.js
        ├── components/
        │   ├── TrialScheduleContainer.jsx
        │   └── ScheduleCalendar.jsx  // 其他相关组件
        ├── hooks/
        │   └── useScheduleData.js // 示例：自定义 Hook
        ├── pages/
        │   └── ScheduleManagementPage.jsx
        ├── styles/
        │   └── Schedule.css // 样式文件
        └── index.js // 统一导出模块
```

## 4. 实施步骤

1.  **创建目录结构**:
    -   在 `omni_desk_frontend/src/` 下创建 `features/schedule` 目录。
    -   在 `features/schedule/` 下创建 `api`, `components`, `hooks`, `pages`, `styles` 等子目录。

2.  **移动文件**:
    -   将 `omni_desk_frontend/src/api/scheduleApi.js` 和 `scheduleApi.test.js` 移动到 `omni_desk_frontend/src/features/schedule/api/`。
    -   将 `omni_desk_frontend/src/pages/ScheduleManagementPage.jsx` 移动到 `omni_desk_frontend/src/features/schedule/pages/`。
    -   将 `omni_desk_frontend/src/components/TrialScheduleContainer.jsx` 和其他相关组件移动到 `omni_desk_frontend/src/features/schedule/components/`。

3.  **更新导入路径**:
    -   在整个 `omni_desk_frontend/src/` 目录中进行全局搜索，查找对已移动文件的引用。
    -   将所有旧的导入路径更新为指向新位置的相对或绝对路径。
    -   例如, `import ... from '~/pages/ScheduleManagementPage'` 需要更新为 `import ... from '~/features/schedule/pages/ScheduleManagementPage'`。

4.  **调整路由配置**:
    -   修改项目的主路由配置文件（通常是 `App.js` 或专门的路由文件），确保 `ScheduleManagementPage` 的路由指向其新路径。

5.  **验证和测试**:
    -   运行 `npm run test` 确保所有单元测试和集成测试都能通过。
    -   手动测试排期管理页面的所有功能，确保在重构后功能正常。

## 5. 预期收益

-   **高内聚性**: 所有与排期功能相关的代码都集中在一起，便于理解和维护。
-   **可扩展性**: 当需要为排期功能添加新特性时，可以轻松地在 `features/schedule` 目录中添加新文件，而不会影响到其他功能模块。
-   **职责清晰**: 目录结构清晰地反映了应用的功能划分，降低了新成员的上手难度。