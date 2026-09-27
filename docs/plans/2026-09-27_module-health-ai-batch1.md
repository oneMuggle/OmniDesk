# 模块健康与 AI 调度：第一批实施计划

> 日期：2026-09-27
> 分支：`feat/module-health-ai-batch1`（基于 `origin/main` `9870f49`）
> 依据：`docs/mcp-module-health-audit.md`（需求一）、`docs/mcp-ai-orchestration-plan.md`（需求二）
> 状态：已实施，待推送与 PR 评审

## 背景与目标

审查发现两个断点：一是管理中心页面的前端权限不生效；二是联邦搜索模块没有完成。这两处会被后续新增的 AI 入口放大，所以放在第一批处理。

本批只做**不依赖业务决策**的内容，即前端权限、只读能力和缺陷修复。AI 写操作、全局 AI 抽屉、数字员工等需要先确认"写操作范围、模型规格、角色"，留到后续批次。

## 范围

| # | 事项 | 对应 |
| --- | --- | --- |
| T1 | 收紧管理中心（`/control-panel/*`）路由权限；入口首页跳到第一个有权限的页面 | 审查 P1-1 |
| T2 | 联邦搜索重做：按模块注册 provider，数据范围复用智能助手的 scope；前端挂载到侧边栏；结果按站内路由跳转 | 审查 P1-2 |
| T3 | 新增只读 AI 工具 `global_search`，复用 T2 的服务，让 AI 一次调用就能跨模块检索 | AI 方案 S1 |
| T4 | 修复 `spreadsheet_qa` 忽略 `sheet_name` 参数的问题 | 审查 P2-1 |
| T5 | 修复公告表单保存后跳转到不存在的 `/control-panel/announcements` | 本次顺带发现 |
| T6 | 文档：修正 `CLAUDE.md`、`AGENTS.md` 中的矛盾和过期信息；新增技术手册"模块目录"章节 | 审查第 4 节，阶段 A |

**不在本批：**

- 主应用（非管理中心）页面的权限模型：现在只要登录即可访问。改为强制页面权限需要先核对生产环境各用户组的 PageRoute 授权，否则会把普通用户挡在备忘录等日常页面之外，需单独评估。
- Paperless 搜索结果的用户级权限（目前使用服务账号）。
- 能力注册中心、complex_task 打通、写操作工具、数字员工。

## 涉及文件

**后端**

- `omni_desk_backend/search_federation/providers.py`（新增）：provider 定义和聚合服务。
- `omni_desk_backend/search_federation/views.py`：改为调用服务；内部检索在请求线程中执行，只有 Paperless 放进线程池。
- `omni_desk_backend/search_federation/tests/test_providers.py`（新增）、`tests/test_views.py`。
- `omni_desk_backend/smart_assistant/tools/global_search_tool.py`（新增）、`smart_assistant/apps.py`、`agent/prompt_builder.py`（意图提示）、`agent/tool_chain_planner.py`（关键词）。
- `omni_desk_backend/smart_assistant/tools/spreadsheet_tool.py`。
- `omni_desk_backend/smart_assistant/tests/test_global_search_tool.py`（新增）、`tests/test_spreadsheet_tool.py`、`tests/test_check_tool_scopes_cmd.py`（工具数改为动态断言）。

**前端**

- `omni_desk_frontend/src/features/admin/config/adminRoutePermissions.js`（新增）：管理中心路由与权限的单一数据源。
- `omni_desk_frontend/src/features/admin/components/AdminIndexRedirect.jsx`（新增）。
- `omni_desk_frontend/src/features/admin/components/AdminLayout.jsx`：菜单权限改为读取上述配置；修正传感器权限码。
- `omni_desk_frontend/src/features/auth/components/ProtectedRoute.jsx`：传入 `permissions` 时严格校验。
- `omni_desk_frontend/src/routes/index.jsx`：管理中心路由显式传入 `permissions`。
- `omni_desk_frontend/src/features/search-federation/components/UnifiedSearchBar.jsx`、`shared/components/Sidebar.jsx`、`App.css`。
- `omni_desk_frontend/src/features/announcements/components/AnnouncementForm.jsx`。
- 对应的 `__tests__` 或 `*.test.jsx`。

**文档**

- `CLAUDE.md`、`AGENTS.md`、`docs/technical/45-module-catalog.md`（新增）、`docs/technical/README.md`、`docs/technical/07-user-permissions.md`（新增 3.1 路由守卫）。
- `docs/mcp-module-health-audit.md`、`docs/mcp-ai-orchestration-plan.md`：本计划的依据，随本分支入库，审查文档末尾附处理进度。

## 技术方案

### T1 管理中心路由权限

- `ProtectedRoute` 的语义：
  - 传入 `permissions` 时进入**严格模式**：所需权限 = `permissions` ∪ { `pagePath` }，用户满足任意一项即可访问，否则跳转 `/unauthorized`。`pagePath` 保留，是为了兼容用户组已有的页面授权（`GroupPagePermission` → `PageRoute.path`）。
  - 只传 `pagePath` 时（主应用页面）保持现有行为不变。
- `adminRoutePermissions.js` 为每个管理中心路由声明所需权限：`admin`（staff 或 superuser 会自动获得）加上对应模型的 Django 权限码（新增、编辑页面用 add/change 权限码）。仅限管理员的页面（审计、系统更新、AI 应用、各类"管理"页）只要求 `admin`。快捷外链、集成中心、插件市场与侧边栏保持一致，要求 `admin` 或 `manager`。
- `/control-panel` 入口要求上述所有权限的并集，外加 `manager`。首页从固定跳转 `personnel` 改为跳转"第一个有权限的菜单"；一个都没有则跳转 `/unauthorized`。
- `AdminLayout` 菜单的可见性也改为读取同一份配置（含页面授权），保证菜单与路由一致。因此 staff 会看到全部管理菜单（此前缺少权限码时部分菜单被隐藏，但通过 URL 仍可进入）。修正错误的权限码 `sensors.view_sensor`，应为 `sensor_management.view_sensor`。
- 后端 API 的鉴权不变。前端权限只负责体验和纵深防御。

### T2 联邦搜索

- 定义 `SearchProvider(source, label, tool_intent, search_fields, to_result)`，首批 5 个：项目、备忘录、人员、合规问题、公文模板。
- 服务入口 `search_internal(context, query, sources=None, limit=5)`：
  - 对每个 provider，先用 `ToolRegistry.get_tool_for_user` 取对应的智能助手工具，再用 `tool.scoped_queryset(context)` 取已按 SELF / DEPARTMENT / GLOBAL 过滤的 queryset。这样权限范围与 AI 查询**同源**，不另写一套。
  - 取不到工具或 queryset 时**跳过该 provider（失败时关闭）**。
  - 在 `search_fields` 上做 `icontains` 的 OR 查询。
  - 结果只返回最少字段：`source/id/title/subtitle/url`，不含手机号、住址等。
- `url` 只指向前端真实存在的路由：备忘录 → `/memos`；人员 → `/control-panel/personnel/{id}`，本人记录 → `/me/personnel`；项目 → `/control-panel/projects`；合规 → `/control-panel/compliance`；公文 → `/control-panel/documents`。
- 视图用 `ToolContext.from_request` 构建上下文。内部检索同步执行，避免在线程里访问数据库导致连接问题。
- 前端 `UnifiedSearchBar`：
  - 内部结果用 `useNavigate` 站内跳转。
  - Paperless 结果原来的 `url` 是后端 API 地址，无法打开，改为进入站内 `/documents-library`。
  - 无权打开的管理中心页面，结果只展示不跳转（复用 `canAccessAdminPath`）。
  - 内部标题按纯文本渲染，不注入 HTML。
  - 修复降级提示被当作 `AutoComplete` 子元素、替换输入框的问题。
  - 补齐来源标签，支持 `style` 参数。
  - 挂载在侧边栏头部下方（`Sidebar.jsx` 的 `.sidebar-search`），仅在已登录、非访客、侧边栏展开时显示。

### T3 AI 工具 `global_search`

- 只读工具（`risk_level="read"`），参数为 `query`（必填）和 `sources`（可选，来源枚举数组）。
- `execute` 从 `ToolContext`（或旧路径的 dict 上下文）中取服务端用户，调用 T2 的服务；无用户时返回 `found=False`。
- 该工具不直接做 scope 过滤（没有实现 `build_base_queryset`），范围由各 provider 复用原工具的 scope 保证。

### T4 / T5

- `spreadsheet_qa`：
  - `execute` 接收 `params`，按 `sheet_name` 精确匹配 sheet；找不到时返回 `found=False` 并列出可选的 sheet 名；不传时仍取第一个 sheet。
  - 顺带修复：原生工具调用路径传入的是 `ToolContext`（附件在 `attachment` 字段），原实现只认 dict，导致该路径总是报"没有表格数据"。
- `AnnouncementForm` 保存后跳转到 `/control-panel/announcements/manage`。

## 实施步骤

### 阶段 1：后端

- [x] T2 新增 `providers.py` 与单元测试，覆盖三种 scope、跨用户隔离、失败时关闭、字段最小化
- [x] T2 改造 `views.py`，更新视图测试
- [x] T3 新增 `GlobalSearchTool` 并注册，编写测试
- [x] T4 修复 `spreadsheet_qa`，补测试
- [x] 运行后端相关测试和全量测试，执行 `check_tool_scopes`、Ruff

### 阶段 2：前端

- [x] T1 新增权限配置和 `AdminIndexRedirect`，改造 `ProtectedRoute`、`AdminLayout`、`routes/index.jsx`，编写测试
- [x] T2 改造 `UnifiedSearchBar` 并挂载到 `SidebarHeader`，编写测试
- [x] T5 修复公告跳转，更新测试
- [x] 运行前端相关 Jest 测试和改动文件的 ESLint

### 阶段 3：文档与收尾

- [x] T6 修订 `CLAUDE.md`、`AGENTS.md`；新增 `docs/technical/45-module-catalog.md` 并更新 README 索引
- [x] 更新本计划的勾选状态，提交到分支

## 验收标准

1. 没有管理权限的账号访问 `/control-panel/*` 会跳转到 `/unauthorized`；staff 或 superuser 行为不变；拥有对应权限码或页面授权的用户可以访问对应页面。
2. 联邦搜索：SELF 范围的用户只能搜到自己的备忘录、自己负责的项目、本人的人员记录；GLOBAL 范围可以搜到全部；返回结果不含敏感字段；链接都能打开。
3. AI 调用 `global_search` 与联邦搜索接口对同一用户返回相同的数据范围。
4. `spreadsheet_qa` 能按名称读取指定 sheet。
5. 后端全量测试通过，覆盖率不低于 80%；前端相关测试和 lint 通过；`check_tool_scopes` 通过。

## 风险与依赖

| 风险 | 应对 |
| --- | --- |
| 之前靠兜底放行进入管理中心、但没有权限码的账号（例如只在 Manager 组、没有页面授权）会失去访问权 | 这是预期的收紧。在发布说明中写明；需要访问的用户通过"权限管理"授予页面权限或 Django 权限码即可恢复 |
| 生产环境中 `PageRoute.path` 与前端路由模式可能不一致 | 严格模式下，staff 的 `admin` 与模型权限码都能单独放行，页面授权只是额外的放行条件 |
| 联邦搜索结果随用户 scope 变少，用户可能以为"搜不到" | 与智能助手的数据范围一致，属于预期行为；前端空结果提示保持不变 |
| staff 账号现在能看到全部管理菜单 | 与路由权限保持一致；页面数据仍由后端 API 鉴权，缺少模型权限时接口会返回 403 |
| 本机没有 Python 和前端依赖 | 在隔离的 Linux 环境（Python 3.10 + Node 20）中验证；最终以 GitHub CI 为准 |

## 验证记录（2026-09-27，Linux 隔离环境：Python 3.10 + Node 20）

- 后端全量测试：3224 passed、2 skipped、2 xfailed、11 xpassed，覆盖率 93.24%（门槛 80%）。新增代码覆盖率：`providers.py` 99%、`global_search_tool.py` 100%、`spreadsheet_tool.py` 100%。`ruff check`、`ruff format --check` 通过；`check_tool_scopes` 显示 24 个工具全部通过。
- 后端定向：`search_federation` 18 个、`global_search` 与 `spreadsheet_qa` 以及 schema 和 scope 相关共 124 个，全部通过。
- 前端定向 Jest：`admin`、`auth`、`search-federation`、`announcements`、`shared/components`、`routes` 共 27 个测试套件、173 个用例，全部通过。
- 改动文件的 ESLint：没有新增错误。剩余 10 个是 `AdminLayout.test.jsx`、`AnnouncementForm.jsx` 中已有的问题，与本次改动无关。
- 未在本地执行：Vite 构建（容器内存不足）、真实 Redis/PG/Celery 环境验收，以 GitHub CI 和预发环境为准。

