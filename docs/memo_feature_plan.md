# 备忘录功能开发计划

## 1. 核心目标

在项目中新增一个独立的备忘录功能，允许用户创建、查看、编辑和删除备忘录，并设置定时提醒。此功能将拥有专属页面，不与现有日历功能耦合。

## 2. 功能分解

-   **独立的备忘录页面**: 创建一个新的路由 `/memos` 和对应的页面 `MemoPage.jsx`。
-   **迷你日历**: 在备忘录页面中，提供一个小日历，用于高亮显示有备忘录的日期，并支持按日期筛选。
-   **备忘录列表**: 显示选定日期的备忘录事项。
-   **增删改查**: 提供完整的备忘录创建、编辑、查看和删除功能，通过弹窗 `MemoModal.jsx` 实现。
-   **定时提醒**: 用户可以为备忘录设置提醒时间。当到达指定时间且用户在线时，浏览器会弹出通知。

## 3. 技术方案

### 3.1 后端 (Django)

-   **新 App (`memos`)**:
    -   创建一个新的 Django App `memos` 来封装所有相关后端逻辑。
    -   命令: `python manage.py startapp memos`
-   **数据模型 (`Memo`)**:
    -   在 `memos/models.py` 中定义 `Memo` 模型。
    -   字段:
        -   `title`: `CharField` - 备忘录标题。
        -   `content`: `TextField` - 备忘录内容。
        -   `reminder_time`: `DateTimeField` (nullable) - 提醒时间。
        -   `is_completed`: `BooleanField` (default: `False`) - 完成状态。
        -   `user`: `ForeignKey` to `CustomUser` - 关联用户。
-   **API 接口**:
    -   使用 `rest_framework` 创建 `MemoSerializer` 和 `MemoViewSet`。
    -   在 `memos/urls.py` 中注册路由，并将其包含在主 `urls.py` 中，提供 `/api/memos/` 端点。

### 3.2 前端 (React)

-   **路由**:
    -   在 `calendar_with_react/src/routes/index.js` 中添加新路由 `/memos`，指向 `MemoPage` 组件。
-   **新组件**:
    -   `calendar_with_react/src/pages/MemoPage.jsx`: 页面级组件，整合迷你日历和备忘录列表。
    -   `calendar_with_react/src/components/Memo/MiniCalendar.jsx`: 迷你日历组件。
    -   `calendar_with_react/src/components/Memo/MemoList.jsx`: 备忘录列表组件。
    -   `calendar_with_react/src/components/Memo/MemoModal.jsx`: 备忘录编辑/创建弹窗。
-   **API 通信**:
    -   `calendar_with_react/src/api/memoApi.js`: 封装所有与 `/api/memos/` 的交互。
-   **状态管理**:
    -   `calendar_with_react/src/hooks/useMemoData.js`: 自定义 Hook，使用 `react-query` 获取和管理备忘录数据。
-   **定时提醒**:
    -   在 `MemoPage.jsx` 或全局 `App.jsx` 中使用 `setInterval` 定时轮询，检查 `useMemoData` 返回的数据中是否有即将到期的提醒。
    -   使用浏览器 `Notification` API 发送桌面通知。

## 4. 架构图

```mermaid
graph TD
    subgraph "前端 (React)"
        Router --> PageA["日历页面 (/calendar)"];
        Router --> PageB["备忘录页面 (/memos, 新)"];

        PageA --> CompA[ScheduleCalendarContainer];
        CompA --> HookA[useScheduleCalendarData];
        HookA --> DataA[排班数据] --> CalendarA[主日历];

        PageB --> CompB["MiniCalendar (新)"];
        PageB --> CompC["MemoList (新)"];
        
        HookB[useMemoData (新)] --> CompB;
        HookB --> CompC;

        CompC -- "点击'添加'或列表项" --> Modal["MemoModal (新)"];
        CompB -- "选择日期" --> CompC;
    end

    subgraph "后端 (Django)"
        APIs --> AppA["events app (现有)"];
        APIs --> AppB["memos app (新)"];

        AppA --> ModelA[Schedule 模型];
        AppB --> ModelB[Memo 模型 (新)];
    end

    HookA -- API请求 --> AppA;
    HookB -- API请求 --> AppB;
    Modal -- "保存/更新" --> AppB;