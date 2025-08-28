# 试验日程与排班日程重构计划

**目标：** 简化“试验日程”和“排班日程”相关的逻辑，解决数据提交和更新时出现的错误和数据不一致问题。

**核心思路：**

1.  **统一数据模型：** 抽象出通用的“日程事件”模型，包含开始时间、结束时间、标题、类型等基本属性。
2.  **职责分离：** 明确前端组件、Hook 和 API 层的职责，避免交叉依赖和重复逻辑。
3.  **强化数据一致性：** 确保前端状态与后端数据同步，特别是在数据更新操作之后。
4.  **错误处理优化：** 改进错误日志和用户反馈机制。

**详细计划步骤：**

**阶段一：前期准备与数据模型统一 (Architect Mode)**

1.  **定义通用日程事件接口/类型：**
    *   在 `omni_desk_frontend/src/types/schedule.js` 或类似文件中定义一个通用的 `ScheduleEvent` 接口。
2.  **抽象数据转换逻辑：**
    *   创建 `omni_desk_frontend/src/utils/eventTransformers.js` 文件，包含将后端原始数据（试验和排班）转换为 `ScheduleEvent` 格式的函数。
3.  **审查后端API设计：**
    *   审查 `omni_desk_backend` 目录下相关的模型和视图文件，确认数据模型和更新逻辑是否合理。

**阶段二：前端数据管理与组件优化 (Code Mode)**

1.  **优化 `useScheduleData.js` 和 `useTrialScheduleData.js`：**
    *   **合并或抽象数据获取逻辑：** 考虑将通用部分抽象为 `useCalendarEvents` Hook。
    *   **确保数据一致性：** 在数据提交或更新后，通过 `queryClient.invalidateQueries()` 精确地使相关查询失效。
2.  **重构 `ShiftSchedule.jsx` 和 `TrialSchedule.jsx` (或 `TrialScheduleContainer.jsx`):**
    *   让这些组件主要负责展示逻辑，接收通用 `ScheduleEvent` 数组作为 `events` prop。
    *   将事件点击、日期选择等交互逻辑统一到上层容器组件或 Hook 中处理。
3.  **统一事件处理和模态框逻辑：**
    *   考虑创建一个通用的 `CalendarEventModal`，根据 `ScheduleEvent` 的 `type` 属性渲染不同的表单内容。

**阶段三：错误处理与用户反馈 (Code Mode)**

1.  **增强 API 层的错误处理：**
    *   在 `apiClient.js` 中集中处理通用的网络错误和服务器响应错误。
    *   为每个 API 调用添加更具体的 `try...catch` 块。
2.  **统一用户通知：**
    *   利用 Ant Design 的 `Modal.error` 或 `message.error` 进行统一的错误提示。

**Mermaid 图：**

```mermaid
graph TD
    subgraph UI Components
        A[ShiftSchedule.jsx] -- uses ScheduleEvent --> C[BaseSchedule.jsx]
        B[TrialScheduleContainer.jsx] -- uses ScheduleEvent --> D[TrialSchedule.jsx]
        E[CalendarEventModal.jsx] -- handles form submission --> F[API Layer]
    end

    subgraph Hooks
        H[useCalendarEvents.js] -- fetches & transforms --> F
        I[useScheduleData.js] -- (deprecated/refactored) --> H
        J[useTrialScheduleData.js] -- (deprecated/refactored) --> H
    end

    subgraph API Layer
        F[API Layer] -- calls --> K[Backend API]
        F -- includes --> L[trialApi.js]
        F -- includes --> M[scheduleApi.js]
        F -- includes --> N[timeSlotApi.js]
    end

    subgraph Backend
        K[Backend API] -- interacts with --> O[Database]
    end

    H --> A
    H --> B
    B --> E
    A -- receives data from --> H
    D -- receives data from --> H

    style A fill:#f9f,stroke:#333,stroke-width:2px
    style B fill:#f9f,stroke:#333,stroke-width:2px
    style C fill:#ccf,stroke:#333,stroke-width:2px
    style D fill:#ccf,stroke:#333,stroke-width:2px
    style E fill:#fcf,stroke:#333,stroke-width:2px
    style H fill:#fcc,stroke:#333,stroke-width:2px
    style I fill:#ccc,stroke:#333,stroke-width:1px
    style J fill:#ccc,stroke:#333,stroke-width:1px
    style F fill:#cff,stroke:#333,stroke-width:2px
    style K fill:#cfc,stroke:#333,stroke-width:2px
    style L fill:#cff,stroke:#333,stroke-width:1px
    style M fill:#cff,stroke:#333,stroke-width:1px
    style N fill:#cff,stroke:#333,stroke-width:1px
    style O fill:#ffc,stroke:#333,stroke-width:2px