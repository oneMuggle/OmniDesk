# OmniDesk 智能助手安全收敛：基于最新 main 的差异实施方案

> 2026-09-27；基点 `110bf5cb`。保留旧工作树 `agent/omni-desk-hardening-20260927` 作为方案/实验记录，**不直接合并其旧代码**。

## 背景与边界

旧工作树基点比远端 `main` 落后 460 个提交；其 33 个已修改的跟踪文件全部与上游改动重叠。上游已经加入 scope-aware 查询、LLM 配置的基础管理鉴权及 SSRF 校验、工具调用和确认流程、可恢复任务执行与事件序号锁。旧工作树里的只读编排、迁移 `0010` 和任务执行器不能整体搬运，否则会覆盖已上线功能并与现有 `0010_smart_assistant_permissions` 冲突。

本 PR 的**业务代码**仅补最新 main 仍存在的权限/缓存漏洞；不改变上游已有的写工具或任务状态机，不声称已完成所有业务模块的端到端验收。本轮不新增 AI 写操作。首轮 PR CI 暴露了与本次业务代码无关、但阻断绿灯的依赖安全和锁文件基线问题；其最小修复单独记录在下文。

## 具体缺口与实施顺序

1. **全局数据与配置管理权限。** `views/logs.py` 仍将任意 `is_staff` 视为跨账号日志审计员；`views/stats.py`、`views/llm_config.py` 使用 DRF `IsAdminUser`，同样仅依赖 `is_staff`。创建本应用专用权限门槛：已认证且为 superuser 或 `Admin` 组（沿用仓库 `users/permissions.py` 的组语义）。普通/Manager/非 Admin staff 只能看自己的日志，不得读取全局统计、修改或探测 LLM 配置。日志的 feedback 保持原有“仅所属用户可写”约束。补双账号、staff、Admin 组与匿名测试。
2. **回答与工具缓存必须拒绝缺失的身份作用域。** `cache.py` 工具缓存 key 虽已含完整 `context_sig`，却允许空字符串；回答缓存只从 `context_sig` 提取 user_id，同一用户的 GLOBAL/SELF 在回答 key 上碰撞。工具及回答缓存的读取/写入均需有效的 `u<用户ID>_s<self|department|global>` 签名，否则不使用缓存；回答 key 加入完整签名，保留历史签名及原生/JSON 路径隔离。回答 key 变更且工具 key 切换至 `tool:scoped:v2` 命名空间，令旧敏感结果缓存一律不可读（无需遍历 Redis 删除旧键，仍可按运维策略清理）。补同一账号提权/降权、跨账号、空签名、匿名签名和旧命名空间回归。
3. **验收。** 针对性运行缓存/权限/视图测试，并以 GitHub PR CI 为准，检查后端 lint、测试、覆盖率、前端/集成及仓库保护要求；**全部相关检查通过且可合并时才合并**。不能把旧基点的本地 `1255 passed` 当成当前 main 的 CI 结果。

本地完整回归额外发现两处与功能无关、但会使 2026-09-27 的 CI 变红的旧测试夹具：会议室 N+1 测试使用已经过去的 2026-09-01 预约日期；备份原子写测试对所有 `os.replace` 注入故障，错误地先拦下数据库转储重命名而非目标元数据写入。本 PR 仅修正这两处**测试本身**的时间与故障注入点，不修改相应生产逻辑。

## PR #494 首轮 CI 的基线阻断与处理

首轮 [CI 运行](https://github.com/oneMuggle/OmniDesk/actions/runs/36292411141) 的后端 lint/测试、前端测试/构建、typecheck 与 shell 检查通过，但已有依赖基线使三个独立门禁失败。为遵守「CI 全绿后才合并」，不降低门槛或隐藏警告，而在本 PR 中单独补最小依赖修复：

- `security`：生产锁中的 DRF 3.15.2 命中 `PYSEC-2026-3827/3828`（修复版本 3.17.2）。将 `requirements.in` 锁定到 3.17.2；维持已有 Django 4.2 的七项明示风险忽略，不增加任何新忽略。更新后的生产锁本地审计为 **0 个新增漏洞、7 个既有忽略**。
- `check-lockfiles`：PyPI 发布新版本后，仓库 dev 锁不再符合 CI 的 `pip-compile --rebuild` 全新解析。使用与 CI 一致的 **Python 3.10.21 / pip-tools 7.6.1** 重新解析 dev/prod 锁，并确保两份 dev 锁正文一致；本地复现两个 freshness diff 均为空。
- `lint-frontend`：既有 npm 锁含 Tiptap core、browserslist、js-yaml 的 high 漏洞。将三个直接 Tiptap 依赖的最低版本提至 `^3.30.5`，将 js-yaml override 改为 4.3.2，并在 Node 20/npm 10 下更新锁文件；本地 `npm audit --audit-level=high` 显示 **0 个漏洞**。没有禁用 audit 或排除包。

更新后本地以 Python 3.10 + 新锁运行完整后端：**3193 passed、2 skipped、2 xfailed、11 xpassed、7 subtests passed，覆盖率 93.16%（门槛 80%）**；Ruff、Django check 和 23 个工具的 scope 检查通过。前端 `npm ci`、`npm ls --depth=0`、ESLint、TypeScript 类型检查与编辑器相关测试通过；完整前端测试和 Vite 构建继续以 GitHub CI 为准（本地容器仅 2 GiB 内存，构建触发 Node heap 上限）。

## 不在本 PR 的内容

- 不迁移旧工作树的 `0010_task_lifecycle_choices`、旧 AgentTask 执行器或“全部工具只读”开关：上游已有同号迁移、可恢复执行及独立审批写工具。
- 不对部门级领域 ACL、真实 Redis/PostgreSQL/Celery、外部 Ragflow/Dify、Windows 部署或历史数据做未经验证的上线承诺；这些依旧需要独立集成验收。
- 若 PR CI 未通过或发生新的上游冲突，先修复/重新评估，不强制合并。
