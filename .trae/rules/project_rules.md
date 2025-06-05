# Trae 项目开发规范

## 一、目录结构规范
### 1.1 整体结构
采用前后端分离架构，根目录包含以下核心目录：
- `DRFForVue/`: Django REST Framework 后端代码
  - `events/`: 试验相关业务模块（模型、视图、序列化器、测试）
  - `users/`: 用户管理模块
  - `documents/`: 文档管理模块
- `calendar_with_react/`: React 前端代码
  - `src/api/`: 统一API请求模块（按功能拆分如`trialApi.js`、`timeSlotApi.js`）
  - `src/components/`: 通用组件（如`EventModal`）
  - `src/pages/`: 页面级组件
- `.trae/rules/`: Trae 专用规则（本文件存放于此）

### 1.2 测试文件
测试文件与源文件同目录（如`DRFForVue/events/tests.py`），测试类命名为`{ModelName}Test`（如`TrialModelTest`），方法名以`test_`开头（如`test_time_period_calculation`）。

## 二、代码风格规范
### 2.1 命名规则
- **前端（React）**：组件名使用帕斯卡命名法（如`TrialDetails.jsx`），变量/函数使用驼峰命名法（如`fetchTrialEvents`）。
- **后端（Django）**：模型字段、视图方法使用蛇形命名法（如`start_time`、`perform_create`），类名使用帕斯卡命名法（如`TrialSerializer`）。

### 2.2 注释规范
- 前端组件/API模块顶部添加JSDoc注释，说明功能（如`/** 试验相关API */`）。
- 后端模型/序列化器添加`verbose_name`元信息（如`title = models.CharField(max_length=200, verbose_name="试验名称")`）。

## 三、API管理规范
### 3.1 接口定义
- 前端统一使用`apiClient`发起请求（如`calendar_with_react/src/api/trialApi.js`），接口路径与后端DRF视图集保持一致（如`/events/trials/`对应`TrialViewSet`）。
- 后端视图集明确`filterset_fields`和`ordering_fields`（如`TrialViewSet`的`filterset_fields`包含`status`、`start_date`）。

### 3.2 错误处理
- 前端使用统一的`handleError`函数处理API错误（如`calendar_with_react/src/api/responseHandler.js`），包含用户友好提示和错误详情记录。
- 后端通过`serializers.ValidationError`返回业务错误（如`TimeSlotSerializer`的时间验证）。

## 四、日期处理规则
- 前后端统一使用ISO 8601时间格式（如`2023-01-01T09:00:00Z`）。
- 前端使用`date-fns`库进行时间计算（如`calendar_with_react/src/api/trialApi.js`中`Math.min(...startDates)`），后端使用`django.utils.timezone`处理时区（如`DRFForVue/events/tests.py`的`timezone.now()`）。

## 五、权限控制规范
- 后端视图集通过`permission_classes`控制访问（如`TrialViewSet`可添加`IsAuthenticated`）。
- 前端根据用户角色动态显示按钮（如`EventModal`中游客模式隐藏编辑按钮），角色状态通过`context`或`localStorage`管理。

## 六、文档维护规则
- 组件文档：在组件文件顶部添加注释，说明`props`类型（如`TrialDetails.jsx`的`selectedTrial`参数）。
- API文档：后端使用DRF自带的`SchemaGenerator`生成OpenAPI文档，前端在`api`模块添加接口说明（如`getTrialById`的`[MCP_DEBUG]`日志）。
- 测试覆盖率：关键业务逻辑（如时间范围计算、多对多关系）测试覆盖率不低于80%（参考`TrialModelTest`的4个测试用例）。

## 七、协作规范
- **Git分支**：使用`feature/{需求名}`（功能开发）、`bugfix/{问题描述}`（缺陷修复）、`release/v1.0`（版本发布）分支。
- **提交信息**：遵循Conventional Commits规范（如`feat(events): 添加试验时间范围自动计算`、`fix(trial): 修复时间段数量验证逻辑`）。
- **合并请求**：需通过CI测试（如`pytest`后端测试、`jest`前端测试）和至少1名成员代码审查后合并。