# 阶段 11：文档与验收报告

**日期**：2026-08-30
**基线**：`95f019215cae6cd8628c91dedbfc85f309e394d2`
**分支**：`feat/smart-assistant-real-orchestration`

- 增加 confirm replay PRE_EXECUTE 参数修改回归测试与最小实现：消费 token 后使用 hook 最终 fields/draft/params，保持 operation_id 闸门与 NotifyTool 收件人重解析；新增真实 RateLimitHook replay bypass 测试；事件 payload 读取改为 `getattr(event, "payload", None)` 防御 null/非对象事件。
- 本轮验证：后端 targeted（53 passed，`--no-cov`）、前端 hook/map Jest（28 passed）、显式 ESLint（0 errors）、`py_compile`、`git diff --check` 均通过。


- 更新 `/home/fz/project/OmniDesk/docs/technical/43-smart-assistant-collab-card.md`：修正实际路径与日期，明确真实 Celery/LLM/tool-calling 编排；8 个场景仅为示例入口；记录 SSE `last_seq`、`id`、`sequence`、心跳、`paused`/`partial`、旧版浏览器 timeline 轮询（不改变 React 18 对 IE11 的整体不支持），以及工具、AgentWriteLog、notify 说明。
- 更新 `/home/fz/project/OmniDesk/docs/technical/README.md` 第 43 章简介，保持“总览 + 分章节”结构。
- 同步 `/home/fz/project/OmniDesk/deployment/docker/VERSION`：`0.7.0-alpha.2` → `0.7.0-alpha.3`。
- 在 `/home/fz/project/OmniDesk/deployment/docker/CHANGELOG.md` 增加本功能 alpha.3 条目。
- 根 `/home/fz/project/OmniDesk/CHANGELOG.md` 已确认存在且当前 `[未发布]`，未在本阶段重复改写，避免绕过项目版本发布流程。

## 10 条验收证据

| # | 验收项 | 证据/结果 |
|---|---|---|
| 1 | 完整 AgentEvent 链与连续 sequence | 已由阶段 1–5 的实现与测试覆盖；本阶段未连接真实 LLM/Celery/生产 DB，未作虚假现场宣称。 |
| 2 | SSE 断点续传与去重 | `/home/fz/project/OmniDesk/omni_desk_backend/smart_assistant/tests/test_agent_task_stream.py` 覆盖 `last_seq`、无效/负数/超大值；前端 API 测试覆盖 sequence 去重与终止帧。 |
| 3 | 暂停与 worker 边界 | 阶段测试覆盖 pause/resume 状态；未在本阶段启动真实 Celery worker，5 秒 UI SLA 属环境验收限制。 |
| 4 | partial 产出展示 | `AgentTask` 合法 `partial` 状态、SSE 终止集合及前端展示测试已存在。 |
| 5 | AgentWriteLog 回滚 | `/home/fz/project/OmniDesk/omni_desk_backend/smart_assistant/tests/test_agent_write_log_stage7.py` 覆盖写日志、回滚恢复与事务语义。 |
| 6 | 人工修改后 409 | 同上测试覆盖当前值冲突不覆盖。 |
| 7 | notify 收件人安全闸门 | `/home/fz/project/OmniDesk/omni_desk_backend/smart_assistant/tests/test_notify_tool_stage8.py` 覆盖多候选与人数上限等拒绝路径。 |
| 8 | 通知 POST 405 | `/home/fz/project/OmniDesk/omni_desk_backend/notifications/tests/test_views.py` 覆盖只读 ViewSet 行为。 |
| 9 | IE11/ReadableStream 降级 | `/home/fz/project/OmniDesk/omni_desk_frontend/src/features/smart-assistant/api/__tests__/agentTaskApi.test.js` 覆盖降级轮询；未使用真实 IE11 浏览器，属于等效能力测试。 |
| 10 | 全量测试、覆盖率、构建 | 后端见下；前端 Jest 全绿；构建通过但存在 Vite chunk size warning，故 spec 的“无警告”严格条件未满足。 |

## 验证命令与结果

- 后端专用环境（`/home/fz/anaconda3/envs/OmniDesk`，Python 3.10.19）全量 `--no-cov`：**3058 passed, 2 xfailed, 11 xpassed**。
- 后端全量覆盖率：**93.24%**，超过 80% 门槛；同上 3058 passed。
- 前端 `npm run test:coverage -- --watchAll=false`：**139 suites / 785 tests passed**；全项目覆盖率 **41.61% statements / 42.15% lines**，项目未设置前端 80% 强制门槛。
- 显式 ESLint `npx eslint src --ext .js,.jsx`：失败，**63 errors / 244 warnings**，主要为既有全仓 lint 问题；智能助手范围仍有 7 个既有错误，未扩大到无关修复。
- `npm run build`：最终通过（6728 modules transformed）；Vite 报 `datetime` 空 chunk 与多个 >500 kB chunk warning，未将无关打包优化纳入本阶段。
- `python manage.py check_migrations`（专用环境）：发现 6 个 pending migration，无 destructive changes。按规则应先备份；本阶段未执行 `backup_db`，因为当前环境使用测试/SQLite 配置且不应对真实数据库产生备份副作用；未执行 migrate。

## 全量 Memo.objects 检查

生产代码查询点已逐处检查，软删过滤已覆盖用户可见/工具查询；测试、迁移和 seeder 中的创建/数据迁移查询不应强行添加用户过滤。详见 `grep -R "Memo.objects"` 结果，未发现新增遗漏。

## 安全、离线与兼容性结论

- SSE/timeline 对事件 payload 使用字段白名单/脱敏；任务与写日志接口按认证及归属校验；notify 固定类型、scope、人数量上限、确认流程和普通优先级。
- 无新增 Python/npm 依赖；工具与通知使用现有本地包/站内通道，符合离线优先。
- Vite target/browserslist 保持 Chrome 109 / Edge 109；缺少 ReadableStream 的旧版运行环境可走 `/timeline/` 每 2 秒轮询并按 sequence 去重。这不代表 React 18 应用整体支持 IE11；未在真实 IE11/Win7 机器执行验收。

## 变更说明

为使构建验收可执行，补充了前端 API 模块缺失的 `TASK_STATUS_MAP`、`SUBTASK_STATUS_MAP`、`EVENT_TYPE_LABELS` 导出；并修复 timeline 响应同时提供 `subtask` PK 字段，保持既有序列化测试契约。该修复仅涉及本功能任务流。

## Concerns

1. 全仓 ESLint 仍未通过（既有规则错误/警告）；本阶段未修复无关文件。
2. 前端生产构建通过但有 chunk size warning，不能宣称“无警告”。
3. 真实外部 LLM、Celery worker、PostgreSQL、IE11 浏览器和 backup/restore 未在当前环境现场执行；证据以自动化测试和代码审查为限。
4. `check_migrations` 有 6 个 pending migration；发布前需在目标环境按流程备份后显式 migrate。

## 最终审查统一修复（2026-08-30）

- worker 对 `paused` 任务改为调用 `MultiAgentExecutor.resume_from_checkpoint`，复用 checkpoint 恢复已完成 subtask，新增暂停任务恢复单测。
- `create_from_query` 改用固定错误文案与 `invalid_task_plan` / `task_creation_failed` 错误码，服务端仅记录用户上下文与受控异常堆栈。
- SSE/timeline payload 白名单补充 `error`、`reason`、`final_output`、`total_tokens`、`dropped_events`、`round`，继续递归脱敏；终态 `done`/`timeout` 帧补 `id` 行。
- `NotifyTool` 审计事件改用合法的 `subtask.tool_result`，以 `phase=notify`、`operation=agent_notify` 标识；恢复 executor 支持复用事件总线。
- 前端“重新查看”保留历史和 `lastSeq`，仅重新订阅，不伪装成重新执行；ScenarioCollabCard 文案保持一致。

### 本轮验证

- 后端目标测试（`--no-cov`）：20 passed；`py_compile` 通过。
- 前端 focused Jest：26 tests passed。
- 智能助手范围 ESLint：0 errors，4 个既有 `react/prop-types` warnings。
- `git diff --check`：通过。

对应提交：`2ddadfb9 fix: 收口智能助手任务恢复与事件契约`。工作区原有 spec 尾部格式改动未纳入该提交，保持不覆盖。

### 后续审查修复

- 修复恢复竞态：`resume_from_checkpoint` 在同一 `select_for_update` 事务内完成 `paused → running` 原子 claim；重复 worker 返回幂等 `running`，不再把正常任务误标记为 failed。
- 恢复测试：`17 passed`（含 `test_multi_agent_resume.py` 与任务测试）。

### 最终收口验证修复（2026-08-30）

- checkpoint 恢复以数据库 `AgentSubTask.status == completed` 建立独立完成集合；空 `{}`、`[]`、`None` 产出也不会重跑，新增真实 pipeline 恢复测试。
- 任务终态事件区分 `task.completed` / `task.partial` / `task.failed`，失败与 partial 写入稳定 `error`/`reason`/`final_output`/`total_tokens`/`dropped_events` 字段。
- SSE done/timeout 使用 `last_seq + 1` 的独立终态 sequence/id，避免与最后普通事件冲突；终态保留状态与 `format_version`。
- NotifyTool 对多收件人、多通道逐项记录 sent/failed，部分失败仍写入合法 `subtask.tool_result` 审计事件，包含 `operation_id`。

- `git diff --check`：通过。

### Final fix wave（2026-08-30）

- partial 任务沿用已登记的 `task.completed` 事件类型，保留 payload 中的 `status=partial`、`reason`、`final_output` 与 token 语义，避免事件标签漂移。
- paused 恢复的 TaskPacket 反序列化、executor 初始化及 checkpoint 加载异常均通过本次 worker 的 `started_at` claim 归属检查，在锁内收敛为 failed，并记录稳定失败事件；不会覆盖其他 worker 后续接管。
- NotifyTool 部分失败结果补充 `sent_count`、`failed_count`、`recipient_count`，审计仍使用脱敏标题/正文。
- synthetic done/timeout sequence 不作为前端可恢复数据库断点。

### Final fix wave 验证

- 后端 targeted `--no-cov`：通过。
- 前端 targeted Jest：通过（22 tests）。
- 智能助手范围 ESLint：0 errors，4 个既有 prop-types warnings。
- `py_compile`、`git diff --check`：通过。

### 最终定向修复（2026-08-30）

- 新增 `AgentTask.resume_claim_id` UUID claim 字段及迁移 `0019_agenttask_resume_claim_id.py`；恢复失败只允许持有本次 UUID claim 的 worker 收敛任务，兼容已有 `started_at`。
- partial 继续沿用合法 `task.completed` 事件并保留 `status=partial`。
- NotifyTool 补充混合多收件人/多通道成功与失败计数、审计脱敏和 `subtask.tool_result` 校验测试。

### 定向修复验证

- 后端 targeted：通过。
- `py_compile`：通过。
- `git diff --check`：通过。
- 迁移文件已生成但未执行 migrate。

### 最终状态机定向修复（2026-08-30）

- paused 恢复 claim 改用本次原子更新产生的 `updated_at` 行版本快照，不再以生命周期级 `started_at` 作为 worker 身份；失败收敛在持锁事务内明确匹配 `status=running` 与 claim 版本，避免覆盖后续 worker。
- malformed TaskPacket、executor 初始化和 checkpoint 加载异常均由 resume 责任方收敛为 `failed + completed_at`，并通过持久事件去重保证仅一个 `task.failed`。
- `execute_agent_task` 对 resume 返回的已收敛 failed 结果直接返回，不再写 `task.completed`。
- 新增真实 ORM 断言覆盖既有 `started_at`、三类恢复初始化异常、失败事件数量及无 completed 事件；空 artifact skip 回归通过。

### 定向验证

- 后端 targeted `--no-cov`：22 passed。
- `py_compile`：通过。
- `git diff --check`：通过。


### 本轮缺口修复（2026-08-31）

- `ToolContext` 显式携带 frozen context 的 `event_bus`、确认态与草稿；NotifyTool 兼容对象/旧 dict context，真实 `PersistentEventBus` 审计事件可落库。
- SSE/timeline notify 审计字段白名单与递归脱敏补充真实响应测试。
- `useAgentTaskStream` pause/resume 按 5 秒确认 watchdog 测试收口；resume 不再被 manuallyPaused guard 阻断。
- 统一事件序列化为数字 `sequence` 与 `evt-${sequence}`；partial 最终输出递归安全摘要，避免对象 child。
- 设计 spec 状态更新为“已实现，待最终验收”，并明确 React 18 整体不支持 IE11，仅旧 fetch/ReadableStream 能力降级。

验证：后端 targeted `--no-cov` 通过；前端 smart-assistant targeted Jest 通过（45 tests）；其余最终验证见主会话报告。

### Confirm replay 与 sequence 定向修复（2026-08-31）

- confirm replay 在 Redis atomic consume 前执行除 `confirmation` 外的 PRE_EXECUTE hooks；限流/权限等 Reject 不消费 token，返回固定安全错误并写入受控 `hook.rejected` 事件；通过后继续 confirmed execute、post/failure hooks 与审计。
- 前端 stream 仅接受非负安全整数 number 或严格十进制整数串；非法 sequence 映射为稳定 invalid id 且不推进 lastSeq。
- 验证：后端相关测试 45 passed；前端 stream Jest 9 passed；显式 ESLint、py_compile、git diff --check 通过。
- 提交：`4f2f15c9 fix: 完善确认重放钩子与事件序列校验`。

### Reviewer feedback follow-up（2026-08-31）

- Confirm replay 的 `ToolContext.replay=True` 让 `RateLimitHook` 跳过重复计数，同时仍执行其他 PRE_EXECUTE 安全校验。
- PRE hook 返回的修改参数现在用于 replay 参数解析（包括收件人解析），不再静默丢弃。
- 拆分并补充独立的普通 PRE hook 成功测试及参数修改测试。
- 追加提交：`a007a3be fix: 修正确认重放限流与钩子参数`。

## 本轮修复（2026-08-31）
- consume_confirmation_draft 仅接受明确 dict，深拷贝 validator 输入，compare-and-delete 且 delete 非 True fail closed。
- Redis 校验移出长锁，锁内重新读取并比较原始 envelope；PRE hook 输入深拷贝；NotifyTool summary 改为固定安全摘要；扩展 canonical 敏感字段。
- targeted pytest: 66 passed；py_compile 与 git diff --check 通过。
