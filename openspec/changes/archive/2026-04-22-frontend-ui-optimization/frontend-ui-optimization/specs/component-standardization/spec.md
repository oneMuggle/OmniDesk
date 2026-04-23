## ADDED Requirements

### Requirement: 通用表格组件
项目必须封装可复用的表格(DataTable)组件。

#### Scenario: 基础表格使用
- **WHEN** 页面需要展示表格数据
- **THEN** 使用DataTable组件，传入columns和dataSource属性

#### Scenario: 分页配置
- **WHEN** 数据需要分页
- **THEN** DataTable组件必须支持pagination配置

#### Scenario: 行操作
- **WHEN** 需要对行进行编辑、删除等操作
- **THEN** DataTable组件必须支持action列配置

#### Scenario: 加载状态
- **WHEN** 表格数据请求中
- **THEN** DataTable显示骨架屏或loading状态

### Requirement: 表单验证标准化
项目必须使用统一的表单验证方案。

#### Scenario: 表单组件选择
- **WHEN** 创建新表单
- **THEN** 优先使用react-hook-form + Zod方案

#### Scenario: 验证规则定义
- **WHEN** 定义表单验证规则
- **THEN** 使用Zod schema定义，示例：z.string().min(1, "不能为空")

#### Scenario: Ant Design集成
- **WHEN** react-hook-form与Ant Design结合
- **THEN** 使用 Controller 组件包装Ant Design Input/Select等

### Requirement: 通用Modal组件
项目必须封装可复用的Modal确认对话框。

#### Scenario: 删除确认
- **WHEN** 用户点击删除按钮
- **THEN** 显示确认对话框，包含标题、描述、确认/取消按钮

#### Scenario: 异步操作确认
- **WHEN** 执行危险操作前需要确认
- **THEN** 显示操作确认对话框，用户确认后才执行

### Requirement: 消息提示统一
项目必须统一使用Ant Design message组件进行提示。

#### Scenario: 成功提示
- **WHEN** 操作成功时
- **THEN** 使用message.success()显示绿色成功提示

#### Scenario: 错误提示
- **WHEN** 操作失败时
- **THEN** 使用message.error()显示红色错误提示

#### Scenario: 加载提示
- **WHEN** 异步操作进行中
- **THEN** 使用message.loading()显示加载提示

### Requirement: 侧边栏状态持久化
侧边栏的折叠状态必须持久化保存。

#### Scenario: 折叠状态保存
- **WHEN** 用户点击侧边栏折叠按钮
- **THEN** 折叠状态保存到localStorage

#### Scenario: 刷新后状态恢复
- **WHEN** 页面刷新
- **THEN** 侧边栏恢复上次折叠状态
