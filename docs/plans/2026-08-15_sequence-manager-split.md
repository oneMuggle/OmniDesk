# R3-D8: SequenceManager.jsx 拆分实施计划

> 日期:2026-08-15 | 状态:规划中 | 关联:round3 计划 `docs/plans/2026-08-14_project-optimization-round3.md` R3-D8
> 模式:与 R3-D1~D7 同款 SDD 拆分流程 —— 拆文件 + 逐字搬运 + repoint + 差分验证
> **范围调整声明**:round3 计划原定"拆为 SequenceList + **SequenceEditor + SequenceRunner**"。经前置调研,代码中**不存在 Runner(运行器)概念**(SequenceManager 是排班设置的 CRUD 界面,无"运行顺序"功能);编辑器实际命名 **SequenceForm**(非 Editor)。本拆分收敛为 **SequenceList + SequenceForm + 薄壳 SequenceManager + `buildSequencePayload` 纯函数**,原因见 §3.1 前置发现。

## 1. 背景与目标

### 背景

`omni_desk_frontend/src/shared/components/SequenceManager.jsx` 当前 **398 行**,职责混杂 3 个组件 + 1 段纯业务逻辑:

| 职责 | 位置 | 行数 |
|---|---|---|
| `SequenceForm`(Modal 弹窗:名称 + 人员搜索/职位筛选 + 左侧人员列表 + 右侧拖拽排序) | L14-185 | ~172 |
| `SequenceList`(Card 列表:新建按钮 + 每条顺序的编辑/删除) | L188-239 | ~52 |
| `SequenceManager`(容器:8 个 state + 数据获取 + CRUD 调用 + onDragEnd + 双列布局) | L241-397 | ~157 |
| `handleSave` 内 payload 构建(create/update × personnel/leader 4 分支) | L306-323 | ~15 |

与 R3-D1~D7 同类,是 round3 计划 R3-D 前端大组件系列的一部分,明确列为 R3-D8(拆为 SequenceList + SequenceForm + 薄壳容器)。

### 关键前置发现(引用与契约)

1. **唯一引用**:`src/features/schedule/pages/ScheduleSettingsPage.jsx` L1 `import SequenceManager from '../../../shared/components/SequenceManager'`。SequenceManager 是懒加载路由组件的**子组件**,非 ProtectedRoute 直接引用 → **不受 generate-routes.js Babel AST 契约约束**,拆子组件对 `public/routes.json` 零影响。
2. **测试 mock 路径**:`ScheduleSettingsPage.test.js` L6-9 `jest.mock('../../shared/components/SequenceManager', ...)`(相对路径)。拆分后 `SequenceManager.jsx` **原地不动** → mock 路径零改动。
3. **既有测试**:`src/shared/components/SequenceManager.test.js` **5 个用例**(render + fetch + 新建/编辑/删除 + 弹窗内添加/移除人员),mock 了 `@hello-pangea/dnd` 三个组件 + 8 个 sequenceApi + 2 个 personnelApi。拆分后默认导出 `SequenceManager` 不变 → 应零回归。
4. **round3 计划命名 vs 代码现实**:计划"SequenceEditor/SequenceRunner"不存在。实际是 `SequenceForm`(编辑器)+ 无 Runner。与 R3-D7 同款"计划目标 vs 代码现实"冲突 → 范围调整声明。
5. **纯业务逻辑**:`handleSave` L306-323 的 payload 构建是唯一可提取的纯函数(无 React/无副作用),适合独立单测。

### 目标

1. 将 172 行 `SequenceForm` + 52 行 `SequenceList` + ~15 行 payload 构建逻辑拆出,`SequenceManager.jsx` 398 → **~160 行**薄壳,聚焦状态管理与 CRUD 编排
2. **对外契约零变化**:默认导出 `SequenceManager` 不变;`ScheduleSettingsPage.jsx` import 零改动;`public/routes.json` 不变
3. 沿用 R3-D1~D7 模式:新文件职责单一 + propTypes 完整(子组件自带)
4. 新增 `buildSequencePayload` 纯函数单测(4 分支)作为回归兜底;既有 5 用例零回归

## 2. 涉及的文件与模块

### 新增(4 个)

| 文件 | 职责 | 预估行数 |
|---|---|---|
| `src/shared/components/sequence/SequenceForm.jsx` | Modal 弹窗表单(逐字搬运 L14-185,含 propTypes) | ~172 |
| `src/shared/components/sequence/SequenceList.jsx` | Card 列表(逐字搬运 L188-239,含 propTypes) | ~52 |
| `src/shared/components/sequence/sequenceUtils.js` | `buildSequencePayload(values, isEditingLeader)` 纯函数(无 JSX → `.js`) | ~25 |
| `src/shared/components/sequence/__tests__/sequenceUtils.test.js` | 4 分支单测(create/update × personnel/leader) | ~60 |

### 修改(1 个)

| 文件 | 改动 |
|---|---|
| `src/shared/components/SequenceManager.jsx` | 删除 `SequenceForm`(L14-185)+ `SequenceList`(L188-239)定义 → 改为 `import SequenceForm/SequenceList from './sequence/...'`;`handleSave` 内 payload 构建(L306-323)替换为 `buildSequencePayload(values, isEditingLeader)` 调用;容器逻辑逐字保留 |

### 不变(3 个)

| 文件 | 说明 |
|---|---|
| `src/features/schedule/pages/ScheduleSettingsPage.jsx` | `import SequenceManager from '../../../shared/components/SequenceManager'` 零改动 |
| `src/features/schedule/pages/ScheduleSettingsPage.test.js` | `jest.mock('../../shared/components/SequenceManager', ...)` 零改动(文件原地不动) |
| `src/shared/components/SequenceManager.test.js` | 既有 5 用例,默认导出不变 → 零回归验证 |

## 3. 技术方案(架构/接口设计)

### 3.1 模块职责划分

```
src/shared/components/SequenceManager.jsx(薄壳 ~160 行,聚焦状态 + CRUD 编排)
  ├── import SequenceForm from './sequence/SequenceForm'   # Modal 弹窗表单
  ├── import SequenceList from './sequence/SequenceList'   # Card 列表
  ├── import { buildSequencePayload } from './sequence/sequenceUtils'
  └── 容器:8 个 state + fetchData + handleAdd/Edit/Delete/Save + onDragEnd + 双列布局

src/shared/components/sequence/SequenceForm.jsx(~172 行)
  └── 默认导出 SequenceForm(Modal + Form + 搜索/筛选 + Droppable/Draggable 排序)+ propTypes

src/shared/components/sequence/SequenceList.jsx(~52 行)
  └── 默认导出 SequenceList(Card + List + 新建/编辑/删除)+ propTypes

src/shared/components/sequence/sequenceUtils.js(~25 行)
  └── export const buildSequencePayload(values, isEditingLeader)  # 无 JSX → .js 扩展名
```

目录 `sequence/` 小写,与 R3-D5 `sidebar/`、R3-D6 `dashboard/` 同款;`__tests__/` 子目录放子组件单测。

### 3.2 接口契约

```js
// sequenceUtils.js — 纯函数,从 handleSave L306-323 提取,行为逐字保留
export const buildSequencePayload = (values, isEditingLeader) => {
  if (!isEditingLeader && values.id) {
    // 人员顺序 UPDATE:合并 sequence + holiday_sequence 去重
    const personnelIds = [...new Set([
      ...(values.sequence || []),
      ...(values.holiday_sequence || [])
    ])];
    return { ...values, personnel: personnelIds };
  }
  if (isEditingLeader) {
    // 领导顺序(create/update 一致):补 personnel 字段
    return { ...values, personnel: values.sequence };
  }
  // 人员顺序 CREATE:rename sequence → personnel
  const { sequence, ...rest } = values;
  return { ...rest, personnel: sequence };
};

// SequenceForm.jsx / SequenceList.jsx — 默认导出,逐字搬运,propTypes 原样保留
```

> 注:原代码 L319-321 对 leader 无论 create/update 都设置 `personnel: values.sequence`(L323 注释 "payload remains values" 与实现不符,属死注释)。纯函数如实保留实现行为,不修复(纯拆分,零行为变化)。

### 3.3 逐字搬运原则

- `SequenceForm` / `SequenceList` 定义 **逐字搬运**(JSX、样式、propTypes、内部 state/useMemo),仅把 `const SequenceForm = ...` 改为默认导出 `export default SequenceForm`
- `handleSave` 的 payload 构建段提取为纯函数(见 §3.2),容器内替换为一行调用;其余 handler 逐字保留
- 不做任何逻辑改动(本轮是纯拆分,非行为优化)

### 3.4 回归验证(本轮核心验收)

1. `npx jest src/shared/components/SequenceManager.test.js` → 既有 5 用例零回归
2. `npx jest src/shared/components/sequence/__tests__/sequenceUtils.test.js` → 新增 4 分支单测通过
3. `npm run build` 后 `git diff public/routes.json` 为空(SequenceManager 非路由组件,验证零影响)
4. `git diff` 确认 `ScheduleSettingsPage.jsx` / `ScheduleSettingsPage.test.js` 零改动

## 4. 实施步骤

### Task 1: 新增 `sequence/SequenceForm.jsx`

- [x] 逐字搬 L14-185(Modal + Form + 搜索/筛选 + Droppable/Draggable)
- [x] `const SequenceForm = ...` → 默认导出 + propTypes 原样
- [x] 扩展名 `.jsx`(含 JSX),import 精简为实际使用项(antd 6 个 + Droppable/Draggable + logger `../../utils/logger`)

### Task 2: 新增 `sequence/SequenceList.jsx`

- [x] 逐字搬 L188-239(Card + List + 新建/编辑/删除)
- [x] 默认导出 + propTypes 原样
- [x] 扩展名 `.jsx`(含 JSX),import 精简为 Card/Button/List/Popconfirm

### Task 3: 新增 `sequence/sequenceUtils.js`

- [x] 从 handleSave L306-323 提取 `buildSequencePayload`(行为逐字保留,含 leader update 的"死注释"实现)
- [x] 扩展名 `.js`(无 JSX)

### Task 4: 重构 `SequenceManager.jsx`

- [x] 删除 `SequenceForm`(L14-185)+ `SequenceList`(L188-239)定义
- [x] 新增 `import SequenceForm from './sequence/SequenceForm'` + `import SequenceList from './sequence/SequenceList'` + `import { buildSequencePayload } from './sequence/sequenceUtils'`
- [x] `handleSave` payload 构建段替换为 `const payload = buildSequencePayload(values, isEditingLeader);`
- [x] 确认默认导出 `SequenceManager` 不变、props 传递不变、`DragDropContext` 包裹结构不变

### Task 5: 新增 `sequence/__tests__/sequenceUtils.test.js`

- [x] 4 分支单测:人员 create(sequence→personnel rename)、人员 update(sequence+holiday_sequence 合并去重)、领导 create、领导 update
- [x] 断言 payload 结构与原逻辑逐字一致(5 用例,含无 holiday_sequence 边界)

### Task 6: 验证

- [x] 既有 5 用例零回归(`npx jest src/shared/components/SequenceManager.test.js`)
- [x] 新增 sequenceUtils 单测通过(5 用例)
- [x] `npm run build` 后 `git diff public/routes.json` 为空
- [x] 全量 `npm test` 三绿(580 passed = 575 既有 + 5 新增,零回归)
- [x] `npm run lint` 通过
- [x] `npm run build` 通过

### Task 7: 文档更新 + PR + merge

- [ ] round3 plan 标注 R3-D8 完成(注明范围调整为 SequenceList + SequenceForm + 薄壳 + buildSequencePayload,原因见 §3.1)
- [ ] feature 分支 push(`refactor/sequence-manager-split`)→ PR → CI 全绿 → code review → 用户 merge → 清理分支

## 5. 验收标准

| 标准 | 验证方式 |
|---|---|
| `SequenceManager.jsx` 398→~160 行(减 ~238,净 ~40%),聚焦容器职责 | `wc -l` + `git diff` |
| `sequence/SequenceForm.jsx` ~172 行 / `sequence/SequenceList.jsx` ~52 行 / `sequence/sequenceUtils.js` ~25 行,均 <800 行/函数 <50 行 | `wc -l` + 目检 |
| 既有 5 个 SequenceManager 用例零回归 | `npx jest src/shared/components/SequenceManager.test.js` |
| 新增 sequenceUtils 单测通过(4 分支) | `npx jest src/shared/components/sequence/__tests__/sequenceUtils.test.js` |
| `ScheduleSettingsPage.jsx` / `ScheduleSettingsPage.test.js` import/mock 零改动 | `git diff` |
| `public/routes.json` 不变 | `npm run build` 后 `git diff public/routes.json` 为空 |
| 全量 jest / lint / build 三绿 | `npm test` + `npm run lint` + `npm run build` |

## 6. 风险评估与依赖

| 风险 | 缓解 |
|---|---|
| **低**:子组件拆分后 import 路径错 | 逐字搬运 + 单测 + `npm run build` 兜底(Vite 暴露解析错误) |
| **低**:payload 提取改变行为 | 提取为纯函数(§3.2 逐字保留实现,含 leader update 死注释行为)+ 4 分支单测 + 既有 5 用例兜底 |
| **低**:round3 计划"SequenceEditor/SequenceRunner"命名与代码现实不符 | 范围调整声明(§顶部)+ 计划如实修订;不强行造 Runner 概念 |
| **低**:.jsx 文件 lint 盲区(memory: `frontend-eslint-jsx-blindspot`) | 依赖 code review 检查新文件 propTypes 与死 props;单测兜底 |
| **低**:`ScheduleSettingsPage.test.js` 的 jest.mock 路径 | `SequenceManager.jsx` 原地不动,mock 相对路径零改动 |
| **不做**:hook 提取(fetchData + 6 state + handler 与容器强耦合) | 提取收益低、风险高,YAGNI;参考 R3-D5 Sidebar(数据工厂不抽 hook)先例 |

## 7. 关联

- 上游:`docs/plans/2026-08-14_project-optimization-round3.md`(R3-D8)
- 同源:R3-D1~D7,同款 utils/ + 子组件拆分流程;R3-D8 因"无 Runner 概念"收敛为 SequenceList + SequenceForm + 薄壳
- memory:`frontend-jsx-in-hook-extension`(含 JSX 文件必须 .jsx)、`frontend-eslint-jsx-blindspot`(.jsx 不在 lint 覆盖)
- 与 R3-D7 对比:SequenceManager 非路由组件,**无 generate-routes.js 契约约束**,拆子组件对 routes.json 零影响
