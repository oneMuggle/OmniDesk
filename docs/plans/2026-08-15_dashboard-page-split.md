# R3-D6: DashboardPage.jsx 拆分实施计划

> 日期:2026-08-15 | 状态:规划中 | 关联:round3 计划 `docs/plans/2026-08-14_project-optimization-round3.md` R3-D6
> 模式:与 R3-D1/D2/D3/D4/D5 同款 SDD 拆分流程 —— 拆文件 + 逐字搬运 + repoint + 差分验证(前端已有先例:`utils/` + `hooks/` + 子组件 + 薄壳页面)

## 1. 背景与目标

### 背景

`omni_desk_frontend/src/shared/pages/DashboardPage.jsx` 当前 **428 行**,单文件承担 6 类职责:

| 职责 | 位置 | 行数 |
|---|---|---|
| `quickActions` 快捷入口数组(6 项,含 JSX 图标) | L30-37 | ~8 |
| `fetchWeeklyOverview` 本周概览拉取(3 API `Promise.allSettled`,单项失败不影响其余) | L40-79 | ~40 |
| `fetchDashboardStats` 仪表盘聚合数据拉取 | L82-85 | ~4 |
| 主 JSX 布局:Header + 5 大区块(统计卡×2 行 / 待办+公告 / 本周概览三列表 / footer) | L104-424 | ~320 |

与 R3-D1~D5 同类,是 round3 计划 R3-D 前端大组件系列的一部分,明确列为 R3-D6(拆为 DashboardShell + 各 widget:统计 / 待办 / 快速入口)。

### 关键前置发现

- **无既有测试**:`grep DashboardPage src/` 仅命中 `routes/index.jsx`(lazy import),`shared/pages/` 下无 `DashboardPage.test.*`
- **唯一引用**:`routes/index.jsx:11` `lazy(() => import('../shared/pages/DashboardPage'))` + L273 `<LazyComponent component={DashboardPage} />`
- **样式独立**:`DashboardPage.css`(183 行)与 JSX 解耦,类名稳定 → **零改动**,子组件沿用现有类名
- **外部契约简单**:仅 1 处 lazy import,薄壳保留原位同名 → **对外契约零变化**

### 目标

1. 将 `DashboardPage.jsx` 拆为**薄壳(~40 行)** + 1 个数据工厂(`.jsx`)+ 1 个数据 hook + 5 个 widget 子组件
2. **对外契约零变化**:`routes/index.jsx` L11 lazy import 不变,默认导出不变;页面渲染与当前完全一致
3. 延续 R3-D1~D5 既定模式(数据工厂 + hook + 子组件 + 薄壳),全部子组件带 propTypes
4. 拆分行为逐字一致;因无既有测试,新增数据层单测(quickActions 结构 + fetch 函数 allSettled 语义)作为回归兜底
5. `DashboardPage.css` 零改动(类名跨组件共用)

## 2. 涉及的文件与模块

### 新增(7 个)

| 文件 | 职责 | 预估行数 |
|---|---|---|
| `shared/pages/dashboard/dashboardData.jsx` | 数据工厂:`quickActions`(6 项快捷入口,含 JSX 图标 → **.jsx**)+ `fetchWeeklyOverview`(3 API allSettled)+ `fetchDashboardStats` | ~85 |
| `shared/pages/dashboard/hooks/useDashboardData.js` | 数据 hook:两个 `useQuery`(dashboard-weekly-overview / dashboard-stats)+ 派生数据(weeklyTrials / weeklySchedules / weeklyBookings / errors / loading / statsLoading) | ~30 |
| `shared/pages/dashboard/DashboardHeader.jsx` | 欢迎标题 + 副标题(静态) | ~15 |
| `shared/pages/dashboard/StatSummaryCards.jsx` | 统计卡行 1:未读通知 / 进行中项目 / 今日值班 | ~60 |
| `shared/pages/dashboard/MemosAndAnnouncements.jsx` | 待办事项 + 最新公告双卡片 | ~75 |
| `shared/pages/dashboard/QuickStatsRow.jsx` | 统计卡行 2:本周试验 / 本周排班 / 会议室预约 + 快捷操作卡 | ~65 |
| `shared/pages/dashboard/WeeklyOverview.jsx` | 本周概览三列表:试验日程 / 排班日程 / 会议室预约 | ~150 |

### 新增测试(1 个)

| 文件 | 覆盖 |
|---|---|
| `shared/pages/dashboard/__tests__/dashboardData.test.jsx` | `quickActions` 6 项结构与字段(to / title / color 唯一);`fetchWeeklyOverview`:mock 3 API → 全成功 / 单项失败(其余仍返回数据,errors 标记)/ 全失败;`fetchDashboardStats` 透传 response.data |

### 修改(1 个)

| 文件 | 改动 |
|---|---|
| `shared/pages/DashboardPage.jsx` | 428 → ~40 行薄壳:调用 `useDashboardData` + 5 个 widget 组件 + footer |

### 不变(3 个)

| 文件 | 说明 |
|---|---|
| `src/routes/index.jsx` | L11 lazy import 与 L273 使用不变,零 repoint |
| `src/shared/pages/DashboardPage.css` | 类名稳定,子组件沿用现有类名,零改动 |
| `dayjs` 插件注册(relativeTime / zh-cn locale) | 保留在薄壳(唯一副作用面),子组件仅用 `dayjs().format()` 纯函数 |

## 3. 技术方案(架构/接口设计)

### 3.1 模块职责划分

```
shared/pages/DashboardPage.jsx(薄壳 ~40 行)
  ├── dayjs.extend(relativeTime) / dayjs.locale('zh-cn')   # 保留唯一副作用面
  ├── useDashboardData() → { weeklyTrials, weeklySchedules, weeklyBookings,
  │                          errors, loading, dashboardStats, statsLoading }
  ├── <DashboardHeader />                                   # 静态头部
  ├── <StatSummaryCards dashboardStats statsLoading />
  ├── <MemosAndAnnouncements dashboardStats statsLoading />
  ├── <QuickStatsRow weeklyTrials weeklySchedules weeklyBookings />
  ├── <WeeklyOverview weeklyTrials weeklySchedules weeklyBookings loading errors />
  └── footer JSX(3 行,并入薄壳)
```

### 3.2 子组件 props 契约

```js
<DashboardHeader />                                      // 无 props,纯静态
<StatSummaryCards dashboardStats statsLoading />         // Statistic 三卡 + Skeleton
<MemosAndAnnouncements dashboardStats statsLoading />    // 待办 List + 公告 List,含 Empty/Skeleton
<QuickStatsRow weeklyTrials weeklySchedules weeklyBookings />
  // 内部:三张 Statistic 卡 + quickActions map 快捷入口(从 dashboardData 导入,不经 props)
<WeeklyOverview weeklyTrials weeklySchedules weeklyBookings loading errors />
  // 内部:三张 list Card,loading→SkeletonList / errors→Empty(加载失败)/ 空→Empty / 数据→List
```

### 3.3 数据工厂契约

```js
// dashboardData.jsx (含 JSX 图标,故 .jsx)
quickActions: { to, icon, title, color }[]          // 6 项,逐字搬自 L30-37
fetchWeeklyOverview() → { trials[], schedules[], bookings[], errors:{trials,schedules,bookings} }
  // 逐字搬自 L40-79,Promise.allSettled + logger.error,单项失败不阻断其余
fetchDashboardStats() → response.data                // 逐字搬自 L82-85
```

### 3.4 数据 hook 契约

```js
// hooks/useDashboardData.js
useDashboardData() → {
  weeklyTrials / weeklySchedules / weeklyBookings,   // weeklyData?.xx ?? []
  errors,                                            // weeklyData?.errors ?? {}
  loading,                                           // weekly.isLoading
  dashboardStats,                                    // stats.data
  statsLoading,                                      // stats.isLoading
}
// 两个 useQuery queryKey 原样保留(['dashboard-weekly-overview'] / ['dashboard-stats'])
```

### 3.5 逐字搬运原则

- 5 个 widget 的 JSX **逐字搬入**对应子组件,仅把内部闭包变量改为 props(`dashboardStats` / `statsLoading` / `weekly*` / `loading` / `errors`)
- `quickActions` 数组字面量逐字搬入 `dashboardData.jsx`(含 icon 组件引用)
- `fetchWeeklyOverview` / `fetchDashboardStats` 函数体逐字搬入,零逻辑改动
- `dayjs` 副作用(extend / locale)保留在薄壳,避免子组件重复注册
- 不做任何逻辑改动(本轮是纯拆分,非行为优化)

### 3.6 propTypes(沿用 R3-D3/D4/D5 约定)

所有子组件定义 propTypes:`dashboardStats` 用 `shape`(可空)/ `object`、`weeklyTrials/Schedules/Bookings` 用 `arrayOf`、`errors` 用 `shape`、loading 类布尔 `isRequired`。

## 4. 实施步骤

### Task 1: 新增 `dashboard/dashboardData.jsx`

- [x] 逐字搬 `quickActions` 数组(6 项)→ 导出 `quickActions`
- [x] 逐字搬 `fetchWeeklyOverview`(3 API allSettled)→ 导出
- [x] 逐字搬 `fetchDashboardStats` → 导出
- [x] 扩展名 `.jsx`(含 JSX 图标)

### Task 2: 新增 `dashboard/hooks/useDashboardData.js`

- [x] 两个 `useQuery` 迁入,queryKey / queryFn 原样
- [x] 返回派生数据对象(weekly* ?? [] / errors ?? {} / loading / statsLoading)

### Task 3: 新增 5 个 widget 子组件

- [x] `DashboardHeader.jsx` — L105-109 逐字搬入,静态
- [x] `StatSummaryCards.jsx` — L112-159 逐字搬入(未读通知 / 进行中项目 / 今日值班)
- [x] `MemosAndAnnouncements.jsx` — L162-224 逐字搬入(待办 + 公告)
- [x] `QuickStatsRow.jsx` — L227-276 逐字搬入(本周三统计 + 快捷操作)
- [x] `WeeklyOverview.jsx` — L279-419 逐字搬入(三列表)
- [x] 全部定义 propTypes(R3-D3/D4/D5 约定)

### Task 4: 重构 `DashboardPage.jsx` 为薄壳

- [x] 保留 dayjs extend / locale
- [x] 调用 `useDashboardData` 替代两个内联 useQuery
- [x] JSX 改为 5 个 widget 组合 + footer
- [x] 确认 `routes/index.jsx` import 零改动

### Task 5: 新增数据层单测

- [x] `__tests__/dashboardData.test.jsx` 覆盖 quickActions 结构 + fetch 函数(allSettled 语义)
- [x] mock `apiClient`(jest.mock `../api/apiClient`)与 `logger`

### Task 6: 验证

- [x] 新增单测通过
- [x] `npx jest src/shared/pages` 全量回归绿
- [x] 全量 `npm test` 三绿(无既有测试可破,纯增量)
- [x] `npm run lint` 通过
- [x] `npm run build` 通过(generate-routes + vite build)

### Task 7: 文档更新 + PR + merge

- [x] round3 plan 标注 R3-D6 完成
- [x] feature 分支 push(`refactor/dashboard-page-split`)→ PR #261 → CI 8/8 全绿 → code review(1 Maintainability 已修复:dayjs relativeTime 全局注册至 index.jsx,commit df65ad38)
- [ ] 用户 merge PR #261 → 清理分支(按 R3-D1~D5 先例)

## 5. 验收标准

| 标准 | 验证方式 |
|---|---|
| `DashboardPage.jsx` ≤45 行薄壳(428→~40,减 90%) | `wc -l` |
| 各新文件 <800 行 / 函数 <50 行 | `wc -l` + 目检 |
| 5 个 widget 全部带 propTypes | 目检 + code review |
| `routes/index.jsx` import 不变 | `git diff` |
| `DashboardPage.css` 零改动 | `git diff` |
| 新增数据层单测通过(allSettled 部分失败语义) | `npx jest src/shared/pages/dashboard` |
| 全量 jest / lint / build 三绿 | `npm test` + `npm run lint` + `npm run build` |
| 页面渲染逐字一致(统计卡 / 待办 / 快捷入口 / 三列表) | 差分验证 + 新增单测兜底 |

## 6. 风险评估与依赖

| 风险 | 缓解 |
|---|---|
| **中**:Dashboard 无既有测试,拆分后无自动兜底 | 新增数据层单测(quickActions + fetch allSettled 语义);widget 为纯展示组件,逐字搬运保证 JSX 一致;人工 `npm run dev` 冒烟(可选) |
| **中**:5 个 widget 共享 props 链(weekly* 重复传 2 处) | props 契约表 + 逐字搬运;hook 集中派生,薄壳单一来源 |
| **低**:`.jsx` 文件不在 lint 覆盖(既有盲区,memory: `frontend-eslint-jsx-blindspot`) | 依赖 code review 检查子组件 propTypes 与死 props;新增单测兜底 |
| **低**:dayjs 副作用若在子组件重复注册 | 显式约定:extend / locale 仅薄壳,子组件只用 `dayjs().format()/fromNow()` 纯函数 |
| **低**:quickActions 抽离后引用方式变化 | 模块内导入,不经 props(仅 QuickStatsRow 使用) |

## 7. 关联

- 上游:`docs/plans/2026-08-14_project-optimization-round3.md`(R3-D6)
- 同源:R3-D1(`smart-chat-page-split`)、R3-D2(`tool-result-split`)、R3-D3(`agent-task-panel-split`)、R3-D4(`user-management-page-split`)、R3-D5(`sidebar-split`),同款 utils/ + hooks/ + 子组件拆分流程
- memory:`frontend-jsx-in-hook-extension`(含 JSX 文件必须 .jsx)、`frontend-eslint-jsx-blindspot`(.jsx 不在 lint 覆盖)
- 技术文档:`docs/technical/` 前端组件相关章节(可选更新)
