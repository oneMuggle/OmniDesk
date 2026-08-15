# R3-D7: routes/index.jsx 拆分实施计划(lazy wrapper 聚焦版)

> 日期:2026-08-15 | 状态:规划中 | 关联:round3 计划 `docs/plans/2026-08-14_project-optimization-round3.md` R3-D7
> 模式:与 R3-D1~D6 同款 SDD 拆分流程 —— 拆文件 + 逐字搬运 + repoint + 差分验证
> **范围调整声明**:本轮收敛为 **lazy wrapper 拆分**(72 个 lazy import + LazyComponent 组件),**不做**路由表/权限 wrapper 提取。原因见 §3.1 前置发现——`generate-routes.js` 的 Babel AST 解析契约与"路由表拆出独立文件"硬冲突。

## 1. 背景与目标

### 背景

`omni_desk_frontend/src/routes/index.jsx` 当前 **416 行**,职责混杂:

| 职责 | 位置 | 行数 |
|---|---|---|
| 72 个 lazy import 声明(含 3 个带 `.jsx` 后缀路径)+ UnauthorizedPage | L11-95 | ~85 |
| `LazyComponent` 组件(Suspense 包装 + propTypes) | L85-93 | ~9 |
| `createBrowserRouter` 路由表:认证 / 管理中心 / 主应用 3 大布局组 | L97-415 | ~320 |

与 R3-D1~D6 同类,是 round3 计划 R3-D 前端大组件系列的一部分,明确列为 R3-D7(拆为路由表 + lazy wrapper + permission wrapper)。

### 关键前置发现(generate-routes.js 解析契约)

`npm run build` 的 prebuild 钩子会跑 `scripts/generate-routes.js`(Babel AST 解析 `src/routes/index.jsx`)生成 `public/routes.json`(当前 **30 条**受保护路由)。解析逻辑**硬性要求字面量结构**:

| 契约 | 要求 | 拆分影响 |
|---|---|---|
| `createBrowserRouter` 参数 | arguments[0] 必须**内联 ArrayExpression** | ❌ 路由数组不可提取到独立文件(提取后 routes.json 为空,全站权限路由失效) |
| 受保护路由 `element` | 顶级 JSX 元素名必须**字面量 `ProtectedRoute`** | ❌ 不可改名/包装为 helper(`openingElement.name.name === 'ProtectedRoute'` 硬编码) |
| `pageName` / `pagePath` | 必须 **StringLiteral**,不接受常量引用 | ❌ 不可提取 pageName 常量(`getAttributeValue` 只认 StringLiteral) |
| `children` | 必须 **ArrayExpression 字面量** | ❌ 子路由数组不可提取 |
| JSX 中组件名(如 `component={DashboardPage}`) | 仅取**组件名字符串**,不解析 import 来源 | ✅ **lazy import 声明提取完全不受影响** |

**结论**:R3-D7 原定"拆为路由表 + permission wrapper"与 `generate-routes.js` 的 AST 解析**硬冲突**——一旦把 route 数组提出 index.jsx 或把 ProtectedRoute 包装改成函数调用,`public/routes.json` 会丢路由/变空,权限路由全站失效。若未来真要拆路由表,需先改造 `generate-routes.js` 支持跨文件 import 追踪(**本轮不做**,破坏面大、风险高、YAGNI)。

因此本轮**可行且无风险的拆分面**是:
- ✅ 72 个 lazy import 声明 → `routes/lazyImports.js`
- ✅ `LazyComponent` 组件(含 Suspense + propTypes)→ `routes/LazyComponent.jsx`
- ✅ 路由表结构**保持字面量不变**,仅加注释分组与头部整理

### 目标

1. 将 72 个 lazy import + `LazyComponent` 拆出,`routes/index.jsx` 416 → **~330 行**,聚焦路由表结构
2. **对外契约零变化**:`src/index.jsx` 引用 `router` 不变;`generate-routes.js` 解析路径不变 → `public/routes.json` **拆分前后逐字一致**(30 条)
3. 沿用 R3-D1~D6 模式:新文件职责单一 + propTypes 完整(`LazyComponent` 自带)
4. 新增 `lazyImports` 结构单测(72 个导出完整性 + 无重复名)作为回归兜底

## 2. 涉及的文件与模块

### 新增(2 个)

| 文件 | 职责 | 预估行数 |
|---|---|---|
| `src/routes/lazyImports.js` | 72 个 lazy import 统一导出(逐字搬运,保留 `.jsx` 后缀路径)+ `UnauthorizedPage` 归位 | ~90 |
| `src/routes/LazyComponent.jsx` | `LazyComponent` 组件(Suspense + PageSuspenseFallback + propTypes),含 JSX → `.jsx` | ~15 |

### 新增测试(1 个)

| 文件 | 覆盖 |
|---|---|
| `src/routes/__tests__/lazyImports.test.jsx` | 72 个命名导出全部为函数(React.lazy 包装)、导出名无重复、`LazyComponent` 默认导出为组件(可渲染 Suspense) |

### 修改(1 个)

| 文件 | 改动 |
|---|---|
| `src/routes/index.jsx` | 删除 L1-95 lazy import 块 + LazyComponent 定义 → 改为 `import { ... } from './lazyImports'` + `import LazyComponent from './LazyComponent'`;createBrowserRouter 数组**字面量原样保留**,仅头部注释整理 |

### 不变(3 个)

| 文件 | 说明 |
|---|---|
| `src/index.jsx` | `import router from './routes'` 不变,零 repoint |
| `scripts/generate-routes.js` | 解析路径 `src/routes/index.jsx` 不变,AST 契约不变 |
| `src/features/auth/components/ProtectedRoute.jsx` / `GuestRoute` | 路由表内 JSX 引用不变 |

## 3. 技术方案(架构/接口设计)

### 3.1 模块职责划分

```
src/routes/index.jsx(薄壳 ~330 行,聚焦路由表)
  ├── import { DashboardPage, ..., UnauthorizedPage } from './lazyImports'
  ├── import LazyComponent from './LazyComponent'
  ├── import { createBrowserRouter, Navigate } from 'react-router-dom'
  ├── import ProtectedRoute / GuestRoute / App / AdminAppWrapper / PageSuspenseFallback
  └── createBrowserRouter([...])  # 字面量结构原样保留(3 大布局组 + catch-all)

src/routes/lazyImports.js
  └── export const DashboardPage = lazy(() => import('../shared/pages/DashboardPage'))
      ... 72 个,逐字搬运(含 3 个 .jsx 后缀路径 + UnauthorizedPage)
      # 不含 JSX 字面量 → .js 扩展名(引用 memory: frontend-jsx-in-hook-extension)

src/routes/LazyComponent.jsx
  └── 默认导出 LazyComponent(含 JSX → .jsx)+ propTypes(component: elementType.isRequired)
```

### 3.2 接口契约

```js
// lazyImports.js — 72 个命名导出 + 1 个额外命名导出(UnauthorizedPage)
export const DashboardPage = lazy(() => import('../shared/pages/DashboardPage'));
// ... 每个 lazy import 原样(含 3 个带 .jsx 后缀路径)

// LazyComponent.jsx — 默认导出,与现行为完全一致
const LazyComponent = ({ component: Component, ...props }) => (
  <Suspense fallback={<PageSuspenseFallback />}>
    <Component {...props} />
  </Suspense>
);
LazyComponent.propTypes = { component: PropTypes.elementType.isRequired };
```

### 3.3 逐字搬运原则

- 72 个 lazy import **逐字搬运**至 `lazyImports.js`(路径、别名、`// P2-3`/`// 文档库路由` 分组注释一并保留),仅把 `const` 改为 `export const`
- `UnauthorizedPage` 从 L95 归位至 lazyImports(它本应与其他 lazy import 同组)
- `LazyComponent` JSX **逐字搬运**至 `LazyComponent.jsx`,补默认导出
- `createBrowserRouter` 数组 **零改动**(字面量契约,generate-routes 依赖)
- **不做任何逻辑改动**(本轮是纯拆分,非行为优化)

### 3.4 generate-routes 回归验证(本轮核心验收)

拆分前记录 `public/routes.json`(30 条,已备份)。拆分后 `npm run build` 触发 prebuild 重新生成 → **`git diff public/routes.json` 必须为空**。这是"拆分零破坏"的最强证据,强于任何单测。

## 4. 实施步骤

### Task 1: 新增 `routes/lazyImports.js`

- [x] 逐字搬 72 个 lazy import → `export const`
- [x] `UnauthorizedPage` 归位
- [x] 保留 `.jsx` 后缀路径(MeetingRoomBookingPage / SensorCategoryManagementPage / SensorArchiveLocationManagementPage)与分组注释
- [x] 扩展名 `.js`(无 JSX 字面量)

### Task 2: 新增 `routes/LazyComponent.jsx`

- [x] 逐字搬 L85-93 + propTypes
- [x] 扩展名 `.jsx`(含 JSX)

### Task 3: 重构 `routes/index.jsx`

- [x] 删除 L1-95 lazy import 块 + LazyComponent 定义
- [x] 新增 `import LazyComponent from './LazyComponent'` + 批量命名 import from `./lazyImports`
- [x] createBrowserRouter 数组零改动,头部注释整理
- [x] 确认 `src/index.jsx` / `generate-routes.js` 引用零改动
- [x] 实测:`NotificationBell` 为死 import(路由表不引用),index.jsx 不再引用,lazyImports 保留作为注册中心

### Task 4: 新增 `lazyImports` 结构单测

- [x] 72 个命名导出全部为 React.lazy 包装(检查 `$$typeof === Symbol.for('react.lazy')`)
- [x] 导出名集合无重复
- [x] `LazyComponent` 可渲染(@testing-library/react)

### Task 5: 验证

- [x] 新增单测通过(3 passed)
- [x] `npm run build` 后 `git diff public/routes.json` 为空(30 条逐字一致)
- [x] 全量 `npm test` 三绿(575 passed,新增 3,零回归)
- [x] `npm run lint` 通过
- [x] `npm run build` 通过(generate-routes + vite build)

### Task 6: 文档更新 + PR + merge

- [ ] round3 plan 标注 R3-D7 完成(注明范围调整为 lazy wrapper 聚焦版 + 原因)
- [ ] feature 分支 push → PR → CI 监控 → code review → merge → 清理(按 R3-D1~D6 先例)

## 5. 验收标准

| 标准 | 验证方式 |
|---|---|
| `routes/index.jsx` 416→399 行(减 17,净 4%);**真实收益为职责解耦**:懒加载注册中心独立(lazyImports.js)+ `LazyComponent` 独立组件;路由表 320 行受 generate-routes 字面量契约约束拆不动 | `wc -l` + `git diff`(原预估 330 行不现实,见 §6 新增说明) |
| 各新文件 <800 行 / 函数 <50 行 | `wc -l` + 目检 |
| `public/routes.json` 拆分前后逐字一致(30 条) | `npm run build` 后 `git diff public/routes.json` 为空 ✅ 实测通过 |
| `src/index.jsx` / `generate-routes.js` import 不变 | `git diff` |
| 路由表数组字面量零改动 | `git diff`(仅删 import 块 + 加 2 个 import) |
| 新增 lazyImports 单测通过 | `npx jest src/routes`(3 passed) |
| 全量 jest / lint / build 三绿 | `npm test`(575 passed)+ `npm run lint` + `npm run build` ✅ 全部通过 |

## 6. 风险评估与依赖

| 风险 | 缓解 |
|---|---|
| **中**:原 R3-D7 方案(拆路由表 + permission wrapper)与 `generate-routes.js` AST 解析硬冲突 | 前置发现已明确;本轮收敛为 lazy wrapper 拆分;route 数组保持字面量;`git diff public/routes.json` 为空作为硬验证 |
| **低**:lazy import 提取后 import 路径错(尤其 3 个 `.jsx` 后缀路径) | 逐字搬运 + `lazyImports` 单测 + `npm run build` 兜底(Vite 会暴露解析错误) |
| **低**:`lazyImports.js` 的 `.js` 扩展名含 lazy 回调但无 JSX | 无 JSX 字面量 → `.js` 合法(memory: `frontend-jsx-in-hook-extension`);若误含 JSX,Vite build 会报错 |
| **低**:`UnauthorizedPage` 归位到 lazyImports 改变 import 顺序 | 纯声明移动,无副作用;单测覆盖导出完整性 |
| **低**:.js/.jsx 文件 lint 盲区(memory: `frontend-eslint-jsx-blindspot`) | 依赖 code review 检查新文件 propTypes 与死 props;单测兜底 |
| **低**:行数收益低于预估(416→399 而非 330) | 72 个 lazy import 换 71 个命名 import,行数基本抵消;路由表 320 行受 generate-routes 字面量契约约束拆不动;R3-D7 的真实价值是**职责解耦 + lazy 注册中心独立可测**,非行数削减(计划 §5 验收标准已如实修订) |

## 7. 关联

- 上游:`docs/plans/2026-08-14_project-optimization-round3.md`(R3-D7)
- 同源:R3-D1~D6,同款 utils/ + hooks/ + 子组件拆分流程;R3-D7 因 generate-routes 契约收敛为 lazy wrapper 版
- memory:`frontend-jsx-in-hook-extension`(含 JSX 文件必须 .jsx)、`frontend-eslint-jsx-blindspot`(.jsx 不在 lint 覆盖)
- 关键依赖:`scripts/generate-routes.js`(Babel AST 解析契约,§3.1)——任何对路由结构字面量的改动都必须过 `git diff public/routes.json` 验证
