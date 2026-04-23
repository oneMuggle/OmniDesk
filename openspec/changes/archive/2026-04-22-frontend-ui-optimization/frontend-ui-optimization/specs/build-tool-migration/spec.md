## ADDED Requirements

### Requirement: Vite构建工具
项目必须从CRA迁移到Vite构建工具。

#### Scenario: Vite配置存在
- **WHEN** 检查项目根目录
- **THEN** 存在 `vite.config.js` 文件

#### Scenario: 开发服务器启动
- **WHEN** 运行 `npm run dev`
- **THEN** Vite开发服务器在3000端口启动（可通过配置修改）

#### Scenario: 生产构建
- **WHEN** 运行 `npm run build`
- **THEN** 生成优化后的静态文件到 `build` 目录

#### Scenario: 构建速度验证
- **WHEN** 首次运行 `npm run build`
- **THEN** 构建时间应少于30秒（相比CRA的2-3分钟）

### Requirement: 路由懒加载
项目必须实现路由懒加载以优化首屏加载。

#### Scenario: 路由懒加载配置
- **WHEN** 定义路由时使用非首屏页面
- **THEN** 必须使用 `React.lazy()` 包装组件

#### Scenario: Suspense边界
- **WHEN** 懒加载组件加载中
- **THEN** 显示Suspense fallback内容，不能出现白屏

#### Scenario: 首屏关键路由
- **WHEN** 首页(/)、登录(/login)、注册(/register)路由
- **THEN** 不使用懒加载，确保首屏渲染速度

### Requirement: Bundle大小优化
项目必须优化最终打包的JavaScript bundle大小。

#### Scenario: Bundle分析
- **WHEN** 运行 `npm run build` 后
- **THEN** 生成 `build/bundle-analysis.html`（如配置）

#### Scenario: 代码分割
- **WHEN** 不同功能模块
- **THEN** 自动分割为独立chunk，实现按需加载

### Requirement: 环境变量兼容
Vite必须兼容现有的环境变量配置。

#### Scenario: 环境变量读取
- **WHEN** 代码中使用 `process.env.REACT_APP_`
- **THEN** 必须改为 `import.meta.env.VITE_` 前缀（Vite约定）
- **或者** 配置Vite兼容REACT_APP_前缀
