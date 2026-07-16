# 32. Smart Assistant 多 Agent 协作

> **状态**：✅ 已实现（v0.5.0，PR #32 — `feat/smart-assistant-multi-agent-collaboration`）
> **代码位置**：`omni_desk_backend/smart_assistant/agents/` + `omni_desk_backend/smart_assistant/hooks/`
> **里程碑 1.1–1.4 全部合入**：基础设施 → TaskPacket → MultiAgentExecutor → Supervisor + SSE

## 1. 设计动机

`smart_assistant` 原有单 Agent 管道（意图分类 → 工具链 → 回答）擅长**短任务单轮对话**，但**多步骤、多角色协作**的长任务（文献调研、数据分析、报告整理、代码开发）超出单 Agent 能力上限。

多 Agent 层在**不替换现有 `AgentOrchestrator`** 的前提下扩展：单轮聊天继续走原路径，长任务通过 `complex_task` 意图分流到 `MultiAgentExecutor`。

## 2. 核心架构

```
┌─────────────────────────────────────────────────────────────┐
│                    IntentClassifier                          │
│      (复杂任务识别 → 路由到 MultiAgentExecutor)                │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                  MultiAgentExecutor                          │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ Supervisor LLM  →  任务分解为 SubTask DAG              │  │
│  └───────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ Pipeline 模式：role(Researcher) → role(Analyst) → ...    │  │
│  │ Fanout 模式：3 个 researcher 并行                          │  │
│  │ Hierarchical：supervisor 动态调度                            │  │
│  └───────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ 共享上下文：TaskPacket + SharedContext 跨 SubTask 传递     │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│              Hook 系统（横向）                                │
│  - audit_log    ：所有 SubTask 写审计日志                       │
│  - pii_sanitizer：输入脱敏                                        │
│  - 其它策略钩子（pluggable）                                      │
└─────────────────────────────────────────────────────────────┘
```

## 3. 模块构成

| 文件 | 职责 |
|---|---|
| `agents/roles.py` | `AgentRole` 枚举 + `RoleProfile` 注册表（researcher / analyst / writer / coder / supervisor） |
| `agents/task_packet.py` | `TaskPacket` / `SubTask` 数据类，承载跨 Agent 任务数据 |
| `agents/shared_context.py` | `SharedContext`：跨 SubTask 共享上下文（tool 输出、变量、partial result） |
| `agents/executor.py` | `MultiAgentExecutor`：主执行器，编排 Pipeline / Fanout / Hierarchical |
| `agents/supervisor.py` | `Supervisor` LLM 任务分解 + 动态调整 |
| `agents/pipeline.py` *(内联在 executor 中)* | Pipeline 模式串行执行 |
| `quality_gate.py` *(内联)* | 质量门禁：基于 role 的 `output_contract` 校验 |
| `recovery.py` *(内联)* | Recovery Recipes：失败自愈 |
| `hooks/base.py` | `ToolHook` 协议 + `HookRegistry` |
| `hooks/builtin/audit_log.py` | 审计日志钩子 |
| `hooks/builtin/pii_sanitizer.py` | PII 脱敏钩子 |

## 4. 数据库模型

| 模型 | 字段要点 | 用途 |
|---|---|---|
| `AgentTask` | `user`, `status`, `intent`, `subtask_ids`, `final_result` | 用户提交的一次多 Agent 任务 |
| `AgentSubTask` | `task`, `role`, `status`, `output`, `error`, `started_at`, `finished_at` | 子任务实例 |
| `AgentEvent` | `task`, `type`, `payload`, `ts` | 事件流（用于回放 + UI 实时进度） |

## 5. API 端点

| 端点 | 方法 | 用途 |
|---|---|---|
| `/api/smart-assistant/tasks/` | GET / POST | 列出 / 提交多 Agent 任务 |
| `/api/smart-assistant/tasks/{id}/` | GET | 任务详情（含 SubTask 状态） |
| `/api/smart-assistant/tasks/{id}/intervene/` | POST | 人工介入（取消 / 重试某 SubTask） |
| `/api/smart-assistant/tasks/{id}/events/` | GET (SSE) | 实时事件流 |
| `/api/smart-assistant/tasks/{id}/timeline/` | GET | 历史事件回放 |

## 6. 关键设计决策

| 决策 | 选择 | 理由 |
|---|---|---|
| 是否引入 LangGraph / CrewAI | ❌ 自研 + 借鉴思想 | 依赖可控、调试可观测 |
| 与单 Agent 管道的关系 | 共存（非替换） | 复杂任务路由到 MultiAgentExecutor，简单对话继续快速通道 |
| 失败处理 | Recovery Recipes + 人工介入 | 关键任务不可静默吞错 |
| 质量门禁 | role × output_contract | 不同角色验证不同 output 形态 |
| 事件流 | SSE + 持久化 `AgentEvent` | 既能实时推送又能事后回放 |

## 7. 部署 / 运行

无需额外配置；多 Agent 任务使用项目同一 LLM 端点，与单 Agent 走同样的降级链：

- `REACT_APP_OLLAMA_ENDPOINT` 环境变量
- `llm_service` 降级链（Ollama → 远程 API → 兜底）
- Celery 异步任务 `execute_agent_task`

## 8. 关联参考

- 设计灵感：`claw-code` (ultraworkers/claw-code) — Worker Boot / Task Packet / Recovery Recipes / Lane Event Sourcing
- 关联计划：`docs/plans/2026-06-21_multi-agent-collaboration.md`（**已归档，删档**）
- 上层架构：`docs/technical/16-smart-assistant.md` + `17-ai-assistant-deep-design.md`

---

> 📅 最近更新：2026-07-16 — 文档归档，从 docs/plans/2026-06-21_multi-agent-collaboration.md 提取。
