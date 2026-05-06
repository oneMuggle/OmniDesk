## Why

当前前端项目存在样式管理混乱、UI一致性不足、性能优化缺失等问题。47个独立CSS文件中存在硬编码颜色值，未充分利用已定义的CSS变量。缺少全局主题配置导致UI一致性差，且首屏加载未实现代码分割影响用户体验。**现在是改进的最佳时机**，因为项目功能已基本完成，需要提升代码质量和用户体验。

## What Changes

1. **添加Ant Design全局主题配置** - 通过ConfigProvider统一主题色、圆角、间距等
2. **实现路由懒加载** - 使用React.lazy + Suspense实现按需加载
3. **提取公共布局组件** - 抽象PageHeader、PageContent、CardContainer等
4. **统一CSS变量使用** - 迁移硬编码颜色到CSS变量
5. **添加骨架屏加载** - 为数据加载添加loading状态

## Capabilities

### New Capabilities
- `ui-theme`: 全局UI主题配置系统
- `route-lazy-loading`: 路由级别代码分割
- `shared-layout`: 公共页面布局组件库
- `skeleton-loading`: 骨架屏加载状态

### Modified Capabilities
- 无（现有功能行为不变）

## Impact

### 代码结构变更
**新增文件：**
- `src/shared/components/ui/ThemeProvider.jsx` - 主题配置提供者
- `src/shared/components/ui/PageLayout.jsx` - 公共页面布局
- `src/shared/components/ui/CardContainer.jsx` - 卡片容器
- `src/shared/components/ui/SkeletonTable.jsx` - 骨架表格
- `src/shared/components/ui/SkeletonCard.jsx` - 骨架卡片

**修改文件：**
- `src/index.js` - 添加ThemeProvider
- `src/shared/styles/global.css` - 扩展CSS变量
- `src/routes/index.js` - 实现懒加载
- `src/App.js` - 使用公共布局

### 验证要求
- 前端构建通过：`npm run build`
- 前端测试通过：`npm test`
- 前端lint通过：`npm run lint`

## 非目标

- 不迁移到TypeScript（长期改进，非本次范围）
- 不迁移到Vite构建工具（影响较大，后续单独评估）
- 不创建组件文档站点（团队协作工具，后续考虑）
- 不修改后端API（纯前端改进）