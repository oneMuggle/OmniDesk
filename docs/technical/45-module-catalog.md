# 45 模块目录

> 维护规则：新增或下线模块、调整前端入口、新增或下线 AI 工具时，同步更新本表。
> 评级：🟢 可用且测试充分 · 🟡 可用但有缺口 · 🔴 断链或不可用。
> 基线：2026-09-27（`origin/main` `9870f49` + `feat/module-health-ai-batch1`）。来源：`docs/mcp-module-health-audit.md`。

## 1. 业务模块

| 模块 | 后端 app | 前端 feature / 主要入口 | 管理中心权限（`/control-panel`） | AI 工具（intent） | 评级 | 已知缺口 |
| --- | --- | --- | --- | --- | --- | --- |
| 用户 / 认证 | `users` | `auth`、`user`、`profile`：`/login`、`/profile` | `users.view_customuser` | — | 🟡 | 主应用页面仍为"登录即可访问"（见第 3 节） |
| 权限 | `permissions` | `admin`：权限管理 | `admin` | — | 🟢 | — |
| 人员 | `personnel` | `personnel`：`/me/personnel`、`/control-panel/personnel` | `personnel.view_personnel` 等 | `personnel_query` | 🟢 | — |
| 排班 / 事件 / 换班 / 节假日 | `events` | `schedule`：`/schedule`、`/shift-schedule`、`/control-panel/schedule*` | `events.view_schedule` 等 | `schedule_query`、`event_query`、`swap_request_*` | 🟢 | 页面文件偏大 |
| 会议室 | `meeting_rooms` | `meeting-room`：`/meeting-rooms` | `meeting_rooms.view_meetingroom` | `meeting_room_query` | 🟡 | 没有 AI 预约写工具；前端测试少 |
| 备忘录 | `memos` | `memo`：`/memos` | — | `memo_query`、`memo_create`、`memo_update`、`memo_delete` | 🟢 | 写工具分散在 v1、v2 两个文件 |
| 项目 | `projects` | `projects`：`/control-panel/projects` | `admin` | `project_status` | 🟡 | 没有详情页 |
| 合规 | `compliance` | `compliance`：`/control-panel/compliance` | `compliance.view_complianceissue` | `compliance_query` | 🟡 | 整改、跟踪流程没有界面 |
| 公文 / 模板 | `documents` | `documents`：`/control-panel/documents` | `documents.view_documenttemplate` | `document_search` | 🟡 | 上传后不会自动进入 RAG |
| 文档库（Paperless） | `paperless_proxy` | `documents-library`：`/documents-library` | — | — | 🟡 | 联邦搜索使用服务账号，未按用户过滤 |
| 交流 | `communication` | `communication`：`/communication` | — | — | 🟢 | — |
| 新闻 / 公告 | `news`、`events` | `news`、`announcements`：`/announcements`、`/control-panel/announcements/manage` | `events.view_announcement` 等 | `news_search`、`announcement_query` | 🟢 | — |
| 电子书 | `ebooks` | `ebook`：`/control-panel/ebooks` | `documents.view_ebook` | — | 🟡 | 测试薄 |
| 传感器 / 设备 | `sensor_management` | `sensor`、`equipment`：`/control-panel/sensors/*` | `sensor_management.view_sensor` | `sensor_query` | 🟡 | 前端测试少 |
| 通知 | `notifications` | `notifications`：`/notifications` | — | `agent_notify`（仅发送） | 🟢 | 缺少查询未读通知的工具 |
| 联培生 | `joint_students` | `joint-students`：`/joint-students/admin/students` | — | — | 🟢 | — |
| 外部集成 / 插件 | `external_integration` | `external-links`、`integration-hub`、`plugin-market` | `admin` 或 `manager`；各"管理"页仅 `admin` | `external_link_query` | 🟡 | 已审核插件还不能作为 AI 工具调用 |
| 联邦搜索 | `search_federation` | `search-federation`：侧边栏搜索框 | — | `global_search` | 🟢 | 项目、合规、公文页面没有详情路由，结果只能跳到列表页 |
| 仪表盘 | `dashboard` | `shared/pages/dashboard` | — | — | 🟡 | 统计口径未按用户权限范围区分 |
| 系统 / 版本 / 备份 | `core`、`config` | `system`：`/control-panel/system-update` | `admin` | — | 🟢 | — |

## 2. AI 支撑模块

| 模块 | 说明 |
| --- | --- |
| `smart_assistant` | 意图识别、原生工具调用、多智能体编排；工具注册在 `smart_assistant/apps.py`（当前 24 个） |
| `llm_service` | 多端点 LLM 路由、用量与成本统计 |
| `ragflow_service` / `dify_apps` / `office_assistant` / `file_processing` | 知识库、外部 AI 应用、办公助手、文件解析 |

**工具数据范围：** 每个查询工具通过 `build_base_queryset()` + `_scope_self()` 实现 SELF / DEPARTMENT / GLOBAL 三级 scope（`smart_assistant/scope.py`）。`global_search` 不直接查询模型，而是调用各模块原工具的 `scoped_queryset()`，因此它的数据范围与联邦搜索接口 `/api/search/unified/` 完全一致。

## 3. 前端权限模型

- **管理中心**（`/control-panel/*`）：权限在 `omni_desk_frontend/src/features/admin/config/adminRoutePermissions.js` 中集中声明，路由守卫、管理菜单、首页跳转、搜索结果可达性共用这一份。满足以下任意一项即可访问：
  - `admin`（staff 或 superuser）；
  - 对应模型的 Django 权限码；
  - 用户组被授予该页面（`PageRoute.path`）。
- **主应用页面**：只传 `pagePath`，已登录即可访问，数据由后端 API 鉴权。收紧主应用页面权限需要先核对生产环境的页面授权数据。
- 前端权限只负责体验和纵深防御，**数据安全以后端为准**。
