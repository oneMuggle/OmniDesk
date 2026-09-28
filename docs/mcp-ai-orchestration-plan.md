# OmniDesk AI 统一调度业务模块优化方案（需求二）

> 日期：2026-09-27
> 基线：`origin/main` `110bf5cb` + PR #494（`9870f49`）。
> 性质：方案建议，尚未开始实施。按 `CLAUDE.md` 的"先写计划"规则，确认后将拆成 `docs/plans/YYYY-MM-DD_*.md` 分批实施。
> 模块现状见 `docs/mcp-module-health-audit.md`。

## 1. 目标

让用户在 OmniDesk 的任意位置，用一句话完成跨模块的**查询、汇总、办理**。例如："下周二下午找个能坐 10 人的会议室，约上项目 A 的成员，顺便把我当天的值班换掉"。

具体要求：

- AI 只能在用户**本人的权限范围**内看数据、办事；
- 写操作一律**先出草稿，人工确认后再执行，执行后可审计、可回滚**；
- 新模块接入 AI 的成本低：**在模块内声明能力即可**，不用改智能助手的核心代码；
- 满足离线内网部署，只用本地模型或私有 API 端点。

## 2. 已经做到了什么（不必重复建设）

| 能力 | 现状 | 证据 |
| --- | --- | --- |
| 工具体系 | 共 23 个工具：16 个只读，6 个写（备忘录新建/修改、换班发起/审批、通知、Office 生成），1 个删除（备忘录删除） | `smart_assistant/apps.py:42-64`，`tools/*.py` 中的 `risk_level` |
| 数据权限 | 按 SELF / DEPARTMENT / GLOBAL 三级范围过滤；工具和回答缓存按用户和范围隔离 | `smart_assistant/scope.py`，`cache.py`（PR #494） |
| 执行治理 | hook 链：审计、二次确认、PII 脱敏、限流、超时 | `smart_assistant/hooks/builtin/` |
| 写操作确认 | confirm-replay 草稿确认框架，一次性令牌，防重放 | 技术手册 43/44 章 |
| 原生函数调用 | 默认开启，但**只对 staff 开放**（`USE_NATIVE_TOOL_CALLS_FOR_ALL=false`）；每次最多 3 轮工具调用 | `settings/base.py:415,428`，`agent/tool_rounds_runner.py:51` |
| 多 Agent 任务 | Supervisor 拆解、pipeline 执行、断点恢复、SSE 按序号续传、暂停/恢复、写日志回滚、协作卡片 | `smart_assistant/agents/`，`views/tasks.py`，技术手册 32/43/44 章 |
| 模型中台 | `LLMRouter` 已统一收口（file_processing、office_assistant 都经过它），支持多端点降级和 Ollama 兜底 | `llm_service/router.py`，`file_processing/ai/query.py` |
| 主动能力雏形 | Celery beat 定时任务：每日简报、备忘录到期、合规到期、传感器校准、换班过期、帖子归档 | `settings/base.py` 中的 `CELERY_BEAT_SCHEDULE`，`smart_assistant/digest.py` |
| 写操作限流 | 默认每用户每分钟 10 次 | `middleware/rate_limit.py:93` |

`docs/plans/2026-08-09_ai-midplatform-digital-employee-optimization.md` 的进度：Phase 0 已全部完成，P1A-1 和 P1A-2 已完成。P1A-3/4/5/6、P1B（数字员工）、P2（体验整合）**都未完成**，本方案继承这些未完成项并重新排序。

## 3. 差距

| # | 差距 | 证据 |
| --- | --- | --- |
| G1 | **模块覆盖不全**：联培生、交流、电子书、文档库、联邦搜索、通知查询没有工具；会议室预约、日程等高频写操作没有工具 | `apps.py` 注册表 |
| G2 | **复杂任务没打通**：意图识别会返回 `complex_task`，但没有任何下游代码处理它；对话和 AgentTask 是两个互不相连的入口 | `agent/prompt_builder.py:82` 是全仓唯一出现的地方 |
| G3 | **多 Agent 只实现了串行**：`fanout`、`hierarchical` 两种模式未实现 | `agents/executor.py:201,207` |
| G4 | **工具元数据太少**：只有 `risk_level`；缺少所属模块、负责人、版本、所需权限码、幂等性、超时、缓存策略、功能开关；所有模块都集中在 `apps.py` 手工注册 | `tools/base.py:42-53`，`apps.py` |
| G5 | **AI 入口分散**：smart-assistant、tasks、stats、audit、knowledge-base、ragflow-chat、ai-showcase、dify-apps、office-assistant、file-analysis、ai-apps，共 11 个页面；Dashboard 没有 AI；AI 感知不到用户当前所在页面 | `routes/index.jsx` |
| G6 | **数字员工、预算治理、插件转工具、MCP 都还没有**；只有上下文长度上限，没有 token 预算或配额 | 全仓 grep 无结果 |
| G7 | **知识来源断裂**：公文和文档库的内容不会自动进入 RAG | `views/knowledge_base.py:28` 是唯一的入库调用点 |
| G8 | **模型能力风险**：文档示例的默认模型是 `deepseek-r1:1.5b`，这类小模型做结构化工具调用不可靠，这可能也是原生函数调用只对 staff 开放的原因之一 | `AGENTS.md` / `CLAUDE.md` 环境变量一节 |

## 4. 参考项目：借鉴什么、不照搬什么

| 参考 | 做法 | 借鉴到 OmniDesk |
| --- | --- | --- |
| **Odoo 19 AI**：[AI server actions](https://www.odoo.com/documentation/19.0/applications/productivity/ai/server-actions.html)、[Helpdesk 中的 Agent 与 Topic](https://www.odoo.com/documentation/19.0/applications/productivity/ai/support_operations.html) | Agent = 系统提示词 + 知识来源 + Topic；一个 Topic 打包一组工具，授予 Agent "能做哪些事"；AI 只负责**决策**选哪个工具、填什么参数，**业务规则必须写在工具代码里**；AI 动作可以由记录事件触发 | ① 能力按业务域分组（Toolset ≈ Topic），数字员工只挂载白名单里的 Toolset；② 工具内部复用业务 service 做校验，不信任 LLM；③ 在页面或记录上下文里直接调用 AI |
| **Frappe Assistant Core**：[GitHub](https://github.com/buildswithpaul/Frappe_Assistant_Core) | 每次工具调用都按**发起请求的用户**实时检查 ERPNext 权限，不缓存权限快照；每次调用都写审计日志；业务 App 通过 `assistant_tools` hook 自带工具，工具随 App 走 | ① 每个 Django app 自带 `ai_tools.py`，自动发现注册（替代手工改 `apps.py`）；② 每次调用都重新鉴权 |
| **django-mcp-server**：[GitHub](https://github.com/gts360/django-mcp-server) | 把 Django 模型、DRF 视图声明成 MCP 工具；注意：它默认关闭 DRF 的认证和权限类，改用 MCP 自己的认证 | 后期对外暴露 MCP 时可参考。**不要直接把 DRF 视图批量转成工具**，否则会绕过 queryset 的权限范围；应暴露已经过权限治理的 ToolSpec |
| **MCP 工具注解**：[规范 2025-06-18 ToolAnnotations](https://modelcontextprotocol.io/specification/2025-06-18/schema#toolannotations) | 用 `readOnlyHint`、`destructiveHint`、`idempotentHint`、`openWorldHint` 描述工具风险；注解只是提示，**不构成安全保证** | 把 `risk_level` 扩展成这四个字段，前端据此决定确认强度；真正的授权仍在服务端完成 |
| **LangGraph 人工介入**：[interrupt / resume](https://docs.langchain.com/oss/python/langgraph/interrupts) | 执行前暂停、保存检查点、人工批准后恢复；恢复时该节点会**从头重跑**，所以写操作必须幂等 | 现有 checkpoint + confirm 已经具备同类能力，**暂不引入 LangGraph**；只借鉴"恢复会重跑，所以要幂等键"这条原则 |
| **飞书 aily 智能伙伴**：[官方介绍](https://www.feishu.cn/content/article/7631864469689240764)、[发布报道](https://www.donews.com/news/detail/4/6475520.html) | 权限与用户本人一致；技能要经过安全审核；敏感动作需人工确认；以"AI 出草稿、人点确认"的半自动模式为主 | 数字员工只能"发起 + 请求确认"，不能代签；插件转工具必须复用插件审核流 |

## 5. 目标架构

```text
触点层    全局 AI 抽屉（任意页面，带页面上下文）| 智能助手页 | Dashboard AI 卡片 | 桌面端托盘
            │
调度层    AIRouter：闲聊 / 知识问答 → RAG
                    单步或多步查询 → 原生函数调用（多轮）
                    跨模块长任务（complex_task）→ AgentTask（pipeline / fanout）
                    写操作 → 草稿 → 确认卡片 → 执行
            │
治理层    PolicyGate：身份（服务端构建 ToolContext）→ 权限码 → 数据范围 → 风险等级 → 确认
                     → 限流 / 预算 → 审计 / 指标 → 脱敏
            │
能力层    Capability Registry：各 app 在 ai_tools.py 中声明的 ToolSpec，按 Toolset 分组
            │
业务层    各 Django app 的 service / queryset（与 HTTP 视图共用同一套权限逻辑）
```

### 5.1 模块能力自注册（解决 G1、G4）

每个 app 新增 `ai_tools.py`，由 `smart_assistant` 在 `ready()` 里自动发现。**已有的 23 个工具先原样迁过去，行为不变。**

```python
# meeting_rooms/ai_tools.py（示意）
from smart_assistant.capabilities import toolset, ToolSpec

@toolset("meeting", owner="行政组", title="会议室")
class MeetingToolset:
    find_available_rooms = ToolSpec(
        handler="meeting_rooms.services.find_available",   # 复用业务 service
        read_only=True, idempotent=True,
        required_permission="meeting_rooms.view_meetingroom",
        timeout_s=5, cache="per_user_60s",
    )
    create_booking = ToolSpec(
        handler="meeting_rooms.services.create_booking",
        read_only=False, destructive=False, idempotent=True,  # 使用 operation_id 保证幂等
        required_permission="meeting_rooms.add_meetingroombooking",
        confirm="draft",            # 走 confirm-replay 草稿确认
        rollback="agent_write_log", # 可回滚
        feature_flag="AI_MEETING_WRITE",
    )
```

- ToolSpec 字段：`name/version/owner/toolset/input_schema/output_schema/read_only/destructive/idempotent/open_world/required_permission/scope_policy/timeout/cache/confirm/rollback/feature_flag`。
- 启动时自检：写操作或删除操作必须声明 `confirm`；必须声明 `required_permission`；参数 schema 必须符合 strict 格式（延续现有 `assert_all_have_openai_schema`）。
- 自动生成"能力目录"页面和文档，也就是 `docs/mcp-module-health-audit.md` 里模块目录的 AI 一栏。

### 5.2 统一调度与 complex_task 打通（解决 G2、G3）

1. 意图识别为 `complex_task` 时，对话里返回一张"任务计划卡"（复用 `ScenarioCollabCard`）。用户确认后调用 `tasks/create_from_query`，在对话中订阅 SSE 进度，完成后把结果回填到对话里。
2. **实现 `fanout`，但只允许只读子任务并行**（例如同时查排班、会议室、项目成员）；带写操作的子任务仍按 pipeline 串行，每步单独确认。`hierarchical` 继续拒绝。
3. 把原生函数调用逐步开放给全员：在"评估集达标 + 模型满足要求"的前提下，按角色和部门分批开放（`USE_NATIVE_TOOL_CALLS_FOR_ALL` 改为按组配置）。`MAX_TOOL_CALLS_ROUNDS` 按场景配置，跨模块场景可设为 5。

### 5.3 写操作统一流程：草稿 → 确认 → 执行 → 可回滚

- 全部复用现有的 confirm-replay、`AgentWriteLog` 和 hook 链。确认卡片展示**目标对象、字段差异、影响人数、权限来源**。
- 第一批写能力按办公频率排序：
  1. 会议室预约和取消（带冲突检查）；
  2. 通知标记已读；
  3. 公告草稿（只生成草稿，由人发布）；
  4. 合规问题状态更新；
  5. 日程或事件创建。
- 禁止项：不能把用户在对话里说的"确认"当作审批凭证；批量操作、跨部门操作要求更高权限或双人审批；删除操作默认关闭。

### 5.4 页面上下文感知（解决 G5）

- 新增全局 AI 抽屉（Ant Design `Drawer`，兼容 Chrome 109），在任意页面都能打开。前端把 `route`、`record_type`、`record_id` 作为提示传给后端；**后端重新读取记录并做鉴权**，不信任前端传来的内容。
- 页面快捷问题由各 Toolset 声明，例如在项目详情页显示"总结本项目本周进展"。
- 11 个 AI 页面收敛为三个：智能助手（对话 + 任务）、知识库、AI 管理（模型、统计、审计、数据集）。Dify、Ragflow、Office 等降为智能助手里的"应用"或工具，保留原有路由重定向。

### 5.5 数字员工与主动巡检（承接原计划 P1B，解决 G6）

- `AgentProfile` 模型：名称、职责说明、系统提示词、挂载的 Toolset 白名单、数据范围、触发方式（被动 / beat 定时 / 业务事件）、启停开关、负责人。
- 首批三个角色：
  1. **个人秘书**：把现有的每日简报升级为晨报，内容包括备忘、值班、会议、待审批换班；
  2. **排班管理员**：巡检排班冲突，代为发起换班协商，最终仍由当事人确认；
  3. **合规专员**：跟踪到期事项，生成整改建议草稿。
- 原则：数字员工只能"发起 + 请求确认"；每次动作都写 `AgentEvent`；每个角色有独立开关和配额。

### 5.6 治理补齐

- **预算和配额**：按用户、应用、数字员工统计每日 token 和调用次数，超额后降级为只读或排队；流式对话回填成本（原计划 P1A-3）。（2026-09 已实施：按用户 / 用户组 / 应用设每日上限，到只读阈值降为只读、到上限当天停用；未做「排队」，见 `docs/plans/2026-09-28_ai-budget-s5.md`）
- **评估集**：先建约 60 条跨模块问句，覆盖普通用户、部门负责人、管理员三类角色，另加越权、提示注入、意图模糊、依赖超时等场景。发布门禁：**未授权的工具执行和数据返回为 0**；工具选择准确率与延迟以实测基线为准。现有测试多为单元和契约级，这个评估集用来验证"模型 + 工具"的整体行为。
- **知识管道**：公文和文档库入库时自动异步写入 RAG，并保留来源权限；检索结果按用户权限过滤（原计划 P1A-4）。
- **模型选型**：内网建议部署支持工具调用的 7B 以上指令模型（具体型号以评估集实测为准）；把 `deepseek-r1:1.5b` 这类小推理模型限制在闲聊或摘要场景。

### 5.7 对外 MCP 与插件转工具（可选，最后做）

- 用同一个 Capability Registry 生成 MCP 服务端（Streamable HTTP，JWT 用户身份），供桌面端或内网其他 Agent 调用。工具注解直接取自 ToolSpec。
- 插件转工具必须满足：插件已通过审核流、manifest 声明了 schema、默认只读、按 AgentProfile 白名单开放。`docs/plans/2026-08-09_*` 中提到的"插件真沙箱"完成之前，只接入白名单内的插件。

## 6. 分阶段路线

| 阶段 | 交付 | 退出条件 |
| --- | --- | --- |
| **S0 基线（约 1 周）** | 评估集 v0；模型选型实测；AI 指标看板（调用量、成功率、p95、成本） | 得到 staff 与全员两种开放方式的对比数据 |
| **S1 能力注册中心（约 2~3 周）** | `capabilities` 包、ToolSpec、自动发现；23 个工具迁移且行为不变；补齐通知、联培生、交流、文档库、全局搜索的只读工具；修复 `spreadsheet_qa` 的参数问题 | 全量后端测试通过；scope 和权限回归通过；能力目录自动生成 |
| **S2 统一入口与调度（约 2~3 周）** | 全局 AI 抽屉 + 页面上下文；`complex_task` 接入 AgentTask；只读 fanout；Dashboard AI 卡片；入口收敛 | 评估集中的跨模块查询达到基线目标；双账号隔离测试通过 |
| **S3 高频写操作（约 3~4 周）** | 5.3 节首批写能力，全部带确认、幂等、回滚 | 每个写能力都有批准、拒绝、重复提交、取消、回滚、409 冲突的测试；预发环境验收通过 |
| **S4 数字员工与治理（约 4 周以上）** | `AgentProfile`、三个首批角色、巡检、预算配额、RAG 自动入库；可选 MCP 和插件转工具 | 角色可在管理端启停；巡检动作全部可审计；超额会降级 |

**前置条件**：先完成 `docs/mcp-module-health-audit.md` 中的 P1-1（前端页面权限）和 P1-2（联邦搜索）。否则 AI 抽屉带来的新入口会放大这些断点。

## 7. 需要你确认的决策

1. **AI 写操作的范围**：第一批是否就是 5.3 节列的五项？哪些需要双人审批？
2. **模型部署**：内网能提供什么规格的 GPU 或私有 API？这决定原生函数调用能否全员开放，以及是否需要保留"意图分类 + 工具路由"作为兜底路径。
3. **数字员工**：首批角色是否就是个人秘书、排班管理员、合规专员三个？
4. **浏览器底线**：是否正式放弃 IE11，以 Chrome 109 / Edge 109 为底线？这会影响全局抽屉的实现方式。
5. **实施位置**：在最新 `main` 上新建分支实施（建议），并同步清理本地过时的 `main` 和 worktree。
