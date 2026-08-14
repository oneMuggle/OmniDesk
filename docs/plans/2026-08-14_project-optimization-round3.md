# OmniDesk 项目优化方案(第三轮)

> 日期:2026-08-14 | 状态:规划中(待 round2 R2-B1 合并后启动)
> 起源:从 `docs/plans/2026-06-05_project-optimization-roadmap.md` 中标注但未在 round1/round2 落地的项 + 静态扫描新增信号 + `docs/technical/` 中描述但未完全落实的项 + 近期 PR 轻量调研 综合得出
> 关联: round1(`PR #127`) / round2(`docs/plans/2026-07-31_project-optimization-round2.md`)

## 1. 背景

round1(2026-07-30)聚焦小范围可快速修复的问题:
CRITICAL 上传文件名净化 + 6 处 N+1 + 6 处索引 + TanStack Query 迁移 + 死代码清理 + 依赖移除。
验证 2020 passed / 91.54% 覆盖率,CI 全绿。

round2(2026-07-31)在 round1 基础上承接高风险/大规模项:R2-A 大文件拆分(executor.py + ScheduleManagementPage)、R2-B 认证 GET 改造、R2-C 沙箱 PoC、R3-D 覆盖率阶梯、R2-E mypy strict / E2E 接入。
R2-B1 / R2-E1 / R2-D2 部分子项已进入 PR/合并流程。

本轮(round3)继承前两轮未做 + 全项目新发现的优化候选,统一成文以备追踪。
本轮明确不重复 round1/round2 已落地项,聚焦**新增/升级/纵深**三类候选。

## 2. 候选清单

### R3-A. 后端代码质量(架构级)

| # | 文件 | 当前规模 / 问题 | 拆分/修复目标 | 来源 |
|---|---|---|---|---|
| R3-A1 | `smart_assistant/agent/orchestrator.py` | **1520 行**,含 5 处 C901 告警(`handle`=31, `process_stream`=30, `stream`=22, `event_stream`=16, `_run_tool_calls_rounds`=12) | 拆为 `orchestrator.py`(orchestration 主流程)+ `stream_runner.py` + `tool_chain_runner.py` + `error_recovery.py` | B1 + B2 |
| R3-A2 | `smart_assistant/agent/tool_chain_executor.py` | 589 行,`validate` 函数 C901=25 | 拆为 `validator.py` + `chain_executor.py` + `dependency_resolver.py` | B1 + B2 |
| R3-A3 | `smart_assistant/agents/task_packet.py` | 534 行,5 处 C901 告警(`create`=17, `execute`=16, `from_dict`=15, `__post_init__`=13, `_execute_pipeline`=11) | 拆为 `packet.py`(数据类)+ `pipeline.py`(执行)+ `validator.py`(校验) | B1 + B2 |
| R3-A4 | `smart_assistant/views/chat.py` | 537 行 | 拆为 `chat_stream.py` + `chat_sync.py` + `conversation_manager.py` | B1 |
| R3-A5 | `smart_assistant/tools/swap_request_tool.py` | 485 行,`_legacy_process` C901=17 | 拆分遗留实现路径,移除 `_legacy_process` | B1 + B2 |
| R3-A6 | `events/models.py` | 453 行 + F811 双重 `timezone` import(第 3 + 232 行) | 拆为 `events/models/__init__.py` + `events/models/occurrence.py` 等子模块;删除 line 232 重复 import | B1 + B2 |
| R3-A7 | `smart_assistant/hooks/base.py` | 449 行 | 拆为 `hooks/base.py` + `hooks/lifecycle.py` + `hooks/registry.py` | B1 |
| R3-A8 | `smart_assistant/agents/executor.py` | 893 行 + `execute` C901=11 + `print(result.final_output)` 残留(L165) | round2 R2-A1 已规划;round3 增加 print→logger 修复 | round2 + B4 |
| R3-A9 | `core/management/commands/generate_release.py` | F541 f-string + F811 重复 + E402 import + E501 行长 | 清理一处 f-string、删除重复 CustomUser import、整理顶部 import | B2 |

**涉及模块:** `smart_assistant/agent/`、`smart_assistant/agents/`、`smart_assistant/views/chat.py`、`smart_assistant/tools/`、`smart_assistant/hooks/`、`events/models/`、`core/management/`
**风险:** 中-高(R3-A1 是核心链路,需配套回归测试)
**预估:** R3-A1 3 天 / R3-A2/A3 各 1.5 天 / R3-A4 1 天 / R3-A5/A7 各 1 天 / R3-A6 1.5 天 / R3-A8/R3-A9 各 0.5 天

### R3-B. 后端 API 安全 & 数据暴露

| # | 文件 | 问题 | 修复方向 | 来源 |
|---|---|---|---|---|
| R3-B1 | 8 个 app ≥40 处 `fields = "__all__"`(`personnel`/`events`/`external_integration`/`documents`/`meeting_rooms`/`users`/`config`/`news`/`projects`/`sensor_management`/`smart_assistant`) | 敏感字段直暴露 | 逐个白名单化,先攻 `personnel/serializers.py`(6/6 全部 `__all__`) + `events/serializers.py`(7 处) + `external_integration/serializers.py`(3 处) | B6 |
| R3-B2 | `external_integration/views.py:97` 等 ≥10 处裸 `.objects.all()` 在 view / serializer field queryset | 一次性加载全部记录,生产数据量上去后 OOM | 加 `.filter(is_active=True)` 或分页;serializer field 加 `limit_choices_to` | B5 |
| R3-B3 | 30+ 处原始 SQL 查询(roadmap BE-6,未在 R2 落地) | N+1 / 性能隐患 | 逐个加 `select_related/prefetch_related`,参考 `docs/technical/25-api-performance-audit.md` 模板 | roadmap BE-6 |
| R3-B4 | `users/views.py:271-303` `django_admin_login` JWT 走 POST body(round2 R2-B1 已规划) | deep-link / 刷新掉会话 | round3 跟踪 R2-B1 实施进度,不再重新立项 | round2 R2-B1 |

**涉及模块:** 跨 8+ app
**风险:** 中-高(R3-B1 涉及多 app 的字段暴露,改动需逐个验证)
**预估:** R3-B1 2-3 天(分 app 审)+ R3-B2 1 天 + R3-B3 1-2 天

### R3-C. 测试覆盖率与守卫

| # | 范围 | 现状 | 目标 | 来源 |
|---|---|---|---|---|
| R3-C1 | `smart_assistant` 总覆盖率专项 | 当前 ~63.25%(`docs/technical/28-smart-assistant-coverage-roadmap.md` 标的目标 85%) | 跟进 §2.2 63 个用例补齐进度,先攻 `views/llm_config.py`(37%) + `tools/event_tool.py`(32%) | C(technical/28) |
| R3-C2 | `# type: ignore` 23 处 | 集中 `smart_assistant/tests/test_task_packet.py`(11/23) | 补 mock 类型注解,移除 ignore | B8 |
| R3-C3 | ruff F841(7 处未用局部变量)+ F811(3 处重定义)+ E402(4 处错位 import)+ E501(20+ 长行) | 累计 ~58 处 ruff issue | 一次性 sweep,合并入 `lint-backend` CI | B2 |
| R3-C4 | 前端覆盖率阶梯(roadmap FE, round2 R2-D1 未启动) | 24% → 50%(短)→ 70%(中) | 接力 round2 P2 阶段,优先补 memos / news / permissions / sensor_management 小 app | round2 R2-D1 |
| R3-C5 | E2E CI 接入(round2 R2-E2) | 仅手动 | 接力 round2,先覆盖登录 + 主导航 5 条关键路径 | round2 R2-E2 |

**涉及模块:** `smart_assistant/tests/`、`tests/`、`.github/workflows/`、`jest.config.js`、`pyproject.toml`
**风险:** 低(纯配置 + 补测试)
**预估:** R3-C1 2-3 天 / R3-C2 0.5 天 / R3-C3 1 天 / R3-C4 阶梯 3-5 天 / R3-C5 5-7 天

### R3-D. 前端架构与性能

| # | 文件 | 问题 | 修复方向 | 来源 |
|---|---|---|---|---|
| R3-D1 | `src/features/smart-assistant/pages/SmartChatPage.jsx` | 713 行 | round2 R2-A2 已拆 ScheduleManagementPage;round3 接力拆 SmartChatPage(拆为 `ChatView` + `MessageList` + `InputBar` + `HookLayer`) | B3 + round2 R2-A2 |
| R3-D2 | `src/features/smart-assistant/components/ToolResult.jsx` | 588 行 | 按工具类型拆分子组件 + 注册中心 | B3 |
| R3-D3 | `src/features/smart-assistant/pages/AgentTaskPanel.jsx` | 522 行 | 拆为 `AgentTaskPanel` + `AgentTaskItem` + `AgentLogStream` | B3 |
| R3-D4 | `src/features/user/pages/UserManagementPage.jsx` | 474 行 | 列表 + 表单 + 权限矩阵拆开 | B3 |
| R3-D5 | `src/shared/components/Sidebar.jsx` | 446 行 | 按角色(管理员/普通/访客)拆分路由表 + Sidebar 渲染 | B3 |
| R3-D6 | `src/shared/pages/DashboardPage.jsx` | 428 行 | 拆为 DashboardShell + 各 widget(统计/待办/快速入口) | B3 |
| R3-D7 | `src/routes/index.jsx` | 416 行 | 拆为路由表 + lazy wrapper + permission wrapper | B3 |
| R3-D8 | `src/shared/components/SequenceManager.jsx` | 398 行 | 拆为 SequenceList + SequenceEditor + SequenceRunner | B3 |

**涉及模块:** `src/features/smart-assistant/`、`src/features/schedule/`、`src/features/user/`、`src/shared/`、`src/routes/`
**风险:** 中(R3-D1/D2/D3 是 smart-assistant 集群,改动影响核心 UX)
**预估:** R3-D1 2 天 / R3-D2 1.5 天 / R3-D3 1 天 / R3-D4/R3-D5 各 1 天 / R3-D6/R3-D7/R3-D8 各 0.5-1 天

### R3-E. CI/CD 与静态门禁

| # | 范围 | 现状 | 目标 | 来源 |
|---|---|---|---|---|
| R3-E1 | ruff 一次性 sweep(C901/F841/F811/F541/E402/E501) | ~58 处问题 | 一次性修复并把 `--select C901,F,E,LOG` 收紧到 CI(已含 LOG,本轮加 C901 + F 大类) | B2 + roadmap BE |
| R3-E2 | mypy 硬门禁(round2 R2-E1) | warnings-only | 接力 round2 切 `--strict` 作为 merge blocker | round2 R2-E1 |
| R3-E3 | `pip-audit` 与 `npm audit` | 已加 advisory(non-blocking),roadmap §5 阶段 5 待落地硬门禁 | 升级为 blocking,按依赖类型分类(直接依赖 vs dev) | roadmap §5 阶段 5 |
| R3-E4 | `docs/plans/` 已完成计划清理(roadmap DOC-2) | 7+ 已完成 plan 未清 | 合并后删除(round3 完成后同步删除 round3 plan 本体) | roadmap DOC-2 |

**涉及模块:** `.github/workflows/ci.yml`、`pyproject.toml`、`ruff.toml`、`mypy.ini`、`docs/plans/`
**风险:** 低-中(E3/E2 短期可能解不开存量)
**预估:** R3-E1 1 天 / R3-E2 3-5 天 / R3-E3 1 天 / R3-E4 0.5 天

### R3-F. 可观测性、性能、LLM 成本

| # | 范围 | 现状 | 目标 | 来源 |
|---|---|---|---|---|
| R3-F1 | `docs/technical/27-logging-standards.md` §3.4 守卫迁移 | BASELINE 29 个文件未迁移,守卫已就位 | 跟进剩余迁移率;评估是否纳入覆盖率类门禁 | C(technical/27) |
| R3-F2 | `docs/technical/29-performance-profiling.md` django-silk | 仅 dev/local,生产无 profiling | 评估生产可观测性方案(Sentry / OpenTelemetry),roadmap 已标 §阶段 4 后续"关键路径加 logger.info/warning"待落地 | C(technical/29) |
| R3-F3 | LLM token 成本治理(roadmap 未单列,但 P1a2 rate-limit 已做) | 限流已有;token 预算与缓存命中率无 dashboard | 加 `llm_token_usage_daily` 聚合 + 前端统计页;评估 prompt 缓存命中率 | D(PR 轻量)+ roadmap §阶段 4 |
| R3-F4 | `django-silk` 接入 dev(roadmap §阶段 2 后续) | 仅手动 | 接入到 docker-compose dev profile | roadmap §阶段 2 后续 |

**涉及模块:** `omni_desk_backend/observability/`、`omni_desk_backend/settings/local.py`、`omni_desk_backend/smart_assistant/views/stats.py`、`docker-compose*.yml`
**风险:** 低-中
**预估:** R3-F1 1-2 天 / R3-F2 调研 2 天 / R3-F3 2 天 / R3-F4 1 天

### R3-G. 文档与技术债

| # | 范围 | 现状 | 目标 | 来源 |
|---|---|---|---|---|
| R3-G1 | drf-spectacular 接入(roadmap DOC-1) | 144 路由仅 43% 有文档 | 接入并产出 OpenAPI,CI 校验 spec 与代码同步 | roadmap DOC-1 |
| R3-G2 | 用户手册零截图(roadmap DOC-3,14 篇) | 全缺 | 各补 1-2 张截图(可复用 round2 截图规范) | roadmap DOC-3 |
| R3-G3 | `docs/technical/` §27 logging 守卫在 `core/tests/` 中的 AST/regex 检查 | 已落地 | 跑通 CI,确认无回归 | C(technical/27) |
| R3-G4 | `docs/technical/28-smart-assistant-coverage-roadmap.md` §5 验收清单 7 项 | 全部未完成 | 跟进逐项落实,作为 round3 R3-C1 的子任务追踪 | C(technical/28) |

**涉及模块:** `docs/user-manual/`、`docs/technical/`、`omni_desk_backend/core/tests/`、`omni_desk_backend/requirements.in`(drf-spectacular)
**风险:** 低
**预估:** R3-G1 1 天 / R3-G2 1 周(可分配多人) / R3-G3 0.5 天 / R3-G4 并入 R3-C1

## 3. 候选来源索引(扫描面 → 候选)

| 扫描面 | 工具 / 来源 | 产出的候选编号 |
|---|---|---|
| **A** roadmap 残留 | `docs/plans/2026-06-05_project-optimization-roadmap.md` §3-5(roadmap 自身清单)+ round1/round2 中未落地 | R3-B3 / R3-C4 / R3-C5 / R3-E2 / R3-E3 / R3-E4 / R3-F4 / R3-G1 / R3-G2 |
| **A** round2 接力项 | round2 P0/P1/P2 中明确推到下轮的(R2-A1 完成需继续 / R2-B1 实施 / R2-D1 接力 / R2-E2 接力) | R3-A8 / R3-B4 / R3-C4 / R3-C5 / R3-E2 / R3-D1 |
| **B** 静态扫描 | ruff C901/F/E 大类 + 大文件 Top10 + 大组件 Top10 + .all() / Serializer `__all__` / print 残留 / type: ignore | R3-A1~A9 / R3-B1 / R3-B2 / R3-C2 / R3-C3 / R3-D1~D8 |
| **C** docs 对齐 | `docs/technical/27-logging-standards.md` / `28-smart-assistant-coverage-roadmap.md` / `29-performance-profiling.md` 中描述但未完成 | R3-C1 / R3-F1 / R3-F2 / R3-G3 / R3-G4 |
| **D** PR 轻量 | 近 2 月 merged PR 中 `perf/refactor/tech-debt` 标签(LLM token 治理、smart_assistant 错误提示、限流) | R3-F3 |

> 没有出现在表中但用户临时提出想加的项,可直接合并入对应分组并标注"用户新增"。

## 4. 优先级与执行顺序

```
第一阶段(优先级 P0,本轮启动后立即)
  ├─ R3-A1 (orchestrator.py 1520 行拆分) — 影响核心链路,优先
  ├─ R3-A8 (executor.py print 残留) — round2 接力,快速
  ├─ R3-B1a (personnel/serializers.py 白名单化) — 敏感字段 6/6 全部 __all__
  └─ R3-E1 (ruff 一次性 sweep) — 防止技术债继续堆积

第二阶段(优先级 P1,1-2 周)
  ├─ R3-A2/A3/A4/A5/A6/A7 (剩余 smart_assistant / events 大文件)
  ├─ R3-B1b / R3-B2 / R3-B3 (其他 app 的 __all__ 与裸 .all())
  ├─ R3-C1 / R3-C2 / R3-C3 (smart_assistant 覆盖 + type:ignore + ruff)
  └─ R3-D1 (SmartChatPage 拆分) — UX 核心

第三阶段(优先级 P2,按业务节奏)
  ├─ R3-D2~D8 (其余前端大组件)
  ├─ R3-C4 / R3-C5 (前端覆盖率阶梯 + E2E CI)
  ├─ R3-E2 / R3-E3 / R3-E4 (mypy strict / 审计硬门禁 / plans 清理)
  ├─ R3-F1 / R3-F2 / R3-F3 / R3-F4 (可观测性 + LLM 成本 + django-silk)
  └─ R3-G1 / R3-G2 / R3-G3 / R3-G4 (文档 + drf-spectacular + 手册截图)
```

## 5. 风险评估与依赖

| 风险 | 缓解 |
|---|---|
| R3-A1 orchestrator.py 拆分引入多 Agent 运行时回归 | 配套补 AgentTask / AgentSubTask 集成测试 + 手工 e2e 跑通完整 pipeline(同 round2 R2-A1 策略) |
| R3-B1 白名单化可能让前端缺字段报错 | 逐 app 推进,每个 app 完成后跑前端 e2e;准备 serializer 字段对照表 |
| R3-D1 SmartChatPage 拆分影响所有用户对话流 | 同 round2 R2-A2 策略:灰度开关 + 保留旧组件 fallback |
| R3-E1 ruff 一次性 sweep 短期解不开存量 C901 | C901 拆分与 R3-A 合并,先做模块级 sweep,再逐函数拆分 |
| R3-C1 smart_assistant 覆盖率提升需大量补测 | 沿 28-coverage-roadmap §2.2 表逐文件补;优先补 views/llm_config(37%) |
| R3-G2 用户手册截图需要真实环境 | 复用 round2 测试截图规范(`test-artifacts/screenshots/`),用 Playwright 跑关键流程 |
| R3-F2 生产可观测性选型(Sentry / OpenTelemetry)需调研 | 先做调研报告(2 天),再决策;不直接引入 |

## 6. 关联

- 上游:
  - `docs/plans/2026-07-30_project-optimization-round1.md`(已合并,PR #127,文档已删)
  - `docs/plans/2026-07-31_project-optimization-round2.md`(P0/P1 阶段合并后,本轮接力 P2 与新发现)
  - `docs/plans/2026-06-05_project-optimization-roadmap.md`(整体 12 周路线图,R3 候选与其 P1/P2/P3 中未在 round1/round2 落地的对齐)
- 同源:
  - `docs/technical/25-api-performance-audit.md`(R3-B3 直接复用其审计模板)
  - `docs/technical/27-logging-standards.md`(R3-F1 / R3-G3 直接相关)
  - `docs/technical/28-smart-assistant-coverage-roadmap.md`(R3-C1 / R3-G4 直接相关)
  - `docs/technical/29-performance-profiling.md`(R3-F2 / R3-F4 直接相关)
- PR: 本轮由 `docs/plans/2026-08-14_project-optimization-round3.md` 本身为第一 PR(本文件),后续每个 R3-* 子项独立 PR

## 7. 不在本轮范围

为避免范围漂移,以下明确**不做**(继承 roadmap §不在本路线图 + round1/round2 跳过项):

- 升级 Django 4.2 → 5.x(roadmap 明确推迟)
- 升级 React 18 → 19(同上)
- 引入微服务 / 前后端分离重构(架构级,YAGNI)
- 引入新 UI 库(Chakra / Radix,antd 已稳)
- 部署到云厂商(内网离线硬约束)
- mutation testing / property-based testing(`docs/technical/28` §6 明确不做)
- 自动化 publish release(roadmap §6 不做)
- `plugins_sandbox.py` 真沙箱调研与 PoC(round2 R2-C1 阶段 3 独立做,不并入 R3)

## 8. 候选统计

| 分组 | 候选数 | 涉及模块数 |
|---|---|---|
| R3-A 后端代码质量 | 9 | 7+ |
| R3-B API 安全 & 数据暴露 | 4(含 1 个 round2 接力) | 8+ |
| R3-C 测试覆盖率与守卫 | 5 | 5+ |
| R3-D 前端架构与性能 | 8 | 5+ |
| R3-E CI/CD 与静态门禁 | 4 | 4+ |
| R3-F 可观测性 / 性能 / LLM 成本 | 4 | 4+ |
| R3-G 文档与技术债 | 4 | 4+ |
| **合计** | **38** | **覆盖全部 14+ app** |

> 注:`R3-B4` 为 round2 接力项,实际"新候选"为 37 条。

## 9. 验收与归档

- **验证**:本轮所有 R3-* 完成合并后,跑 `pytest --cov-fail-under=80`(后端)+ `npm run test:coverage`(前端),CI 全绿;smart_assistant 子模块覆盖率 ≥ 85%(沿 `docs/technical/28` §3.2 阶梯)
- **归档**:本轮全部 R3-* 合并完成后,**删除本文件**(按 `docs/plans/` 仅保留进行中计划的约定),各功能点并入 `docs/technical/` 对应章节
