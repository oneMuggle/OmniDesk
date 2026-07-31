# OmniDesk 项目优化方案(第二轮)

> 日期:2026-07-31 | 状态:规划中(待 round1 合并后启动)
> 起源:从 `2026-07-30_project-optimization-round1.md` 第 24 行("本轮不做")与第 108 行("不在本轮范围")提取;round1 合并后该文档会被删除,候选需独立成文以备追踪

## 1. 背景

round1(`chore/project-optimization-round1`,PR #127)聚焦小范围可快速修复的问题:
CRITICAL 上传文件名净化 + 6 处 N+1 + 6 处索引 + TanStack Query 迁移 + 死代码清理 + 依赖移除。
验证 2020 passed / 91.54% 覆盖率,CI 全绿。

调研过程中识别出一组**高风险/大规模/需独立方案**的项,不适合在 round1 范围处理,
本计划统一承接。

## 2. 候选清单

### R2-A. 大文件拆分(架构级)

| # | 文件 | 当前规模 | 拆分目标 |
|---|---|---|---|
| R2-A1 | `omni_desk_backend/smart_assistant/agents/executor.py` | 892 行 | 拆为 `pipeline.py` + `checkpoint.py` + `subtask_runner.py`,按职责分层 |
| R2-A2 | `omni_desk_frontend/src/features/schedule/pages/ScheduleManagementPage.jsx` | 909 行 | 拆为页面壳 + 子模块(列表 / 表单 / 日历视图 / 详情面板) |
| R2-A3 | `ScheduleManagementPage` while 循环全量拉取 | - | 改用后端分页端点(当前实现一次性拉全表,数据量大时前端卡顿) |

**涉及模块:** `smart_assistant/agents/`、`features/schedule/`
**风险:** 中(R2-A1 多 Agent 框架核心逻辑,改动需配套回归测试) / 中-高(R2-A3 需前后端同步)
**预估:** R2-A1 2 天 / R2-A2 1 天 / R2-A3 1 天

### R2-B. 认证与会话

| # | 文件 | 问题 | 修复方向 |
|---|---|---|---|
| R2-B1 | `omni_desk_backend/users/views.py:271-303` `django_admin_login` | JWT 经 POST body 传递,无法做 deep-link 与浏览器刷新保持 | 改造为 GET 传递(JWT 写入 HttpOnly cookie 或 URL 一次性 token),需前端 `LoginPage` 联动 |

**涉及模块:** `users/views.py`、前端 `LoginPage.jsx`、`axiosConfig.js` 拦截器
**风险:** 中(影响所有用户登录路径,需 E2E 覆盖)
**预估:** 1-2 天

### R2-C. 插件安全加固

| # | 范围 | 现状 | 目标 |
|---|---|---|---|
| R2-C1 | `plugin_sandbox.py` | 当前仅做 `subprocess.run` + 超时,无资源限制、无 syscall 限制、无网络隔离 | 评估 Docker / gVisor / nsjail / 简单 `resource.setrlimit` 四档方案,产出可行性报告 |

**涉及模块:** `external_integration/plugin_sandbox.py`
**风险:** 高(架构级,需独立 PoC)
**预估:** 调研 2 天 + 实施 3-5 天

### R2-D. 测试覆盖率提升

| # | 范围 | 当前 | 目标 |
|---|---|---|---|
| R2-D1 | 前端覆盖率阈值 | 24%(基线) | 阶梯提升至 50%(短期) → 70%(中期)。当前 CI 仅产出覆盖率报告,无硬门禁 |
| R2-D2 | 后端覆盖率硬门禁 | 已有 80% 阈值 | 维持并跟进各 app 增量,重点补 `smart_assistant/agents/` 与 `llm_service/` |

**涉及模块:** `jest.config.js` `coverageThreshold`、`pyproject.toml` `[tool.coverage.report]`
**风险:** 低(纯配置 + 补测试用例)
**预估:** R2-D1 阶梯 3-5 天(分 app 逐个补) / R2-D2 持续

### R2-E. CI/CD 强化

| # | 范围 | 现状 | 目标 |
|---|---|---|---|
| R2-E1 | mypy 硬门禁 | 当前 warnings-only | 切换到 `--strict` 模式作为 merge blocker |
| R2-E2 | E2E 接入 CI | 仅手动跑 | Playwright/Cypress 接入 PR check,先覆盖登录 + 主导航 5 条关键路径 |

**涉及模块:** `.github/workflows/ci.yml`、`playwright.config.js` 或 `cypress.config.js`
**风险:** 中(R2-E1 可能短期内解不开现有 type 错误 / R2-E2 需稳定 e2e harness)
**预估:** R2-E1 3-5 天 / R2-E2 5-7 天

## 3. 优先级与执行顺序

```
第一阶段(优先级 P0,合并 round1 后立即启动)
  └─ R2-B1 (认证 GET 改造) — 影响面大,优先修

第二阶段(优先级 P1)
  ├─ R2-A1 (executor.py 拆分)
  ├─ R2-A3 (ScheduleManagementPage 全量拉取)
  └─ R2-E1 (mypy 硬门禁)

第三阶段(优先级 P2,按业务节奏插入)
  ├─ R2-A2 (ScheduleManagementPage 拆分)
  ├─ R2-C1 (插件真沙箱调研 + PoC)
  ├─ R2-D1 (前端覆盖率阶梯)
  └─ R2-E2 (E2E CI 接入)
```

## 4. 风险评估与依赖

| 风险 | 缓解 |
|---|---|
| R2-A1 多 Agent 框架拆分可能引入运行时回归 | 配套补 AgentTask / AgentSubTask 集成测试 + 手工 e2e 跑通完整 pipeline |
| R2-B1 登录流程改动可能影响所有用户 | 灰度开关;先保留 POST body 通道作为 fallback |
| R2-C1 沙箱方案选错导致插件无法运行 | 启动前先做 4 方案 benchmark,选最稳的再开工 |
| R2-D1 前端覆盖率提升需大量补测 | 按 app 优先级排,memos / news / permissions / sensor_management 等小 app 优先 |

## 5. 关联

- 上游: `docs/plans/2026-07-30_project-optimization-round1.md`(合并后删除,功能点已并入 `docs/technical/`)
- 路线图: `docs/plans/2026-06-05_project-optimization-roadmap.md`(整体 12 周路线图,R2 候选与其中 BE-4 / FE-3 等条目对齐)
- PR: https://github.com/oneMuggle/OmniDesk/pull/127(round1)