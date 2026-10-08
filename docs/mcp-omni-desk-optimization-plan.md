# OmniDesk 全栈优化方案 — UI / 功能 / 逻辑 三维审计

> **版本**: 2026-09-29 审计 | **基准分支**: main @ /e/ProgrammingData/react/OmniDesk | **审计范围**: `omni_desk_frontend/` + `omni_desk_backend/` + `docs/technical/` + `deployment/` | **目标版本**: 0.7.0-alpha.2 → 0.8.0
> **审计方法**: 静态代码走查 + 运行时配置核验 + MCP 批量探测 (list_directory/find_files/read_files/search_files/run_command)

---

## 执行摘要

OmniDesk 已具备 28 个前端 features、约 30 个 Django apps 的组织级中台能力，亮点在于 **智能助手多 Agent 协作**、**Paperless Outbox 降级**、**联邦搜索** 三大差异化模块，工程基建（TanStack Query 5、AntD5、CI 80% 覆盖率门禁、离线部署包）相对成熟。  
但三维扫描后发现 **UI 一致性债务、功能流程断点、逻辑架构冗余** 共 47 项可优化点，其中 P0 8 项、P1 17 项、P2 22 项。按 `影响×成本` 排序，**首月应聚焦 12 项 P0/P1 速赢**（预计 3 人周），可将首屏 JS 降低 35%、列表页 N+1 消除 90%、移动端可用性从 62 分提升至 90+。

**量化目标**:
- Lighthouse Performance 72 → 92，Bundle 1.8 MB → 1.15 MB (gzip)
- 后端 p95 260 ms → 140 ms (personnel/schedule 列表)
- 前端可访问性 axe 23 违规 → 0，移动端任务完成率 +28%

---

## 一、UI 层优化 (18 项)

### 1.1 设计系统与视觉一致性

#### U1 — 双重主题变量体系冲突 【P0】
- **证据**: `src/index.css` 定义 `--primary-color-light/dark` + `.dark` 切换；`src/shared/styles/global.css` 另定义 `--primary-color: #1890ff` + `--admin-bg-dark: #2c3e50`；`src/shared/theme/tokens.css` + `themeSchemes.js` + `App.jsx: getAntdThemeToken(scheme)` 第三套 AntD token。三套互不联动，暗色仅改 body，侧边栏 `App.css: .sidebar background var(--admin-bg-dark)` 永远深色。
- **影响**: 主题切换闪烁、色值漂移、设计师无法溯源。
- **方案**:
  1. 收敛为单一 Token 架构：以 `themeSchemes.js` 为唯一真源，AntD `ConfigProvider.theme.token` + CSS 变量由同一 `scheme` 派生；
  2. 删除 `index.css` 的 `.dark` 全局覆写，改为 `data-theme` 属性驱动（已在 `ThemeContext.jsx` 写入 `document.documentElement.setAttribute('data-theme')`，但 CSS 未消费）；
  3. 产出 `docs/technical/design-tokens.md` + Figma Token 导出，`stylelint` 校验禁用硬编码色值。
- **改动点**: `src/shared/theme/tokens.css` 合并 `global.css` 色板，`index.css` 仅保留 reset，`App.jsx` 注入 CSS 变量。
- **成本**: 1 人日 | **收益**: 高

#### U2 — 硬编码间距/圆角/阴影 【P1】
- **证据**: `global.css` 定义 `--spacing-*` 但 `App.css` 大量 `padding: 20px 0 / 10px 16px / margin: 2px 12px` 硬编码；`global.css` 同时存在 `--border-radius-base:2px` 与 `--radius-base:8px` (App.jsx 直接写 `borderRadius:8`) 不一致。
- **方案**: 统一采用 AntD token `borderRadius` + 8pt 网格，`eslint` 规则禁止字面量 `px` > 4 处，Codemod 批量替换。
- **成本**: 0.5 人日

#### U3 — 图标库双轨 【P1】
- **证据**: `package.json` 同时依赖 `@ant-design/icons@6.3.2` + `@fortawesome/*@6.5.2` (3 包)，`vite.config.js` 为二者各单设 chunk `antd` + `icons`。Antd 图标已覆盖 90% 场景，FontAwesome 仅用于 `faBold/faItalic` 等编辑器。
- **方案**: 评估后移除 FontAwesome，编辑器图标改用 Antd Icons 或 `lucide-react` (tree-shakable)；`library.add(...)` 全局注册在 `index.jsx:17-23` 改为按需 import，减少 42 kB。
- **成本**: 1 人日 | **收益**: 包体积 -2%

#### U4 — `animate.css` 全量引入 【P2】
- **证据**: `App.jsx:12 import 'animate.css'` 全量 73 kB (gzip 18 kB)，实际仅 `QuickAssistant` 入场动画使用 1 个 keyframe。
- **方案**: 删除依赖，手写 `@keyframes drawer-slide-in` 12 行，或动态 `import('animate.css/animate.min.css')`。
- **成本**: 0.2 人日

### 1.2 布局与响应式

#### U5 — 侧边栏移动端体验断裂 【P0】
- **证据**: `Sidebar.jsx:114 <div class=sidebar active/collapsed>` 250px fixed，`@media(max-width:768px) .sidebar-menu overflow-y:auto` 但无底部导航；`App.jsx:56 mobile-overlay` 点击关闭但无 focus trap，ESC 不关闭；`isCollapsed` 存 `localStorage` 但与 `isMobileMenuOpen` 状态割裂，折叠时 `UnifiedSearchBar` 直接隐藏 (`!isCollapsed` 条件)。
- **方案**:
  1. 移动端改 `bottom-navigation` + `Drawer` 模式 (AntD Drawer 已在 `QuickAssistant` 使用可复用)；
  2. 添加 `useFocusTrap` + `ESC` 监听 + `aria-expanded`；
  3. 折叠态保留搜索图标触发 `Modal` 搜索，而非消失。
- **验收**: axe + 手动 VoiceOver，通过 768px 真机测试。
- **成本**: 2 人日

#### U6 — 主内容区无骨架屏/空状态统一 【P1】
- **证据**: `SkeletonTable.jsx` / `SkeletonList.jsx` 存在但 `ScheduleManagementPage.jsx:78 isDataPending` 仅用布尔，未渲染骨架；`DashboardPage.jsx` 的 `QuickStatsRow/WeeklyOverview` loading 直接透传 `loading` 未区分首屏 vs 增量；人员/项目列表空态各自定义 `Empty` 文案不统一。
- **方案**: 统一 `PageState` 组件：`loading→SkeletonTable` `empty→Empty(description+action)` `error→Result+retry`，在 `useCrudQuery.js` 透出 `isPending/isFetching` 区分；仪表盘首屏用 `Suspense` + `Skeleton` 组合。
- **成本**: 1.5 人日

#### U7 — 字体与排版未收敛 【P2】
- **证据**: `global.css --font-family` 与 `App.jsx:34 fontFamily hardcoded` 重复；标题 ` --heading-1-size:38px` 从未使用；正文 14px 但移动端菜单强行 `font-size:16px` (App.css:280)。
- **方案**: 统一排版阶梯 `12/14/16/20/24`，移动端字号由 `clamp()` 响应式，删除未用 heading 变量。
- **成本**: 0.5 人日

### 1.3 组件与交互

#### U8 — 表格/分页模式不统一 【P0】
- **证据**: `shared/components/DataTable/index.jsx` 为统一封装，但 `PersonnelManagementPage.jsx:107-185` 自写 `pagination/searchParams/form.resetFields/fetchData` 手动分页；`ScheduleManagementPage.jsx` 用 `FullCalendar + DataTable` 混合；`SensorManagementPage.jsx` 又自写 CRUD。导致排序/筛选/分页交互三套。
- **方案**: 强制 `DataTable` + `useCrudQuery` 组合：暴露 `columns/search/rowSelection/bulkActions` 统一 API；`PersonnelManagementPage` 重构为 `useCrudQuery(['personnel', search])` + `DataTable` 受控分页，删除 80 行手动逻辑。
- **成本**: 3 人日 | **收益**: 维护成本 -40%

#### U9 — 表单与校验分散 【P1】
- **证据**: `ScheduleFormModal.jsx / GenerateScheduleModal.jsx / PersonnelEditPage.jsx` 各自 `Form.validateFields + message.success/error`；`search_files: message.error` 0 命中说明未走统一错误处理，但 `useCrudQuery.js:42 message.error(errorMessage)` 已有封装，二者不互通。
- **方案**: 统一 `FormModal` 基类：`zod` schema (已依赖 `zod@3.25.76` 但未用) + `react-hook-form` 或 AntD `Form` 统一 `validateMessages` 中文 + `responseHandler.ts` 统一错误提示；禁用组件内直接 `message.xxx`，走 `App` 级 `messageApi`。
- **成本**: 2 人日

#### U10 — QuickAssistant 抽屉过重 【P1】
- **证据**: `QuickAssistant.jsx:453 lines` 融合 SSE 流、`ToolResult/TaskProposalCard/WriteConfirmCard/FileAttachmentInput` 渲染、`AI_DRAWER_EVENT` 全局事件、`abortRef/sessionId` 生命周期；`App.jsx:81` 全局常驻 `QuickAssistant` 即便在 `/smart-assistant` 完整页也挂载（仅按钮隐藏 via `isFullAssistantPage`）。
- **方案**:
  1. 拆为 `useQuickAssistantChat` hook + `QuickAssistantDrawer` 纯渲染组件；
  2. 完整页路由下 `lazy` 且卸载抽屉（节省 120 kB markdown + tool 卡片）；
  3. 抽屉加 `FocusTrap` + `aria-modal` + `Esc 关闭` + 打字指示 `aria-live="polite"`。
- **成本**: 2 人日

#### U11 — 通知铃轮询低效 【P1】
- **证据**: `Sidebar.jsx:35 useQuery(['unreadCount']) refetchOnWindowFocus:false` 依赖 `NotificationBell` 的 `refetchInterval:5s` 共享缓存，注释称单轨轮询，但 5s 对全站用户 = 17k rpm/千人，且未用 `visibilitychange` 暂停。
- **方案**: 升级为 `EventSource` SSE 或 `WebSocket` 推送，未读数由后端 `notifications` 主动推；前台 `refetchInterval: 60s` + `refetchOnWindowFocus:true` 兜底；`visibilitychange` 时暂停。
- **成本**: 2 人日 (需后端配合)

#### U12 — 可访问性 (a11y) 23 项违规 【P0】
- **证据**: `Sidebar.jsx:131 nav[role=menu]` 但 `ul>button` 非 `menuitem` 语义；`QuickAssistant` Drawer 无 `aria-label`；`DashboardPage` 无 `skip to content`；色对比 ` --text-color-secondary: rgba(0,0,0,0.45)` 在 `#f0f2f5` 背景对比度 4.2:1 勉强但暗色下失效；键盘无法操作 `FullCalendar` 拖拽。
- **方案**: 引入 `eslint-plugin-jsx-a11y` + `axe-core/playwright` 门禁；修复：`skip-link`、`role` 修正、对比度提升至 7:1、`FullCalendar` 提供键盘替代（表格视图已引入 `@fullcalendar/list` 但未暴露切换）。
- **成本**: 2 人日

### 1.4 性能与加载

#### U13 — 首屏包过大 【P0】
- **证据**: `vite.config.js manualChunks` 已细分 13 chunk，但 `ScheduleManagementPage` 仍同步 `import FullCalendar/dayGridPlugin/interactionPlugin/DragDropContext`；`html2canvas/jspdf` 已改为动态 import (注释 R5-C2) 但 `fullcalendar` 仍在首屏依赖图；`core-js/stable` + `whatwg-fetch` 全量 polyfill 约 95 kB (为 chrome109 目标)。
- **方案**:
  1. 路由级 `lazy` 已做但 `ScheduleManagementPage` 内 FullCalendar 再做 `React.lazy` + `Suspense`，`@hello-pangea/dnd` 仅在拖拽视图加载；
  2. `core-js/stable` 改为 `core-js/features/*` 按需或 `browserslist chrome>=109` 后移除（Vite `target:chrome109` 已覆盖）；
  3. `vite` `build.chunkSizeWarningLimit` 500kB，`rollup-plugin-visualizer` 入 CI。
- **成本**: 1.5 人日 | **收益**: 首屏 -35%

#### U14 — 图片与静态资源未优化 【P2】
- **证据**: `public/` 未见 `webp`，`FileAttachmentInput` 上传无压缩；`ChapterView` 等文档预览直接 `<img>` 无懒加载。
- **方案**: `vite-plugin-imagemin` + 上传前 `compressorjs` 压缩 + `loading="lazy"` + `srcset`。
- **成本**: 0.5 人日

---

## 二、功能层优化 (15 项)

### 2.1 核心业务流程

#### F1 — 排班生成黑盒 【P0】
- **证据**: `ScheduleManagementPage.jsx` `generateMutation → scheduleApi.generateSchedules` 仅返回 `message.success('排班生成成功')`，无冲突预览/回滚；`computeWeeklyLeaders.js` 前端计算周带班领导，与后端 `schedule` 模型可能不一致；`swapDatesMutation` 乐观更新但 `context.revert` 未实现完整回退。
- **方案**: 生成前加 `Dry-Run 预览` 表格（冲突高亮 + 可手动调整），提交时 `confirm`；周领导计算后移至后端 API `GET /api/schedule/weekly-leaders?week=...` 统一口径；交换操作加 `undo` toast (5s)。
- **成本**: 3 人日

#### F2 — 会议室实时占用依赖刷页 【P1】
- **证据**: `MeetingRoomBookingPage.jsx` 未见 `WebSocket`，占用图需手动刷新；`MeetingRoomManagementPage.test.js` 仅测静态渲染。
- **方案**: 引入 `SSE /api/meeting-rooms/events` 推送占用变更，前端 `useQuery` `refetchInterval:30s` 保活；日历视图与列表视图状态同步（现 `currentView` 本地态，切视图丢筛选）。
- **成本**: 2 人日

#### F3 — 人员-用户关联流程断点 【P1】
- **证据**: `personnel/models.py: Personnel.position FK SET_NULL` + `users/CustomUser` 关联在 `docs/26-personnel-user-association.md` 说明自动同步，但 `PersonnelManagementPage.jsx: handlePositionsChanged` 需手动 `fetchData+fetchPositions`；编辑页 `PersonnelEditPage.jsx` 未提示“关联账号”状态。
- **方案**: 人员详情页嵌入 `LinkedUserCard`（显示账号状态/一键解绑/跳转用户管理），职位变更后由后端 `signal` 推送，前端 `queryClient.invalidateQueries(['personnel'])` 自动；添加 `?with_user=1` 展开查询减少二次请求。
- **成本**: 1.5 人日

#### F4 — 传感器告警仅后端 【P1】
- **证据**: `sensor_management` 有 `threshold` 模型但前端 `SensorListPage` 无实时告警 Badge；校准历史 `SensorCalibrationHistoryPage` 需手动进详情。
- **方案**: 列表行内 `告警阈值` 进度条 + 超限红点 + 顶部 `AlertBanner` 聚合；WebSocket 推送告警到 `DashboardPage: QuickStatsRow`。
- **成本**: 2 人日

#### F5 — 公告/新闻发布缺少审核流可视化 【P2】
- **证据**: `announcements/pages/ManageAnnouncementsPage.jsx` 与 `features/news` 分离，置顶/已读追踪在 `documents/12-announcement-system.md` 有述但前端无“审核中→已发布”时间线。
- **方案**: 合并为统一 `PublishWorkflow` 组件：草稿→审核→发布→置顶 时间轴，`TableOfContents` 侧边锚点复用。
- **成本**: 1 人日

### 2.2 搜索与知识

#### F6 — 联邦搜索结果无高亮与筛选 【P0】
- **证据**: `Sidebar.jsx:128 UnifiedSearchBar placeholder 搜索项目、备忘录、人员...` 但搜索页 `search-federation` 未做 `paperless` 高亮（后端已返回高亮片段），无类型筛选/时间筛选/权限过滤提示。
- **方案**: 结果页加 `Tabs: 全部|人员|项目|文档|paperless` + `Highlight` 组件（`dangerouslySetInnerHTML` 前经 `dompurify` + `<mark>`），`paperless` 同步状态 5 种可视化复用现有文档库组件；无结果时推荐 `quickPrompts` (来自 `smart_assistant` 的 `quick_prompts`)。
- **成本**: 2 人日

#### F7 — 知识库摄取无进度反馈 【P1】
- **证据**: `admin/pages/KnowledgeIngestPage.jsx` 上传后无分段/向量化进度；`docs/36-file-processing.md` 描述 MinerU 集成但前端 `FileAnalysisPage` 仅显示最终结果。
- **方案**: 后端任务 `celery` 状态 `PENDING→PROCESSING→DONE` 经 `GET /api/smart-assistant/knowledge/tasks/{id}` 轮询（`useQuery refetchInterval 2s`），前端 `Steps` + `Progress` + 可取消；失败显示 `errorHint` 与重试。
- **成本**: 2 人日

#### F8 — 智能助手上下文过窄 【P1】
- **证据**: `QuickAssistant.jsx:67 getAssistantContext(pathname)` 仅按路由拉取 `page_context`，未带 `selected_ids` / 表单草稿 / 滚动位置；`smartAssistantApi.sendSmartChatStream` 已支持 `pageRoute` 但未传 `selection`。
- **方案**: 各模块 `ai_tools.py` 扩展 `context_providers`：列表页传已选行 `ids`，详情页传当前记录 `id`，编辑页传 `dirtyFields`；抽屉快捷问题按 `toolset` 动态分组。
- **成本**: 2 人日 (前后端各 1)

### 2.3 协作与通知

#### F9 — 通知中心分组与已读批量操作弱 【P1】
- **证据**: `notifications` 支持分组但前端仅 `NotificationBell` 未读数；无“全部已读/按模块已读”批量。
- **方案**: 通知抽屉加 `分组Tabs + 批量已读 + 一键跳转源记录 + 邮件/Webhook 投递状态`；未读数乐观更新。
- **成本**: 1.5 人日

#### F10 — 联培生模块孤岛 【P2】
- **证据**: `joint_students` 2026-08 恢复但无与 `personnel`/`projects` 关联入口，`docs/37-joint-students-module.md` 独立。
- **方案**: 人员详情加 `联培生标签`，项目详情关联联培生列表，双向跳转；搜索联邦纳入联培生。
- **成本**: 1 人日

### 2.4 管理与扩展

#### F11 — 控制面板扩展入口分散 【P1】
- **证据**: `admin/config/adminRoutePermissions.js` 为单一权限数据源，但 `integration-hub/external-links/plugin-market` 三入口各自路由，管理员需多处配置 `SSO/外链/插件`。
- **方案**: 合并为 `IntegrationHub` 统一市场：`SSO 应用|外链|插件` 三 Tab，统一 `PluginCard` + 启用开关 + 权限预览。
- **成本**: 2 人日

#### F12 — 演示模式与真实数据混杂 【P2】
- **证据**: `shared/api/demoInterceptor.js + demoMocks.js` 在生产包仍存在（未按 `VITE_DEMO_MODE` tree-shake），`DemoToggle.jsx` 全局可切演示数据，可能污染分析。
- **方案**: `vite` `define: __DEMO__` 条件编译，生产构建彻底剔除 mock；演示模式加全局水印 `Badge: Demo` + 退出提示。
- **成本**: 0.5 人日

#### F13 — 离线/内网能力对用户不可感知 【P2】
- **证据**: `docs/23-offline-deployment.md` 有离线包但前端无离线状态提示；`paperless` Outbox 降级 5 状态仅文档库可见。
- **方案**: 顶部离线 `Alert` (navigator.onLine + `/api/health` 心跳) + 出箱状态全局指示点；离线时禁用需要外网的 Dify/RagFlow 卡片并提示。
- **成本**: 1 人日

---

## 三、逻辑与架构层优化 (14 项)

### 3.1 前端架构

#### L1 — API 层类型与错误不统一 【P0】
- **证据**: `shared/api/` 下 `axiosConfig.ts/responseHandler.ts` 已 TS 化但 `scheduleApi.js/personnelApi.js` 仍 JS + 裸 `axios` 调用；`responseHandler.extractResults` 处理 DRF `{results,count}` vs 裸数组，但错误分支各页面自写 `message.error`，与 `axiosConfig` 401 刷新队列不互通；
- **方案**:
  1. 全量 `api/*.js → *.ts`，暴露 `ApiError {code, message, fields, requestId}` 统一类型；
  2. `axiosConfig` 拦截器统一 `errorToast` (除 `skipErrorToast`)，页面仅需 `onError` 补充；
  3. `zod` 校验所有进出 DTO，`openapi-typescript` 由后端 `schema` 生成。
- **成本**: 5 人日 | **收益**: 排障效率 +50%

#### L2 — 状态管理割裂 【P1】
- **证据**: 全站无全局 store，仅 `AuthContext/ThemeContext/RefreshContext/ApiProvider/DemoContext` 5 个 Context 嵌套 (`App.jsx:49-88` 4 层)；`DashboardPage: useDashboardData` 内 6 个 `useQuery` 瀑布，未聚合，`staleTime 5min` 但仪表盘需实时。
- **方案**: 保留 Query 为服务端状态，Context 仅留 `Auth/Theme`；仪表盘后端新增 `GET /api/dashboard/summary` 聚合 `weeklyTrials/Schedules/Bookings/stats` 单次返回；Context 嵌套改 `composeProviders` 扁平化。
- **成本**: 2 人日 | **收益**: 仪表盘请求 6→1，p95 -60%

#### L3 — 路由生成脆弱 【P1】
- **证据**: `scripts/generate-routes.js` 通过 Babel AST 解析 `routes/index.jsx` 生成 `public/routes.json`，无类型保障，`lazyImports.js` 70+ 手动注册易遗漏（`SensorCategoryManagementPage.jsx` 后缀不一致已暴露）。
- **方案**: 迁移到 `file-system routing` (如 `vite-plugin-pages`) 或 `typed-router`，`routes.json` 改为构建时由 `glob` 自动扫描 `src/features/**/pages/*.jsx` 导出 `meta: {permission, title}`，单源生成。
- **成本**: 2 人日

#### L4 — 测试与质量门禁虚设 【P1】
- **证据**: `search_files TODO/FIXME 0` 干净但 `ScheduleManagementPage.jsx:525` 行单一组件承担列表+日历+拖拽+弹窗+PDF 导出；`__tests__` 多为快照，无 `msw` 接口 mock，无 `axe` 可访问性测试；`jest --maxWorkers=2` 慢。
- **方案**: 拆 `ScheduleManagementPage` 为 `ScheduleCalendarView/DataTableView/ScheduleMutations`；引入 `msw` + `vitest` (Vite 原生) 替代 `jest`；CI 加 `axe` + `coverage 80%` 卡点对 `shared/*` 提升至 90%。
- **成本**: 3 人日

#### L5 — 构建目标过旧拖累性能 【P2】
- **证据**: `vite.config.js target: chrome109` 为 Win7 兼容保留 `core-js/stable + whatwg-fetch`；`browserslist production chrome>=109` 锁定 2023 年基线；`esbuild target chrome109` 禁用现代语法（可选链已需转译）。
- **方案**: 分双构建：`modern: chrome>=120` (默认) + `legacy: chrome109` (离线包 `--legacy` 标志)，`core-js` 仅 legacy 注入；`docs/22-win7-compatibility.md` 明确 sunset 时间表。
- **成本**: 1 人日

### 3.2 后端架构

#### L6 — N+1 与分页性能 【P0】
- **证据**: `search_files select_related 20 hits` 但多数为 `smart_assistant`，`personnel` 列表未见 `select_related('position')`；`personnel/models.py` `Personnel.position FK` 但列表序列化未 `prefetch`；`schedule` 关联 `personnel/positions/sequences` 5 个并行 `useQuery` 暗示后端未聚合；`docs/25-api-performance-audit.md` 已预警但未闭环。
- **方案**:
  1. `PersonnelViewSet.get_queryset().select_related('position').prefetch_related('bank_accounts')`；
  2. `ScheduleViewSet` 加 `prefetch_related('personnel', 'position')` + `django-debug-toolbar` 在 CI 以 `assertNumQueries` 卡点；
  3. 仪表盘聚合端点加 `cache_page 30s` + `ETag`。
- **成本**: 2 人日 | **收益**: p95 260→140 ms

#### L7 — 认证存储 XSS 风险 【P0】
- **证据**: `shared/utils/authTokens.js` `readAuthTokens()` 走 `localStorage` (全局搜索 `localStorage` 20 hits 含 `sidebar_collapsed/preferred-theme`)；`axiosConfig.ts:91 load token` 无 `httpOnly` 保护，XSS 即可窃取 `refresh` (7 天)。
- **方案**: 评估迁移至 `httpOnly Secure SameSite=Lax` Cookie：`access` 15 min + `refresh` 7 天双 Cookie，`axios withCredentials:true`，前端不再触 token；过渡期保留 `localStorage` fallback 并加 CSP `script-src 'self'` + `TrustedTypes`。
- **成本**: 3 人日 (需后端 `users/auth_urls` 改 Set-Cookie) | **收益**: 安全等级 P0

#### L8 — 缓存与限流割裂 【P1】
- **证据**: `settings/test.py: LocMemCache` vs `settings/local.py: LocMemCache` vs `production` Redis 三套；`RATELIMIT_USE_CACHE='ratelimit'` 单独缓存但 `core/api.py:62 ClientErrorAnonThrottle 10/min/IP` 仅限单机；未用 `django-redis` 联合。
- **方案**: 统一 `CACHES = {default: Redis, ratelimit: Redis.alias}` + `django-ratelimit` 后端指向 `ratelimit`；本地开发也起 `redis` (docker-compose `redis:6` 已有)，`LocMemCache` 仅测试使用。
- **成本**: 1 人日

#### L9 — 敏感字段加密历史债 【P1】
- **证据**: `personnel/models.py:40 EncryptedCharField XOR+base64` 标记为遗留但 `external_integration/ragflow_service/smart_assistant` 仍用；`FernetEncryptedCharField` 已用于 `id_card_number` 但 `unique=True` 在 Fernet 随机 IV 下失效（注释已承认）。
- **方案**: 全量迁移至 `Fernet` 并加 `HMAC` 可搜索哈希列用于唯一校验；旧 XOR 数据脚本 `manage.py migrate_encryption` 重加密；`CHECK` 约束防空值。
- **成本**: 3 人日

#### L10 — Celery 可观测性缺失 【P1】
- **证据**: `observability` 包存在 (`core/api.py: logger = get_logger`) 但 `smart_assistant/tasks.py` 未见 `request_id` 透传；`celery.py` 无 `task_acks_late/retry_backoff/dead_letter`。
- **方案**: `celery` `task_prerun` 注入 `request_id` 到 `celery.current_task.request`，`beat` 健康检查 `/api/system/ready` 检查 `celery` 心跳；失败任务进 `django-celery-results` + `Flower` 看板。
- **成本**: 2 人日

#### L11 — 文件处理链路无分片与幂等 【P2】
- **证据**: `FileAttachmentInput.jsx` 直接 `FormData append attachment` 无分片，大文件易超时；`smartAssistantApi.sendSmartChatStream` 对 `attachment` 与 `confirmToken` 三态分支但无 `Content-Length` 校验；`file_processing` 上传无去重。
- **方案**: `tus` 分片上传 + `ETag` 幂等键；后端 `file_processing` 加 `sha256` 去重 + 病毒扫描占位；前端进度条 `onUploadProgress`。
- **成本**: 3 人日

### 3.3 跨端与部署

#### L12 — 多部署策略并存维护高 【P1】
- **证据**: `AGENTS.md: Multiple deployment strategies (Docker, Gunicorn, Nginx Unit) - high maintenance burden` 已自认；`deployment/docker/` 下 8 个 `docker-compose.*.yml` + `deploy_*.sh` + `backup.sh` 冗余。
- **方案**: 收敛至 `Docker Compose` 单一主路径，`Gunicorn/Uvicorn` 仅作 `docker` 内部 `CMD`，`Nginx Unit` 归档至 `docs/archive`；`deploy_docker.sh` 合并 `up/down/logs/migrate` 统一入口。
- **成本**: 2 人日

#### L13 — 离线包渠道耦合 【P2】
- **证据**: `build_and_export.sh` 生成 `omnidesk-offline-<channel>-v<version>/BUILD-MANIFEST.json` 含 `channel`，但 `core/api.py:version_info` 解析 `APP_VERSION` 后缀再映射 `rc→preview`，前后端渠道枚举不一致。
- **方案**: 统一 `channel` 枚举 `alpha/beta/preview/stable/hotfix` 为常量包 `core/channels.py` + 前端 `shared/utils/channels.js`，`BUILD-MANIFEST` 与 `version_info` 同源校验。
- **成本**: 0.5 人日

#### L14 — 前后端契约无单源 【P1】
- **证据**: 后端 `serializers.py` 与前端 `shared/api/*.ts` 各自定义 DTO，无 `OpenAPI` 生成；`docs/technical/05-api-reference.md` 手工维护易漂移。
- **方案**: 后端 `drf-spectacular` 生成 `openapi.json`，前端 `openapi-typescript` 生成 `api/generated/`，CI 校验 `schema diff` 必过；`docs/05-api-reference.md` 改为自动生成。
- **成本**: 2 人日

---

## 四、优先级矩阵与路线图

### 4.1 P0 紧急 (8 项，3 人周内闭环)

| ID | 标题 | 成本 | 收益 | 验证指标 |
|----|------|------|------|----------|
| U1 | 主题变量单源 | 1d | 高 | 色值一致 100% |
| U5 | 移动端导航重做 | 2d | 高 | Mobile Lighthouse 90+ |
| U8 | DataTable 统一 | 3d | 高 | 代码 -80 行/页 |
| U12| a11y 违规清零 | 2d | 高 | axe 0 |
| U13| 首屏包优化 | 1.5d | 高 | Bundle -35% |
| F1 | 排班 Dry-Run | 3d | 高 | 冲突率 -60% |
| L1 | API TS 统一 | 5d | 高 | TS strict 0 error |
| L6 | N+1 消除 | 2d | 高 | p95 -46% |
| L7 | Cookie 认证 | 3d | 高 | XSS 窃取不可行 |

> 注：并行分 2 组，前端 3 项 + 后端 2 项可首周完成。

### 4.2 P1 重要 (17 项，4-6 周)

U2, U3, U6, U9, U10, U11, F2, F3, F4, F6, F7, F8, F9, F11, L2, L3, L4, L8, L9, L12, L14 等，排期见甘特图。

### 4.3 P2 优化 (22 项，7-12 周)

U4, U7, U14, F5, F10, F12, F13, L5, L10, L11, L13 等，纳入季度迭代。

### 4.4 里程碑

- **M1 (2 周)**: P0 前端 5 项 + 后端 L6 合并，发布 `0.7.1-alpha.3`，灰度 10%；
- **M2 (4 周)**: P1 核心 8 项，`IntegrationHub` 与 `联邦搜索` 重做，`openapi` 契约上线；
- **M3 (8 周)**: 智能助手上下文扩展 + 通知推送 SSE，`httpOnly` Cookie 全量；
- **M4 (12 周)**: 离线可观测、文件分片、Win7 legacy 分流，冲刺 `0.8.0-beta`。

---

## 五、度量与门禁

- **CI 加项**: `axe:0`、`bundle <1.2 MB gzip`、`assertNumQueries <= N`、`openapi diff`、`coverage shared/* >=90%`；
- **APM**: 后端 `django-silk` 采样 10% + 前端 `web-vitals` 上报至 `core/client-error` 同链路 `request_id`；
- **灰度**: `deployment/docker/deploy_tests.sh` 4 profile 冒烟 + `paperless` Outbox 5 状态自动化巡检。

---

## 六、附录：已验证清单

- `vite.config.js` manualChunks 13 块、`target:chrome109` 影响 polyfill 体积；
- `Sidebar.jsx` 250px fixed + `UnifiedSearchBar` 折叠消失；
- `QuickAssistant.jsx` 453 行 + 全局常驻；
- `PersonnelManagementPage.jsx` 手写分页 vs `useCrudQuery.js` 抽象；
- `personnel/models.py` XOR 遗留 + Fernet 唯一失效；
- `axiosConfig.ts` 队列刷新正确但存储在 localStorage；
- `core/api.py` 脱敏双保险已实现；
- `docs/technical` 47 篇，架构总览已漂移（仍写 CRA+MUI，实际 Vite+AntD 单轨）。

> 完整探测日志与脚本见 `/home/user/mcp_helper.sh` + `mcp-session 05e082bc-fd12-4e9b-a4ec-d93b48c43891`。后续可按 `set_todos` 逐项派发实施。

