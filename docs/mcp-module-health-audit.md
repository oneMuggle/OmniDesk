# OmniDesk 模块完整性与可用性审查（需求一）

> 日期：2026-09-27
> 审查基线：`origin/main` `110bf5cb` + PR #494（已于 2026-09-27 合并为 `9870f49`，GitHub 显示 10 项检查通过），代码内容与 worktree `agent/omni-desk-reconcile-20260927`（`2447e7f1`）一致。
> 方法：静态代码审阅 + 引用仓库内验收记录与 PR CI 结论。本机（Windows 主机）没有 Python，前端也没有 `node_modules`，**本轮没有安装依赖、没有运行测试、没有修改业务代码**。

## 0. 先要知道的三件事

1. ~~本地 `main`（`30cd9d46`，2026-06-24）落后 `origin/main` 460 个提交。~~ **已于 2026-09-27 同步到 `9870f49`**；本文所有路径都以最新 `main` 为准。
2. **`docs/mcp-omni-desk-module-ai-architecture-plan.md` 基于旧基线编写，已经过时。** 它列出的 P0/P1（日志跨账号、LLM 配置越权、工具不传用户、缓存不隔离、链式参数未传递、任务状态不一致）已由上游 #477/#478 和 PR #494 修复或重构。以本文和 `docs/mcp-ai-orchestration-plan.md` 为准，旧文件建议删除。
3. **已有的验证证据**（非本轮执行）：
   - PR #494：后端 3193 passed、覆盖率 93.16%（门槛 80%），Ruff、Django check、23 个工具的 scope 检查都通过；GitHub CI 10 项检查全绿后合并。
   - `docs/technical/44-smart-assistant-real-orchestration-acceptance.md`（2026-08-30）：前端 Jest 139 个 suite / 785 个用例通过，但前端覆盖率只有约 42%；全仓 ESLint 63 errors / 244 warnings；Vite 有大于 500 kB 的 chunk 警告；`check_migrations` 显示 6 个待执行迁移。
   - **从未在真实 PostgreSQL + Redis + Celery + 本地 LLM + Win7/Chrome 109 环境做过端到端验收**（验收文档自己也这么写）。

## 1. 总体结论

- **后端基础扎实。** 26 个本地 Django app 都已在 `INSTALLED_APPS` 注册，并挂到 `omni_desk_backend/omni_desk_backend/urls.py`，每个 app 都有测试；`dashboard`、`search_federation` 各只有 2 个用例，最薄弱。
- **"能用"的短板主要在四处：**
  1. **前端页面权限基本不生效**：任何已登录用户都能直接打开 `/control-panel/*` 下的页面（详见 P1-1）。
  2. **几个模块是半成品**：联邦搜索、合规、项目前端、Dashboard。
  3. **前端质量债**：覆盖率低、ESLint 不干净、个别大模块几乎没有测试。
  4. **缺真实环境验收**：迁移、离线包、Celery、LLM 都没在目标环境跑过。
- **AI 能力已覆盖 11 个业务模块的查询，以及备忘录和换班的写操作。** 但有 6 个业务模块没有 AI 接口，跨模块调度入口也还没打通。这部分另见 `docs/mcp-ai-orchestration-plan.md`。

## 2. 模块健康矩阵

评级：🟢 链路完整、有测试；🟡 基本可用，有明确缺口；🔴 未完成或断链。
代码行数（LOC）不含测试和迁移；"测试"一栏：后端为 `def test_` 个数，前端为测试文件个数。

| 模块 | 后端 app（LOC / 测试） | 前端 feature（LOC / 测试文件） | AI 工具 | 评级 | 主要问题 |
| --- | --- | --- | --- | --- | --- |
| 用户 / 认证 / 个人资料 | `users` 1734 / 157 | `auth` 642 / 9，`user` 736 / 3，`profile` 379 / 1 | 无 | 🟡 | 页面权限不生效（P1-1）；Axios 读到非法 token JSON 时的保护未做（核心链路计划 P3 未勾选） |
| 权限 | `permissions` 511 / 43 | `admin` 1170 / 2 | 无 | 🟡 | 后端权限码存在，但前端路由没使用 |
| 人员 | `personnel` 667 / 54 | `personnel` 1514 / 9 | `personnel_query` | 🟢 | — |
| 排班 / 事件 / 换班 / 节假日 / 试验 | `events` 3728 / 196 | `schedule` 3037 / 9 | `schedule_query`、`event_query`、`swap_request_query`、`swap_request_create`、`swap_request_decide` | 🟢 | AI 接入最深的模块；页面文件偏大 |
| 会议室 | `meeting_rooms` 407 / 27 | `meeting-room` 839 / 2 | `meeting_room_query`（只读） | 🟡 | 预约是最高频的办公写操作，但没有 AI 写工具；前端测试少 |
| 备忘录 | `memos` 173 / 18 | `memo` 451 / 2 | 查询、新建、修改、删除 | 🟢 | 写工具分散在 `memo_write_tools.py` 和 `memo_write_tools_v2.py` 两个文件，建议合并 |
| 项目 | `projects` 203 / 21 | `projects` 190 / 1（只有 API 测试） | `project_status` | 🟡 | 前端只有一个列表页，没有详情路由；联邦搜索返回的 `/projects/{id}/` 链接打不开 |
| 合规 | `compliance` 306 / 24 | `compliance` 111 / 2 | `compliance_query` | 🟡 | 前端只有一个 111 行的列表页，整改、跟踪流程没有界面 |
| 公文 / 模板 | `documents` 1686 / 72 | `documents` 221 / 2 | `document_search` | 🟡 | 上传后不会自动进入 RAG 知识库 |
| 文档库（Paperless） | `paperless_proxy` 1271 / 90 | `documents-library` 868 / 3 | 无 | 🟡 | AI 查不到文档库 |
| 交流 | `communication` 201 / 33 | `communication` 476 / 5 | 无 | 🟢 | 过期归档的定时任务已上线；无 AI |
| 新闻 / 公告 | `news` 153 / 13；公告在 `events` | `news` 141 / 1，`announcements` 357 / 2 | `news_search`、`announcement_query` | 🟢 | — |
| 电子书 | `ebooks` 76 / 10 | `ebook` 303 / 1 | 无 | 🟡 | 功能简单，测试薄 |
| 传感器 / 设备 | `sensor_management` 636 / 24 | `sensor` 1815 / **1**，`equipment` 227 / 1 | `sensor_query` | 🟡 | 前端 1800 多行只有 1 个测试文件 |
| 通知 | `notifications` 578 / 68 | `notifications` 336 / 2 | `agent_notify`（只能发，不能查） | 🟢 | 缺少"我有哪些未读通知"这类查询工具 |
| 联培生 | `joint_students` 1266 / 61 | `joint-students` 1397 / 18 | 无 | 🟢 | 2026-08-19 恢复的模块；无 AI |
| 外部集成 / 插件市场 | `external_integration` 974 / 46 | `external-links` 307 / 2，`integration-hub` 371 / 1，`plugin-market` 660 / 2 | `external_link_query` | 🟡 | 已审核的插件还不能作为 AI 工具调用（原计划 P1A-6 未做） |
| 联邦搜索 | `search_federation` **81 / 2** | `search-federation` 124 / 1（**没有挂载到任何页面**） | 无 | 🔴 | 见 P1-2 |
| 仪表盘 | `dashboard` **83 / 2** | `shared/pages/dashboard/*` | 无 | 🟡 | 没有 AI 简报卡片，统计口径不区分用户权限范围 |
| AI 支撑模块 | `smart_assistant` 19850 / 1480，`llm_service`，`ragflow_service` 372 / 43，`dify_apps` 83 / 11，`office_assistant` 153 / 16，`file_processing` 941 / 48 | `smart-assistant` 6342 / 19，`dify-apps`，`office-assistant` 等 | 23 个工具 | 🟡 | 分散在 11 个 AI 入口页面；详见 AI 方案 |
| 系统 / 版本 / 备份 | `core` 2161 / 173，`config` 255 / 15 | `system` 44 / 1 | — | 🟢 | 待执行迁移需按"先备份再迁移"的流程处理 |

## 3. 问题明细

### P1-1 前端页面权限基本不生效（需尽快处理）

- `omni_desk_frontend/src/routes/index.jsx:106-120`：`/control-panel` 外层是不带参数的 `<ProtectedRoute>`；子页面都写成 `pagePath="/control-panel/..."` 这种 URL 形式，**没有一个路由传入 `permissions=`**。
- `omni_desk_frontend/src/features/auth/components/ProtectedRoute.jsx:31-35`：只要 `pagePath` 以 `/` 开头且用户已登录，权限校验失败时仍然**直接放行**。
- 代码注释说"AdminLayout 已在父级校验"，但 `features/admin/components/AdminLayout.jsx:28-35` 只按权限码**过滤菜单显示**，不拦截路由访问。
- **影响**：任何已登录账号（访客模式如果也签发登录态，同样包括在内）都能直接在地址栏输入 URL 进入管理页面。数据是否泄露取决于对应的后端 API，而后端 API 各自鉴权（这点仍需逐页核实）。
- **修复**：`AdminLayout` 里已经有"菜单 → 权限码"的对应关系（例如 `personnel.view_personnel`），把它抽成共享配置，路由和菜单都用它，路由上显式传 `permissions`；删掉按 URL 放行的兜底逻辑；补齐匿名、访客、普通用户、管理员四类用例。这也是 `docs/plans/2026-08-26_core-chain-breakpoint-repair.md` 阶段 P3 里尚未勾选的内容。

### P1-2 联邦搜索是断链模块

- `omni_desk_backend/search_federation/views.py`：文档注释写的是搜索"项目/合同/人员/合规/备忘录"，但 `_search_internal` **只查了 `Project.name`**，而且没有按用户权限范围过滤（智能助手的 `project_status` 工具是按范围过滤的，两边不一致）。
- 返回结果里的 `url` 是 `/projects/{id}/`，前端没有这个路由。
- 前端 `features/search-federation` 没有被任何页面或布局引用，用户根本找不到这个功能。
- **修复**：做成"统一搜索服务"，按模块注册 provider（人员、备忘录、合规、公文、文档库），每个 provider 复用业务模块自己的权限范围查询；在前端顶栏挂载；同一个服务也注册成 AI 工具 `global_search`，供 AI 方案使用。

### P1-3 真实环境验收缺失

- 一直没有在目标环境跑通 6 个待执行迁移、离线包的"校验 → 部署 → 升级 → 回滚"、Celery beat 定时任务（备忘录提醒、每日简报、合规到期、帖子归档）以及本地 LLM 的工具调用。
- `docs/plans/2026-08-26_core-chain-breakpoint-repair.md` 中还有未勾选项："CI Compose 缺 postgres/redis/mysql/ragflow 镜像"、阶段 P3 全部内容、全量验收。
- **修复**：搭一套和生产一致的离线预发环境，按 `CLAUDE.md` 的升级规则执行"备份 → `check_migrations` → `migrate` → 冒烟测试 → 按角色跑 E2E"，保留报告。

### P1-4 Django 4.2 已停止维护

- PR #494 说明生产依赖锁里保留了"Django 4.2 EOL 的 7 项风险忽略"（Django 4.2 LTS 的支持已于 2026 年 4 月结束）。
- **建议**：立项升级到 Django 5.2 LTS（支持 Python 3.10，DRF 3.17 也兼容），先在分支上跑全量测试，按"主版本升级需要人工迁移方案"的规则处理。

### P2 可以顺手修的问题

| # | 问题 | 位置 | 建议 |
| --- | --- | --- | --- |
| P2-1 | `spreadsheet_qa` 的参数定义里有 `sheet_name`，但 `execute()` 从不读取它，永远取第一个 sheet | `omni_desk_backend/smart_assistant/tools/spreadsheet_tool.py:44,56-62` | 接收 `params` 并按名称选 sheet，补测试 |
| P2-2 | 备忘录写工具分散在 v1、v2 两个文件 | `smart_assistant/tools/memo_write_tools*.py` | 合并成一个 `memo_tools.py`，行为不变 |
| P2-3 | 公文上传后不会自动进入 RAG；目前只有知识库页面上传才会调用 `process_document_embedding` | `smart_assistant/views/knowledge_base.py:28` | 公文或文档库入库后异步投递（原计划 P1A-4） |
| P2-4 | 知识库数据集后端已有接口，前端没有管理页 | `smart_assistant/urls.py:21` | 补管理页（原计划 P1A-5） |
| P2-5 | 流式对话没有记录成本 | `smart_assistant/views/chat_stream.py:356`（`estimated_cost=None`） | 在 done 事件里回填 usage 和成本（原计划 P1A-3） |
| P2-6 | 前端测试和 lint 债：覆盖率约 42%，ESLint 63 errors | `omni_desk_frontend` | 采用"只许变好"策略：CI 对改动文件要求 0 error，每轮下调 warning 上限；优先给 sensor、projects、meeting-room 补页面测试 |
| P2-7 | Vite 有大于 500 kB 的 chunk | 构建输出 | 按路由拆包，Win7 机器上首屏收益明显 |
| P2-8 | 文档漂移 | 见下 | 见第 4 节 |

## 4. 文档治理（与"模块可用"同样重要）

- `CLAUDE.md:66` 说"Ant Design 和 MUI 同时使用"，但 `:75` 说 MUI 已移除，前后矛盾；应保留 `:75` 的说法。
- `AGENTS.md` 的 CI/CD 小节里 `ci-test.yml`、`ci-develop.yml` 已经不存在（实际是 `ci.yml`、`deploy-test.yml`、`build-and-push-images.yml`、`release-channel-matrix.yml` 等），入口文件也写成了 `index.js`（实际是 `index.jsx`）。
- `docs/plans/` 里有 19 个文件，其中已完成或已过期的（如 `2026-08-13_memo-write-tools*.md`、`2026-08-04_sa-confirm-framework.md`、round3~5）违反 `CLAUDE.md`"只保留进行中计划"的规定。建议并入 `docs/technical/` 后删除。
- IE11 的要求自相矛盾：`CLAUDE.md` 要求"不要放弃 IE11"，但验收文档写明"React 18 整体不支持 IE11"。需要业务方正式拍板（建议以 Chrome 109 / Edge 109 为底线），然后同步修订 `CLAUDE.md`。

## 5. 优化方案（分阶段）

| 阶段 | 内容 | 退出条件 |
| --- | --- | --- |
| A. 基线（约 1 周） | 本地仓库同步到最新；新建 `docs/technical/45-module-catalog.md`，每个模块一行，记录负责人、前端路由、后端 API、AI 工具、测试和 E2E 链接、评级；修复 P1-1 | 非管理员账号直接访问 `/control-panel/*` 会被拦截；模块目录评审通过 |
| B. 补断链（约 2 周） | P1-2 联邦搜索；合规、项目前端补齐详情页和整改流程；Dashboard 按权限范围统计；P2-1 ~ P2-3 | 表中 🔴 清零；每个修复都有接口测试和页面测试 |
| C. 真实环境验收（约 1~2 周，可与 B 并行） | P1-3 离线预发环境全流程；补全 CI Compose 镜像；按角色跑 E2E | 留存"迁移 → 冒烟 → E2E → 回滚"报告；6 个待执行迁移在预发环境执行过 |
| D. 质量与维护（持续） | P1-4 Django 5.2 升级分支；P2-6/P2-7；第 4 节的文档治理 | 前端覆盖率和 lint 指标逐轮改善；文档无矛盾 |

**每个模块的完成标准**（建议写进 PR 模板）：

1. 至少一条"路由 → API → service → 数据库 → 页面反馈"的端到端测试。
2. 访客、普通用户 A 与 B、模块管理员、系统管理员五类角色的权限用例齐全。
3. 覆盖空数据、校验失败、依赖故障、重复提交。
4. 迁移可以回滚。
5. 在模块目录中登记，并附测试和 CI 链接。

---

## 附：处理进度

| 问题 | 状态 | 位置 |
| --- | --- | --- |
| P1-1 前端页面权限 | 管理中心已收紧；主应用页面待评估 | `docs/plans/2026-09-27_module-health-ai-batch1.md` T1 |
| P1-2 联邦搜索 | 已重做（按 scope 过滤 + 侧边栏入口 + AI 工具 `global_search`） | 同上 T2 / T3 |
| P2-1 `spreadsheet_qa` 的 `sheet_name` | 已修复 | 同上 T4 |
| 文档漂移（第 4 节 CLAUDE.md / AGENTS.md） | 已修正；新增 `docs/technical/45-module-catalog.md` | 同上 T6 |

