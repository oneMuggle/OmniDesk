# OmniDesk 项目优化方案(第五轮 · 调研产物)

> 日期:2026-08-20 | 状态:**调研完成 / 待启动** (本轮只调研、不实施)
> 起源:三路并行静态扫描(代码质量与重复 / 性能与可观测 / 安全与依赖)+ 主对话收敛去重
> 关联: round1(`PR #127`) / round2(`docs/plans/2026-07-31_project-optimization-round2.md`,已清) / round3(`2026-08-14`) / round4(`2026-08-16`) / pre-deploy-hardening(`2026-08-17`)
> 说明: 本轮**只产出可执行优化清单**;条目按 ROI 排序,每条含文件位置 / 问题描述 / 推荐改法 / 验证方式 / 工作量估算,便于后续拆分 PR 推进。

## 1. 背景

round1~round4 + pre-deploy-hardening 已完成:
- round1: 上传文件名净化 + 6 处 N+1 + 6 处索引 + TanStack Query 迁移 + 死代码清理
- round2: 大文件拆分、认证 GET 改造、mypy 基线
- round3: 后端 A1~A9 + serializer 白名单 + 前端 D1~D8 + E4
- round4: 14 项后端稳定性与安全(7 PR 合并)+ 7 项前端架构(B5~B7 重复收敛)+ 8 项 CI/依赖/可访问性
- pre-deploy-hardening: 可观测性 + smoke 覆盖 + 部署卫生 + 9 个 0% app logger 基线
- P0-1~5: 安全数据安全批处理 + 备忘录归档 + 前端接线与死链修复

2026-08-20 对全仓做三路并行只读扫描,合计 20 条原始条目,本轮收敛为 **20 条可执行优化项**,按 ROI(高/中/低)分三档,与 Round 4 表格风格一致。

**与 R4 的差异**:
- **新增关注点**:
  - 安全:`.env` 真实凭证驻留磁盘、游客账号无 expiry、敏感写接口缺 throttle、AuditLogEntry 仅 1 处使用
  - 性能:UserPermissionView 菜单树无缓存、MeetingRoomBooking 嵌套 N+1、dashboard_stats 5 条 SQL、LLMRouter 每次重建、AgentLog 缺索引
  - 依赖:前端缺 lockfile drift gate、depcheck 未跑
- **继续推进的**:smart-assistant 工具层抽象(orchestrator / chat_sync / chat_stream / _extract_keywords),前端 DataTable 推广
- **R4 未碰的层面**:LLM 配置层缓存、权限菜单缓存、Redis/Celery 健康检查

## 2. 候选清单(按 ROI 排序)

### R5-A. 安全与限流

| # | 文件 | 问题 | 修复方向 | 严重度 |
|---|---|---|---|---|
| R5-A1 | `deployment/docker/.env:6,11` | 文件含形似真实值的 `POSTGRES_PASSWORD` 与 `SECRET_KEY`,`.gitignore` 兜底但 `git add -f` 可绕过;docker-compose 默认 cwd 加载注入凭据 | 移到仓库外 `~/.omni_desk/dev.env`,新增 README 指引;`.gitignore` 显式规则 `**/deployment/docker/.env` 双重保护 | **HIGH** |
| R5-A2 | `users/auth_serializers.py:110-124` + `users/tasks.py:13-22` | 游客账号无 `expires_at`,`cleanup_expired_guest_users` 仅看 `last_login <= now-7d`,活跃游客永不删除 + 永久占 `CustomUser` 行 + `groups.add(guest_group)` | `CustomUser` 加 `guest_until DateTimeField(null=True)`,`GuestLoginSerializer.create` 写 `now()+24h`;清理任务改为 `guest_until__lt=now()`;`/users/me/` 拦截已过期 guest | **HIGH** |
| R5-A3 | `file_processing/views.py:32-44` + `smart_assistant/middleware/rate_limit.py:57` | `RateLimitMiddleware` 仅匹配 `/api/smart-assistant/chat/`;`FileProcessingViewSet.upload` 仅 `IsAuthenticated`,无 throttle;写接口 0 防护 | `settings/base.py` `DEFAULT_THROTTLE_RATES` 加 `upload` / `guest_create` scope;upload + `GuestLoginView` 配 `ScopedRateThrottle`;中间件扩展到 `/api/smart-assistant/tools/` 与 `/api/file-processing/` | **HIGH** |
| R5-A4 | `users/models.py:67` + `permissions/views.py:25,33,50,102` | `AuditLogEntry.objects.create` 全仓仅 1 处 hit(`link_user_personnel.py:214`);权限 / 组 / 数据导出 / 人员关联解绑等敏感操作无统一审计留痕 | `AuditLogEntry` 加 `category` 字段(`permission_change`/`group_change`/`export`/`delete`);`permissions/views.py` 写操作接入 signal 或显式 `AuditLogEntry.objects.create()`;参照 `smart_assistant/hooks/builtin/audit_log.py` | MEDIUM |

**涉及模块:** users / permissions / file_processing / smart_assistant / deployment
**风险:** 中(A1 涉及凭据管理流程,需 README 配套;A3 中间件扩展需回归)
**预估:** A1 0.25 天 / A2 1 天 / A3 1 天 / A4 1 天

### R5-B. 性能与可观测性

| # | 文件 | 问题 | 修复方向 | 严重度 |
|---|---|---|---|---|
| R5-B1 | `permissions/views.py:80-94` | `GET /api/permissions/users/me/permissions/` 每次执行 `PageRoute.objects.all()` + `user.groups` + `GroupPagePermission` + `PageRoute.filter(id__in=...)` 共 4 条 SQL;前端每次路由切换触发(AuthContext / PermissionGate),是最高频读接口 | `cache.get_or_set('user_menu_<user_id>', ..., timeout=300)` 包装整个 view;`GroupPagePermission` / `PageRoute` 保存时通过 signals 失效对应 user 的缓存(参考已有 `user_permissions_<id>` 模式) | **HIGH** |
| R5-B2 | `meeting_rooms/views.py:47-49` | `MeetingRoomBookingViewSet` 已 `select_related('user','meeting_room')`,但嵌套 `UserDetailSerializer` 访问 `user.phone_numbers`(反向 FK)+ `assigned_by`(FK)+ `personnel`(FK),每条 booking 多 3 条 N+1 | queryset 改为 `.select_related('user','meeting_room','user__assigned_by','user__personnel').prefetch_related('user__phone_numbers')`;`UserDetailSerializer` 加 context-aware 缓存避免重复读 | **HIGH** |
| R5-B3 | `dashboard/views.py:11-70` | `GET /api/dashboard/stats/` 5 领域(Schedule/Announcement/Memo/Project/Notification)聚合;`recent_projects` 用 `.values('manager__username')` 隐式 JOIN,`active_projects` 单独 count;Memo/Project 排序未走索引;前端 `useDashboardData` 无 `refetchInterval` | 5 个 query 并行或合并为单次 round-trip(values + Subquery 合并 count);`Project.updated_at` 加 `db_index` 或 `Meta.indexes`;前端 `useDashboardData` 加 `refetchInterval: 60000` | **HIGH** |
| R5-B4 | `llm_service/router.py:25-46` | `LLMRouter.__init__` 每次构造都查 `LlmAppConfig.objects.select_related('endpoint')`,所有 LLM 调用路径(智能助手/办公助手/RAGFlow)都构造 router,每次 chat/embedding 多 1 条 SQL | `LLMRouter` 加 `classmethod @lru_cache(maxsize=64)` 或 `cache.get_or_set('llm_router_<app_name>', ..., timeout=60)`;`LlmAppConfig` / `LlmEndpoint` `post_save` 信号触发 `cache.delete_pattern('llm_router_*')` | **HIGH** |
| R5-B5 | `smart_assistant/models.py:218,400` | `AgentLog` 与 `AgentEvent` 均按 `-created_at` 排序,被 `stats.py:24/58/74` 与 `logs.py:48/50` 反复 `created_at__gte/__lte` 过滤;`Meta` 仅 `ordering` 无 `db_index`,几万行后全表扫描 + filesort;timeline 接口(`views/tasks.py:285-305`)同样受影响 | `AgentLog.Meta` 加 `indexes = [Index(fields=['-created_at']), Index(fields=['intent'])]`;`AgentEvent.Meta` 加 `Index(fields=['task','-sequence'])`;配合 `select_related('subtask')` 解决 timeline 的 subtask FK N+1 | MEDIUM |
| R5-B6 | `omni_desk_backend/health.py:15-36` | `/health/` 仅 `connections['default'].ensure_connection()`,Redis 挂不返 503,Celery worker 全挂也不发现;`core/api.py:230-300` 的 `/ready/` 才完整覆盖,但 K8s livenessProbe 通常只配 `/health/` | `/health/` 内增加 `redis.Redis.from_url(settings.CELERY_BROKER_URL).ping()`(timeout=0.5s)和 `app.control.ping(timeout=0.5s)` 探针,任一失败即返 503;或 `/health/` 与 `/ready/` 共用 `_check_dependencies` 助手 | MEDIUM |
| R5-B7 | `permissions/views.py:19`, `compliance/tasks.py:11`, `paperless_proxy/tasks.py:19`, `file_processing/tasks.py:6`, `sensor_management/tasks.py:12`, `events/tasks.py:24`, `core/exception_handler.py:35`, `core/api.py:19`, `ragflow_service/{client.py:10,views.py:13}`, `omni_desk_backend/health.py:10` 等 30 文件 | 30 个模块仍用 stdlib `logging.getLogger(__name__)`,绕过 `observability.get_logger` 自动注入的 `event` 字段;`request_id` 仍能关联但结构化事件名丢失,跨服务事件排查困难 | 机械替换为 `from observability import get_logger; logger = get_logger(__name__, '<app>.<event>')`;参照 `core/tests/test_zero_coverage_apps.py` 已有强约束规则加 AST 守卫 | XS |

**涉及模块:** permissions / meeting_rooms / dashboard / llm_service / smart_assistant / 7+ apps
**风险:** 低(B1 信号失效要注意缓存一致性;B4 LLM router 缓存失效要严格)
**预估:** B1 0.5 天 / B2 0.5 天 / B3 1 天 / B4 0.5 天 / B5 0.5 天 / B6 0.5 天 / B7 0.5 天

### R5-C. 依赖与 CI 卫生

| # | 文件 | 问题 | 修复方向 | 严重度 |
|---|---|---|---|---|
| R5-C1 | `.github/workflows/ci.yml:137-179` | 后端有 `check-lockfiles` 用 `pip-compile --rebuild` 比对两把锁(对应行 21-43),前端 ci.yml 只跑 `npm ci` + lint + audit,无 lockfile drift gate;`package-lock.json` 与 `package.json` 漂移绕过审计直接进 main | ci.yml `lint-frontend` 前加 `npm ls --workspaces --depth=0` 与 `git diff --exit-code package.json package-lock.json`;`npm audit --audit-level=high` 改为 `--audit-level=moderate`,或加一道 fail-on-moderate | **HIGH** |
| R5-C2 | `omni_desk_frontend/package.json:25-37` + `src/features/schedule/pages/ScheduleManagementPage.jsx` | `react-markdown` 仅 5 处 import,`react-slick` 仅 1 处(AnnouncementsPage),`jspdf` + `html2canvas` 仅 1 处(ScheduleManagementPage),`react-copy-to-clipboard` 仅 1 处(MessageMarkdown);离线内网 + Windows 7 场景下 bundle 体积直接影响首屏与离线包大小;CLAUDE.md 已明示 MUI 已清理,但未做 depcheck 收尾 | 跑 `npx depcheck omni_desk_frontend` 列出未用依赖;低频包评估按需引入(`react-markdown → marked`)或拆 chunk(`react-slick` 仅 1 处用 → 改原生 CSS 滚动);产线前 `npm dedupe` 收敛 `esbuild` / `braces` / `nanoid` 等 overrides | MEDIUM |

**涉及模块:** `.github/workflows/` + `omni_desk_frontend/`
**风险:** 低(C1 是纯 CI 加固;C2 拆 chunk 需回归页面)
**预估:** C1 0.5 天 / C2 1 天

### R5-D. 代码质量与重复收敛

| # | 文件 | 问题 | 修复方向 | 严重度 |
|---|---|---|---|---|
| R5-D1 | `omni_desk_backend/smart_assistant/tools/{memo,document,news,sensor,personnel,project,event,schedule,external_link,compliance}_tool.py` | 10 个 read 工具的 `execute()` 都有同样的 `if qs is not None and scope is not None` + `_extract_keywords(query/params)` + `qs.filter(title__icontains=keywords)[:10]` 双分支(旧路径走 `Model.objects.filter` 泄露全量数据,新路径走 `build_base_queryset` scoped),重复 ~30 行/工具,合计 ~300 行;任何一行修改都要同步 10 个文件,history 已知造成过「SELF scope 看到他人备忘录」安全回归 | `BaseTool` 新增 `_search_by_keywords(self, qs, params, query, scope_fallback, fields=('title',))` 内部方法,统一新旧路径(优先用 qs,缺则用 `build_base_queryset` + `get_queryset_for_scope` 自取);每个工具 `execute()` 收敛为 1-2 行调用,`_extract_keywords` 内置,消除跨文件 if/filter 块 | **HIGH** |
| R5-D2 | `omni_desk_backend/smart_assistant/tools/{document,memo,news,sensor,personnel}_tool.py:_extract_keywords` | 5 个工具各自定义静态方法 `_extract_keywords(query)`,全是大同小异的 `query.replace('搜索','').replace('查找','').replace('文档/备忘录/新闻/...','').strip()`,只有 stopword 集合不同;且 `BaseTool` 已有默认 `extract_keywords(self, query) -> list`(返回 token 列表,与子类的 `str -> str` 签名不一致),所以没人用基类实现 | `BaseTool.extract_keywords` 升级为返回字符串的统一实现,接 `stopwords: set[str]` 参数;5 个工具子类只声明 `stopwords = {'备忘录','便签'}` 等类属性,删除自己版本,统一通过基类签名,确保新旧 path 关键词口径一致 | MEDIUM |
| R5-D3 | `omni_desk_backend/smart_assistant/views/chat_sync.py:44-86` + `chat_stream.py:47-79` | sync / stream 两路径前 90 行各自重复 `SmartChatRequestSerializer` 校验 → `extract_attachment` → `load_session` → `ToolContext` 构造 → `inject_attachment` 同款 7 行代码,任何 session / serializer schema 变更要双修;`chat.py:18-30` 的 `_extract_attachment` / `_inject_attachment` 瘦壳法已废弃但仍存在(只为了让历史调用点兼容,实际只有 view 内部在用) | `conversation_manager.py` 新增 `prepare_chat_context(request, require_session: bool) -> (query, tool_context, history, session, err)` 一步返回;删除 `chat.py` 里 `_extract_attachment` / `_inject_attachment` 虚方法(确认无外部调用方后),`chat.py` 变为纯 ViewSet 路由层 | MEDIUM |
| R5-D4 | `omni_desk_frontend/src/shared/components/DataTable/index.jsx` + `SkeletonTable.jsx` + `src/features/**/<Table *.jsx` (46 文件) | `DataTable` / `SkeletonTable` 已封装好 loading + scroll + actions column + locale 模板,但 `grep -rln 'import DataTable' src/` 仅返回定义文件,0 个 feature 引用;features 里有 46 个文件直接用裸 `<Table>`(常重复写 `loading={isLoading}`、`rowKey='id'`、`scroll={{x:'max-content'}}`、`locale={{ emptyText }}` 模板,还各自实现 actions 列) | `DataTable` 扩展支持 column alignment / 自定义 rowSelection / extra columns,挑选最大 5-8 个 feature page 做改造样板(MeetingRoom / Compliance / Equipment / Permissions / Sensor Archive 等);CI lint 加规则禁止 `<Table` 必须配 DataTable 或 SharedTable 替代品;后续批量迁移剩余 38 个 | MEDIUM |
| R5-D5 | `omni_desk_backend/smart_assistant/agent/orchestrator.py:72-562` + `stream_runner.py:281-488` | `orchestrator.py` 是项目最大单文件(660 行,内含 `process` / `process_stream` + 多个 `_legacy_*` / `_process_*` 路径),每个路径里都有「`use_native_tool_calls` 决策 + 用户上下文校验 + 编排 AgentLog 与持久化 + 异常降级」~40 行重复骨架;`stream_runner.py`(488 行,内含 117 行 `_event_stream_generator`)已尝试拆分,但生成器与编排器之间还有 ~150 行参数、状态、异常处理耦合 | 把 `use_native_tool_calls` 决策与降级到 JSON 路径的逻辑抽成 `_resolve_run_path(query, ctx, use_native=None) -> RunPath` 枚举(`NATIVE` / `JSON` / `STREAM_NATIVE` / `STREAM_JSON`),create / stream 两条主路径共用该选择;Orchestrator 拆为 3 个子模块(`orchestrator/entry.py` 公开 process / process_stream、`orchestrator/run_path.py` 决策、`orchestrator/persistence.py` 持久化)各 ≤250 行 | LOW |
| R5-D6 | `omni_desk_frontend/src/features/user/hooks/useUserManagementPage.js` + 47 处 `res.data.results || []` 散落文件 | R3/R4 已统一 React Query,但仍有 page / hooks 走 `useState` + `useEffect` + `try/catch` + `message.error` 手动 fetch 模式(`useUserManagementPage` 是典型);`grep -rln 'staleTime:' src/features` 仅 4 个文件(meeting-room / schedule),其余 60+ `useQuery` 默认 0,易触发挂起重查 / 多次重复加载;`res.data.results` 风格未抽出 helper,28 个文件复制同一句 | `shared/api/responseHandler.ts` 新增 `extractResults<T>(p): T[]`(处理 `{results, count}` 与裸数组两种),`apiClient` 增加 `interceptors.response.use` 自动 unpack `data.results`(开发环境可关);`shared/hooks` 新增 `useCrudQuery<T>(key, fetcher, opts)` 默认 `staleTime=5min`;改造 `useUserManagementPage` 等剩余 3-5 个 `useState` 模式 page | MEDIUM |
| R5-D7 | `omni_desk_frontend/src/components/communication/{PostList,PostDetail,PostForm}.jsx` + `src/test-utils.js` + `src/test-utils/test-utils.jsx` | `src/components/communication/` 3 个组件(总 629 行)位于 feature 同名目录外,被 `features/communication` 页面与 `shared/pages` 引用,与 CLAUDE.md「按业务模块拆分 features」原则冲突;`src/test-utils.js` 与 `src/test-utils/test-utils.jsx` 提供两套几乎一样的 `renderWithProviders`(分别支持 `ConfigProvider/local` 与不带),feature 测试两个都用,造成 Provider 行为不一致风险 | 把 `src/components/communication/` 3 个组件以 `git mv` 迁到 `features/communication/components/` 并修 3 个 import 相对路径;二选一保留 test-utils(推荐 `test-utils/test-utils.jsx`,补齐 `ConfigProvider locale = zh_CN` 与当前 default 一致),删除 `src/test-utils.js`,并强制 lint `no-restricted-imports` 禁止 `test-utils` 顶层导入 | LOW |

**涉及模块:** smart_assistant + 前端 shared/components + features
**风险:** 中(D1 历史已造成过安全回归,回归测试必备;D4 需保留旧 fallback)
**预估:** D1 1 天 / D2 0.25 天 / D3 0.5 天 / D4 1.5 天 / D5 1.5 天 / D6 1 天 / D7 0.5 天

## 3. 汇总

### 数量分布

| 类别 | 条目数 | HIGH | MEDIUM | LOW | XS |
|---|---|---|---|---|---|
| R5-A 安全与限流 | 4 | 3 | 1 | 0 | 0 |
| R5-B 性能与可观测 | 7 | 4 | 2 | 0 | 1 |
| R5-C 依赖与 CI | 2 | 1 | 1 | 0 | 0 |
| R5-D 代码质量与重复 | 7 | 1 | 3 | 2 | 0 |
| **合计** | **20** | **9** | **7** | **2** | **1** |

### 工作量估算

- R5-A: 3.25 天
- R5-B: 4 天
- R5-C: 1.5 天
- R5-D: 6.25 天
- **合计: 约 15 人天**

### 建议启动顺序(2 周节奏)

1. **Week 1 Sprint 1**: R5-A1+A2+A3+A4 + R5-C1(快速赢 + 安全门面) → 4 PR,4.75 天
2. **Week 1 Sprint 2**: R5-B1+B2+B3+B4(高频读路径性能) → 4 PR,2.5 天
3. **Week 2 Sprint 1**: R5-D1+D2+D3(smart-assistant 工具层抽象) → 3 PR,1.75 天
4. **Week 2 Sprint 2**: R5-D4+D6(前端 DataTable 推广 + RQ 统一) → 2 PR,2.5 天
5. **Week 3+ 收尾**: R5-B5+B6+B7 + R5-C2 + R5-D5+D7 → 5 PR,3.5 天

## 4. 状态追踪

### 已合并
- [x] R5-A1 `.env` 凭据外移(PR #393,含 dev 锁文件 ruff 0.16.4 同批升级)
- [x] R5-A2 游客账号 expiry(PR #396,`guest_until` 字段 + 24h TTL + 清理任务改造)
- [x] R5-A3 写接口 throttle(PR #397,upload 10/h/user + 中间件扩展 `/api/file/`;guest_create 经核实已有 django-ratelimit 覆盖,`/api/smart-assistant/tools/` 路由不存在,均按实况修正)
- [x] R5-A4 AuditLogEntry 推广(PR #398,category 字段 + 组/权限写操作审计)
- [x] R5-B1 UserPermissionView 缓存(PR #399,`user_menu_<pk>` TTL 300s + 三路信号失效:GroupPagePermission/PageRoute/user.groups m2m;失效按 pk 逐键删兼容 LocMemCache)
- [x] R5-B2 MeetingRoomBooking 嵌套 N+1(PR #400,select_related 扩 user__assigned_by/user__personnel + prefetch phone_numbers,21→4 SQL)
- [x] R5-B3 dashboard 性能(PR #401,**方案调整**:核实后 6 条查询均为小表 top-5/count 聚合,SQL 合并收益微小,经用户确认改为 Project.updated_at 加 db_index(迁移 0004)+ 前端 dashboard-stats refetchInterval 60s)
- [x] R5-B4 LLMRouter 配置缓存(PR #402,`_load_configs` 结果缓存 60s + LlmAppConfig/LlmEndpoint 信号全量失效;llm_service 不在 INSTALLED_APPS,信号挂 smart_assistant.apps.ready())

### 进行中
_(暂无)_

### 调研产物本轮未启动
- [ ] R5-B5 AgentLog/AgentEvent 索引
- [ ] R5-B6 /health/ 探针扩 Redis+Celery
- [ ] R5-B7 30 文件迁移 observability
- [ ] R5-C1 前端 lockfile drift gate
- [ ] R5-C2 前端 depcheck 收尾
- [ ] R5-D1 smart-assistant 工具 execute() 统一
- [ ] R5-D2 BaseTool.extract_keywords 统一
- [ ] R5-D3 chat_sync/chat_stream 前置上下文合并
- [ ] R5-D4 DataTable 推广 46 文件
- [ ] R5-D5 orchestrator 拆 3 子模块
- [ ] R5-D6 useState 模式 + staleTime 收口
- [ ] R5-D7 communication 双轨合并 + test-utils 单一入口