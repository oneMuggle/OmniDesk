## Context

### 当前状态
- **UI库**: Ant Design v5 + MUI (@emotion) 混用
- **构建工具**: CRA (react-scripts 5.0.1) - 已停止维护
- **样式管理**: 全局CSS + 组件CSS + 内联样式混合使用
- **状态管理**: useState + TanStack Query
- **路由**: React Router v6，无懒加载

### 约束条件
- 必须保持向后兼容，不能破坏现有功能
- 迁移过程需要平滑过渡
- 需要兼容现有16个Django后端应用的数据结构
- CI/CD流水线需要相应调整

### 利益相关者
- 前端开发人员（日常开发体验）
- 最终用户（UI/UX体验）
- 运维人员（构建部署流程）

## Goals / Non-Goals

**Goals:**
1. 移除MUI依赖，统一使用Ant Design，预计减少~200KB bundle size
2. 迁移到Vite构建工具，提升10倍构建速度
3. 建立Design Tokens系统，统一样式管理
4. 添加骨架屏、错误边界等现代化UX模式
5. 实现路由懒加载，首屏加载时间减少60%+

**Non-Goals:**
- 添加TypeScript（单独变更）
- 添加国际化i18n（单独变更）
- 修改后端API
- 添加端到端测试
- 实现暗色主题切换

## Decisions

### Decision 1: 移除MUI，统一使用Ant Design
**选项分析:**
- A) 保留MUI，移除Ant Design - MUI灵活性更高但国内生态弱
- B) 移除MUI，统一使用Ant Design - **选中**，原因：项目主要使用Ant Design，社区生态完善

**理由:** 项目中80%组件使用Ant Design，MUI仅用于少量场景。统一后可减少bundle size、消除样式冲突、降低维护成本。

### Decision 2: CRA迁移到Vite
**选项分析:**
- A) 迁移到Next.js - 功能完整但改动较大，需要重构路由
- B) 迁移到Vite - **选中**，原因：与CRA API兼容，改动最小，构建速度提升显著
- C) 保持CRA - 不选，已停止维护，安全风险增加

**理由:** Vite与现有项目结构兼容，改动可控。开发模式`npm run dev`可直接替代`npm start`。

### Decision 3: 样式管理方案
**选项分析:**
- A) CSS Modules - 需要重写所有组件，工作量大
- B) Styled Components - 与MUI方案类似，保留已有知识
- C) CSS变量 + 全局CSS - **选中**，原因：Ant Design本身支持CSS变量主题，与现有global.css兼容

**理由:** Ant Design 5.x支持CSS变量主题覆盖，无需额外依赖。可平滑将现有硬编码颜色迁移到CSS变量。

### Decision 4: 路由懒加载方案
**选项分析:**
- A) 使用React.lazy() + Suspense - **选中**，React官方方案
- B) 使用react-loadable - 第三方方案，不再维护
- C) 手动代码分割 - 工作量大，收益低

**理由:** React.lazy()是官方方案，与现有React Router v6兼容，无额外依赖。

### Decision 5: 表单验证方案
**选项分析:**
- A) 保持现有Ant Design Form - 简单但难以复用
- B) 使用react-hook-form + Zod - **选中**，原因：社区主流方案，TypeScript友好
- C) 使用Formik - 功能类似但性能略差

**理由:** react-hook-form性能优异，Zod提供运行时验证，与Ant Design可良好集成。

## Risks / Trade-offs

### Risk 1: 样式不兼容
**风险:** 移除MUI后，部分使用MUI样式的组件可能出现样式问题
**缓解:**
- 迁移前先统计MUI使用情况
- 逐模块迁移，每迁移一个模块进行验证
- 保留MUI包作为devDependency以便快速回滚

### Risk 2: Vite配置兼容性
**风险:** 部分CRA特有配置在Vite中不兼容
**缓解:**
- 使用@vitejs/plugin-react插件兼容React Scripts配置
- 逐步迁移webpack特有配置
- 保留原build命令用于对比验证

### Risk 3: 路由懒加载导致白屏
**风险:** Suspense边界处理不当会导致短暂白屏
**缓解:**
- 为每个lazy路由配置Suspense fallback
- 添加全局Loading组件
- 首屏关键路由不使用懒加载

### Risk 4: 破坏现有功能
**风险:** 大规模重构可能引入bug
**缓解:**
- 每次commit保持功能可用
- 迁移完成后进行完整回归测试
- 准备原项目分支用于紧急回滚

### Trade-off 1: 开发体验 vs 稳定性
- 选择分阶段迁移而非一次性重构，降低风险但延长周期
- 每个阶段可独立部署和验证

### Trade-off 2: 包体积 vs 功能完整
- 移除MUI后某些高级组件需要手动实现
- 评估后认为Ant Design可覆盖95%需求，剩余5%可接受手写

## Migration Plan

### Phase 1: 依赖清理（第1周）
1. 统计MUI使用情况：`grep -r "@emotion" src/`
2. 替换MUI组件为Ant Design等价组件
3. 移除MUI相关依赖
4. 验证构建和运行正常

### Phase 2: Vite迁移（第2周）
1. 安装Vite依赖
2. 创建vite.config.js
3. 调整package.json scripts
4. 迁移public目录资源
5. 验证开发模式和构建

### Phase 3: 样式系统（第3周）
1. 完善Design Tokens（颜色、间距、字体）
2. 迁移global.css到CSS变量
3. 统一组件样式方案
4. 添加全局Error Boundary

### Phase 4: UX增强（第4周）
1. 实现路由懒加载
2. 添加骨架屏组件
3. 重构登录页面
4. 提取通用Table组件
5. 完善响应式布局

### Rollback Plan
- 每个Phase完成后打tag
- 出现问题可回退到上一个tag
- 紧急情况可切回原CRA分支

## Open Questions

1. **Q: 是否需要保留MUI作为可选依赖？**
   - 建议：不需要，完全移除可减少维护负担

2. **Q: 路由懒加载是否需要配合Code Splitting？**
   - 建议：Vite自动支持，不需要额外配置

3. **Q: 如何处理原有的组件级CSS文件？**
   - 建议：合并到global.css或转为CSS Modules视文件大小而定
