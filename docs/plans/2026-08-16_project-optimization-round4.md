# OmniDesk 项目优化方案(第四轮)

> 日期:2026-08-16 | 状态:规划中(待 R3 剩余项推进时并行启动)
> 起源:三路并行静态扫描(后端 Python / 前端 React / 工程·依赖·CI)+ 对 R3 计划剩余项的实测核实 综合得出
> 关联: round1(`PR #127`) / round2(`docs/plans/2026-07-31_project-optimization-round2.md`,已清) / round3(`docs/plans/2026-08-14_project-optimization-round3.md`)
> 说明: 本轮**聚焦 R3 计划之外**的新信号 + 对 R3 剩余项的两点数字修正;与 R3 重叠项(R3-B2 裸 `.all()` 收敛、R3-C 覆盖率、R3-E2/E3 门禁等)不重复立项,仅以引用方式衔接

## 1. 背景

round1/round2/round3 已完成:
- round1: 上传文件名净化 + 6 处 N+1 + 6 处索引 + TanStack Query 迁移 + 死代码清理
- round2: 大文件拆分、认证 GET 改造、mypy 基线
- round3(A 组后端拆分 + B1 serializer 白名单 + D 组前端拆分): A1~A9 / B1(4 PR) / D1~D8 / E4 全部 ✅,CI 绿

2026-08-16 对全仓做三路只读扫描(后端 N+1/安全/事务/Celery,前端大文件/重复/性能/RQ 一致性,工程依赖/CI/分支/文档),并实测核实 R3-B2/B3 剩余规模。发现 R3 计划未覆盖的**新信号 25+ 条**,统一成文。

**关键实测结论(修正 R3 计划数字)**:
- **R3-B3 原始 SQL 实际仅剩 2 处**(`smart_assistant/views/stats.py:74` `.extra()` + `core/api.py:168` 健康检查 `SELECT 1`)。roadmap BE-6 的"30+ 处"已被前几轮重构消化,建议核实后直接收尾,预算挪给 B2。
- **R3-B2 裸 `.objects.all()` 实际 47 处**(计划估 10+),是 B 组真正大头,建议提优先级。本轮不重复立项,在 §7 中标注衔接。

## 2. 候选清单

### R4-A. 后端稳定性与安全(架构级)

| # | 文件 | 问题 | 修复方向 | 严重度 |
|---|---|---|---|---|
| R4-A1 | `paperless_proxy/tasks.py:22` `:118` / `file_processing/tasks.py:9` / `smart_assistant/tasks.py:10` | 全仓仅 `execute_agent_task` 设了 `task_time_limit/soft_time_limit`;`process_paperless_outbox`(**每 1 分钟**跑,阻塞 HTTP + 整文件读内存)、`check_paperless_health`(**每 30 秒**)、`process_file_task`(OCR/PDF)、`process_document_embedding`(读整文件 + 上传 Ragflow)全部无 time limit → paperless 一挂 worker 被粘死、队列积压 | 批量补 `task_time_limit/soft_time_limit`(抄 `smart_assistant/tasks.py:93-94` 成熟范式);`file_processing/tasks.py:56` 注释写"指数退避"实际 `countdown=60` 恒定,补 `retry_backoff` | HIGH |
| R4-A2 | `smart_assistant/views/tasks.py:96` | AgentTask 列表 `filter(user=request.user)` 无 `prefetch_related("subtasks")`,serializer(`:58`)嵌套 `subtasks = AgentSubTaskSerializer(many=True)` → 每任务 1 条 N+1 | 加 `prefetch_related("subtasks")` | HIGH |
| R4-A3 | `documents/views/books.py:15` | Book 列表仅 `prefetch_related("tags", "chapters")`;`ChapterSerializer`(serializers.py:81-83)嵌套 `comments`+`annotations` 两个 many=True → 每章 2 条 N+1(注意 `ChapterViewSet:84` 自己是对的,只 Book 嵌套路径漏) | 补 `prefetch_related("chapters__comments", "chapters__annotations")` | HIGH |
| R4-A4 | `users/views.py:351-380` `django_admin_login` | `@csrf_exempt` + `AllowAny` + GET 端点,JWT 放 query string → 进 nginx 日志/浏览器历史/Referer;同文件注册(:46)/游客(:310)都有 `ratelimit 5/15m`,此端点**无限流** | 改 POST + header 携带 token;套上 `ratelimit` 装饰器 | MEDIUM |
| R4-A5 | `external_integration/plugin_loader.py:17,58,74` | `DEFAULT_MEMORY_LIMIT_MB=256` 定义但 `subprocess.run` 从未传 `resource.setrlimit`/`preexec_fn`,内存限制是**死配置**;`:71` `entry_point.lstrip("./")` 允许 `../` 逃逸 | 用 `preexec_fn` 落地 `setrlimit`;入口路径白名单化 | MEDIUM |
| R4-A6 | `settings/production.py:47` | `os.environ.get("DJANGO_ALLOWED_HOSTS","").split(",")` 未过滤空串(同文件 CORS/CSRF 都过滤了,唯独漏这)→ 未设环境变量时 `ALLOWED_HOSTS=[""]` | `[h for h in ... if h]` | MEDIUM |
| R4-A7 | `personnel/serializers.py:26-29` | `id_card_number` 显式声明且可读,与 `FamilyMemberSerializer:14-18`(write_only)和 R3 隐私方向相左(该端点仅 `IsAdminOrManagerOrReadOnly`) | 收敛为 `write_only` | LOW |
| R4-A8 | `events/views/schedules.py:30,318` | `select_related("duty_person","duty_leader")` 只追一层;`PersonnelSerializer.to_representation`(personnel/serializers.py:82-83)访问 `instance.position` → 每行多 2 条 position 查询 | `select_related("duty_person__position","duty_leader__position")` | MEDIUM |
| R4-A9 | `config/views.py:40-47` | `PageVisibility.objects.all()` 后逐行 `v.page.id`/`v.group.id` 触发 2N 查询 | 加 `select_related("page","group")` | MEDIUM |
| R4-A10 | `smart_assistant/views/stats.py:74` | `.extra(select={"date":"DATE(created_at)"})` 静态裸 SQL,PG/SQLite 方言不跨库,与 ORM 聚合链混排 | 改用 `django.db.models.functions.TruncDate("created_at")` | LOW |
| R4-A11 | `external_integration/services/plugin_service.py:9-16` + `views.py:45-51` | `SsoService.generate_redirect_url` 全仓零引用死代码,`sso_token` action 用相同的 `f"sso_placeholder_{link.id}"` 重复实现 | 只留一处;删死代码 | MEDIUM |
| R4-A12 | `events/views/trials.py:88` | `transaction.on_commit(lambda: None)` 是 no-op | 删除 | LOW |
| R4-A13 | `notifications/service.py:29-42` | dedupe 查询在 `atomic()` 之外,并发下同 key 可能创建两条 | 唯一索引或 `select_for_update` | LOW |
| R4-A14 | `external_integration/views.py:39` | 循环内 `ExternalLinkSerializer(link).data` 逐条序列化 | `many=True` 后按 category 分组 | LOW |

**涉及模块:** 8 app + settings
**风险:** 低-中(R4-A4/A5 涉及认证与子进程,需回归)
**预估:** R4-A1 0.5 天 / A2/A3 各 0.5 天 / A4/A5 各 0.5 天 / A6~A14 合计 1 天

### R4-B. 前端架构与一致性

| # | 文件 | 问题 | 修复方向 | 严重度 |
|---|---|---|---|---|
| R4-B1 | `shared/components/Sidebar.jsx:59` + `features/notifications/components/NotificationBell.jsx:14-20` | 通知未读数"双轨轮询":Sidebar 手动 `setInterval` 60s 轮询 `getUnreadCount`,NotificationBell 用 RQ `refetchInterval:5s` 拉**同一接口同一 `['unreadCount']` query** → 重复请求 + 计数可能不一致 | Sidebar 改消费同一个 RQ query,删手写轮询,保留一个周期 | HIGH |
| R4-B2 | `shared/components/QuickAssistant.jsx`(305 行,12 个 useState) | 本地重写 `parseSSE`(chatUtils.js:49 已有共享实现) + 整条 SSE 流式循环(:82-137 与 useSmartChat `runStream` 重复) + `ensureSession` 重复;无 useMemo/useCallback,全站静态加载(App.jsx:10) | 收敛为共享 `useChatStream` hook 或复用 `parseSSE`;拆 hook 降 12 个 useState | HIGH |
| R4-B3 | 全库 390 文件仅 20 用 RQ;18 个 feature 零 RQ;同一 feature 内混用(meeting-room/sensor/schedule) | `MeetingRoomManagementPage.jsx:31-85`(3 个 useCallback fetch + useEffect 并发 3 次 setState)、`AddCalibrationRecordPage.jsx:45-56`、`CalendarEventModal.jsx:34-44` 手动 fetch 无缓存去重 | 优先迁这 3 个页面到 RQ(queryKey 去重);作为 RQ 统一推进的第一批 | HIGH |
| R4-B4 | `features/schedule/pages/ScheduleManagementPage.jsx`(**909 行**,R3-D 唯一遗漏) | 内联 `ScheduleFormModal`(L26)+ `GenerateScheduleModal`(L218);`:397` 手动 while 翻页拉全量 personnel(page_size 1000)与 `personnelApi.js:40` `getAllPersonnel` 重复;Table columns 组件体内联(L745) | 复用 R3-D 手法外拆两个 Modal;改用 `getAllPersonnel`;columns 提升 | MEDIUM |
| R4-B5 | toast / 文件上传 / 错误提取 / 权限判断 四类重复 | `shared/utils/notifications.js` 仅 profile 3 文件在用,其余 67 文件直接 `message.error/success` 样式不统一;10MB 校验在 `FileAttachmentInput.jsx:7` 与 `FileUploadSection.jsx:24` 重复,4 个几乎相同的图标上传按钮;`error.response?.data?.message` 模式多处重复;`EventsPage.jsx:12`/`MeetingRoomBookingPage.jsx:79`/`CalendarEventModal.jsx:28` 用 `user?.role==='admin'||'manager'` 内联绕过 `hasPermission` | 统一 toast 工具;抽公共上传组件;推广错误封装;权限改走 `hasPermission` | MEDIUM |
| R4-B6 | `shared/components/Sidebar.jsx:59` / `features/smart-assistant/pages/KnowledgeBasePage.jsx:42` | 手写 `setInterval` 轮询(60s/5s)未走 RQ `refetchInterval`;`routes/lazyImports.js:74` lazy `NotificationBell` 未被 index 引用,实际由 SidebarHeader 静态 import 全站常驻加载 | 轮询统一走 RQ;删无引用 lazy 导出 | LOW/MEDIUM |
| R4-B7 | `useSmartChat.js:64-66` | `scrollToBottom` 依赖 `[messages, streamingAnswer]`,打字机 50ms tick 每次触发 `scrollIntoView({behavior:'smooth'})` 高频平滑滚动 | 降频(节流或仅新消息触发) | LOW |

**涉及模块:** shared/components + 5 features + routes
**风险:** 中(R4-B2/B4 影响核心 UX,需保留旧逻辑 fallback)
**预估:** R4-B1 0.5 天 / B2 1 天 / B3 每页 0.5 天 / B4 1 天 / B5 1 天 / B6/B7 各 0.5 天

### R4-C. CI/依赖/安全门禁

| # | 文件 | 问题 | 修复方向 | 严重度 |
|---|---|---|---|---|
| R4-C1 | `.github/dependabot.yml:54` | `security-updates:` 顶层块**不是合法 dependabot 键**(合法键仅 `version`/`updates`/`registries`/`enable-beta-ecosystems`),"daily 安全扫描"意图实际不生效 | 删无效块;若只收安全 PR 用 `open-pull-requests-limit: 0`;安全更新走仓库设置开关 | HIGH |
| R4-C2 | `ci.yml` npm audit 步骤 | 仅拦截 critical,8 个 high 静默通过:`react-router-dom`(open redirect XSS + `deserializeErrors()` 任意构造器注入,**生产依赖**)、`dompurify`(IN_PLACE hook XSS,**生产依赖**)、vite/postcss/js-yaml/brace-expansion/nanoid/eslint 等;且 `package.json` `overrides: js-yaml@4.2.0` 已被 audit 证明无效(CVE 在 4.2.x 未修复) | 收紧 `audit-level=high` 拦截;升级 vite/js-yaml/postcss;处理或移除无效 override | HIGH |
| R4-C3 | `.github/workflows/deploy-test.yml:76,85` + `.env.production.example` + `docker-compose.offline.yml` | 镜像 tag 硬编码 `v0.4.0`,当前 `VERSION` 已是 `0.7.0-alpha.2` → deploy 测试实际在测 2 个版本前的镜像,结果失真 | 从 `deployment/docker/VERSION` 动态注入 tag | HIGH |
| R4-C4 | `.github/workflows/ci.yml` + `deploy-test.yml` | pytest 在 CI 链路跑两遍(test-backend 含 `--cov-fail-under=80` + Deploy Test 的 `shell-and-django-tests` job 又跑一遍) | Deploy Test 只保留 shell 单测 + 集成场景,或 CI 产物传递 | MEDIUM |
| R4-C5 | `ci.yml:179` typecheck job | 永久 `continue-on-error: true`,mypy 实际不设防;`pip install mypy` 不锁版本 | 去掉 continue-on-error 并设基线,或移除该 job(避免"有检查"假象) | MEDIUM |
| R4-C6 | 定时依赖审计 | pip-audit/npm audit 只在 PR 触发,无定时兜底 | 加每周 cron 的审计任务(结果写入 issue) | LOW |
| R4-C7 | `desktop_notifier_ci.yml` | 两个 job 用 `python-version: '3.8'`(2024-10 已 EOL);`on.push` 覆盖 develop/test/main 3 分支每次 push 都重跑慢速 PyQt 测试;`pip install pyinstaller<6.0` 陈旧 | 升级 Python 3.10+/PyInstaller;合并触发事件;requirements 纳入锁文件管理 | MEDIUM |
| R4-C8 | 无 secret 扫描 hook | CI 与 pre-commit 均无 gitleaks/trufflehog/detect-secrets | 加轻量 secret 扫描步骤 | LOW |

**涉及模块:** `.github/workflows/*`、`dependabot.yml`、`package.json`、`deployment/docker/*`
**风险:** 低-中(C2 升级依赖需回归;建议先发依赖升级 PR 再收紧拦截线)
**预估:** R4-C1 0.5 天 / C2 1 天 / C3 0.5 天 / C4 0.5 天 / C5-C8 各 0.5 天

### R4-D. 测试与可访问性

| # | 范围 | 现状 | 目标 | 严重度 |
|---|---|---|---|---|
| R4-D1 | `features/documents-library/`(8 文件) | **完全零测试**;paperless-ngx 集成 + `usePaperlessHealth.js` 30s 轮询 hook,全库集成逻辑最复杂 | 补 hook + 页面最小单测 | MEDIUM |
| R4-D2 | `features/profile/`(4 文件,含 EditProfileForm/ChangePasswordForm)、`features/search-federation/`(3 文件,含 useUnifiedSearch hook) | 完全零测试,含表单/鉴权 hook | 补最小单测 | MEDIUM |
| R4-D3 | `features/integration-hub/`(5 文件)、`features/system/`(1 文件) | 完全零测试 | 补集成卡片 + 版本页最小单测 | LOW |
| R4-D4 | 14 处 icon-only Button 无 `aria-label`/`title` | `IntegrationManagementPage.jsx:100,102`、`PluginManagementPage.jsx:90,97`、`ExternalLinkManagementPage.jsx:86,88`、`ProjectsPage.jsx:112-114`、`GroupPermissionManager.jsx:189-190`、`KnowledgeBasePage.jsx:106` 等 | 逐个补 `aria-label`,或统一包 Tooltip(全库仅 6 文件在用) | MEDIUM |
| R4-D5 | 120 个文件用内联 `style={{`,sensor feature 最严重(SensorDetailPage/AddCalibrationRecordPage 各 13 处) | 主题系统(themeSchemes/tokens.css)未利用 | 先攻 sensor feature,提取到主题 token | LOW/MEDIUM |

**涉及模块:** 5 个零测试 feature + 全库 action 按钮
**风险:** 低
**预估:** R4-D1 1 天 / D2 1 天 / D3 0.5 天 / D4 0.5 天 / D5 1 天

### R4-E. 工程卫生

| # | 范围 | 现状 | 目标 | 严重度 |
|---|---|---|---|---|
| R4-E1 | `git worktree list` + 本地分支 | 10 个 `.claude/worktrees/agent-*` 残留 worktree(7 月下旬) + `agent-task7`/`fix/offline-upgrade-data-safety-task6`/`joint-students`/`sync-beta`/`sync-rc` 过期 worktree + `.qoder` detached worktree;工作均已 merge,本地 commit 是分歧副本 | 先验证各分支独有 commit 无未合并内容,再 `git worktree remove` + 删分支 | MEDIUM |
| R4-E2 | `.pre-commit-config.yaml` vs CI vs `requirements-dev.txt` | ruff 三套版本漂移:pre-commit `v0.12.0` vs CI `>=0.16,<0.17` vs 锁文件 `0.16.2`;mypy pre-commit `v1.15.0` vs 锁文件 `2.3.0` → 同一代码三套把关结果不一致(ruff 0.12→0.16 有大量新规则) | pre-commit rev 对齐 requirements-dev.txt 版本 | MEDIUM |
| R4-E3 | `requirements.txt`(dev) vs `requirements-prod.txt`(prod) | `asgiref` 两份锁不一致:dev 解析 `3.11.1` vs prod `3.12.1`,说明两份锁在不同时间点各自编译,存在漂移 | 同批重新 `pip-compile`;CI 加 `pip-compile --check` 锁新鲜度门禁 | MEDIUM |
| R4-E4 | `run_tests.sh` | 本地 pytest 不指定 `--ds=`(走默认 local)+ 不设 `--cov-fail-under`,与 CI(settings.test + 80%)行为不一致 → 本地全绿、CI 覆盖率挂的落差 | 补 `--ds=omni_desk_backend.settings.test` + `--cov-fail-under=80` | LOW |
| R4-E5 | `docs/technical/README.md` | 章节 35-39 标"待建预留"是刻意的,但已上线的 `notifications`/`file_processing`/`llm_service`/`observability` 4 个 app 缺文档(36 文件处理/38 LLM 服务/39 可观测性优先) | 补 36/38/39 三章(35 通知中心次之;37 联培生确未实现可保留占位) | MEDIUM |
| R4-E6 | 远程分支堆积 | 全仓分支 140 个(远端 112);channel-sync 远端分支 89 个,66 个 open `🔁 [sync]` PR,最老 8 个生成于 07-31 已 2 周未合并;33 个分支已无对应 open PR(孤儿) | 一次性清理 33 个孤儿分支;为 sync PR 加 stale 自动关闭(7-14 天);关 #2/#3/#4 远古僵尸同步 | MEDIUM |
| R4-E7 | `omni_desk_frontend/package.json` deps | `tippy.js` 在 src/ **0 处引用**,死依赖 | 移除 | LOW |

**涉及模块:** git 管理 + pre-commit + 锁文件 + scripts + docs
**风险:** 低-中(R4-E1/E6 涉及分支删除,操作前需用户确认)
**预估:** R4-E1 0.5 天 / E2 0.5 天 / E3 0.5 天 / E4-E7 各 0.5 天

## 3. 候选来源索引(扫描面 → 候选)

| 扫描面 | 工具 / 来源 | 产出的候选编号 |
|---|---|---|
| **A** 后端静态扫描 | Explore agent(grep N+1/裸 SQL/安全/事务/Celery/配置) | R4-A1~A14 |
| **B** 前端静态扫描 | Explore agent(grep 大文件/重复/RQ/内联样式/零测试 feature) | R4-B1~B7 / R4-D1~D5 |
| **C** 工程·依赖·CI 扫描 | Explore agent(grep dependabot/audit/分支/工具链/文档章节) | R4-C1~C8 / R4-E2~E7 |
| **D** R3 剩余项实测核实 | Bash 实测 `.objects.all()` 47 处 / 原始 SQL 仅 2 处 | §1 数字修正 → 衔接 R3-B2/B3 |

> 与 R3 重叠不重复立项项(仅衔接):R3-B2 裸 `.all()` 收敛(47 处,提优先级)、R3-B3 原始 SQL(核实收尾)、R3-C 覆盖率/type:ignore、R3-E1 ruff sweep、R3-E2 mypy strict、R3-E3 audit 硬门禁、R3-F 可观测性/LLM 成本、R3-G 文档。
> 没有出现在表中但用户临时提出想加的项,可直接合并入对应分组并标注"用户新增"。

## 4. 优先级与执行顺序

```
第一批(优先级 P0,1-2 天,纯配置/一行改动,零风险)
  ├─ R4-A1 (Celery 补 time limit 4 个任务) — 最易出生产事故
  ├─ R4-A2 / R4-A3 (两处 N+1 补 prefetch) — 一行改动
  ├─ R4-A6 (production ALLOWED_HOSTS 空串过滤)
  ├─ R4-A10 / R4-A11 / R4-A12 (stats ORM 化 + 删 SsoService 死代码 + 空 on_commit)
  └─ R4-C1 (dependabot 无效配置) + R4-C2 (npm audit 收紧 high)

第二批(优先级 P1,安全加固,各半天)
  ├─ R4-A4 (django_admin_login: POST + header + 限流)
  ├─ R4-A5 (插件子进程 setrlimit + entry_point 白名单)
  ├─ R4-A8 / R4-A9 (select_related 深度: position / page-group)
  └─ R4-C3 (deploy-test 动态 tag)

第三批(优先级 P1,前端一致性)
  ├─ R4-B1 (通知双轨轮询统一) — UX 高频
  ├─ R4-B2 (QuickAssistant 收敛共享 hook)
  ├─ R4-B4 (ScheduleManagementPage 外拆 Modal,复用 R3-D 手法)
  └─ R4-B3 (RQ 迁移: MeetingRoomManagementPage / AddCalibrationRecordPage / CalendarEventModal)

第四批(优先级 P2,按业务节奏)
  ├─ R4-B5~B7 / R4-D1~D5 (重复逻辑 + 零测试 feature + 可访问性)
  ├─ R4-C4~C8 (pytest 去重 / typecheck / 定时审计 / desktop_notifier / secret 扫描)
  ├─ R4-E1~E7 (分支/worktree 清理、工具链对齐、锁文件、run_tests.sh、文档、死依赖)
```

## 5. 风险评估与依赖

| 风险 | 缓解 |
|---|---|
| R4-A4 django_admin_login 改 POST 可能破坏现有 deep-link / 刷新流程 | 与 R2-B1 认证 GET 改造协调,前端同步改调用方;保留兼容期 |
| R4-A5 插件 setrlimit 误杀正常大内存插件 | 先白名单 approved 插件,限制从 `DEFAULT_MEMORY_LIMIT_MB=256` 起步,配置可调 |
| R4-C2 npm audit 收紧到 high 可能短期爆红 | 先发依赖升级 PR(react-router-dom/dompurify/vite),绿后再收紧拦截线 |
| R4-B2 QuickAssistant 收敛影响全局悬浮助手 UX | 保留旧组件 fallback;复用 R3-D 灰度开关手法 |
| R4-B4 ScheduleManagementPage(909 行)拆分影响排班核心页 | 同 R3-D 策略:先拆纯展示的 Modal,再动数据流;全量 580+ 用例兜底 |
| R4-E1/E6 分支删除不可逆 | 删除前逐分支列独有 commit 清单 + 用户确认;sync PR 先 stale 再删 |
| R4-D1~D3 补测 paperless 集成需 mock 外部服务 | 复用现有 paperless 测试 fixtures;hook 单测纯 mock |

## 6. 关联

- 上游:
  - `docs/plans/2026-06-05_project-optimization-roadmap.md`(整体 12 周路线图)
  - `docs/plans/2026-08-14_project-optimization-round3.md`(R3-B2/B3/C/E/F/G 剩余项,本轮不重复)
  - round1(`PR #127`) / round2(已清)
- 同源:
  - `docs/technical/25-api-performance-audit.md`(R4-A2/A3/A8/A9 复用其 N+1 审计模板)
  - `docs/technical/27-logging-standards.md`、`29-performance-profiling.md`(可观测性衔接)
- PR: 本轮由 `docs/plans/2026-08-16_project-optimization-round4.md` 本身为第一 PR(本文件),后续每个 R4-* 子项独立 PR

## 7. 不在本轮范围

为避免与 R3 重叠/范围漂移,以下明确**衔接 R3 或不做**:

- R3-B2 裸 `.all()` 47 处收敛 → **R3 计划内,本轮只提优先级,不重新立项**
- R3-B3 原始 SQL → 实测仅剩 2 处,建议 R3 侧核实后直接收尾
- R3-C1/C2/C3、R3-E1/E2/E3、R3-F1~F4、R3-G1~G4 → 均属 R3 剩余项,由 R3 计划追踪
- 升级 Django 4.2 / React 18(既定约束,不做)
- 引入微服务 / 新 UI 库 / 云部署(架构级 YAGNI,不做)
- 自动化 publish release / mutation testing / property-based testing(roadmap 明确不做)

## 8. 候选统计

| 分组 | 候选数 | 涉及模块数 |
|---|---|---|
| R4-A 后端稳定性与安全 | 14 | 8 app + settings |
| R4-B 前端架构与一致性 | 7 | shared + 5 features + routes |
| R4-C CI/依赖/安全门禁 | 8 | workflows + dependabot + package.json + deployment |
| R4-D 测试与可访问性 | 5 | 5 零测试 feature + 全库按钮 |
| R4-E 工程卫生 | 7 | git + pre-commit + 锁文件 + scripts + docs |
| **合计** | **41** | **覆盖全部 14+ app** |

## 9. 验收与归档

- **验证**:P0 第一批合并后跑 `pytest --cov-fail-under=80`(后端)+ `npm run test:coverage`(前端),CI 全绿;R4-A4/A5 配套回归测试
- **归档**:本轮全部 R4-* 合并完成后,**删除本文件**(按 `docs/plans/` 仅保留进行中计划的约定),各功能点并入 `docs/technical/` 对应章节
