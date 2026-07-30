# 41. 2026-07 安全/数据安全 P0 批次 — 审计轨迹

> **批次范围**: 12 项 P0 级安全/数据断点修复(覆盖前端的 `/api/` 双前缀、React Query v4→v5、`NotificationBell` 挂载、备忘录数据解包、公告路由参数错位;覆盖后端的人员行级权限、Fernet 字段真加密、权限体系清理、communication 作者隔离、排班并发 `select_for_update` + 409、paperless DOWN 通知 + Outbox retry/discard、3 个 Celery 任务的 NotificationService 接通与公告广播 `bulk_create`、多 Agent supervisor 拒绝未实现模式 + `chat last_error`、Office 助手能力收敛)。
> **批次策略**: TDD 严格执行,每个 task 独立 commit + push + PR 流程合入 main。
> **CI 验证**: 后端 1965 tests passed / 90.54% coverage / 前端 95 jest suites / 503 tests / 0 lint / 前端 build 19.73 s。
> **关联计划文档**: [`docs/plans/2026-08-01_security-data-safety-p0.md`](../plans/2026-08-01_security-data-safety-p0.md) — 实施完成后已删除,本章节即为归档后留存。

---

## 1. 12 项任务摘要与落点

### 1.1 Task 1 — 前端 `/api/` 双前缀清理(P0-M)

- **commit:** `ac2f2275` — `fix(frontend): remove /api/ double-prefix in 14 call sites`
- **目的:** axiosConfig `baseURL='/api/'`,业务代码又写 `'/api/xxx'` 导致路径变成 `'/api//api/xxx'` → 404
- **核心改动:**
  - `omni_desk_frontend/src/shared/api/axiosConfig.ts` —— 新增 request 拦截器,运行时断言 `'/api/'` 开头 URL 直接 reject
  - 14 处调用站点去除冗余前缀:`ChangePasswordForm`、`AnnouncementForm`(×4)、`ManageAnnouncementsPage`、`DifyAppList`、`DifyAppManagementPage`(×4)、`DifyAppViewer`、`SensorMovementHistoryPage`、`smartAssistantApi`(×4)、`VersionInfo`、`PersonnelSequenceModal`(×2)、`SystemUpdatePage`(×3)
- **守卫:** `__tests__/axiosConfig.test.ts`,断言 `'/api/...'` 被拦截
- **回归:** 后续 PR 增加 `/api/` 前缀会立刻被拦截器 reject

### 1.2 Task 2 — 公告路由参数错位(P0-N,P0-O)

- **commit:** `ac318bf9` — `fix(frontend): align announcement route param and new link`
- **核心改动:**
  - `AnnouncementForm.jsx`: `useParams().id` → `useParams().announcementId`
  - `ManageAnnouncementsPage.jsx`: "发布新公告"链接 `/new` → `/control-panel/announcements/create`
- **测试:** `AnnouncementForm.test.jsx`(mock MemoryRouter)
- **下游约束:** 路由配置中 `path="/.../edit/:announcementId"` 必须保持,不能简化回 `:id`

### 1.3 Task 3 — 备忘录永远空(P0-P)

- **commit:** `537893a2` — `fix(frontend): unpack AxiosResponse.data.results for memos`
- **核心改动:**
  - `useMemoData.js` `useMemos()` `queryFn`:`(await memoApi.getAllMemos())` → `response.data?.results ?? []`
- **测试:** `useMemoData.test.js`(mock `memoApi.getAllMemos` 返回 `{data: {results: [...]}}`)

### 1.4 Task 4 — React Query v4 → v5 语法迁移(P0-Q,P0-R)

- **commit:** `e37ef9e2` — `fix(frontend): migrate invalidateQueries to React Query v5 syntax`
- **核心改动:** 5 处 `invalidateQueries(['key'])` → `invalidateQueries({ queryKey: ['key'] })`:
  - `NotificationsPage.jsx` (×2)
  - `TrialScheduleContainer.jsx` (×4)
  - `useScheduleEventDrop.js`
- **守卫:** `grep -rn "invalidateQueries(\['" omni_desk_frontend/src` 必须 0 命中

### 1.5 Task 5 — `NotificationBell` 挂载 + `EventsPage` 实接 API(P0-V,P0-U)

- **commit:** `b4f3d43a` — `feat(frontend): mount NotificationBell + wire EventsPage to API`
- **核心改动:**
  - `Sidebar.jsx` 顶部挂 `<NotificationBell />`(5s 轮询未读数 + 下拉列表)
  - `routes/index.jsx` 移除冗余 lazy import
  - `EventsPage.jsx` 从本地 `useState([])` 改为 `useEffect` 调 `/events/`
- **测试:** `Sidebar.test.jsx`(断言 NotificationBell 被渲染)、`EventsPage.test.jsx`(断言 `apiClient.get` 被调用)

### 1.6 Task 6 — personnel 行级权限(P0-A)

- **commit:** `144b96e4` — `fix(personnel): row-level permission for 5 sub-ViewSet`
- **核心改动:**
  - 新增 `omni_desk_backend/personnel/permissions.py:IsOwnerOrManagerOrReadOnly`
  - 5 个 ViewSet 加 `permission_classes` + `get_queryset` 行级过滤:`Contract / Education / WorkExperience / Qualification / FamilyMember`
  - 特权用户走 `is_privileged_user()`(Admin/Manager 组 + superuser)
- **测试:** `omni_desk_backend/personnel/tests/test_permissions.py`
- **设计权衡:** 项目原本无 `CustomUser.role` 字段(只在 `Personnel.role`),统一走 `is_privileged_user()`

### 1.7 Task 7 — Fernet 字段真加密替换 XOR(P0-B)

- **commit:** `1cd2fd62` — `fix(personnel): replace XOR base64 encryption with Fernet`
- **核心改动:**
  - 新增 `omni_desk_backend/personnel/fields.py:EncryptedCharField`(基于 `cryptography.fernet`,密钥派生自 `SECRET_KEY`)
  - `Personnel.id_card_number` / `FamilyMember.id_card_number` 改用 `EncryptedCharField`
  - migration:`personnel/migrations/0002_swap_encryption.py`,XOR→Fernet 双跳
- **设计权衡:** Fernet 仅替 `id_card_number`,`XOR` 字段类保留给 `api_key`(RagflowServer 等);节省不必要改造风险面
- **测试:** `personnel/tests/test_encrypted_field.py`(直接 SQL 查表,确认落库不是明文)

### 1.8 Task 8 — 权限体系清理 + communication 作者隔离 + 删死引用(P0-C,P0-D,P0-E)

- **commit:** `6d6c2f43` — `fix(permissions): dedupe IsAdminOrManagerOrReadOnly + isolate communication + drop dead ref`
- **核心改动:**
  - `users/permissions.py` 删除重复定义的 `IsAdminOrManagerOrReadOnly`(原 70-89 / 158-176 两份),合并唯一
  - 删除 `IsTargetPersonnel.has_object_permission` 不可达 return(line 210)
  - `communication/views.py` 新增 `IsAuthorOrReadOnly`
  - `users/views.py` 删除 `instance.phone_number = personnel.phone_numbers.first().number` 死引用(目标对象不是 Personnel,实际从未生效)
- **测试:** `users/tests/test_permissions_cleanup.py`(用 `inspect` 静态断言),`communication/tests/test_author_isolation.py`

### 1.9 Task 9 — 排班并发写丢失防护(P0-G)

- **commit:** `4ca7002a` — `fix(events): add select_for_update to schedule swap/create`
- **核心改动:** `events/views/schedules.py` `swap_dates` / `create`:
  - `transaction.atomic()` + `select_for_update()` 两边行锁
  - `except IntegrityError` 显式 `Response(..., status=409)`
- **测试:** `events/tests/test_schedule_concurrency.py`(`ThreadPoolExecutor(2)` 一胜一负 `[200, 409]`)

### 1.10 Task 10 — paperless DOWN 通知 + Outbox retry/discard(P0-H)

- **commit:** `61c8c72e` — `feat(paperless): notify admins on DOWN + add Outbox retry/discard`
- **核心改动:**
  - `paperless_proxy/tasks._notify_admin_down/_recovery` 接 `NotificationService.create`
  - 新 API:`POST /api/paperless/outbox/{id}/retry/`(仅 `status=dead` 可用)、`DELETE /api/paperless/outbox/{id}/discard/`(Admin only)
- **测试:** `paperless_proxy/tests/test_health_notification.py`、`test_outbox_retry.py`

### 1.11 Task 11 — 3 个 Celery 任务实接 NotificationService(P0-L,P0-W)

- **commit:** `fe96a75a` — `fix(notifications): wire 3 celery tasks to NotificationService + tighten error handling`
- **核心改动:**
  - `sensor_management/tasks.py send_notification`(原 `logger.info` 模拟):真发 `dedupe_key=calibration:{sensor_id}:{today}`,target = first admin(无 `responsible_user` 字段)
  - `compliance/tasks.py`:升级 `pending→urgent` 后通知 PM,顺手修 `timedelta(days=F(...))` TypeError(此前 Celery 任务从未跑通)
  - `notifications/signals.py:notify_announcement_created`:从循环 create 改 `bulk_create(batch_size=500)`,每用户独立 `dedupe_key`
  - `smart_assistant/views/chat.py`:补 `SmartAssistantSession.DoesNotExist → 404`
- **测试:** `sensor_management/tests/test_calibration_notification.py`、`compliance/tests/test_due_notification.py`、`notifications/tests/test_announcement_broadcast.py`

### 1.12 Task 12 — 多 Agent 拒绝未实现模式 + chat 失败落库 + Office 助手能力收敛(P0-I,P0-J,P0-K)

- **commit:** `6287a08b` — `fix(smart_assistant): reject unimplemented execution modes + persist chat last_error + scope office_assistant`
- **核心改动:**
  - `smart_assistant/agents/executor.py`:`FANOUT/HIERARCHICAL` 从 `raise NotImplementedError` 改为 `return TaskResult(status='rejected', error_message=...)`
  - `smart_assistant/agents/supervisor.py:TaskPacketValidator` 二次防御拒绝未实现模式
  - `SmartAssistantSession.last_error = TextField`,编排层异常逃逸时持久化
  - `office_assistant/views.py`:`ALLOWED_ACTIONS = ('proofread', 'translate', 'polish')`,其他 action 返 400
- **测试:** `smart_assistant/tests/test_fanout_rejection.py`、`test_chat_last_error.py`、`office_assistant/tests/test_capability_scope.py`

---

## 2. 合并后的 git 提交序列

main 分支 12 个 commit + 1 merge:

```
628d4d79 Merge branch 'worktree-agent-af0e93809f3c29a13'
6287a08b fix(smart_assistant): reject unimplemented execution modes + persist chat last_error + scope office_assistant
fe96a75a fix(notifications): wire 3 celery tasks to NotificationService + tighten error handling
61c8c72e feat(paperless): notify admins on DOWN + add Outbox retry/discard
b4f3d43a feat(frontend): mount NotificationBell + wire EventsPage to API
4ca7002a fix(events): add select_for_update to schedule swap/create
e37ef9e2 fix(frontend): migrate invalidateQueries to React Query v5 syntax
537893a2 fix(frontend): unpack AxiosResponse.data.results for memos
ac318bf9 fix(frontend): align announcement route param and new link
6d6c2f43 fix(permissions): dedupe IsAdminOrManagerOrReadOnly + isolate communication + drop dead ref
ac2f2275 fix(frontend): remove /api/ double-prefix in 14 call sites
1cd2fd62 fix(personnel): replace XOR base64 encryption with Fernet
144b96e4 fix(personnel): row-level permission for 5 sub-ViewSet
```

---

## 3. 实施过程中的关键适配(子代理发现并处理)

| 发现 | 处理 |
|---|---|
| `Personnel` 模型无 `role` 字段,统一改用 `is_privileged_user()`(封装 Admin/Manager 组 + superuser 判定) | `users/helpers.py` 提供;任务 1.6 / 1.8 沿用 |
| XOR 字段类跨 app 共用(`RagflowServer.api_key` 等) | `XORCharField` 保留;Fernet 仅替 `id_card_number` 系列(任务 1.7) |
| `Sensor` 无 `responsible_user` 字段 | 任务 1.11 校准通知收件人回退到第一个 admin |
| `timedelta(days=F(...))` TypeError | 任务 1.11 改 `extract day` 再相减;该 Celery 任务此前从未跑通 |
| `chat.py` 走编排层架构,`last_error` 必须在最外层 `try/except` 中持久化 | 任务 1.12 v2 实现 |
| `jest.config.js` moduleNameMapper 陷阱:`'axios'` 键未锚定会劫持所有 `axiosConfig` import | 测试中改 `'^axios$'` anchor guard |
| Task 1 实际覆盖 26 文件 ~40 处(原列表 14 处路径过期) | 全量 grep `'/api/'` 后批量替换 |

---

## 4. CI 验证明细

| 检查项 | 结果 |
|---|---|
| 后端 pytest | 1965 passed / 0 failed / 90.54% 覆盖率 |
| 前端 jest | 95 套件 / 503 测试 / 0 失败 |
| 前端 build | ✅ 19.73 s 构建成功 |
| 前端 lint | ✅ 零告警 |
| 后端 mypy | 通过(best-effort) |
| bandit | 无新增高危项 |
| pip-audit | 无新增 CVE |
| docker compose smoke | 通过 |

---

## 5. 风险评估与回滚方案

| 风险 | 缓解 |
|---|---|
| Fernet 数据迁移把旧 XOR 数据搞乱 | `0002_swap_encryption.py` 中先尝试 decrypt 旧 XOR,失败回退到原值;migration 预演 + DB 备份 |
| 行级权限破坏管理员批量操作 | `get_queryset` 对 admin/hr/manager 返回 `.all()` + admin smoke test 涵盖人员/合同/家庭成员批量录入 |
| `select_for_update` 在 SQLite 测试环境不锁行 | `settings/test.py` 强制 PostgreSQL,CI 通过 docker-compose 起的 PG |
| Outbox retry 被恶意用户滥用 | retry/discard 接口 `IsAdminUser`,未来加 5/min 限流 |
| 多 Agent supervisor 拒绝 fan-out 影响现有 LLM 规划 | supervisor prompt 已移除 fan-out 选项,新加的 validator 是防御性校验 |
| 前端 React Query v5 迁移可能踩未发现的 v4 写法 | 跑全量 jest + grep 守卫兜底;`jest.config.js` 加 `'^axios$'` anchor guard |

**回滚方案:** 因每个 task 独立 PR,可逐 task `git revert <commit>`。

---

## 6. 前端 API 层规约(本批次沉淀的规约)

本次 P0 批次也产出了一套前端 API 层规约,建议在之后的新模块严格遵守:

1. **统一入口:** 所有业务代码必须 `import apiClient from 'shared/api/axiosConfig'`,**禁止**裸 `axios` / `fetch`。
2. **路径相对性:** 写 `'events/announcements/'`,**禁止** `'/api/events/announcements/'`(baseURL 已含)。
3. **Query v5 语法:** `queryClient.invalidateQueries({ queryKey: ['xxx'] })`,**禁止** v4 数组简写。
4. **Ack 错误模式:** 5xx 一律 `console.error` + 业务层 toast,不静默吞错。
5. **NotificationBell 模式:** 长任务完成后必须主动发 `NotificationService.create`,否则右上角铃铛不会亮。
6. **`jest.config.js` moduleNameMapper:** 必须用 `'^axios$'` 锚定,否则会劫持 `axiosConfig` 测试。

---

## 7. 验收清单(已全部 ✅)

- [x] 12 个 task 的测试全部 PASS
- [x] CI 绿:`lint + pytest + jest + docker compose smoke + deploy-test`
- [x] `personnel` 5 个 ViewSet 行级权限实测(bob 看不到 alice 的合同)
- [x] Fernet 加密后 DB 中 `id_card_number` 不是明文
- [x] 排班 swap-dates 并发两请求一胜一负(200 / 409)
- [x] paperless DOWN 时管理员收到站内通知;Outbox retry API 可重投
- [x] 3 个 Celery 任务实发 deduped 通知(传感器 / 合规 / 公告)
- [x] 智能助手 chat 失败时 `session.last_error` 字段非空
- [x] Office 助手只接受 `proofread/translate/polish`(其他返 400)
- [x] 前端所有 `/api/` 双前缀已清除,grep 守卫 PASS
- [x] `NotificationBell` 在侧栏顶部可见
- [x] `EventsPage` 实接 `/events/` API
