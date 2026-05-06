## Context

### 当前状态
- 前端使用 React + CRA + Ant Design
- 47个独立CSS文件，CSS变量已定义但未充分利用
- 无路由级别代码分割，所有页面打包在一起
- 页面组件直接在routes/index.js中静态导入

### 约束
- 保持与现有后端API兼容
- 不修改Django后端代码
- 使用现有技术栈（React、TanStack Query、Ant Design）
- 保持向后兼容，不破坏现有功能

### 利益相关者
- 前端开发人员（直接受益）
- 最终用户（获得更好的用户体验）

## Goals / Non-Goals

**Goals:**
1. 统一全局UI主题，提升视觉一致性
2. 实现路由懒加载，优化首屏加载性能
3. 提取公共布局组件，减少代码重复
4. 添加骨架屏loading状态，改善感知性能

**Non-Goals:**
- 不迁移到TypeScript
- 不迁移到Vite构建工具
- 不修改后端API
- 不添加新的外部依赖

## Decisions

### Decision 1: 主题配置方案
**选择:** 使用Ant Design ConfigProvider + 自定义CSS变量

**理由:** 
- Ant Design已内置ConfigProvider，无需新依赖
- CSS变量可在global.css中集中管理，与现有样式体系兼容
- 改动最小化，渐进式改进

**备选方案:**
- emotion/styled: 已安装但未使用，引入新范式学习成本
- CSS Modules: 需要重构现有CSS文件，改动过大

### Decision 2: 路由懒加载实现
**选择:** React.lazy + Suspense

**理由:**
- React官方推荐方案，与现有Router v6兼容
- CRA内置支持，无需额外配置
- 可配合现有routes/index.js结构

**备选方案:**
- 按需加载库: 需要引入新依赖
- 手动代码分割: 需要自定义构建配置

### Decision 3: 公共布局组件
**选择:** 在src/shared/components/ui/下创建可复用组件

**理由:**
- 遵循现有项目结构（src/shared/components/）
- 渐进式替换，避免大规模重构
- 与现有Ant Design组件无缝集成

## Risks / Trade-offs

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 懒加载导致首屏闪烁 | 用户体验 | 添加Suspense fallback |
| CSS变量迁移遗漏 | UI不一致 | 分模块迁移，逐个验证 |
| 组件Breaking Change | 功能损坏 | 保持原有props兼容 |

## Migration Plan

### Phase 1: 主题配置
1. 扩展global.css的CSS变量
2. 创建ThemeProvider组件
3. 在index.js中集成

### Phase 2: 路由懒加载
1. 改造routes/index.js使用React.lazy
2. 添加Suspense包装
3. 测试各路由正常工作

### Phase 3: 公共组件
1. 创建PageLayout等组件
2. 在关键页面中使用
3. 验证显示一致性

### 回滚策略
- 使用git checkout可快速回滚单个文件
- 保持原有routes/index.js备份

## Open Questions

1. 是否需要为懒加载路由添加预加载（prefetch）？
2. 骨架屏样式是否需要适配深色模式？
3. 公共组件是否需要支持RTL语言？