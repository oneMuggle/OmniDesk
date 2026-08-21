# OmniDesk Round5 剩余项执行计划(2026-08-21)

> 状态:**执行中**(subagent-driven-development 模式)
> 范围:round5 调研清单剩余 12 项(B5~B7 / C1~C2 / D1~D7)
> 前置:B 批 4 项已合并(#399 #400 #401 #402),A 批 4 项已合并(#393 #396 #397 #398)
> 关联:`docs/plans/2026-08-20_project-optimization-round5.md`(调研产物,状态源)

## 1. 背景

R5-A 安全批与 R5-B 性能批(高频读路径)已完成并合并。本计划覆盖剩余 12 项:
性能收尾 3 项(B5~B7)、CI/依赖 2 项(C1~C2)、代码质量收敛 7 项(D1~D7)。

**工作节奏**:沿用已验证流程——每项独立 PR、TDD、CI 全绿后 squash merge。
本轮改用 subagent 并行实施以提高吞吐;每项完成后由 controller 更新状态。

## 2. 任务分解(按依赖与风险排序)

### 批次 1:后端独立项(可并行,互不依赖)

| 任务 | 内容 | 文件 | PR 分支 |
|---|---|---|---|
| T1 (R5-B5) | AgentLog/AgentEvent 索引 + timeline subtask N+1 | `smart_assistant/models.py` Meta.indexes + 迁移;`smart_assistant/views/tasks.py:285-305` timeline 加 select_related('subtask') | `feat/r5-b5-agent-log-indexes` |
| T2 (R5-B6) | `/health/` 探针扩 Redis+Celery | `omni_desk_backend/health.py`;任一探针失败返 503,timeout 0.5s | `feat/r5-b6-health-probes` |
| T3 (R5-C1) | 前端 lockfile drift gate | `.github/workflows/ci.yml` lint-frontend job 加 `npm ls` + `git diff --exit-code package.json package-lock.json`;audit 升 moderate | `feat/r5-c1-lockfile-gate` |

### 批次 2:smart-assistant 工具层抽象(D1 依赖 D2 的基类改造,先 D2 后 D1)

| 任务 | 内容 | 文件 | PR 分支 |
|---|---|---|---|
| T4 (R5-D2) | BaseTool.extract_keywords 统一 | `smart_assistant/tools/base.py` 基类实现接 stopwords 参数返回 str;5 个工具(document/memo/news/sensor/personnel)删自有 `_extract_keywords`,声明 `stopwords = {...}` 类属性 | `feat/r5-d2-extract-keywords-unify` |
| T5 (R5-D1) | 工具 execute() 双分支统一 | `base.py` 新增 `_search_by_keywords(qs, params, query, scope_fallback, fields)`;10 个工具收敛调用。**回归重点:scope 泄露安全测试必备**(历史曾造成 SELF scope 见他人备忘录) | `feat/r5-d1-tool-execute-unify` |
| T6 (R5-D3) | chat_sync/chat_stream 前置上下文合并 | `conversation_manager.py` 新增 `prepare_chat_context(request, require_session)`;两视图收敛;删除 chat.py 废弃虚方法 | `feat/r5-d3-chat-context-merge` |

### 批次 3:前端与机械迁移项(相互独立)

| 任务 | 内容 | 文件 | PR 分支 |
|---|---|---|---|
| T7 (R5-B7) | 30 文件 logging 迁移 observability | 机械替换 stdlib getLogger → `from observability import get_logger`;参照 core/tests/test_zero_coverage_apps.py 守卫规则加 AST 检查 | `feat/r5-b7-observability-migrate` |
| T8 (R5-D7) | communication 组件迁移 + test-utils 单一入口 | `git mv src/components/communication/{PostList,PostDetail,PostForm}.jsx → features/communication/components/`;修 import;test-utils 二选一(test-utils/test-utils.jsx 补 ConfigProvider zh_CN),删 src/test-utils.js,lint no-restricted-imports | `feat/r5-d7-comm-test-utils-consolidate` |
| T9 (R5-C2) | 前端依赖收尾 | depcheck 清未用依赖评估;react-slick(1 处)→ 原生 CSS 或保留决策记录;jspdf+html2canvas 动态 import;npm dedupe | `feat/r5-c2-frontend-deps` |

### 批次 4:大型重构(最后做,依赖前面批次稳定)

| 任务 | 内容 | 文件 | PR 分支 |
|---|---|---|---|
| T10 (R5-D4) | DataTable 推广样板改造 | DataTable 扩展 alignment/rowSelection/extra columns;选 5-8 个 feature page 改造(MeetingRoom/Compliance/Permissions 等);CI lint 规则暂不加(46 文件全量迁移超范围,后续轮次) | `feat/r5-d4-datatable-rollout` |
| T11 (R5-D6) | useCrudQuery + extractResults 收口 | `shared/api/responseHandler.js` extractResults helper;`shared/hooks/useCrudQuery.js` 默认 staleTime 5min;改造 useUserManagementPage 等 useState 模式 page 3-5 个 | `feat/r5-d6-crud-query-hook` |
| T12 (R5-D5) | orchestrator 拆 3 子模块 | `orchestrator/entry.py`(process/process_stream)+ `run_path.py`(_resolve_run_path 决策)+ `persistence.py`(持久化);各 ≤250 行;公开接口不变 | `feat/r5-d5-orchestrator-split` |

## 3. 技术方案要点

### B5 索引设计
- AgentLog.Meta: `indexes = [models.Index(fields=['-created_at']), models.Index(fields=['intent'])]`
- AgentEvent.Meta: `Index(fields=['task', '-sequence'])`
- 非破坏性迁移;timeline N+1 用 select_related

### B6 健康检查
- Redis: `redis.Redis.from_url(settings.CELERY_BROKER_URL, socket_timeout=0.5).ping()`
- Celery: `celery_app.control.ping(timeout=0.5)` — worker 未启动时 ping 会阻塞,须捕获异常降级为 warning 不阻断(仅 Redis 硬失败才 503);Celery ping 失败计入响应体 degraded 字段
- 测试用 mock,不依赖真实服务

### D1 安全红线
- 统一路径必须保持 scope 过滤语义:`build_base_queryset` 优先,`_search_by_keywords` 不得绕过 scope 直接 `Model.objects.filter`
- 必备回归测试:SELF scope 用户搜索他人数据必须返回空

### B7 迁移规则
- 只替换 logger 构造行,不动调用点;event 名格式 `<app>.<module>`
- AST 守卫脚本放 `scripts/check_logging_imports.py` + CI job 引用

### D5 拆分约束
- 公开导入路径不变:`from smart_assistant.agent.orchestrator import Orchestrator` 必须继续可用(orchestrator.py 变包或保留 re-export)
- 行为零变化,纯结构拆分,现有测试全部通过为准

## 4. 实施步骤

- [ ] T1 R5-B5 AgentLog/AgentEvent 索引 + timeline N+1
- [ ] T2 R5-B6 /health/ 探针扩展
- [ ] T3 R5-C1 前端 lockfile drift gate
- [ ] T4 R5-D2 extract_keywords 统一
- [ ] T5 R5-D1 工具 execute() 统一(含 scope 回归测试)
- [ ] T6 R5-D3 chat 前置上下文合并
- [ ] T7 R5-B7 observability 迁移 + AST 守卫
- [ ] T8 R5-D7 communication 迁移 + test-utils 合并
- [ ] T9 R5-C2 前端依赖收尾
- [ ] T10 R5-D4 DataTable 样板推广
- [ ] T11 R5-D6 useCrudQuery 收口
- [ ] T12 R5-D5 orchestrator 拆分

## 5. 验证方式(每任务通用)

1. TDD:先写失败测试再实现
2. 本地:相关 app pytest --ds=omni_desk_backend.settings.test 全绿(前端 jest)
3. ruff check + format 通过
4. push 后 CI 全绿(gh pr checks)
5. squash merge 到 main,更新 round5 计划文档状态追踪

## 6. 风险与依赖

- D1 是历史安全回归重灾区,scope 测试不通过即 BLOCK
- D5 是最大单文件重构,放在最后,以"现有测试全过"为唯一验收
- C2 依赖评估可能得出"保留现状"结论——允许,但需在 PR 中记录决策理由
- B7 涉及 30 文件机械改动,AST 守卫防新增回退
- 各任务文件面无交叉(除 D2→D1 有先后依赖),可安全并行
