# OmniDesk 功能优化建议方案：迈向「AI 中台 + 数字员工」的桌面办公系统

> 日期：2026-08-09
> 状态：🔄 Phase 0（修复断链）已完成，Phase 1+ 待启动
> 调研依据：对 `omni_desk_backend/`、`omni_desk_frontend/src/`、`docs/technical/`、`docs/plans/` 的全量走查 + git 进度核实（PR #127/#174/#175/#176/#178）

---

## 一、背景与目标

### 1.1 项目新定位

将 OmniDesk 从当前的「全栈业务管理平台 + 贾维斯式聊天助手」升级为：

> **结合 AI 中台与数字员工的桌面办公系统**

拆解为三个关键词：

| 关键词 | 含义 | 当前差距 |
|---|---|---|
| **AI 中台** | 统一的模型接入/路由/计费、工具注册与准入、知识库管道，供全系统各模块复用 | LLM 调用未完全收口（`file_processing` 绕过 Router、`office_assistant` 无 DB 配置）；工具/插件/模型三要素缺统一注册与准入机制；无预算治理 |
| **数字员工** | 有角色、有职责、能主动干活的 Agent 实体，而非被动应答的聊天框 | 全部 AI 是「人发起、AI 响应」；无数字员工实体（角色/排班/主动性）；多 Agent 未与 chat 入口打通；19 个工具 16 读 3 写，写操作生产上几乎不可用 |
| **桌面办公系统** | 桌面端（PyQt5）+ Web + 通知三位一体，AI 能力触达桌面 | `desktop_notifier` 目前仅是「内嵌浏览器 + 通知」壳，无任何 AI 能力 |

### 1.2 现状盘点（调研结论摘要）

**已就绪的资产（本方案的复用基础，不重复建设）：**

- ✅ **单 Agent 编排成熟**：意图分类 → 工具路由 → hook 链执行 → LLM 合成；三级缓存、降级、审计、PII 脱敏、scope 数据权限、工具超时熔断一应俱全
- ✅ **原生 Function Calling（L1/L1.1）已上线**（staff 灰度），confirm-replay 二次确认框架完整落地
- ✅ **多 Agent 框架骨架完整**：Supervisor + 11 角色 + Pipeline 执行 + DB 断点恢复 + SSE 时间线 + 人工介入
- ✅ **LLM 路由层设计合理**：DB 配置 `LlmEndpoint` 优先级降级链 + Ollama 兜底 + token 成本核算
- ✅ **RAG 已通**：外部 RAGFlow 集成 + 多数据集标签路由 + 异步向量化
- ✅ **外部集成三层框架**：外链 / 服务代理（SSRF 防护）/ 沙箱插件市场（manifest 标准化 + 审核流）
- ✅ **事件驱动通知中枢**：`NotificationService`（dedupe 24h 合并）+ Celery beat 定时体系

**核心缺口（本方案要解决的问题）：**

1. **生产阻断**：`swap_extractor.py::_call_llm` 是 stub（`NotImplementedError`），导致换班写工具生产不可用——唯一的业务写操作场景断链
2. **中台性缺失**：AI 调用未统一收口、无预算/配额治理、工具准入无统一机制
3. **数字员工主体性缺失**：无主动巡检、无角色实体、多 Agent 与 chat 割裂
4. **业务渗透浅**：15 个业务模块约半数纯 CRUD 孤岛（memos/projects/meeting_rooms/communication/news/ebooks），`reminder_time`、`expires_at` 等字段「有字段没逻辑」
5. **入口体验碎**：AI 能力散落 7+ 页面，Dashboard 无 AI、多处死链与孤儿代码（QuickCommands/search-federation/menuConfig 分叉/compliance 断头路由）

### 1.3 与既有规划的关系（防重复声明）

本方案**不重复**以下已在队列中的工作，仅在依赖处引用：

- Round 2 候选：executor.py/ScheduleManagementPage 大文件拆分、JWT 登录改造、插件真沙箱、mypy 硬门禁、E2E 进 CI、覆盖率提升
- 智能助手 Phase 8（性能）/ Phase 9（ReAct+Reflexion）
- AI 中台 L2（长上下文压缩）/ L3（MCP）中属于纯技术演进的部分

本方案**正式承接** AI 中台 L 级路线中的 L4（工具/插件市场）与 L5（数字员工 Persona），将其从「远期愿景」提升为「主线目标」。

---

## 二、技术方案

### 2.1 目标架构

```
┌─────────────────────────────────────────────────────────────┐
│                      桌面办公触点层                            │
│   Web 工作台(Dashboard)  │  智能助手页  │  PyQt5 桌面端(通知+快捷问) │
├─────────────────────────────────────────────────────────────┤
│                       数字员工层                              │
│  AgentProfile(角色实体) → 主动巡检(beat) → 任务执行(多Agent)      │
│  内置角色: 排班管理员/合规专员/文档管理员/个人秘书                  │
├─────────────────────────────────────────────────────────────┤
│                        AI 中台层                              │
│  模型网关(LLMRouter统一收口+预算治理)                          │
│  工具注册中心(19业务工具+插件转工具, 统一准入/审核)               │
│  知识管道(documents→RAGFlow 自动入库+多数据集路由)              │
├─────────────────────────────────────────────────────────────┤
│                       业务模块层                              │
│  events/personnel/documents/compliance/memos/projects/...   │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 三条主线

**主线 A：AI 中台筑基**——把分散的 AI 调用收口为统一中台（模型网关 + 工具注册中心 + 知识管道）。

**主线 B：数字员工上岗**——从「被动助手」到「主动员工」：角色实体 + 主动巡检触发 + 多 Agent 与 chat 打通。

**主线 C：体验整合**——Dashboard 升级为 AI 工作台，收拢死链/孤儿代码，桌面端补 AI 触点。

三条主线有依赖顺序（A → B → C 可部分并行），但各自内部可独立交付验收。

---

## 三、优化建议明细（按优先级）

### P0：修复断链（先让已有的东西真正可用）

> 原则：不新增功能，只修复「已建未通」的断点。成本最低、收益立现。

| # | 事项 | 现状 | 动作 | 涉及文件 |
|---|---|---|---|---|
| P0-1 | **换班写工具接线** | `swap_extractor._call_llm` 是 stub，生产不可用 | 接入 `LLMRouter.generate_json`，实现自然语言→换班参数抽取；补 llm-swap-shift Phase 2（INTENT_PROMPT 加 swap 三分支 + tool_chain_planner 关键词「换班/替班/调班」） | `smart_assistant/extractors/swap_extractor.py`、`agent/intent_classifier.py`、`agent/tool_chain_planner.py` |
| P0-2 | **备忘录到期提醒** | `Memo.reminder_time` 是死字段 | 新增 Celery beat 任务：扫描到期 memo → 走 NotificationService 提醒 | `memos/tasks.py`(新增) |
| P0-3 | **QuickCommands 接线** | 组件已写好未挂载聊天页 | 挂到 SmartChatPage 输入区 | `features/smart-assistant/pages/SmartChatPage.jsx` |
| P0-4 | **修复死链/断头路由** | `/projects`、`/documents` 主应用路由缺失被静默重定向；`/control-panel/compliance` 空白页 | 补路由或移除侧边栏入口；compliance 补列表页（复用现有 API） | `src/routes/index.jsx`、Sidebar、`features/compliance/` |
| P0-5 | **菜单统一** | `menuConfig.jsx` 与 `Sidebar.jsx` 分叉 | 以 menuConfig 为单一数据源，Sidebar 引用之 | `shared/config/menuConfig.jsx`、`Sidebar.jsx` |
| P0-6 | **communication 过期归档** | `Post.expires_at/is_archived` 有字段没逻辑 | beat 任务自动归档过期帖 | `communication/tasks.py`(新增) |

### P1-A：AI 中台筑基

| # | 事项 | 说明 | 涉及文件 |
|---|---|---|---|
| P1A-1 | **LLM 调用统一收口** | `file_processing/ai/query.py` 绕过 Router 直连 Ollama SDK 且硬编码 `qwen2.5:7b` → 收编进 `LLMRouter`；`office_assistant` 登记进 `LlmAppConfig.APP_CHOICES` 使其可配端点 | `file_processing/ai/query.py`、`smart_assistant/models.py` |
| P1A-2 | **写工具速率限制** | llm-swap-shift Phase 5 遗留：写工具单独限流（如 10/min），区别于 chat 全局 30/min | `smart_assistant/middleware/rate_limit.py` |
| P1A-3 | **流式成本统计** | 流式/原生路径 `estimated_cost=None` → 在 done 事件回填 usage 与成本，写入 AgentLog | `views/chat.py`、`agent/orchestrator.py` |
| P1A-4 | **documents→RAGFlow 自动入库管道** | 补上 documents 与 ragflow 的断裂：公文/文档上传后异步入 RAG 数据集（复用 `process_document_embedding`），喂养 `knowledge_qa` | `documents/` → `smart_assistant/tasks.py` |
| P1A-5 | **知识库数据集管理页** | 后端 `KnowledgeDataset` 支持多数据集但无前端 CRUD 页 → 补管理界面（标签/优先级/启停） | `features/smart-assistant/`(新页) |
| P1A-6 | **工具注册中心雏形（承接 L4）** | 将 `external_integration` 插件 manifest 自动转 OpenAI tool schema 注册进 smart_assistant，复用插件审核流作为工具准入——**数字员工获得操作任意外部系统的能力，全系统性价比最高一步** | `external_integration/` → `smart_assistant/tools/registry.py` |

### P1-B：数字员工上岗

| # | 事项 | 说明 | 涉及文件 |
|---|---|---|---|
| P1B-1 | **AgentProfile 实体模型** | 数字员工 = name/角色描述/system prompt/工具白名单/数据 scope/触发方式(被动/定时/事件)/启停。承接 L5 Persona，先落模型与 admin，UI 随后 | `smart_assistant/models.py`(新 `AgentProfile`) |
| P1B-2 | **主动巡检框架** | beat 驱动的巡检循环：检测条件 → 命中 → 数字员工发起动作（写操作仍走 confirm 框架，推确认通知给人）。首个场景：**排班冲突巡检 → 主动代发换班协商**（swap 写工具就绪，只缺触发循环） | `smart_assistant/tasks.py`、`events/` |
| P1B-3 | **多 Agent 与 chat 打通** | `complex_task` 意图目前无下游（落 general_chat）→ 路由到 `/tasks/create/`；实现 fanout 执行模式（当前被 ValidationError 拒绝） | `agent/orchestrator.py`、`agents/executor.py` |
| P1B-4 | **内置 4 个数字员工角色** | 排班管理员（冲突巡检+换班协商）、合规专员（整改建议生成+到期跟踪）、文档管理员（上传自动分类打标入 RAG）、个人秘书（个性化晨报+备忘拆解）。每个角色 = AgentProfile 一条 seed 数据 + 对应工具/巡检 | seed 数据 + 各业务模块 |

### P2：业务渗透与体验整合

| # | 事项 | 说明 |
|---|---|---|
| P2-1 | **Dashboard 升级 AI 工作台** | 加「今日风险/待办」AI 简报卡（复用 digest 链路）+ 数字员工任务状态卡 + 快捷助手入口 |
| P2-2 | **QuickAssistant 体验对齐** | 抽 SmartChatPage 的 Markdown/打字机渲染为共享组件，消除纯文本割裂 |
| P2-3 | **search-federation 接线** | 统一搜索栏孤儿模块 → 接入顶栏，聚合各业务模块 + 知识库检索 |
| P2-4 | **各模块单点 AI 自动化**（选做，按需） | personnel 合同到期巡检 / projects 周报摘要 / sensor 校准工单 / news 周简报 / notifications 智能合并摘要 |
| P2-5 | **StatsPage 图表化** | 纯表格 → antd Charts/echarts 可视化对话量与成本 |
| P2-6 | **桌面端 AI 触点** | PyQt5 托盘加快捷问对话框（复用 Web SSE API）；数字员工待确认动作推桌面通知 |

### P3：远期（承接 L 级路线，本期不展开）

- L2 长上下文工具调用压缩
- L3 MCP 客户端（标准化工具协议）
- 语音交互（内网需离线 ASR 模型，成本高，单独立项评估）
- Phase 9 ReAct + Reflexion 架构升级

---

## 四、实施步骤（分阶段里程碑）

### Phase 0 — 修复断链（P0-1 ~ P0-6）
- [x] P0-1 换班写工具 LLM 接线 + 意图/关键词补齐（fix/sa-swap-extractor-wiring）
- [x] P0-2 备忘录到期提醒任务（feat/backend-beat-automation）
- [x] P0-3 QuickCommands 接入聊天页（fix/frontend-broken-links）
- [x] P0-4 修复死链与断头路由（projects/documents/compliance）（fix/frontend-broken-links）
- [x] P0-5 菜单单一数据源统一（fix/frontend-broken-links）
- [x] P0-6 communication 过期自动归档（feat/backend-beat-automation）

**里程碑验收**：换班写工具端到端可用（自然语言发起→确认→落库）；侧边栏所有入口可达；孤儿组件接线。

### Phase 1 — AI 中台筑基（P1A-1 ~ P1A-6）
- [ ] P1A-1 LLM 调用收口（file_processing 收编 + office_assistant 注册）
- [ ] P1A-2 写工具速率限制
- [ ] P1A-3 流式成本统计回填
- [ ] P1A-4 documents→RAGFlow 自动入库管道
- [ ] P1A-5 知识库数据集管理页
- [ ] P1A-6 插件 manifest → 工具注册中心

**里程碑验收**：所有 LLM 调用经 LLMRouter 且有成本记录；文档上传自动可被 knowledge_qa 检索；至少 1 个外部插件作为工具被数字员工调用。

### Phase 2 — 数字员工上岗（P1B-1 ~ P1B-4）
- [ ] P1B-1 AgentProfile 模型 + admin
- [ ] P1B-2 主动巡检框架（首场景：排班冲突→代发换班）
- [ ] P1B-3 多 Agent 与 chat 打通 + fanout 模式
- [ ] P1B-4 内置 4 角色 seed + 对应巡检/工具

**里程碑验收**：排班冲突发生时数字员工主动发起换班协商并推确认通知；复杂任务在 chat 内自动分流多 Agent；4 角色可在管理界面查看/启停。

### Phase 3 — 体验整合（P2，可与 Phase 2 部分并行）
- [ ] P2-1 Dashboard AI 工作台
- [ ] P2-2 QuickAssistant 渲染对齐
- [ ] P2-3 search-federation 接线
- [ ] P2-4 各模块单点自动化（按需选做）
- [ ] P2-5 Stats 图表化
- [ ] P2-6 桌面端 AI 触点

**里程碑验收**：Dashboard 呈现个性化 AI 简报与数字员工状态；快捷助手与完整页体验一致。

### 收尾
- [ ] 功能点并入 `docs/technical/` 对应章节（16/17 智能助手、新增数字员工章节）与 `docs/user-manual/`
- [ ] 删除本计划文件

---

## 五、风险评估与依赖

### 技术风险

| 风险 | 等级 | 缓解 |
|---|---|---|
| **换班写工具 LLM 抽取准确率不足**（P0-1 是全链路关键） | 高 | 保留 dry_run + confirm 二次确认兜底；抽取失败明确提示而非静默；补 e2e 测试覆盖典型话术 |
| **数字员工主动动作失控/误操作** | 高 | 写操作强制走 confirm 框架，数字员工只能「发起+请求确认」不能「代签」；巡检动作全量审计日志；每角色独立启停开关 |
| **多 Agent fanout 复杂度**（P1B-3） | 中 | 先做 chat→现有 Pipeline 分流（低风险），fanout 作为独立子任务后置 |
| **插件转工具的安全面扩大**（P1A-6） | 中 | 复用现有插件沙箱 + 审核流；工具白名单按 AgentProfile scope 收敛；注意 Round 2「插件真沙箱」尚未做，需先评估 |
| **内网离线约束**：无外部云 LLM/ASR 可用 | 中 | 所有 AI 能力基于 LLMRouter 已配置的私有端点 + Ollama 兜底；语音等依赖外部服务的能力单独立项 |

### 依赖关系

- **P0-1 依赖** llm-swap-shift 已合入的工具骨架（PR #175/#176）✅ 已就绪
- **P1B-2 依赖** P0-1（换班写工具可用）+ confirm 框架 ✅ 已就绪
- **P1A-6 依赖** external_integration 插件 manifest 标准化 ✅ 已就绪；但**受 Round 2「插件真沙箱」进度影响**，建议先做白名单内插件试点
- **P2-6 桌面端** 依赖 desktop_notifier 现有 SSE/通知基础；注意 Win7/PyQt5/Python3.8 兼容约束
- **并行项**：Round 2 工程债（大文件拆分、覆盖率、E2E）与本方案功能线可并行，但 executor.py 拆分（R2-A1）建议在 P1B-3 fanout 改造**之前或同期**完成，避免两次大改同一文件

### 不在本方案范围（YAGNI）

- ❌ React 19 升级、微服务重构、新 UI 库、云部署（沿用既有排除项）
- ❌ 自建 RAG/向量库（继续用外部 RAGFlow）
- ❌ 自建 LLM provider SDK（继续 OpenAI 兼容 HTTP + Ollama）
- ❌ 语音交互、OCR 扫描件解析（成本高，单独立项评估）

---

## 六、建议的启动顺序

若资源有限，建议最小启动集（性价比最高的 5 件事）：

1. **P0-1 换班写工具接线** —— 修复唯一业务写操作断链，其余数字员工能力都以此为样板
2. **P1A-6 插件转工具** —— 一步让数字员工获得操作外部系统的能力，复用现成审核流
3. **P1A-4 documents 自动入 RAG** —— 补知识库断裂，喂养核心问答能力
4. **P1B-2 主动巡检框架（排班冲突场景）** —— 数字员工「主动性」的第一个落地样板
5. **P2-1 Dashboard AI 工作台** —— 让 AI 中台与数字员工的价值在入口可见

以上 5 项均**复用已就绪基础设施**（confirm 框架 / 插件沙箱 / RAG 管道 / digest 链路），无大规模新建。
