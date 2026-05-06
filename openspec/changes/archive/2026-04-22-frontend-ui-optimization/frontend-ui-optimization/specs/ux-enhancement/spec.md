## ADDED Requirements

### Requirement: 骨架屏组件
项目必须实现骨架屏(Skeleton)组件用于内容加载状态。

#### Scenario: 列表加载状态
- **WHEN** 列表数据加载中
- **THEN** 显示Skeleton组件占位，不能显示LoadingOutlined Spinner

#### Scenario: 卡片加载状态
- **WHEN** 卡片内容加载中
- **THEN** 显示卡片形状的Skeleton，不能显示空白

#### Scenario: 表格加载状态
- **WHEN** 表格数据加载中
- **THEN** 显示表格行Skeleton占位

### Requirement: 错误边界(Error Boundary)
项目必须实现全局错误边界组件用于捕获渲染错误。

#### Scenario: 组件渲染错误
- **WHEN** 子组件发生JavaScript错误
- **THEN** 错误边界捕获错误，显示错误提示，不影响其他正常组件

#### Scenario: 错误恢复
- **WHEN** 错误边界捕获错误后
- **THEN** 提供"重试"按钮，点击后可重新渲染子组件

#### Scenario: 错误日志
- **WHEN** 发生错误时
- **THEN** 将错误信息记录到控制台，便于调试

### Requirement: Dashboard页面优化
Dashboard页面必须优化数据加载体验。

#### Scenario: 并行API请求
- **WHEN** Dashboard加载本周数据
- **THEN** 使用Promise.all并行请求多个API，不能串行请求

#### Scenario: 部分数据加载失败
- **WHEN** 某一API请求失败
- **THEN** 其他API数据正常显示，失败部分显示错误提示

#### Scenario: 空数据展示
- **WHEN** API返回空数组
- **THEN** 显示"暂无数据"的友好提示，不能显示空白

### Requirement: 响应式布局
项目必须完善响应式布局以支持多种设备。

#### Scenario: 移动端菜单
- **WHEN** 屏幕宽度小于768px
- **THEN** 侧边栏隐藏，显示汉堡菜单按钮

#### Scenario: 表格响应式
- **WHEN** 表格在小屏幕设备显示
- **THEN** 水平滚动或使用Ant Design Table的responsive属性

#### Scenario: 卡片网格响应式
- **WHEN** Dashboard卡片在不同屏幕尺寸
- **THEN** 使用Ant Design Col的xs/sm/md/lg响应式断点
