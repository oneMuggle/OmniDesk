## ADDED Requirements

### Requirement: UI库统一使用Ant Design
项目必须仅使用Ant Design作为UI框架，禁止使用MUI(@emotion/react, @emotion/styled)。

#### Scenario: MUI依赖已移除
- **WHEN** 运行 `npm list @emotion/react @emotion/styled`
- **THEN** 依赖不存在或未安装

#### Scenario: 组件使用Ant Design
- **WHEN** 需要使用按钮、输入框、表格等基础组件
- **THEN** 必须使用Ant Design组件库，不能使用MUI等价组件

### Requirement: Design Tokens系统
项目必须建立基于CSS变量的Design Tokens系统。

#### Scenario: 主色调定义
- **WHEN** 需要使用主色调
- **THEN** 必须使用CSS变量 `--primary-color`，值为 `#1890ff`

#### Scenario: 间距系统定义
- **WHEN** 需要使用间距
- **THEN** 必须使用CSS变量 `--spacing-xs` (4px), `--spacing-sm` (8px), `--spacing-md` (16px), `--spacing-lg` (24px), `--spacing-xl` (32px)

#### Scenario: 边框圆角统一
- **WHEN** 需要使用圆角
- **THEN** 必须使用CSS变量 `--border-radius-base`

### Requirement: 样式冲突消除
项目必须消除Ant Design与MUI之间的样式冲突。

#### Scenario: 无样式冲突
- **WHEN** 同时使用多个Ant Design组件
- **THEN** 组件样式正确显示，无异常覆盖

#### Scenario: 全局样式隔离
- **WHEN** 定义全局样式时
- **THEN** 必须使用CSS类名隔离，避免直接使用HTML标签选择器

### Requirement: 登录页面现代化
登录页面必须使用Ant Design Form组件重写。

#### Scenario: 登录表单渲染
- **WHEN** 访问登录页面
- **THEN** 使用 `<Form>` 组件渲染，包含用户名、密码、记住我复选框

#### Scenario: 表单验证
- **WHEN** 用户提交空用户名或密码
- **THEN** 显示验证错误信息，不提交表单

#### Scenario: 登录按钮状态
- **WHEN** 登录请求进行中
- **THEN** 按钮显示loading状态，不可点击
