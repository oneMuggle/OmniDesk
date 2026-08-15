# R3-D4: UserManagementPage.jsx 拆分实施计划

> 日期:2026-08-15 | 状态:实施完成 | 关联:round3 计划 `docs/plans/2026-08-14_project-optimization-round3.md` R3-D4
> 模式:与 R3-D1/D2/D3 同款 SDD 拆分流程 —— 拆文件 + 逐字搬运 + repoint + 差分验证(前端已有先例:`utils/` + `hooks/` + `components/<subdir>/` 子组件 + 薄壳页面)

## 1. 背景与目标

### 背景

`omni_desk_frontend/src/features/user/pages/UserManagementPage.jsx` 当前 **474 行**,单文件同时承担 3 类职责:

| 职责 | 位置 | 行数 |
|---|---|---|
| 模块级纯函数 `getAllKeys`(权限树全展开 key 收集) | L14-24 | ~11 |
| `GroupPermissionManager` 子组件(用户组权限矩阵:组 CRUD + 权限树 + 搜索高亮 + 新增/编辑 Modal) | L26-291 | ~266 |
| `UserManagementPage` 主组件(用户列表表格 `userColumns` + 关联人员/用户组 Select + Tabs 组合 + 初始加载) | L294-473 | ~180 |

与 R3-D1(713 行 SmartChatPage)/ R3-D2(588 行 ToolResult)/ R3-D3(522 行 AgentTaskPanel)同类,是 round3 计划 R3-D 前端大组件系列的一部分,明确列为 R3-D4(拆为"列表 + 表单 + 权限矩阵")。

### 目标

1. 将 `UserManagementPage.jsx` 拆为**薄壳(~60 行)** + 2 个 HookLayer(`useUserManagementPage` / `useGroupPermissionManager`) + 1 个 utils 模块 + 4 个子组件,各新文件 <800 行、函数 <50 行
2. **对外契约零变化**:`routes/index.jsx` lazy import 路径不变,默认导出不变 → 路由不受影响
3. 拆分行为逐字一致,经既有测试套件(3 用例)全量回归 + 差分验证,并新增 utils 单测补 `getAllKeys` 覆盖
4. 延续 R3-D1/D2/D3 既定模式(utils/ + hooks/ + components/ 子组件目录),保持一致结构

## 2. 涉及的文件与模块

### 新增(8 个)

| 文件 | 职责 | 预估行数 |
|---|---|---|
| `features/user/utils/userManagementUtils.js` | 纯函数:`getAllKeys`(权限树全展开 key 收集) | ~15 |
| `features/user/hooks/useUserManagementPage.js` | HookLayer:users/groups/personnel/loading 状态 + fetchUsers/fetchGroups/fetchPersonnel + handleGroupsChange/handleAssociationChange + 初始加载 effect | ~90 |
| `features/user/hooks/useGroupPermissionManager.jsx` | HookLayer:selectedGroupId/permissions/checkedKeys/expandedKeys/searchValue/modal/form 全部状态 + fetchPermissions/fetchGroupPermissions/handleSavePermissions/onExpand/onCheck/onSearch/showModal/handleCancel/handleOk/handleDelete + treeData/allKeys useMemo + 2 个 effect。**扩展名 .jsx**(含 `generatedTreeData` 高亮 JSX,Vite 解析 .js 时拒绝 JSX 语法) | ~150 |
| `features/user/components/userManagement/UserListTable.jsx` | 用户列表表格:userColumns 列定义(头像/用户名/邮箱/电话/关联人员 Select/用户组 Select/加入日期/操作) | ~130 |
| `features/user/components/userManagement/GroupPermissionManager.jsx` | 权限矩阵容器薄壳:Card + 组合 GroupActionBar + PermissionTreePanel + GroupFormModal,内部组合 useGroupPermissionManager | ~60 |
| `features/user/components/userManagement/GroupActionBar.jsx` | 组选择 Select + 创建/编辑/删除/保存权限按钮组 | ~50 |
| `features/user/components/userManagement/PermissionTreePanel.jsx` | 权限树面板:全部展开/折叠 + 搜索框 + Tree(checkable + 高亮 title) | ~80 |
| `features/user/components/userManagement/GroupFormModal.jsx` | 新增/编辑用户组 Modal + Form(名称字段) | ~50 |

### 修改(1 个)

| 文件 | 改动 |
|---|---|
| `pages/UserManagementPage.jsx` | 474 → ~60 行薄壳,组合 useUserManagementPage + UserListTable + GroupPermissionManager + Tabs |

### 新增测试(1 个)

| 文件 | 覆盖 |
|---|---|
| `features/user/utils/__tests__/userManagementUtils.test.js` | `getAllKeys` 各分支:空树 / 单层 / 多层嵌套 / children 为 undefined |

### 不变(3 个)

| 文件 | 说明 |
|---|---|
| `src/routes/index.jsx` | `lazy(() => import('../features/user/pages/UserManagementPage'))`,不变 |
| `api/userManagementApi.js` / `api/personnelApi.js` / `shared/api/permissionsApi.js` | 被 hook 复用,不变 |
| `pages/__tests__/UserManagementPage.test.jsx` | 全部 `render(<UserManagementPage />)` 整页渲染 + mock API 模块,不引用内部函数 → **零 repoint** |

## 3. 技术方案(架构/接口设计)

### 3.1 模块职责划分

```
pages/UserManagementPage.jsx(薄壳 ~60 行)
  ├── useUserManagementPage()              # HookLayer:users/groups/personnel/loading
  │     ├── state: users / groups / personnel / loading
  │     ├── data:  fetchUsers / fetchGroups / fetchPersonnel
  │     ├── actions: handleGroupsChange / handleAssociationChange
  │     ├── effect: 初始并行加载 Promise.all + logger.error
  │     └── 返回扁平对象 { users, groups, personnel, loading,
  │                        fetchUsers, fetchGroups, fetchPersonnel,
  │                        handleGroupsChange, handleAssociationChange }
  │
  ├── 标题 + Card + Tabs(薄壳内联,原封不动)
  ├── Tab「用户列表」→ <UserListTable users personnel groups currentUserId
  │        onGroupsChange onAssociationChange />
  │     └── 内部 userColumns 列定义(含关联 Select / 用户组 Select / 编辑删除按钮 logger.warn)
  └── Tab「用户组与权限」→ <GroupPermissionManager groups fetchGroups />
        ├── useGroupPermissionManager()    # HookLayer:全部权限矩阵状态/逻辑
        ├── <GroupActionBar groups selectedGroupId loading
        │        onGroupChange onCreate onClickEdit onClickDelete onSavePermissions />
        ├── <PermissionTreePanel permissions checkedKeys expandedKeys
        │        autoExpandParent loading selectedGroupId searchValue
        │        onExpand onCheck onSearch onExpandAll onCollapseAll />
        └── <GroupFormModal visible editingGroup form onOk onCancel />
```

### 3.2 Hook 返回契约(扁平对象)

**`useUserManagementPage`**:

```js
const {
  users, groups, personnel, loading,
  fetchUsers, fetchGroups, fetchPersonnel,
  handleGroupsChange, handleAssociationChange,
} = useUserManagementPage();
```

**`useGroupPermissionManager`**:

```js
const {
  selectedGroupId, permissions, loading, checkedKeys, expandedKeys,
  searchValue, autoExpandParent, isModalVisible, editingGroup, form,
  fetchPermissions, fetchGroupPermissions, handleGroupChange,
  handleSavePermissions, onExpand, onCheck, onSearch,
  allKeys, generatedTreeData,
  showModal, handleCancel, handleOk, handleDelete,
} = useGroupPermissionManager({ groups, fetchGroups });
```

### 3.3 子组件 props 契约

```js
<UserListTable users personnel groups currentUserId
  onGroupsChange onAssociationChange />
  // userColumns 定义移入本组件;currentUser.id 作为 currentUserId prop 传入
<GroupPermissionManager groups fetchGroups />
  <GroupActionBar groups selectedGroupId loading
    onGroupChange onCreate onClickEdit onClickDelete onSavePermissions />
  <PermissionTreePanel permissions checkedKeys expandedKeys autoExpandParent
    loading selectedGroupId searchValue allKeys generatedTreeData
    onExpand onCheck onSearch onExpandAll onCollapseAll />
  <GroupFormModal visible editingGroup form onOk onCancel />
```

### 3.4 逐字搬运原则

- `getAllKeys` 纯函数逐字搬入 `utils/userManagementUtils.js`
- `GroupPermissionManager` 的 state 声明与全部 handler 逐字搬入 `hooks/useGroupPermissionManager.js`,仅新增 return 暴露;**不改语义**:
  - `fetchPermissions` 的 `Object.keys(data).map(...)` 树格式化原样保留
  - `onSearch` 里 `setAutoExpandParent(true)` + 展开 key 去重逻辑原样保留
  - `generatedTreeData` useMemo 的 `loop` 递归 + 高亮 title JSX 原样保留
  - `allKeys = useMemo(() => getAllKeys(permissions), [permissions])` 原样保留
  - `showModal/handleCancel/handleOk` 中 form 操作与 `permissionsApi.createGroup/updateGroup` 原样保留
  - `handleDelete` 的 `Modal.confirm` 配置(okType danger + onOk async)原样保留
  - `handleSavePermissions` 用 `message.warn('请先选择一个用户组')` 原样保留
  - `fetchGroups()` fire-and-forget 调用原样保留
  - 初始 `fetchPermissions()` effect(无依赖数组,触发 set-state-in-effect 告警)原样保留,加 eslint-disable 注释
- `UserManagementPage` 的 state/handlers 逐字搬入 `useUserManagementPage.js`:
  - `fetchUsers` 用 `res.data.results` 兜底空数组原样保留
  - `handleGroupsChange` / `handleAssociationChange` 成功后 `fetchUsers()` 原样保留
  - 初始加载 `Promise.all([fetchUsers(), fetchGroups(), fetchPersonnel()])` + `logger.error` + `setLoading` 时序原样保留(effect 内 setLoading 加 eslint-disable)
  - `userColumns` 逐字搬入 `UserListTable.jsx`,含 `record.permissions?.can_change` 条件按钮 + `logger.warn('Edit user handler not implemented', record.id)` 未实现占位
- 渲染 JSX 按区块逐字搬入子组件,props 对齐 hook 返回契约
- 不做任何逻辑改动(本轮是纯拆分,非行为优化)

### 3.5 propTypes(沿用 R3-D3 补的约定)

R3-D4 拆分**直接携带 propTypes 契约**(R3-D3 检阅沉淀:components/ 下组件必须带 propTypes)。4 个子组件全部定义 propTypes,回调 `isRequired`、`groups`/`users`/`personnel` 用 `arrayOf(shape)`、`permissions` 用 `arrayOf(shape)`。

## 4. 实施步骤

### Task 1: 新增 `utils/userManagementUtils.js`

- [x] 逐字搬运 `getAllKeys` 纯函数
- [x] 模块级导出,无 React 依赖(纯 ES 模块)

### Task 2: 新增 `hooks/useUserManagementPage.js`

- [x] 逐字搬运全部 useState/useEffect(L294-473 主组件部分)
- [x] `getAllPersonnel` 从 personnelApi import,`permissionsApi` 复用
- [x] 返回扁平对象暴露 state + handlers + fetchers
- [x] 初始加载 effect 内 `setLoading(true)` 加 eslint-disable 注释(7.1.1 规则)

### Task 3: 新增 `hooks/useGroupPermissionManager.js`

- [x] 逐字搬运 GroupPermissionManager 全部 useState/useMemo/useEffect/handler(L26-216)
- [x] `getAllKeys` 从 utils import(不再本地定义)
- [x] 初始 `fetchPermissions()` effect 加 eslint-disable 注释
- [x] 返回扁平对象暴露全部 state + handlers
- [x] **扩展名修正**:含高亮 JSX → 改名为 `.jsx`(Vite build 要求,见 §2 文件清单)

### Task 4: 新增 4 个子组件(`components/userManagement/`)

- [x] `UserListTable.jsx` — 用户列表表格(userColumns 移入)
- [x] `GroupActionBar.jsx` — 组操作按钮组
- [x] `PermissionTreePanel.jsx` — 权限树面板
- [x] `GroupFormModal.jsx` — 组表单 Modal
- [x] 全部定义 propTypes(R3-D3 约定)
- [x] 无独立 CSS(沿用页面内联 style,与拆分前一致)
- [x] 补充 `GroupPermissionManager.jsx` 组合容器(原 §2 清单的第 5 个组件,承接 hook + 3 个子组件装配)

### Task 5: 重构 `pages/UserManagementPage.jsx` 为薄壳

- [x] 组合 useUserManagementPage + UserListTable + GroupPermissionManager
- [x] 保留标题 + Card + Tabs 布局
- [x] 确认 `routes/index.jsx` lazy import 路径零改动

### Task 6: 新增 utils 单测

- [x] 新增 `utils/__tests__/userManagementUtils.test.js` 覆盖 `getAllKeys` 各分支(空树/单层/多层嵌套/混合)

### Task 7: 验证

- [x] 既有 `UserManagementPage.test.js`(3 用例)**零改动**通过
- [x] 新增 utils 单测通过
- [x] `npx jest src/features/user` 全量回归绿(3 套件 17 用例)
- [x] `npm run lint` 通过
- [x] `npm run build` 通过(generate-routes + vite build)
- [x] 修复记录:`UserListTable` logger import 路径 `../../../` → `../../../../`(深 4 层);hook 未用参数 `groups` 移除;`react-hooks/immutability` 2 处 effect 前置调用加 eslint-disable

### Task 8: 文档更新 + PR + merge

- [x] round3 plan 标注 R3-D4 完成
- [x] feature 分支 push → PR #255 → CI 监控(8/8 绿)→ code review(4 条 MEDIUM/LOW 已修)→ 用户 merge(f62a0282)→ 分支清理完成(本地+远程)

## 5. 验收标准

| 标准 | 验证方式 |
|---|---|
| `UserManagementPage.jsx` ≤80 行薄壳 | `wc -l` |
| 各新文件 <800 行 / 函数 <50 行 | `wc -l` + 目检 |
| 既有 3 用例零改动通过 + 新增 utils 单测通过 | `npx jest pages/__tests__/UserManagementPage.test.jsx` + `npx jest utils/__tests__/userManagementUtils.test.js` |
| 全量 jest / lint / build 三绿 | `npm test` + `npm run lint` + `npm run build` |
| 4 个子组件全部带 propTypes | `npx eslint components/userManagement/*.jsx` 0 warning |
| `routes/index.jsx` lazy import 不变 | `git diff` |
| 行为逐字一致(树搜索高亮 / 组 CRUD / 权限保存 / 未实现编辑删除占位) | 差分验证 + 既有测试兜底 |

## 6. 风险评估与依赖

| 风险 | 缓解 |
|---|---|
| **高**:Hook 抽离引入闭包 / 依赖数组回归(权限树搜索 + form 操作是核心) | 逐字搬运 + 既有 3 用例覆盖列表渲染 + 编辑/删除按钮;`generatedTreeData`/`allKeys` useMemo 依赖数组原样保留;新增 utils 单测兜底 `getAllKeys` |
| **中**:`userColumns` 移入 UserListTable 后 `currentUser.id` / personnel / groups 引用需经 props 传入(无 TypeScript) | 逐字搬运 + props 契约表 + jest 全量回归兜底;`record.permissions?.can_change` 条件不改变 |
| **中**:`GroupPermissionManager` 拆分后 props 传递链变长(4 个 props 传递子组件) | props 契约表逐字段对齐;既有测试从顶层渲染兜底 |
| **低**:子组件无独立 CSS,依赖页面内联 style | 逐字保留内联 style(拆分前即内联,不引 CSS 文件) |
| **低**:既有测试 mock 了 createUser/updateUser/deleteUser 但页面未用 | 逐字保留(历史遗留 mock,不删不改) |

## 7. 关联

- 上游:`docs/plans/2026-08-14_project-optimization-round3.md`(R3-D4)
- 同源:R3-D1(`docs/plans/2026-08-15_smart-chat-page-split.md`)、R3-D2(`docs/plans/2026-08-15_tool-result-split.md`)、R3-D3(`docs/plans/2026-08-15_agent-task-panel-split.md`),同款 utils/ + hooks/ + 子组件拆分 + 测试零 repoint 流程
- 技术文档:`docs/technical/` 用户模块相关章节(可选更新)
