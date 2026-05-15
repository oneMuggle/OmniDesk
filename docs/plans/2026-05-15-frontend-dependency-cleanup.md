# 2026-05-15 前端依赖冗余清理方案

## 现状分析

### 1. 日历库重叠

| 库 | 使用位置 | 功能 |
|----|---------|------|
| `react-big-calendar` (1 处) | `features/meeting-room/pages/MeetingRoomBookingPage.jsx` | 会议室预约日历视图 |
| `@fullcalendar/*` (2+ 处) | `features/schedule/components/BaseSchedule.jsx`<br>`features/schedule/pages/ScheduleManagementPage.jsx` | 排班管理日历视图 |

**结论**: 两个日历库各自服务于不同业务场景，但功能高度重叠。

**推荐**: 统一使用 `@fullcalendar`，理由：
- FullCalendar 在项目中已被更多模块使用（排班管理是核心功能）
- FullCalendar 插件化架构更灵活（dayGrid、timeGrid、interaction 按需加载）
- `react-big-calendar` 仅 1 个文件使用，迁移成本低
- FullCalendar 内置中文 locale，react-big-calendar 需要额外配置

### 2. 富文本编辑器重叠

| 库 | 使用位置 | 功能 |
|----|---------|------|
| `react-quill` (2 处) | `features/announcements/components/AnnouncementForm.jsx`<br>`components/communication/PostForm.jsx` | 公告编辑、帖子发布（支持图片上传） |
| `@tiptap/*` (1 处) | `features/office-assistant/pages/OfficeAssistant.jsx` | Office 助手（AI 文本处理：纠错/翻译/润色） |

**结论**: Quill 用于传统富文本编辑（带工具栏+图片上传），Tiptap 用于 headless 编辑器（AI 处理场景）。两者使用场景差异明显。

**推荐**: 保留两者，但可以考虑统一为 Tiptap（长期）。短期保留现状，因为：
- Quill 在公告和帖子中已稳定运行，有图片上传定制
- Tiptap 在 Office 助手中是 headless 模式，不需要工具栏 UI
- 统一的代价大于收益

### 3. 其他依赖问题

| 问题 | 详情 | 严重度 |
|------|------|--------|
| `react-scripts` 5.0.1 | CRA 已停止维护，缺少 modern bundler 特性 | 中 |
| Jest 版本不一致 | devDeps: jest@27.5.1, deps: @testing-library/dom@10.4.0（兼容 Jest 29+） | 中 |
| `moment` 未声明 | `ScheduleManagementPage.jsx` 使用 `moment` 但 package.json 中无此依赖 | **高** |
| `dayjs` + `dayjs-plugin-utc` | 仅声明了 `dayjs-plugin-utc`，未声明 `dayjs` 本体 | **高** |
| `babel-jest`@29 vs `jest`@27 | 版本不匹配可能导致测试运行异常 | 中 |
| 测试库版本混乱 | `@testing-library/react`@16 与 `jest`@27 兼容性问题 | 中 |

## 实施进度

- [x] Phase 1: 修复断裂依赖
  - [x] 添加 dayjs、moment 显式声明
  - [x] Jest 27→29 升级 + jest-environment-jsdom 对齐
  - [x] 318/321 测试通过，build 成功
- [x] Phase 2: 日历库统一
  - [x] MeetingRoomBookingPage 迁移到 @fullcalendar
  - [x] 移除 react-big-calendar
  - [x] 清理 CalendarPage.css 中 .rbc-* 死样式
  - [x] build 成功
- [x] Phase 3: Vite 迁移
  - [x] 移除 react-scripts，安装 Vite 5 + @vitejs/plugin-react
  - [x] 新建 vite.config.js（含 API 代理、手动分块）
  - [x] 新建 index.html 作为 Vite 入口
  - [x] 9 个 .js 文件重命名为 .jsx
  - [x] 新建 env.js 兼容 import.meta.env + process.env
  - [x] 所有 .env 文件前缀 REACT_APP_* → VITE_*
  - [x] npm run build 成功（~19s）
  - [x] 318/321 测试通过（2 个为既有问题）

## 实施计划

### Phase 1: 修复断裂依赖（1 天）

**1.1 添加缺失依赖**

```bash
npm install dayjs
```

确认 `moment` 是否为隐式依赖（被其他包引入），如果不是则显式添加。

**1.2 统一测试工具链版本**

将 Jest 从 27 升级到 29，与 `babel-jest@29`、`@testing-library/dom@10` 对齐。

### Phase 2: 日历库统一（2-3 天）

**2.1 将 MeetingRoomBookingPage 从 react-big-calendar 迁移到 @fullcalendar**

- 使用 `@fullcalendar/react` + `dayGridPlugin` + `timeGridPlugin` + `interactionPlugin`
- 保留现有功能：自定义 toolbar、事件颜色映射、拖拽预约、ResizeObserver 事件卡片
- FullCalendar 的 `select` 对应 react-big-calendar 的 `onSelectSlot`
- FullCalendar 的 `eventClick` 对应 react-big-calendar 的 `onSelectEvent`

**2.2 移除 react-big-calendar**

```bash
npm uninstall react-big-calendar
```

### Phase 3: 构建工具评估（可选，后续迭代）

评估从 `react-scripts` 迁移到 Vite 的可行性，这不是紧迫任务。

## 风险评估

| 风险 | 缓解措施 |
|------|---------|
| FullCalendar 迁移后 UI 不一致 | 复用现有 `Schedule.css` 样式，保持视觉一致 |
| 会议室预约功能回归 | 迁移后手动测试所有交互路径 |
| 测试工具链升级导致现有测试失败 | 先跑现有测试，确保 baseline 通过再升级 |
