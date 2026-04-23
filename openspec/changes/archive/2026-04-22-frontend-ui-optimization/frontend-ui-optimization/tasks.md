## 1. 依赖清理

- [x] 1.1 统计MUI使用情况：执行 `grep -r "@emotion" omni_desk_frontend/src/` 列出所有使用位置
- [x] 1.2 替换MUI组件为Ant Design等价组件（按钮、输入框、卡片等）- 无使用，直接移除
- [x] 1.3 更新package.json：移除 `@emotion/react`, `@emotion/styled` 依赖
- [x] 1.4 运行 `npm install` 更新lock文件
- [x] 1.5 验证构建：`npm run build` 成功

## 2. Design Tokens系统

- [x] 2.1 创建 `omni_desk_frontend/src/shared/theme/tokens.css` 定义完整CSS变量
- [x] 2.2 迁移global.css中的硬编码颜色到CSS变量
- [x] 2.3 在App.js中引入tokens.css
- [x] 2.4 配置Ant Design主题变量覆盖 (ConfigProvider)

## 3. Vite迁移 (已暂停 - 需要Vite 8配置调整)

- [x] 3.1 安装Vite依赖：`npm install --save-dev vite @vitejs/plugin-react`
- [x] 3.2 创建 vite.config.js (已创建，待Vite 8配置完善)
- [x] 3.3 创建 index.html (Vite入口，已创建)
- [x] 3.4 迁移环境变量配置（REACT_APP_ → VITE_）
- [x] 3.5 更新package.json scripts：添加 dev:vite, build:vite
- [ ] 3.6 验证开发模式：`npm run dev` 正常启动 (Vite 8 Rolldown配置待完成)
- [ ] 3.7 验证构建：`npm run build` 生成静态文件

## 4. 登录页面重构

- [x] 4.1 重写 Login.jsx 使用 Ant Design Form 组件
- [x] 4.2 添加表单验证规则（用户名、密码必填）
- [x] 4.3 添加"记住我"复选框功能
- [x] 4.4 美化登录页面样式（使用Ant Design Card）
- [ ] 4.5 验证登录功能正常 (需启动后端服务)

## 5. Error Boundary

- [x] 5.1 创建 `omni_desk_frontend/src/shared/components/ErrorBoundary.jsx`
- [x] 5.2 在App.js中包裹根组件
- [x] 5.3 测试：错误发生时显示友好提示而非白屏
- [x] 5.4 添加"重试"按钮功能

## 6. 骨架屏组件

- [x] 6.1 创建 `omni_desk_frontend/src/shared/components/SkeletonList.jsx`
- [x] 6.2 创建 `omni_desk_frontend/src/shared/components/SkeletonTable.jsx`
- [x] 6.3 替换DashboardPage中的Spin为Skeleton
- [ ] 6.4 替换人员��理页面的loading状态

## 7. Dashboard优化

- [x] 7.1 使用Promise.all并行请求三个API
- [x] 7.2 添加部分加载失败的处理逻辑 (Promise.allSettled)
- [x] 7.3 添加空数据友好提示 (Empty component)
- [x] 7.4 优化卡片响应式布局

## 8. 路由懒加载

- [x] 8.1 在App.js中使用React.lazy()懒加载非首屏路由
- [x] 8.2 添加Suspense边界和fallback
- [x] 8.3 首屏关键路由(/, /login, /register)不使用懒加载
- [ ] 8.4 验证首屏加载时间改善

## 9. 通用表格组件

- [x] 9.1 创建 `omni_desk_frontend/src/shared/components/DataTable/index.jsx`
- [x] 9.2 实现columns、dataSource、pagination属性
- [x] 9.3 实现loading状态（骨架屏）
- [ ] 9.4 替换PersonnelManagementPage使用DataTable (需要接口适配)
- [ ] 9.5 替换其他页面表格

## 10. 响应式布局优化

- [x] 10.1 完善Sidebar移动端菜单
- [x] 10.2 添加localStorage保存折叠状态
- [ ] 10.3 优化表格在小屏幕的显示
- [ ] 10.4 测试320px-1920px响应式显示

## 11. 最终验证

- [x] 11.1 运行 `npm run lint` 无错误 (警告可接受)
- [x] 11.2 运行 `npm run build` 成功
- [ ] 11.3 手动测试关键页面功能
- [x] 11.4 验证bundle大小减少 (~28 packages removed)