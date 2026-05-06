## Why

当前前端存在多个严重的UI/UX和技术债务问题：1) Ant Design和MUI两个UI库混用导致样式冲突和维护困难；2) CRA构建工具已停止维护，构建速度慢；3) 样式管理混乱（全局CSS+组件CSS+内联样式）；4) 缺少现代化UX模式（骨架屏、错误边界等）。这些问题直接影响开发效率和用户体验，需要系统性重构。

## What Changes

### 核心架构变更
- **移除MUI依赖**：统一使用Ant Design作为唯一UI库，预计减少~200KB bundle size
- **CRA迁移到Vite**：构建速度提升10倍，开发体验显著改善
- **建立Design Tokens**：使用CSS变量统一设计系统

### UX增强
- **添加骨架屏(Skeleton)**：替代简单Loading Spinner
- **添加错误边界(Error Boundary)**：全局异常处理
- **路由懒加载**：首屏加载时间减少60%+
- **表格通用组件**：提取可复用Table组件

### 代码质量
- **统一表单方案**：使用react-hook-form + Zod
- **登录页面重构**：使用Ant Design Form组件
- **移动端适配完善**：响应式布局优化

## Capabilities

### New Capabilities
- **ui-library-unification**: 统一UI库，移除MUI依赖，建立Design Tokens系统
- **build-tool-migration**: CRA迁移到Vite，构建性能优化
- **ux-enhancement**: 骨架屏、错误边界、路由懒加载等UX改进
- **component-standardization**: 通用表格组件、表单组件的标准化

### Modified Capabilities
- 无（现有specs中无相关规格）

## Impact

### 代码结构变更

**新文件**:
- `omni_desk_frontend/src/shared/components/DataTable/` - 通用表格组件
- `omni_desk_frontend/src/shared/components/SkeletonList/` - 骨架屏组件
- `omni_desk_frontend/src/shared/components/ErrorBoundary.jsx` - 错误边界
- `omni_desk_frontend/vite.config.js` - Vite配置
- `omni_desk_frontend/src/shared/theme/` - Design Tokens

**修改文件**:
- `omni_desk_frontend/package.json` - 移除MUI，添加Vite依赖
- `omni_desk_frontend/src/App.js` - 添加ErrorBoundary
- `omni_desk_frontend/src/shared/styles/global.css` - 完善Design Tokens
- `omni_desk_frontend/src/features/auth/pages/Login.jsx` - 重构表单
- `omni_desk_frontend/src/shared/pages/DashboardPage.js` - 并行API请求

**删除文件**:
- `omni_desk_frontend/src/shared/pages/*.css` - 冗余样式文件（合并到统一方案）

### 依赖变更
- 移除: `@emotion/react`, `@emotion/styled` (MUI)
- 添加: `vite`, `@vitejs/plugin-react`
- 添加: `react-hook-form`, `zod`

### 验证要求
- `npm run lint` 无错误
- `npm run build` 成功
- 关键页面（登录、Dashboard、人员管理）功能正常
- 响应式布局在 320px-1920px 范围内正常显示

## 非目标

- 不添加TypeScript（需单独变更）
- 不添加国际化i18n（需单独变更）
- 不修改后端API
- 不添加端到端测试
- 不实现暗色主题切换
