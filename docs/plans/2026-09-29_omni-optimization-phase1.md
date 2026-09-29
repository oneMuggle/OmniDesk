# OmniDesk 优化落地实施方案 — 2026-09-29 P0 速赢

> **关联审计**: `docs/mcp-omni-desk-optimization-plan.md` (47 项) | **分支**: `agent/omni-optimization-20260929` | **Worktree**: `.worktrees/omni-optimization-20260929` | **基线**: `feat/ai-eval-s0@edae9f0b`

## 1. 目标与原则

- **量化目标**: 首屏 JS 1.8MB→1.15MB(gzip)、后端 p95 260→140ms、axe 0、移动端 Lighthouse 90+
- **原则**: 小步原子补丁、可回滚、每步 `get_diagnostics + pytest/jest` 门禁、文档同步至 `docs/`
- **分阶段**: P0 速赢(3周) → P1 功能补齐(6周) → P2 体验精修(12周)

## 2. 现状核验 (Worktree 实测)

| 模块 | 核验结果 | 结论 |
|------|----------|------|
| `tokens.css` | 已为 `data-theme` 四主题 (teal/indigo/amber/skyblue) 单源，`ThemeContext` 写入 `data-theme` | U1 已部分完成，剩余 `index.css .dark` 与 `global.css` 色值重复需收敛 |
| `ScheduleViewSet` | `select_related(duty_person,duty_leader,duty_person__position,...)` 已加 | L6 排班部分已完成，需扩展至 `notifications/projects/compliance` |
| `PersonnelViewSet` | `select_related(position)` + `prefetch_related` 已加 | L6 人员部分已完成 |
| `dashboard/views.dashboard_stats` | 已聚合 `today_schedule/recent_announcements/memos_due/projects/unread_notifications` 单接口 | L2 仪表盘瀑布已解决 |
| `App.jsx:12 import 'animate.css'` | 仍全量引入 73kB，仅 QuickAssistant 用 1 keyframe | U4 未完成 |
| `index.jsx:1-2 core-js/stable, whatwg-fetch` | 仍全量 polyfill，与 `vite target chrome109` 重复 | U13 未完成 |
| `Sidebar.jsx` | 无 ESC/焦点陷阱/aria，折叠时搜索消失 | U5/U12 未完成 |
| `DataTable` vs `PersonnelManagementPage` | 手写分页 80 行 vs `useCrudQuery`割裂 | U8 未完成 |

> 策略：已完成项不再重做，未完成项按 **影响×成本** 优先。

## 3. 分阶段任务

### Phase 1 — P0 速赢 (本次 Worktree, 5 工作日)

| ID | 任务 | 文件 | 成本 | 验证 |
|----|------|------|------|------|
| T1 | 移除 `animate.css` 全量，改局部 keyframes | `App.jsx`, `QuickAssistant.css` | 0.5d | `npm run build` 体积 -18kB gzip, 视觉无回归 |
| T2 | `index.jsx` Polyfill 瘦身 (移除 `core-js/stable`，`whatwg-fetch` 按需) | `index.jsx`, `vite.config.js` | 0.5d | `vite build --report` + Chrome109 真机 + `eslint` |
| T3 | 侧边栏 a11y & 移动端增强 (ESC、焦点陷阱、aria、搜索保留) | `Sidebar.jsx`, `App.jsx`, `App.css` | 2d | `axe-core` 0, 手机 768px 手动 |
| T4 | 统一 `DataTable + useCrudQuery` 示范 (重构 `PersonnelManagementPage`) | `PersonnelManagementPage.jsx`, `shared/components/DataTable` | 3d | `jest` + `pytest` + 手动分页/搜索 |
| T5 | 后端 N+1 补漏 (notifications/projects/compliance) | `notifications/views.py`, `projects/views.py` | 1d | `assertNumQueries` + `silk` |
| T6 | 新增 `PageState` 统一空/加载/错误态 | `shared/components/PageState.jsx` + 应用至 `DashboardPage` | 1d |  Story + `axe` |

> 本次提交聚焦 **T1+T2+T3** (可 1 日内闭环，低风险高可见)，T4-T6 作为后续 PR。

### Phase 2 — P1 功能补齐 (4-6 周)

- F1 排班 Dry-Run 预览 + `weekly-leaders` 后端单源
- F6 联邦搜索高亮 + Tabs
- U10 QuickAssistant 拆 hook + 完整页卸载
- L1 API TS 全量 + `openapi-typescript`
- L7 Cookie 认证 (需产品决策)

### Phase 3 — P2 精修 (7-12 周)

- Win7 legacy 双构建、`tus` 分片上传、离线心跳全局化

## 4. 详细设计 (本次 T1-T3)

### T1 — animate.css 移除

- **现状**: `App.jsx:12 import 'animate.css'` 全量 73kB，`QuickAssistant` 仅用 `animate__fadeIn`。
- **方案**:
  - 删除 `import 'animate.css'` 与 `package.json` 依赖 (保留则 `npm uninstall`，本次仅删 import 以最小变更)
  - 在 `QuickAssistant.css` 新增:
    ```css
    @keyframes qa-drawer-in { from { opacity:0; transform: translateX(12px)} to {opacity:1; transform:none}}
    .quick-assistant-drawer .ant-drawer-content { animation: qa-drawer-in 0.2s ease }
    ```
  - 验收: `npm run build` `assets` 中无 `animate`，抽屉动画保留。

### T2 — Polyfill 瘦身

- **现状**: `index.jsx:1-2` `core-js/stable` 为 Chrome109 目标冗余；`whatwg-fetch` 仅 Safari<14 需要，Vite `target:chrome109` 已含 fetch。
- **方案**:
  - 删除 `import 'core-js/stable'`，保留 `whatwg-fetch` 但改为 `import 'whatwg-fetch'` 仅在 `!window.fetch` 时 (或直接删除，因 Vite 已 polyfill 基础语法，保留注释说明)
  - `vite.config.js` 注释 `target:chrome109` 为 Win7 保留，现代构建加 `legacy` 双轨 (注释先行)
  - 验证: `npm run build` 无 `core-js`  chunk，`npx vite --host` 在 Chrome109 边界测试通过。

### T3 — 侧边栏 a11y & 移动端

- **改动点**:
  - `App.jsx`: 新增 `<a href="#main-content" class="skip-link">跳至主内容</a>` + `#main-content` id，`.skip-link` 仅键盘聚焦可见
  - `App.css`: 新增 `.skip-link { position:absolute; left:-9999px } .skip-link:focus { left:16px; top:16px; z-index:1080 }`
  - `Sidebar.jsx`:
    - 注入 `useEffect` 监听 `Escape` 关闭移动菜单
    - `mobile-overlay` 加 `role="button" aria-label="关闭菜单" tabIndex=0` + `onKeyDown`
    - `nav.sidebar-menu` 加 `aria-label="主导航"` 并修正 `role` (ul=menu, li=menuitem)
    - 折叠态 (`isCollapsed`) 搜索不消失，改为渲染图标按钮触发 `Modal` 搜索
    - `SidebarHeader` 透传 `aria-expanded`

## 5. 测试与门禁

- `npm run lint` + `npm run test:coverage -- --watchAll=false` (前端)
- `pytest --ds=omni_desk_backend.settings.test -q` (后端)
- `axe` 手动: `npx playwright test --project=chromium --grep a11y` (后续)
- 体积门禁: `npm run build 2>&1 | grep -E "gzip|chunk"`

## 6. 风险与回滚

- **T1**: 动画丢失可回滚单行 import
- **T2**: 若 Win7 用户反馈白屏，回退 `core-js` 并切 legacy 构建
- **T3**: 无数据迁移，纯前端，`git revert` 即回滚

## 7. 提交计划

- `commit 1`: `refactor(ui): remove animate.css, add local keyframes (T1)`
- `commit 2`: `perf(frontend): slim polyfills, document chrome109 target (T2)`
- `commit 3`: `feat(a11y): sidebar esc/focus/aria + skip-link (T3)`
- 每 commit 独立 `get_diagnostics` + `npm run build` 验证

---

> 本方案已对齐审计 47 项，首批 T1-T3 可 1 日内在当前 Worktree 闭环并提 PR 至 `feat/ai-eval-s0`。
