# R3-D5: Sidebar.jsx 拆分实施计划

> 日期:2026-08-15 | 状态:规划中 | 关联:round3 计划 `docs/plans/2026-08-14_project-optimization-round3.md` R3-D5
> 模式:与 R3-D1/D2/D3/D4 同款 SDD 拆分流程 —— 拆文件 + 逐字搬运 + repoint + 差分验证(前端已有先例:`utils/` + `hooks/` + `components/<subdir>/` 子组件 + 薄壳页面)

## 1. 背景与目标

### 背景

`omni_desk_frontend/src/shared/components/Sidebar.jsx` 当前 **446 行**,单文件承担 5 类职责:

| 职责 | 位置 | 行数 |
|---|---|---|
| `menuItems` 菜单配置 useMemo(主菜单数组,含 submenu / permission / badgeCount) | L84-131 | ~48 |
| `userDropdownItems` 用户下拉配置 useMemo | L336-360 | ~25 |
| `renderMenuItem` 菜单项渲染 useCallback(button / submenu / link 三型 × collapsed 两态,含 Tooltip / Popover / Badge) | L138-334 | ~197 |
| Sidebar 状态 + 3 个 effect(折叠持久化 / body 滚动锁 / 通知轮询) | L35-83 | ~49 |
| 主 JSX 布局(header 用户区/游客区/主题/折叠 + nav 菜单 + 移动端 toggle) | L362-439 | ~78 |

与 R3-D1/D2/D3/D4 同类,是 round3 计划 R3-D 前端大组件系列的一部分,明确列为 R3-D5(按角色拆分路由表 + Sidebar 渲染)。

### 关键前置发现:`menuConfig.jsx` 是过时死代码

`src/shared/config/menuConfig.jsx`(101 行)已存在 `createMainMenuItems`,但:

- **全库零引用**(grep 仅匹配文件自身),属未接线死代码
- **内容与 Sidebar 当前有效菜单不一致**:旧菜单含已删除路由 `/ai-showcase`、`外部集成` 子菜单,缺 `智能助手`/`知识库`/`多Agent任务`/`Office 助手` 等当前菜单项
- 其测试 `menuConfig.test.js` / `menuConfig.additional.test.js` 断言 `AI 助手` 子菜单 **5 项**(旧),与当前实际 **7 项**矛盾,进一步佐证过时

**处理决策:不接入,一并删除**(死代码清理)。当前有效菜单从 Sidebar 内联逐字搬入新文件,保证行为零变化。

### 目标

1. 将 `Sidebar.jsx` 拆为**薄壳(~110 行)** + 1 个菜单数据工厂(`.jsx`) + 4 个渲染子组件
2. **对外契约零变化**:`App.jsx` L9 `import Sidebar` 不变,默认导出不变;菜单行为与当前完全一致
3. 删除死代码 `menuConfig.jsx` + 2 个过时测试
4. 拆分行为逐字一致,经既有 7 用例全量回归,并新增菜单单测
5. 延续 R3-D1/D2/D3/D4 既定模式(数据工厂 + 子组件 + 薄壳)

## 2. 涉及的文件与模块

### 新增(6 个)

| 文件 | 职责 | 预估行数 |
|---|---|---|
| `shared/components/sidebar/sidebarMenuItems.jsx` | 菜单数据工厂:`createMenuItems({logout, unreadNotificationCount})` + `createUserDropdownItems({navigate, logout})`。**含 JSX 图标 → 扩展名 .jsx**(R3-D4 memory 教训,Vite 拒绝 .js 内 JSX) | ~90 |
| `shared/components/sidebar/SidebarButtonItem.jsx` | 按钮型菜单项(退出登录)渲染 + collapsed Tooltip | ~45 |
| `shared/components/sidebar/SidebarLinkItem.jsx` | 链接型菜单项渲染 + collapsed Tooltip + active 态 | ~55 |
| `shared/components/sidebar/SidebarSubMenu.jsx` | 子菜单渲染:expanded CSS 动画态 + collapsed Popover 浮动子菜单 + badgeCount | ~135 |
| `shared/components/sidebar/SidebarHeader.jsx` | header:brand / 用户下拉 / 通知铃 / 游客区 / 主题+Demo / 折叠关闭按钮 | ~70 |

### 修改(1 个)

| 文件 | 改动 |
|---|---|
| `shared/components/Sidebar.jsx` | 446 → ~110 行薄壳:状态 + 3 effects + header + nav(map 3 型子组件) + 移动端 toggle |

### 删除(3 个,死代码清理)

| 文件 | 理由 |
|---|---|
| `shared/config/menuConfig.jsx` | 未接线、内容过时(旧 AI 助手 5 项/含已删路由),被新 sidebarMenuItems.jsx 取代 |
| `shared/config/menuConfig.test.js` | 断言过时内容(AI 5 项),随源文件删除 |
| `shared/config/menuConfig.additional.test.js` | 同上 |

### 新增测试(1 个)

| 文件 | 覆盖 |
|---|---|
| `shared/components/sidebar/__tests__/sidebarMenuItems.test.jsx` | `createMenuItems` 各分支:退出登录 action / 通知 badgeCount / 日历子菜单 3 项 / AI 助手 7 项(当前)/ 管理中心权限;`createUserDropdownItems`:profile/settings/logout + divider |

### 不变(2 个)

| 文件 | 说明 |
|---|---|
| `shared/components/Sidebar.test.js` | 7 用例全部顶层 `render(<Sidebar />)` + mock,不引用内部函数 → **零 repoint** |
| `src/App.jsx` | `import Sidebar from './shared/components/Sidebar'`,不变 |

## 3. 技术方案(架构/接口设计)

### 3.1 模块职责划分

```
shared/components/Sidebar.jsx(薄壳 ~110 行)
  ├── state: isCollapsed(STORAGE_KEY 持久化) / expandedSubMenu / collapsedPopoverOpen / unreadNotificationCount
  ├── effects: 折叠持久化 / body 滚动锁 / 通知轮询(60s,非折叠时)
  ├── useAuth() → isAuthenticated / user / logout / hasPermission / isGuest
  ├── useMemo: createMenuItems({logout, unreadNotificationCount}) + createUserDropdownItems({navigate, logout})
  ├── <SidebarHeader ... />                          # header 全量 JSX 搬入
  ├── nav: menuItems.filter(hasPermission).map(item =>   # 按 type 分发 3 型子组件
  │     ├── type==='button'  → <SidebarButtonItem .../>
  │     ├── type==='submenu' → <SidebarSubMenu .../>
  │     └── default          → <SidebarLinkItem .../>
  └── 移动端 toggle 按钮
```

### 3.2 子组件 props 契约

```js
<SidebarHeader isAuthenticated user isGuest isCollapsed isMobileMenuOpen
  userDropdownItems onToggleCollapsed onCloseMobile onNavigate />
  // 内部:brand + 用户下拉 + 通知铃(NotificationBell) + 游客区 + ThemeSelector/DemoToggle + 折叠/关闭按钮
<SidebarButtonItem item isCollapsed isMobileMenuOpen onCloseMobile />
  // 内部:button 渲染 + collapsed Tooltip;onClick → item.action() + onCloseMobile()
<SidebarLinkItem item isCollapsed isMobileMenuOpen location onCloseMobile />
  // 内部:Link + active 态 + collapsed Tooltip
<SidebarSubMenu item isCollapsed isMobileMenuOpen location hasPermission
  expandedSubMenu collapsedPopoverOpen onToggleSubMenu onCollapsedPopoverChange onCloseMobile />
  // 内部:subMenuHeader(折叠判定) + expanded 两态渲染 + collapsed Popover 浮动子菜单 + badgeCount
```

### 3.3 数据工厂契约

```js
// sidebarMenuItems.jsx (含 JSX 图标,故 .jsx)
createMenuItems({ logout, unreadNotificationCount }) => MenuItem[]
  // 逐字搬自 Sidebar L84-131:首页/公告栏/日历(sub)/AI 助手(sub 7 项)/文档库/备忘录/交流/个人资料/项目管理(sub,admin)/管理中心(admin,manager)/退出登录(button)
createUserDropdownItems({ navigate, logout }) => DropdownItem[]
  // 逐字搬自 Sidebar L336-360:个人资料/设置/divider/退出登录(danger)
```

### 3.4 逐字搬运原则

- `menuItems` useMemo 数组字面量逐字搬入 `sidebarMenuItems.jsx` 的 `createMenuItems`(含 icon 组件引用、permission 字段、badgeCount 引用)
- `userDropdownItems` 逐字搬入 `createUserDropdownItems`(含 `icon: <UserOutlined />` JSX)
- `renderMenuItem` 三支 JSX 逐字搬入对应子组件,仅把 Sidebar 内部闭包变量改为 props:
  - button 支(L139-171)→ SidebarButtonItem
  - link 支(L304-333)→ SidebarLinkItem(含 `role=menuitem` / `aria-current` / active 类)
  - submenu 支(L173-302)→ SidebarSubMenu(subMenuHeader + collapsed Popover + expanded 态)
- header JSX(L365-425)逐字搬入 SidebarHeader(含 Avatar/NotificationBell/ThemeSelector/DemoToggle 条件渲染)
- 不做任何逻辑改动(本轮是纯拆分 + 死代码清理,非行为优化)

### 3.5 propTypes(沿用 R3-D3/D4 约定)

所有子组件定义 propTypes:回调 `isRequired`、`item` 用 `shape({...})`、`permission` 用 `oneOfType([string, array])`。`Sidebar.jsx` 薄壳保留现有 propTypes(isMobileMenuOpen / toggleMobileMenu)。

## 4. 实施步骤

### Task 1: 新增 `sidebar/sidebarMenuItems.jsx`

- [x] 逐字搬 `menuItems` 数组字面量 → `createMenuItems({logout, unreadNotificationCount})`
- [x] 逐字搬 `userDropdownItems` → `createUserDropdownItems({navigate, logout})`
- [x] 扩展名 `.jsx`(含 JSX 图标)

### Task 2: 新增 4 个渲染子组件

- [x] `SidebarButtonItem.jsx` — button 支逐字搬入
- [x] `SidebarLinkItem.jsx` — link 支逐字搬入
- [x] `SidebarSubMenu.jsx` — submenu 支逐字搬入(collapsed Popover + expanded 两态)
- [x] `SidebarHeader.jsx` — header JSX 逐字搬入
- [x] 全部定义 propTypes(R3-D3/D4 约定)

### Task 3: 重构 `Sidebar.jsx` 为薄壳

- [x] 状态 + 3 effects 保留
- [x] 菜单数据改用 `createMenuItems` / `createUserDropdownItems`
- [x] nav 改 map 分发 3 型子组件
- [x] 确认 `App.jsx` import 零改动

### Task 4: 删除死代码

- [x] 删除 `config/menuConfig.jsx` + `menuConfig.test.js` + `menuConfig.additional.test.js`

### Task 5: 新增菜单单测

- [x] `sidebar/__tests__/sidebarMenuItems.test.jsx` 覆盖 `createMenuItems` / `createUserDropdownItems`

### Task 6: 验证

- [x] 既有 `Sidebar.test.js`(7 用例)**零改动**通过
- [x] 新增菜单单测通过
- [x] `npx jest src/shared/components` 全量回归绿
- [x] `npm run lint` 通过
- [x] `npm run build` 通过(generate-routes + vite build)

### Task 7: 文档更新 + PR + merge

- [x] round3 plan 标注 R3-D5 完成
- [ ] feature 分支 push → PR → CI 监控 → code review → merge → 清理(按 R3-D1/D2/D3/D4 先例)

## 5. 验收标准

| 标准 | 验证方式 |
|---|---|
| `Sidebar.jsx` ≤130 行薄壳 | `wc -l` |
| 各新文件 <800 行 / 函数 <50 行 | `wc -l` + 目检 |
| 既有 7 用例零改动通过 + 新增菜单单测通过 | `npx jest shared/components` |
| 全量 jest / lint / build 三绿 | `npm test` + `npm run lint` + `npm run build` |
| 4 个子组件全部带 propTypes | 目检 + code review |
| `App.jsx` import 不变 / menuConfig 死代码已删 | `git diff` + `git grep menuConfig` |
| 菜单行为逐字一致(树 / 权限过滤 / collapsed 态 / badge) | 差分验证 + 既有测试兜底 |

## 6. 风险评估与依赖

| 风险 | 缓解 |
|---|---|
| **高**:`renderMenuItem` 是核心交互(collapsed Popover / expanded 动画 / 键盘可达性),拆组件后 props 链长(SubMenu ~10 props) | 逐字搬移 + props 契约表 + 既有 7 用例兜底(Sidebar 顶层渲染,不 mock 内部) |
| **中**:删除 `menuConfig.jsx` 若隐藏引用(如动态 require) | grep 全库确认仅测试引用;删除后 `npm test` 全量回归兜底 |
| **中**:菜单数据抽离后 `badgeCount`/`logout`/`navigate` 注入方式变化 | 工厂函数参数注入,useMemo 依赖数组原样保留 |
| **低**:`.jsx` 文件不在 lint 覆盖(既有盲区) | 依赖 code review 检查子组件 propTypes 与死 props;新单测兜底 |
| **低**:Sidebar 依赖 ThemeContext/DemoContext/AuthContext(既有测试已包裹 Provider) | 测试环境不变,薄壳保留全部 context 使用 |

## 7. 关联

- 上游:`docs/plans/2026-08-14_project-optimization-round3.md`(R3-D5)
- 同源:R3-D1(`smart-chat-page-split`)、R3-D2(`tool-result-split`)、R3-D3(`agent-task-panel-split`)、R3-D4(`user-management-page-split`),同款 utils/ + 子组件拆分 + 测试零 repoint 流程
- memory:`frontend-jsx-in-hook-extension`(含 JSX 文件必须 .jsx)、`frontend-eslint-jsx-blindspot`(.jsx 不在 lint 覆盖)
- 技术文档:`docs/technical/` 前端组件相关章节(可选更新)
